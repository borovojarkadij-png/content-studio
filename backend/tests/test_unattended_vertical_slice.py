"""Actual durable services + migrated SQL, only synthetic external boundaries."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from os import getenv
from pathlib import Path

import pytest
from alembic.config import Config
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow import worker
from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.telegram import (
    FakeTelegramProvider,
    FloodWait,
    TelegramChannelCheckpoint,
    TelegramChannelDifference,
    TelegramMessage,
)
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.automatic_approval import AutomaticApprovalPolicyService
from newsflow.services.channel_sync_enforcement import ChannelSyncEnforcement
from newsflow.services.durable_publication_runner import PublicationReceipt
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.durable_semantic_runner import DurableSemanticRunner
from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
from newsflow.services.publication_planning import PublicationPlanningService
from newsflow.services.telegram_configuration import TelegramConfigurationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)
CHANNEL = -1001888999000
SOURCE = "Завод открыл 3 линии."
DRAFTS = {1: "На заводе открыты 3 линии.", 2: "Открыты 3 линии на заводе."}
CIPHER = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
ACCEPTED = TelegramMessage(
    "1",
    str(CHANNEL),
    20,
    SOURCE,
    media_type="photo",
    media_id="123",
    media_protected=False,
    source_updated_at=NOW,
)
REJECTED = TelegramMessage(
    "1", str(CHANNEL), 21, "Негативное утверждение о защищённой сущности.", source_updated_at=NOW
)
ACCEPTED_KEY = f"1:{CHANNEL}:20:revision:1"
REJECTED_KEY = f"1:{CHANNEL}:21:revision:1"


@contextmanager
def reopened(url):
    engine = create_engine(url)
    try:
        yield sessionmaker(engine)
    finally:
        engine.dispose()


@pytest.fixture
def unattended(tmp_path, monkeypatch):
    postgres = getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL")
    url = (
        create_postgres_namespace(postgres)
        if postgres is not None
        else f"sqlite:///{tmp_path / 'unattended.db'}"
    )
    monkeypatch.setenv("DATABASE_URL", url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    media = tmp_path / "media"
    media.mkdir()
    mappings = []
    with reopened(url) as sessions:
        with sessions() as session:
            service = TelegramConfigurationService(session)
            account = service.create_account("Synthetic unattended only", 1001)
            donor = service.create_donor(account["id"], CHANNEL, "Synthetic donor only")
            for number in (1, 2):
                output = service.create_output(
                    account["id"], CHANNEL - number, f"Synthetic {number}"
                )
                mapping = service.create_mapping(
                    donor["id"],
                    output["id"],
                    100,
                    100,
                    eligibility_mode="IMMEDIATE" if number == 1 else "DELAYED",
                    delay_minutes=0 if number == 1 else 2,
                    priority=number,
                    media_policy="REUSE_SOURCE",
                )
                mappings.append(mapping["id"])
                service.set_source_media_rights(
                    mapping["id"], "PERMISSION", "Synthetic permission only"
                )
                PublicationPlanningService(session).configure_plan(
                    output["id"], "AUTOMATIC", 1, (1 if number == 1 else 3,), "UTC"
                )
            session.add(
                models.SemanticVerifierReleaseModel(
                    id=1,
                    provider="OPENAI",
                    model="synthetic-model",
                    prompt_version="semantic-facts-v1",
                    benchmark_version="semantic-facts-v1",
                    report_sha256="f" * 64,
                    active=True,
                )
            )
            session.commit()
            # Trusted qualification is synthetic test data, never operational.
            for number in (1, 2):
                AutomaticApprovalPolicyService(session).configure(number, "VERIFIED", 1)
        with sessions.begin() as session:
            account = session.get(models.TelegramAccount, 1)
            account.health_status = "CONNECTED"
            account.encrypted_session = CIPHER.encrypt("synthetic-session-marker-not-telegram")
            for number in (1, 2):
                session.add(
                    models.TelegramPeerModel(
                        telegram_account_id=1,
                        telegram_channel_id=CHANNEL - number,
                        encrypted_peer=CIPHER.encrypt("synthetic-peer-marker"),
                    )
                )
            session.add(
                models.ChannelDifferenceCursorModel(
                    donor_channel_id=donor["id"],
                    telegram_account_id=1,
                    telegram_user_id=1001,
                    telegram_channel_id=CHANNEL,
                    pts=10,
                    available_at=NOW,
                )
            )
        ChannelSyncEnforcement(sessions).enable(now=NOW)
    return url, media, mappings


class Rewriter:
    def __init__(self, channel):
        self.channel, self.calls = channel, []

    def rewrite(self, text):
        self.calls.append(text)
        assert text == SOURCE
        return DRAFTS[self.channel]


class Verifier:
    provider, model, prompt_version = "OPENAI", "synthetic-model", "semantic-facts-v1"

    def __init__(self):
        self.calls = []

    def verify(self, source, draft):
        self.calls.append((source, draft))
        return {
            "verdict": "PRESERVED",
            "source_complete": True,
            "draft_complete": True,
            "claims": [{"source_quote": source, "draft_quote": draft, "relation": "SUPPORTED"}],
        }


class Photos(FakeTelegramProvider):
    def __init__(self, *, flood=False):
        super().__init__()
        image = BytesIO()
        Image.new("RGB", (64, 32), "navy").save(image, format="PNG")
        self.content, self.calls = image.getvalue(), []
        self.flood = flood
        self._messages[("1", str(CHANNEL), 20)] = ACCEPTED
        self._photos[("1", str(CHANNEL), 20)] = self.content
        self.seed_channel_checkpoint(TelegramChannelCheckpoint("1", str(CHANNEL), 1001, 10))
        self.seed_channel_difference(
            TelegramChannelDifference("1", str(CHANNEL), 10, 11, True, 0, (), ())
        )

    def download_photo(self, account_id, donor_identifier, message_id):
        self.calls.append((account_id, donor_identifier, message_id))
        if self.flood and len(self.calls) == 1:
            raise FloodWait(30)
        return super().download_photo(account_id, donor_identifier, message_id)


class Publisher:
    def __init__(self):
        self.calls = []

    def publish(self, envelope, nonce, *, execution_guard):
        execution_guard()
        self.calls.append((envelope, nonce))
        return PublicationReceipt(
            envelope.account_id,
            envelope.telegram_channel_id,
            nonce,
            100 + envelope.output_channel_id,
        )


def ingest_all(sessions, mappings):
    for event in (REJECTED, ACCEPTED):
        for mapping_id in mappings:
            with sessions() as session:
                result = DurableIngestionWorkflow(session, configured_mapping_id=mapping_id).ingest(
                    event,
                    observed_at=NOW,
                    protected_entities=("Russia",) if event is REJECTED else (),
                    sentiment="negative" if event is REJECTED else "neutral",
                    framing="hostile" if event is REJECTED else "neutral",
                )
                assert result.status == (
                    "REJECTED_EDITORIAL" if event is REJECTED else "REWRITE_QUEUED"
                )


def reject_current(sessions):
    with sessions.begin() as session:
        row = session.scalar(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key == ACCEPTED_KEY
            )
        )
        row.status, row.rewrite_allowed = "REJECT", False


def assert_original_reject(sessions):
    with sessions() as session:
        rejected = session.scalar(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key == REJECTED_KEY
            )
        )
        assert (rejected.status, rejected.rewrite_allowed) == ("REJECT", False)
        assert (
            session.scalar(
                select(models.RewriteJobModel).where(
                    models.RewriteJobModel.content_key == REJECTED_KEY
                )
            )
            is None
        )
        assert (
            session.scalar(
                select(models.PublicationCandidateModel).where(
                    models.PublicationCandidateModel.content_key == REJECTED_KEY
                )
            )
            is None
        )
        assert session.scalar(select(func.count()).select_from(models.RewriteJobModel)) == 2
        assert session.scalar(select(models.RewriteUsageModel)) is None
        assert (
            CIPHER.decrypt(session.get(models.TelegramAccount, 1).encrypted_session)
            == "synthetic-session-marker-not-telegram"
        )


@pytest.mark.parametrize("revoke_at", [None, "verification", "media", "publication", "floodwait"])
def test_unattended_original_photo_pipeline_reopens_every_stage_and_rejects_stale_work(
    unattended, revoke_at
):
    url, media, mappings = unattended
    rewriters = {number: Rewriter(number) for number in (1, 2)}
    verifier, photos, publisher = Verifier(), Photos(flood=revoke_at == "floodwait"), Publisher()
    with reopened(url) as sessions:
        ingest_all(sessions, mappings)
        assert_original_reject(sessions)
        assert worker.run_scheduler_tick(sessions, now=NOW).active_reservations == 0
    with reopened(url) as sessions:
        execution = DurableRewriteRunner(
            sessions, provider_for_channel=rewriters.__getitem__, clock=lambda: NOW
        )
        assert [execution.run_next(now=NOW) for _ in range(3)] == ["SUCCEEDED", "SUCCEEDED", "IDLE"]
        assert [provider.calls for provider in rewriters.values()] == [[SOURCE], [SOURCE]]
        with sessions() as session:
            drafts = session.scalars(
                select(models.RewriteOutputModel).order_by(
                    models.RewriteOutputModel.output_channel_id
                )
            ).all()
            assert [draft.rewritten_text for draft in drafts] == list(DRAFTS.values())
            assert [draft.approval_state for draft in drafts] == ["PENDING", "PENDING"]
    with reopened(url) as sessions:
        if revoke_at == "verification":
            reject_current(sessions)
        execution = DurableSemanticRunner(
            sessions, verifier_for_release=lambda _: verifier, clock=lambda: NOW
        )
        assert execution.enqueue_pending(now=NOW) == (0 if revoke_at == "verification" else 2)
    with reopened(url) as sessions:
        execution = DurableSemanticRunner(
            sessions, verifier_for_release=lambda _: verifier, clock=lambda: NOW
        )
        want = ["IDLE"] * 3 if revoke_at == "verification" else ["SUCCEEDED", "SUCCEEDED", "IDLE"]
        assert [execution.run_next(now=NOW) for _ in range(3)] == want
        assert len(verifier.calls) == (0 if revoke_at == "verification" else 2)
        if revoke_at == "media":
            reject_current(sessions)
        execution = DurableSourcePhotoRunner(sessions, media, provider=photos, clock=lambda: NOW)
        assert execution.enqueue_pending(now=NOW) == (
            0 if revoke_at in {"verification", "media"} else 2
        )
    with reopened(url) as sessions:
        execution = DurableSourcePhotoRunner(sessions, media, provider=photos, clock=lambda: NOW)
        if revoke_at == "floodwait":
            assert execution.run_next(now=NOW) == "RETRY"
            assert execution.run_next(now=NOW) == "IDLE"
            assert photos.calls == [("1", str(CHANNEL), 20)]
    with reopened(url) as sessions:
        media_now = NOW + timedelta(seconds=31) if revoke_at == "floodwait" else NOW
        if revoke_at == "floodwait":
            with sessions() as session:
                waiting = session.scalars(
                    select(models.MediaAcquisitionJobModel).order_by(
                        models.MediaAcquisitionJobModel.id
                    )
                ).all()
                assert [(job.state, job.attempts) for job in waiting] == [
                    ("QUEUED", 1),
                    ("QUEUED", 0),
                ]
            paused = DurableSourcePhotoRunner(
                sessions, media, provider=photos, clock=lambda: media_now
            )
            assert paused.run_next(now=media_now) == "IDLE"
            # Expiry alone cannot waive sync quarantine. Actual opt-in worker
            # tick verifies the session and resumes deletion-first synchronization.
            recovered = worker.run_channel_sync_tick(
                sessions,
                enabled=True,
                cipher=CIPHER,
                provider=photos,
                now=media_now,
                clock=lambda: media_now,
            )
            assert recovered.health_outcomes == ((1, "CONNECTED"),)
            assert recovered.outcomes == ((1, "POLL_COMPLETE"),)
        execution = DurableSourcePhotoRunner(
            sessions, media, provider=photos, clock=lambda: media_now
        )
        want = (
            ["IDLE"] * 3
            if revoke_at in {"verification", "media"}
            else ["SUCCEEDED", "SUCCEEDED", "IDLE"]
        )
        assert [execution.run_next(now=media_now) for _ in range(3)] == want
        assert len(photos.calls) == (
            0 if revoke_at in {"verification", "media"} else 3 if revoke_at == "floodwait" else 2
        )
        with sessions() as session:
            for asset in session.scalars(select(models.MediaAssetModel)):
                assert (media / asset.storage_key).read_bytes() == photos.content
        result = worker.run_scheduler_tick(sessions, now=NOW)
        assert result.failed_plan_ids == ()
        assert result.active_reservations == (0 if revoke_at in {"verification", "media"} else 2)
    with reopened(url) as sessions:
        repeat = worker.run_scheduler_tick(sessions, now=NOW)
        assert repeat.active_reservations == (0 if revoke_at in {"verification", "media"} else 2)
        with sessions() as session:
            plans = session.scalars(
                select(models.PlannedPublicationModel).order_by(
                    models.PlannedPublicationModel.output_channel_id
                )
            ).all()
            if plans:
                assert [item.scheduled_for.replace(tzinfo=UTC) for item in plans] == [
                    NOW + timedelta(minutes=1),
                    NOW + timedelta(minutes=3),
                ]
        if revoke_at == "publication":
            reject_current(sessions)
        late = NOW + timedelta(minutes=4)
        options = {
            "enabled": True,
            "cipher": CIPHER,
            "media_root": media,
            "now": late,
            "publisher": publisher,
            "clock": lambda: late,
        }
        for _ in range(3):
            worker.run_publication_tick(sessions, **options)
    with reopened(url) as sessions:
        for _ in range(3):
            worker.run_publication_tick(sessions, **options)
        assert len(publisher.calls) == (2 if revoke_at in {None, "floodwait"} else 0)
        assert_original_reject(sessions)
        with sessions() as session:
            jobs = session.scalars(select(models.PublicationJobModel)).all()
            assert len(jobs) == (2 if revoke_at in {None, "floodwait"} else 0)
            if revoke_at in {None, "floodwait"}:
                assert [(row.state, row.attempts) for row in jobs] == [
                    ("SUCCEEDED", 1),
                    ("SUCCEEDED", 1),
                ]
                assert len({row.request_nonce for row in jobs}) == 2
                assert set(session.scalars(select(models.PublicationCandidateModel.state))) == {
                    "PUBLISHED"
                }
                assert [call[0].text for call in publisher.calls] == [
                    DRAFTS[1] + "\n\nSynthetic permission only",
                    DRAFTS[2] + "\n\nSynthetic permission only",
                ]
                assert all(call[0].media_asset_id is not None for call in publisher.calls)
