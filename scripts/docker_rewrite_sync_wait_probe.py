"""Create-only synthetic pending-rewrite synchronization restart acceptance."""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.telegram import (
    FakeTelegramProvider,
    TelegramChannelCheckpoint,
    TelegramChannelDifference,
    TelegramMessage,
)
from newsflow.security.master_key import load_runtime_master_key
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.channel_baseline import ChannelBaselineService
from newsflow.services.channel_difference_runner import ChannelDifferenceRunner
from newsflow.services.channel_sync_enforcement import ChannelSyncEnforcement, sync_enforced
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.source_deletions import SourceDeletionService
from newsflow.services.source_revisions import source_is_current
from newsflow.services.telegram_configuration import TelegramConfigurationService

NAME = "synthetic-rewrite-sync-wait-v1"
CHANNEL = -1001777666040
KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
FILE = "synthetic-rewrite-sync-wait-v1.json"


def _validate(manifest):
    if manifest.get("version") != 1:
        raise RuntimeError("Unsupported rewrite-sync-wait manifest version; preserve history")
    if any(
        type(manifest.get(field)) is not int or manifest[field] <= 0
        for field in ("account", "donor")
    ):
        raise RuntimeError("Invalid rewrite wait identity")
    jobs = manifest.get("jobs")
    if (
        not isinstance(jobs, list)
        or len(jobs) != 4
        or len(set(jobs)) != 4
        or any(type(row) is not int or row <= 0 for row in jobs)
    ):
        raise RuntimeError("Invalid rewrite wait job vector")


def _key(manifest, message):
    return f"{manifest['account']}:{CHANNEL}:{message}:revision:1"


def _forbidden(_channel):
    raise AssertionError("Rejected/deleted/exhausted/waiting source reached synthetic AI")


class FailureProvider(FakeTelegramProvider):
    def channel_difference(self, *args, **kwargs):
        raise TimeoutError("Synthetic pre-response read timeout")


def seed(sessions, root, *, now):
    root = Path(root)
    with sessions() as session:
        if (root / FILE).exists() or session.scalar(
            select(models.TelegramAccount.id).where(models.TelegramAccount.name == NAME)
        ):
            raise RuntimeError("Use a fresh fixture; refusing to replace rewrite wait history")
        config = TelegramConfigurationService(session)
        account = config.create_account(NAME, 700803)
        donor = config.create_donor(account["id"], CHANNEL, NAME)
        output = config.create_output(account["id"], CHANNEL - 1, NAME)
        mapping = config.create_mapping(donor["id"], output["id"], 100, 50)
    with sessions.begin() as session:
        row = session.get(models.TelegramAccount, account["id"])
        row.encrypted_session = SessionCipher(KEY).encrypt("synthetic rewrite wait session")
        row.health_status = "CONNECTED"
    ChannelSyncEnforcement(sessions).enable(now=now)
    provider = FailureProvider()
    provider.seed_channel_checkpoint(
        TelegramChannelCheckpoint(str(account["id"]), str(CHANNEL), 700803, 10)
    )
    assert (
        ChannelBaselineService(sessions, provider=provider, clock=lambda: now).bootstrap(
            donor["id"]
        )
        == "BASELINE_RECORDED"
    )
    manifest = {"version": 1, "account": account["id"], "donor": donor["id"], "jobs": []}
    for message in (201, 202, 203, 204):
        with sessions() as session:
            result = DurableIngestionWorkflow(session, configured_mapping_id=mapping["id"]).ingest(
                TelegramMessage(
                    str(account["id"]),
                    str(CHANNEL),
                    message,
                    f"Wait source {message}",
                    source_updated_at=now,
                ),
                observed_at=now,
                sentiment="neutral",
                framing="neutral",
            )
            assert result.status == "REWRITE_QUEUED"
            manifest["jobs"].append(
                session.scalars(
                    select(models.RewriteJobModel.id).where(
                        models.RewriteJobModel.content_key == _key(manifest, message)
                    )
                ).one()
            )
    with sessions.begin() as session:
        session.get(models.RewriteJobModel, manifest["jobs"][3]).attempts = 2
    with (root / FILE).open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle)
    assert (
        ChannelDifferenceRunner(sessions, provider=provider, clock=lambda: now).run_donor(
            donor["id"], now=now
        )
        == "RETRY_PROVIDER"
    )
    runner = DurableRewriteRunner(
        sessions, provider_for_channel=_forbidden, clock=lambda: now, max_attempts=2
    )
    for _ in range(4):
        assert runner.run_next(now=now) == "RETRY"
    with sessions.begin() as session:
        decision = session.scalars(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key == _key(manifest, 202)
            )
        ).one()
        decision.status, decision.rewrite_allowed = "REJECT", False
        decision.protected_entities, decision.sentiment, decision.framing = (
            "Украина",
            "negative",
            "negative",
        )
    SourceDeletionService(sessions).record(
        TelegramChannelDifference(str(account["id"]), str(CHANNEL), 10, 11, True, 0, (), (203,)),
        observed_at=now,
    )
    verify(sessions, manifest, completed=False)
    return manifest


def verify(sessions, manifest, *, completed):
    _validate(manifest)
    with sessions() as session:
        assert sync_enforced(session)
        account = session.get(models.TelegramAccount, manifest["account"])
        assert account.name == NAME and account.telegram_user_id == 700803
        assert (
            SessionCipher(KEY).decrypt(account.encrypted_session)
            == "synthetic rewrite wait session"
        )
        cursor = session.get(models.ChannelDifferenceCursorModel, manifest["donor"])
        assert (
            cursor.telegram_account_id,
            cursor.telegram_user_id,
            cursor.telegram_channel_id,
        ) == (account.id, 700803, CHANNEL)
        assert cursor.pts == (12 if completed else 10)
        assert cursor.last_error_code == (None if completed else "RETRY_PROVIDER")
        expected = (
            ("SUCCEEDED", "BLOCKED_EDITORIAL", "SUPERSEDED", "FAILED")
            if completed
            else ("RETRY",) * 4
        )
        jobs = [session.get(models.RewriteJobModel, job_id) for job_id in manifest["jobs"]]
        assert tuple(job.state for job in jobs) == expected
        assert tuple(job.attempts for job in jobs) == ((1, 1, 1, 2) if completed else (0, 0, 0, 2))
        for message, job in zip((201, 202, 203, 204), jobs, strict=True):
            assert job.content_key == _key(manifest, message)
            assert (
                job.idempotency_key
                == f"rewrite.requested:{job.content_key}:{job.output_channel_id}"
            )
            assert job.claim_token is None and job.lease_expires_at is None
        drafts = session.scalars(
            select(models.RewriteOutputModel).where(
                models.RewriteOutputModel.rewrite_job_id.in_(manifest["jobs"])
            )
        ).all()
        assert len(drafts) == (1 if completed else 0)
        if completed:
            assert (
                drafts[0].rewrite_job_id == manifest["jobs"][0]
                and drafts[0].approval_state == "PENDING"
            )
        decision = session.scalars(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key == _key(manifest, 202)
            )
        ).one()
        assert decision.status == "REJECT" and decision.rewrite_allowed is False
        assert (
            session.get(models.SourceDeletionModel, (str(account.id), str(CHANNEL), 203))
            is not None
        )
        assert source_is_current(session, _key(manifest, 201)) is completed
        assert not source_is_current(session, _key(manifest, 203))
        assert session.scalar(select(models.RewriteUsageModel)) is None
        assert session.scalar(select(models.PublicationJobModel)) is None


def recover(sessions, manifest, *, now):
    verify(sessions, manifest, completed=False)
    with sessions() as session:
        cursor = session.get(models.ChannelDifferenceCursorModel, manifest["donor"])
        if cursor.available_at.replace(tzinfo=UTC) > now or any(
            session.get(models.RewriteJobModel, job).available_at.replace(tzinfo=UTC) > now
            for job in manifest["jobs"]
        ):
            raise RuntimeError("Synthetic sync/rewrite retry is not due; refusing to reset it")
    provider = FakeTelegramProvider()
    provider.seed_channel_difference(
        TelegramChannelDifference(
            str(manifest["account"]), str(CHANNEL), 10, 12, True, 0, (), (203,)
        )
    )
    assert (
        ChannelDifferenceRunner(sessions, provider=provider, clock=lambda: now).run_donor(
            manifest["donor"], now=now
        )
        == "DIFFERENCE_COMPLETE"
    )
    calls = []

    class SyntheticRewrite:
        def rewrite(self, text):
            assert text == "Wait source 201"
            calls.append(text)
            return text

    allowed = DurableRewriteRunner(
        sessions,
        provider_for_channel=lambda _: SyntheticRewrite(),
        clock=lambda: now,
        max_attempts=2,
    )
    assert allowed.run_next(now=now) == "SUCCEEDED"
    blocked = DurableRewriteRunner(
        sessions, provider_for_channel=_forbidden, clock=lambda: now, max_attempts=2
    )
    assert [blocked.run_next(now=now) for _ in range(3)] == [
        "BLOCKED_EDITORIAL",
        "SUPERSEDED",
        "FAILED",
    ]
    assert calls == ["Wait source 201"]
    verify(sessions, manifest, completed=True)


def verify_overview(report):
    assert report["scope"] == "ALL_RETAINED_HISTORY"
    assert report["network_checked"] is False and report["billing_complete"] is False
    assert report["history"]["rewrite_jobs"] >= 4
    assert report["history"]["source_posts"] >= 4
    assert [item["operation"] for item in report["usage"]] == ["REWRITE", "SEMANTIC_VERIFICATION"]
    for item in report["usage"]:
        assert 0 <= item["cached_tokens"] <= item["input_tokens"]
        assert 0 <= item["unknown_cost_records"] <= item["records"]
        assert 0 <= item["unobserved_attempts"] <= item["durable_attempts"]
        assert isinstance(item["known_estimated_cost_usd"], str)


def verify_api(inbox, outputs, manifest, *, completed):
    _validate(manifest)
    rows = {row["source_key"]: row for row in inbox["items"]}
    permitted = rows[_key(manifest, 201).removesuffix(":revision:1")]
    assert permitted["rewrite_allowed"] is completed and permitted["editorial_status"] == "PASS"
    rejected = rows[_key(manifest, 202).removesuffix(":revision:1")]
    assert rejected["editorial_status"] == "REJECT" and rejected["rewrite_allowed"] is False
    deleted = rows[_key(manifest, 203).removesuffix(":revision:1")]
    assert deleted["source_deleted"] is True and deleted["rewrite_allowed"] is False
    drafts = [row for row in outputs["items"] if row["rewrite_job_id"] in manifest["jobs"]]
    assert len(drafts) == (1 if completed else 0)
    if completed:
        assert drafts[0]["rewrite_job_id"] == manifest["jobs"][0]
        assert drafts[0]["approval_state"] == "PENDING"
    else:
        assert permitted["state"] == "SOURCE_SYNC_REQUIRED"


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
        or make_url(url).get_backend_name() != "postgresql"
    ):
        raise RuntimeError("Rewrite wait probe requires isolated PostgreSQL verification database")
    if mode not in {"seed", "verify-pending", "recover", "verify"}:
        raise ValueError("Unsupported rewrite wait probe mode")
    for flag in (
        "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
        "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
        "NEWSFLOW_REWRITE_ENABLED",
        "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
        "NEWSFLOW_INTERNET_MEDIA_ENABLED",
        "NEWSFLOW_SOURCE_PHOTO_ENABLED",
        "NEWSFLOW_PUBLICATION_ENABLED",
    ):
        if os.getenv(flag, "0") != "0":
            raise RuntimeError("Rewrite wait probe requires all network workers disabled")
    if load_runtime_master_key() != KEY:
        raise RuntimeError("Unexpected synthetic secret; refusing to regenerate or replace key")
    engine = create_engine(url)
    try:
        sessions, root = sessionmaker(engine), Path(os.environ["NEWSFLOW_MEDIA_ROOT"])
        if mode == "seed":
            seed(sessions, root, now=datetime.now(UTC))
        else:
            manifest = json.loads((root / FILE).read_text(encoding="utf-8"))
            if mode == "recover":
                recover(sessions, manifest, now=datetime.now(UTC))
            else:
                verify(sessions, manifest, completed=mode == "verify")
                with urlopen("http://api:8000/api/telegram/incoming-posts", timeout=15) as response:
                    assert response.status == 200
                    inbox = json.load(response)
                with urlopen(
                    "http://api:8000/api/telegram/rewrite-outputs", timeout=15
                ) as response:
                    assert response.status == 200
                    outputs = json.load(response)
                verify_api(inbox, outputs, manifest, completed=mode == "verify")
                with urlopen("http://api:8000/api/studio/overview", timeout=15) as response:
                    assert response.status == 200
                    assert response.headers["Cache-Control"] == "no-store"
                    verify_overview(json.load(response))
    finally:
        engine.dispose()
    print(f"Synthetic rewrite wait {mode}: PASS; zero real Telegram/AI/send calls")


if __name__ == "__main__":
    main(sys.argv[1])
