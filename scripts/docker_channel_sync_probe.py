"""Create-only synchronization restart acceptance; synthetic read provider only.

Run in a separate fresh fixture: durable global enforcement is never undone.
No real Telegram adapter, credentials, AI client or sending transport is used.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, select, text
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
from newsflow.services.channel_sync_tick import run_channel_sync_tick
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.source_revisions import source_is_current
from newsflow.services.source_sync_replay import SourceSyncReplayService
from newsflow.services.telegram_configuration import TelegramConfigurationService

NAME = "synthetic-channel-sync-v1"
CHANNEL = -1001777666000
KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
FILE = "synthetic-channel-sync-v1.json"


def _key(manifest, message, *, legacy=False):
    channel = CHANNEL - 10 if legacy else CHANNEL
    return f"{manifest['account']}:{channel}:{message}:revision:1"


def _validate(manifest):
    if manifest.get("version") != 1:
        raise RuntimeError("Unsupported channel-sync manifest version; preserve fixture history")
    for field in ("account", "donor", "legacy", "legacy_job"):
        if type(manifest.get(field)) is not int or manifest[field] <= 0:
            raise RuntimeError("Invalid channel-sync fixture identity")


class SyntheticProvider(FakeTelegramProvider):
    def __init__(self, sessions, manifest, *, final):
        super().__init__()
        self.sessions, self.manifest, self.final, self.calls = sessions, manifest, final, []
        self.seed_channel_checkpoint(
            TelegramChannelCheckpoint(str(manifest["account"]), str(CHANNEL), 700801, 10)
        )
        for message, caption in (
            (101, "Deleted later"),
            (102, "Retained news"),
            (103, "Deleted first"),
            (104, "New news"),
        ):
            event = TelegramMessage(
                str(manifest["account"]),
                str(CHANNEL),
                message,
                caption,
                source_updated_at=datetime(2020, 1, 1, tzinfo=UTC),
            )
            self._messages[(event.account_id, event.donor_identifier, message)] = event

    def _unlocked(self):
        # A second PostgreSQL writer inside the injected RPC must acquire these
        # exact row locks. SQLite unit coverage is not proof of this behavior.
        with self.sessions.begin() as session:
            if session.bind.dialect.name == "postgresql":
                session.execute(text("SET LOCAL lock_timeout = '2s'"))
            session.get(models.DonorChannel, self.manifest["donor"], with_for_update=True)
            session.get(models.TelegramAccount, self.manifest["account"], with_for_update=True)
            session.get(
                models.ChannelDifferenceCursorModel, self.manifest["donor"], with_for_update=True
            )

    def channel_checkpoint(self, *args):
        self._unlocked()
        self.calls.append("checkpoint")
        return super().channel_checkpoint(*args)

    def channel_difference(self, account, channel, *, pts, limit):
        self._unlocked()
        assert (account, channel, pts) == (
            str(self.manifest["account"]),
            str(CHANNEL),
            11 if self.final else 10,
        )
        assert 10 <= limit <= 100
        self.calls.append("difference")
        messages = (104,) if self.final else (101, 102)
        return TelegramChannelDifference(
            account,
            channel,
            pts,
            12 if self.final else 11,
            self.final,
            0,
            tuple(self._messages[(account, channel, message)] for message in messages),
            (101,) if self.final else (103,),
        )

    def history(self, *args, **kwargs):
        self._unlocked()
        self.calls.append("history")
        return super().history(*args, **kwargs)


def seed(sessions, root, *, now):
    root = Path(root)
    with sessions() as session:
        if (root / FILE).exists() or session.scalar(
            select(models.TelegramAccount.id).where(models.TelegramAccount.name == NAME)
        ):
            raise RuntimeError("Use a fresh fixture; refusing to replace sync history")
        config = TelegramConfigurationService(session)
        account = config.create_account(NAME, 700801)
        donor = config.create_donor(account["id"], CHANNEL, NAME)
        legacy = config.create_donor(account["id"], CHANNEL - 10, NAME + " legacy")
        mappings = []
        for number in (1, 2):
            output = config.create_output(account["id"], CHANNEL - number, f"Sync output {number}")
            mappings.append(config.create_mapping(donor["id"], output["id"], 100, 50)["id"])
        legacy_mapping = config.create_mapping(legacy["id"], output["id"], 100, 50)["id"]
    with sessions.begin() as session:
        row = session.get(models.TelegramAccount, account["id"])
        row.encrypted_session = SessionCipher(KEY).encrypt("synthetic sync session")
        row.health_status = "CONNECTED"
    with sessions() as session:
        result = DurableIngestionWorkflow(session, configured_mapping_id=legacy_mapping).ingest(
            TelegramMessage(str(account["id"]), str(CHANNEL - 10), 201, "Legacy permitted source"),
            observed_at=now,
            sentiment="neutral",
            framing="neutral",
        )
        assert result.status == "REWRITE_QUEUED"
        legacy_job = (
            session.scalars(
                select(models.RewriteJobModel).where(
                    models.RewriteJobModel.content_key
                    == f"{account['id']}:{CHANNEL - 10}:201:revision:1"
                )
            )
            .one()
            .id
        )
    manifest = {
        "version": 1,
        "account": account["id"],
        "donor": donor["id"],
        "legacy": legacy["id"],
        "legacy_job": legacy_job,
        "mappings": mappings,
    }
    # Exclusive create; failed/incomplete fixture remains evidence, never reseeded.
    with (root / FILE).open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle)
    ChannelSyncEnforcement(sessions).enable(now=now)
    provider = SyntheticProvider(sessions, manifest, final=False)
    assert (
        ChannelBaselineService(sessions, provider=provider, clock=lambda: now).bootstrap(
            donor["id"]
        )
        == "BASELINE_RECORDED"
    )
    difference = ChannelDifferenceRunner(sessions, provider=provider, clock=lambda: now)
    outcome = difference.run_donor(donor["id"], now=now)
    assert outcome == "DIFFERENCE_CONTINUE", outcome
    with sessions() as session:
        assert (
            session.get(models.ChannelDifferenceCursorModel, donor["id"]).last_error_code
            == "DIFFERENCE_INCOMPLETE"
        )
    assert difference.claim(donor["id"], now=now) is not None
    assert provider.calls == ["checkpoint", "difference"]
    verify(sessions, manifest, completed=False)
    return manifest


def recover(sessions, manifest, *, now):
    _validate(manifest)
    verify(sessions, manifest, completed=False)
    with sessions() as session:
        lease = session.get(models.ChannelDifferenceCursorModel, manifest["donor"]).lease_expires_at
        if lease is None or lease.replace(tzinfo=UTC) >= now:
            raise RuntimeError("Wait for the persisted synthetic lease; refusing to reset it")
    provider = SyntheticProvider(sessions, manifest, final=True)
    result = run_channel_sync_tick(
        sessions,
        now=now,
        clock=lambda: now,
        enabled=True,
        cipher=SessionCipher(KEY),
        provider=provider,
    )
    assert (manifest["donor"], "POLL_COMPLETE") in result.outcomes
    assert (manifest["legacy"], "LEGACY_SYNC_REQUIRED") in result.outcomes
    assert provider.calls == ["difference", "history"], (
        "Restart must reuse original pts, never re-bootstrap"
    )

    def forbidden(_channel):
        raise AssertionError("Unscanned legacy source reached an AI provider")

    runner = DurableRewriteRunner(sessions, provider_for_channel=forbidden)
    # The base persistence fixture may own an earlier synthetic legacy job.
    # Exercise its real guard too; never silently skip jobs or invent completion.
    for _ in range(4):
        assert runner.run_next(now=now) == "SUPERSEDED"
        with sessions() as session:
            if session.get(models.RewriteJobModel, manifest["legacy_job"]).state == "SUPERSEDED":
                break
    else:
        raise AssertionError("Synthetic legacy guard scan exceeded its bound")
    assert SourceSyncReplayService(sessions, clock=lambda: now).run_batch().outcomes == ()
    verify(sessions, manifest, completed=True)


def verify(sessions, manifest, *, completed):
    _validate(manifest)
    with sessions() as session:
        assert sync_enforced(session)
        account = session.get(models.TelegramAccount, manifest["account"])
        assert account.name == NAME and account.telegram_user_id == 700801
        assert SessionCipher(KEY).decrypt(account.encrypted_session) == "synthetic sync session"
        cursor = session.get(models.ChannelDifferenceCursorModel, manifest["donor"])
        assert (
            cursor.telegram_account_id,
            cursor.telegram_user_id,
            cursor.telegram_channel_id,
        ) == (manifest["account"], 700801, CHANNEL)
        assert cursor.pts == (12 if completed else 11)
        # Claim clears non-gap errors; its retained token itself fences freshness.
        assert cursor.last_error_code is None
        assert (cursor.claim_token is None) is completed
        assert session.get(models.ChannelDifferenceCursorModel, manifest["legacy"]) is None
        assert (
            session.get(models.SourceDeletionModel, (str(account.id), str(CHANNEL), 103))
            is not None
        )
        tombstone = session.get(models.SourceDeletionModel, (str(account.id), str(CHANNEL), 101))
        assert (tombstone is not None) is completed
        posts = session.scalars(
            select(models.IncomingPostModel).where(
                models.IncomingPostModel.telegram_account_id == str(account.id),
                models.IncomingPostModel.donor_channel_id == str(CHANNEL),
            )
        ).all()
        assert {row.telegram_message_id for row in posts} == (
            {101, 102, 104} if completed else {101, 102}
        )
        keys = [_key(manifest, message) for message in (101, 102, 104)]
        revisions = session.scalars(
            select(models.ContentRevisionModel).where(
                models.ContentRevisionModel.incoming_post_id.in_([row.id for row in posts])
            )
        ).all()
        assert len(revisions) == (3 if completed else 2)
        assert not source_is_current(session, _key(manifest, 201, legacy=True))
        assert not source_is_current(session, keys[0])
        assert source_is_current(session, keys[1]) is completed
        decisions = session.scalars(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key.in_(keys)
            )
        ).all()
        assert len(decisions) == (2 if completed else 0)
        assert all(
            row.status == "MANUAL_REVIEW" and row.rewrite_allowed is False for row in decisions
        )
        assert not session.scalars(
            select(models.RewriteJobModel).where(models.RewriteJobModel.content_key.in_(keys))
        ).all()
        assert session.get(models.RewriteJobModel, manifest["legacy_job"]).state == (
            "SUPERSEDED" if completed else "DISPATCHED"
        )
        for key in keys[: (3 if completed else 2)]:
            assert (
                session.scalar(
                    select(models.OutboxEventModel.id).where(
                        models.OutboxEventModel.idempotency_key == f"source.sync_quarantined:{key}"
                    )
                )
                is not None
            )
            done = session.scalar(
                select(models.OutboxEventModel.id).where(
                    models.OutboxEventModel.idempotency_key == f"source.sync_replay_completed:{key}"
                )
            )
            assert (done is not None) is completed
        assert session.scalar(select(models.RewriteUsageModel)) is None
        assert session.scalar(select(models.PublicationJobModel)) is None


def verify_inbox(payload, manifest, *, completed):
    _validate(manifest)
    rows = {row["source_key"]: row for row in payload["items"]}
    legacy = rows[_key(manifest, 201, legacy=True).removesuffix(":revision:1")]
    assert legacy["state"] == "SOURCE_SYNC_REQUIRED"
    assert legacy["editorial_status"] == "PASS" and legacy["rewrite_allowed"] is False
    for message in (101, 102, 104) if completed else (101, 102):
        row = rows[_key(manifest, message).removesuffix(":revision:1")]
        expected = (
            "SOURCE_DELETED"
            if completed and message == 101
            else "MANUAL_REVIEW"
            if completed
            else "SOURCE_SYNC_REQUIRED"
        )
        assert row["state"] == expected and row["rewrite_allowed"] is False
        assert row["source_deleted"] is (completed and message == 101)
        assert row["revision_number"] == 1
        assert row["editorial_status"] == (
            "MANUAL_REVIEW" if completed and message != 101 else None
        )


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
        or make_url(url).get_backend_name() != "postgresql"
    ):
        raise RuntimeError("Channel-sync probe requires isolated PostgreSQL verification database")
    if mode not in {"seed", "recover", "verify-pending", "verify"}:
        raise ValueError("Unsupported channel-sync probe mode")
    for flag in (
        "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
        "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
        "NEWSFLOW_REWRITE_ENABLED",
        "NEWSFLOW_PUBLICATION_ENABLED",
        "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
        "NEWSFLOW_INTERNET_MEDIA_ENABLED",
        "NEWSFLOW_SOURCE_PHOTO_ENABLED",
    ):
        if os.getenv(flag, "0") != "0":
            raise RuntimeError("Channel-sync probe requires all network workers disabled")
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
                    verify_inbox(json.load(response), manifest, completed=mode == "verify")
    finally:
        engine.dispose()
    print(f"Synthetic channel sync {mode}: PASS; zero real Telegram/AI/send calls")


if __name__ == "__main__":
    main(sys.argv[1])
