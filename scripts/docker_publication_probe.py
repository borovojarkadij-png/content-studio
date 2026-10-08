"""Create-only synthetic publication recovery. Never imports a Telegram sender."""

import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import (
    EditorialDecisionModel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    PublicationJobModel,
    RewriteJobModel,
    TelegramAccount,
    TelegramPeerModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_publication_runner import (
    DurablePublicationRunner,
    PublicationClaim,
    PublicationReceipt,
)
from newsflow.services.publication_planning import PublicationPlanningService
from newsflow.services.rewrite_outputs import RewriteOutputService
from newsflow.services.telegram_configuration import TelegramConfigurationService

NAME = "synthetic-publication-intent"
CHANNEL = -1001777665000


class SyntheticPublisher:
    def __init__(self, sessions):
        self.sessions, self.calls = sessions, []

    def publish(self, envelope, nonce, *, execution_guard):
        # Separate PostgreSQL writer proves no locks are retained across transport.
        with self.sessions.begin() as session:
            session.execute(text("SET LOCAL lock_timeout = '2s'"))
            job = session.scalar(
                select(PublicationJobModel)
                .where(PublicationJobModel.planned_id == envelope.planned_id)
                .with_for_update()
            )
            assert job.state == "SENDING" and job.request_nonce == nonce
            session.get(TelegramAccount, envelope.account_id, with_for_update=True)
            session.get(PublicationCandidateModel, envelope.candidate_id, with_for_update=True)
        execution_guard()
        self.calls.append(nonce)
        return PublicationReceipt(envelope.account_id, envelope.telegram_channel_id, nonce, 901)


def seed(sessions, root, execution):
    now = datetime.now(UTC)
    with sessions() as session:
        if session.scalar(select(TelegramAccount.id).where(TelegramAccount.name == NAME)):
            raise RuntimeError("Use a fresh fixture; refusing to replace publication history")
        config = TelegramConfigurationService(session)
        account = config.create_account(NAME, 700701)
        donor = config.create_donor(account["id"], CHANNEL, NAME)
        output = config.create_output(account["id"], CHANNEL - 1, NAME)
        mapping = config.create_mapping(donor["id"], output["id"], 100, 100)
    with sessions.begin() as session:
        row = session.get(TelegramAccount, account["id"])
        cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        row.encrypted_session, row.health_status = (
            cipher.encrypt("synthetic publication session"),
            "CONNECTED",
        )
        session.add(
            TelegramPeerModel(
                telegram_account_id=account["id"],
                telegram_channel_id=CHANNEL - 1,
                encrypted_peer=cipher.encrypt("synthetic output peer"),
            )
        )
    planned = []
    for message_id in (101, 102, 103):
        caption = f"Synthetic publication {message_id}"
        with sessions() as session:
            result = DurableIngestionWorkflow(session, configured_mapping_id=mapping["id"]).ingest(
                TelegramMessage(
                    str(account["id"]),
                    str(CHANNEL),
                    message_id,
                    caption,
                    media_type="text",
                    media_protected=False,
                    source_updated_at=now,
                ),
                observed_at=now,
                sentiment="neutral",
                framing="neutral",
            )
            assert result.status == "REWRITE_QUEUED"
        key = f"{account['id']}:{CHANNEL}:{message_id}:revision:1"
        with sessions() as session:
            job = session.scalars(
                select(RewriteJobModel).where(RewriteJobModel.content_key == key)
            ).one()
            job.state = "SUCCEEDED"  # Fixture only, not a real AI qualification.
            session.commit()
            review = RewriteOutputService(session)
            draft = review.record_succeeded_output(job.id, caption)
            review.approve(draft["id"], activate_candidate=True)
        with sessions.begin() as session:
            candidate = session.scalars(
                select(PublicationCandidateModel).where(
                    PublicationCandidateModel.content_key == key
                )
            ).one()
            candidate.state, candidate.eligible_at = "SCHEDULED", now - timedelta(seconds=1)
            item = PlannedPublicationModel(
                candidate_id=candidate.id,
                output_channel_id=output["id"],
                scheduled_for=now + timedelta(seconds=message_id - 103),
                state="PLANNED",
            )
            session.add(item)
            session.flush()
            planned.append(item.id)
    jobs = [execution.enqueue(plan_id, now=now) for plan_id in planned]
    assert execution.enqueue(planned[0], now=now) == jobs[0]
    first, second = execution.claim_next(now=now), execution.claim_next(now=now)
    assert first.job_id == jobs[0] and second.job_id == jobs[1]
    with sessions.begin() as session:
        session.get(PublicationJobModel, second.job_id).state = "SENDING"
    manifest = {
        "plans": planned,
        "jobs": jobs,
        "old_claim": asdict(first),
        "sending_claim": asdict(second),
    }
    (root / "synthetic-publication-intents.json").write_text(json.dumps(manifest), encoding="utf-8")


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Publication probe requires isolated verification database")
    if mode not in {"seed", "recover", "verify", "quota"}:
        raise ValueError("Unsupported publication probe mode")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    root = Path(os.environ["NEWSFLOW_MEDIA_ROOT"])
    publisher = SyntheticPublisher(sessions)
    execution = DurablePublicationRunner(sessions, root, publisher=publisher)
    if mode == "seed":
        seed(sessions, root, execution)
    else:
        manifest = json.loads(
            (root / "synthetic-publication-intents.json").read_text(encoding="utf-8")
        )
        jobs = manifest["jobs"]
        if mode == "recover":
            old = PublicationClaim(**manifest["old_claim"])
            current = execution.claim_next(now=datetime.now(UTC))
            assert (
                current.job_id == old.job_id and current.attempt == 2 and current.token != old.token
            )
            assert execution.execute(old) == "LOST_LEASE" and publisher.calls == []
            assert execution.execute(PublicationClaim(**manifest["sending_claim"])) == "LOST_LEASE"
            assert execution.execute(current) == "SUCCEEDED" and len(publisher.calls) == 1
            with sessions.begin() as session:
                item = session.get(PlannedPublicationModel, manifest["plans"][2])
                candidate = session.get(PublicationCandidateModel, item.candidate_id)
                decision = session.scalars(
                    select(EditorialDecisionModel).where(
                        EditorialDecisionModel.content_key == candidate.content_key
                    )
                ).one()
                decision.status, decision.rewrite_allowed = "REJECT", False
            assert (
                execution.run_next(now=datetime.now(UTC)) == "BLOCKED" and len(publisher.calls) == 1
            )
        elif mode == "quota":
            with sessions.begin() as session:
                item = session.get(PlannedPublicationModel, manifest["plans"][1])
                item.state = "CANCELLED"
                candidate = session.get(PublicationCandidateModel, item.candidate_id)
                decision = session.scalars(
                    select(EditorialDecisionModel).where(
                        EditorialDecisionModel.content_key == candidate.content_key
                    )
                ).one()
                decision.status, decision.rewrite_allowed = "REJECT", False
                output_id, day = item.output_channel_id, item.scheduled_for.astimezone(UTC).date()
            with sessions() as session:
                service = PublicationPlanningService(session)
                plan = service.configure_plan(output_id, "AUTOMATIC", 2, (0, 60))
                reservations = service.plan_day(plan["id"], day)
                assert {row["id"] for row in reservations} == set(manifest["plans"][:2])
                assert len(reservations) == 2  # Published + unknown cancelled retain quota.
            assert publisher.calls == []
        else:
            with sessions() as session:
                rows = [session.get(PublicationJobModel, identity) for identity in jobs]
                assert [row.state for row in rows] == [
                    "SUCCEEDED",
                    "NEEDS_RECONCILIATION",
                    "BLOCKED",
                ]
                assert (
                    rows[0].attempts == 2
                    and rows[0].sent_message_id == 901
                    and rows[0].request_nonce > 0
                )
                assert (
                    session.get(PlannedPublicationModel, manifest["plans"][0]).state == "PUBLISHED"
                )
            assert execution.run_next(now=datetime.now(UTC)) == "IDLE" and publisher.calls == []
            for planned_id, expected in zip(
                manifest["plans"], ("SUCCEEDED", "NEEDS_RECONCILIATION", "BLOCKED"), strict=True
            ):
                url = f"http://api:8000/api/telegram/planned-publications/{planned_id}/delivery-status"
                with urlopen(url, timeout=15) as response:
                    status = json.load(response)
                    assert (
                        response.status == 200 and response.headers["Cache-Control"] == "no-store"
                    )
                    assert status["planned_id"] == planned_id and status["state"] == expected
                    assert status["live_publication_available"] is False
                    assert (
                        not {"request_nonce", "claim_token", "encrypted_session", "binding_sha256"}
                        & status.keys()
                    )
                try:
                    urlopen(Request(url, method="POST"), timeout=15)
                except HTTPError as exc:
                    assert exc.code == 405
                else:
                    raise AssertionError("Read-only delivery status allowed POST")
    engine.dispose()
    print(f"Synthetic publication {mode}: PASS; zero Telegram/AI network calls")


if __name__ == "__main__":
    main(sys.argv[1])
