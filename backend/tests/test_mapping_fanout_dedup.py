"""Migrated SQL fan-out must reserve cheap dedup in every eligible mapping."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from os import getenv
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy import event as sql_event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.editorial import EditorialGate
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    EditorialDecisionModel,
    IncomingPostModel,
    MappingContentFingerprintModel,
    OutboxEventModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.telegram_configuration import TelegramConfigurationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)
CHANNEL = -1001234567890


class CountingGate(EditorialGate):
    def __init__(self):
        self.calls = 0

    def evaluate(self, **kwargs):
        self.calls += 1
        return super().evaluate(**kwargs)


@pytest.fixture
def mapping_store(tmp_path, monkeypatch):
    postgres = getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL")
    url = (
        create_postgres_namespace(postgres)
        if postgres is not None
        else f"sqlite:///{tmp_path / 'fanout.db'}"
    )
    monkeypatch.setenv("DATABASE_URL", url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    with Session(engine) as session:
        session.add(
            TelegramAccount(
                name="Synthetic fanout account", telegram_user_id=1001, encrypted_session=""
            )
        )
        session.commit()
        configuration = TelegramConfigurationService(session)
        donor = configuration.create_donor(1, CHANNEL, "Synthetic fanout donor")
        first = configuration.create_output(1, -1001234567891, "First synthetic output")
        second = configuration.create_output(1, -1001234567892, "Second synthetic output")
        mappings = tuple(
            configuration.create_mapping(donor["id"], output["id"], 100, 50)["id"]
            for output in (first, second)
        )
    yield url, mappings
    engine.dispose()


def ingest(store, index, event, gate, **classification):
    url, mappings = store
    # New actual engine/session between deliveries; no cache or Redis truth.
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            return DurableIngestionWorkflow(
                session, editorial_gate=gate, configured_mapping_id=mappings[index]
            ).ingest(
                event,
                observed_at=NOW,
                sentiment=classification.pop("sentiment", "neutral"),
                framing=classification.pop("framing", "neutral"),
                **classification,
            )
    finally:
        engine.dispose()


def counts(store):
    engine = create_engine(store[0])
    try:
        with Session(engine) as session:
            return tuple(
                session.scalar(select(func.count()).select_from(model))
                for model in (
                    MappingContentFingerprintModel,
                    EditorialDecisionModel,
                    RewriteJobModel,
                    PublicationCandidateModel,
                )
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("media", ["text", "photo"])
def test_fanout_reserves_exact_fingerprint_before_a_later_same_mapping_duplicate(
    mapping_store, media
):
    gate = CountingGate()
    source = TelegramMessage("1", str(CHANNEL), 20, "Same headline", media_type=media)
    assert ingest(mapping_store, 0, source, gate).status == "REWRITE_QUEUED"
    assert ingest(mapping_store, 1, source, gate).status == "REWRITE_QUEUED"
    duplicate = TelegramMessage("1", str(CHANNEL), 29, " same headline ", media_type=media)
    assert ingest(mapping_store, 1, duplicate, gate).status == "REJECTED_DUPLICATE"
    assert gate.calls == 1
    assert counts(mapping_store) == (2, 1, 2, 2)


def test_preexisting_duplicate_reservation_blocks_new_fanout_work(mapping_store):
    gate = CountingGate()
    source = TelegramMessage("1", str(CHANNEL), 20, "Shared headline")
    earlier = TelegramMessage("1", str(CHANNEL), 29, "Shared headline")
    assert ingest(mapping_store, 0, source, gate).status == "REWRITE_QUEUED"
    assert ingest(mapping_store, 1, earlier, gate).status == "REWRITE_QUEUED"
    before = counts(mapping_store)
    assert ingest(mapping_store, 1, source, gate).status == "REJECTED_DUPLICATE"
    assert counts(mapping_store) == before == (2, 2, 2, 2)
    assert gate.calls == 2


@pytest.mark.parametrize(
    "classification,status",
    [
        (
            {"protected_entities": ["Protected"], "sentiment": "negative", "framing": "hostile"},
            "REJECTED_EDITORIAL",
        ),
        ({"sentiment": "unknown", "framing": "unknown"}, "MANUAL_REVIEW"),
    ],
)
def test_rejected_or_unclassified_fanout_never_creates_work_or_calls_rewrite(
    mapping_store, classification, status
):
    gate = CountingGate()
    source = TelegramMessage("1", str(CHANNEL), 20, "Protected hostile source")
    assert ingest(mapping_store, 0, source, gate, **classification).status == status
    assert ingest(mapping_store, 1, source, gate).status == status
    assert ingest(mapping_store, 1, source, gate).status == status
    assert counts(mapping_store) == (1, 1, 0, 0)
    assert gate.calls == 1
    engine = create_engine(mapping_store[0])
    try:

        def no_provider(_channel):
            pytest.fail("Rejected/unclassified fan-out must not construct an AI provider")

        assert (
            DurableRewriteRunner(sessionmaker(engine), provider_for_channel=no_provider).run_next(
                now=NOW
            )
            == "IDLE"
        )
        with Session(engine) as session:
            assert session.scalar(select(EditorialDecisionModel)).rewrite_allowed is False
            assert session.scalar(select(func.count()).select_from(IncomingPostModel)) == 1
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEventModel)
                    .where(OutboxEventModel.event_type == "rewrite.requested")
                )
                == 0
            )
    finally:
        engine.dispose()


def test_fanout_reservation_rolls_back_with_job_failure_then_retry_succeeds(
    mapping_store, monkeypatch
):
    gate = CountingGate()
    source = TelegramMessage("1", str(CHANNEL), 20, "Atomic fanout source")
    assert ingest(mapping_store, 0, source, gate).status == "REWRITE_QUEUED"
    original = DurableEditorialService.create_rewrite_job

    def fail(*_args, **_kwargs):
        raise RuntimeError("Synthetic job storage failure")

    monkeypatch.setattr(DurableEditorialService, "create_rewrite_job", fail)
    with pytest.raises(RuntimeError, match="Synthetic job storage failure"):
        ingest(mapping_store, 1, source, gate)
    assert counts(mapping_store) == (1, 1, 1, 1)
    monkeypatch.setattr(DurableEditorialService, "create_rewrite_job", original)
    assert ingest(mapping_store, 1, source, gate).status == "REWRITE_QUEUED"
    assert counts(mapping_store) == (2, 1, 2, 2)
    assert gate.calls == 1


def test_first_ingress_classifier_failure_does_not_poison_dedup_retry(mapping_store):
    class FailingGate(EditorialGate):
        def evaluate(self, **_kwargs):
            raise RuntimeError("Synthetic classifier unavailable")

    source = TelegramMessage("1", str(CHANNEL), 20, "Atomic initial source")
    with pytest.raises(RuntimeError, match="Synthetic classifier unavailable"):
        ingest(mapping_store, 0, source, FailingGate())
    assert counts(mapping_store) == (0, 0, 0, 0)
    gate = CountingGate()
    assert ingest(mapping_store, 0, source, gate).status == "REWRITE_QUEUED"
    assert counts(mapping_store) == (1, 1, 1, 1)
    assert gate.calls == 1


def test_each_output_executes_its_own_rewrite_once_despite_fanout_retries_and_text_duplicates(
    mapping_store,
):
    gate = CountingGate()
    source = TelegramMessage("1", str(CHANNEL), 20, "Завод открыл 3 линии.")
    for mapping in (0, 1):
        assert ingest(mapping_store, mapping, source, gate).status == "REWRITE_QUEUED"
        assert ingest(mapping_store, mapping, source, gate).status == "REJECTED_DUPLICATE"
        assert (
            ingest(
                mapping_store, mapping, TelegramMessage("1", str(CHANNEL), 29, source.text), gate
            ).status
            == "REJECTED_DUPLICATE"
        )
    calls = []
    drafts = {1: "На заводе открыты 3 линии.", 2: "Открыты 3 линии на заводе."}

    class SyntheticProvider:
        def __init__(self, channel):
            self.channel = channel

        def rewrite(self, text):
            calls.append((self.channel, text))
            return drafts[self.channel]

    # Dispose/reopen between real durable worker calls, no live providers.
    for expected in ("SUCCEEDED", "SUCCEEDED", "IDLE"):
        engine = create_engine(mapping_store[0])
        try:
            assert (
                DurableRewriteRunner(
                    sessionmaker(engine), provider_for_channel=SyntheticProvider, clock=lambda: NOW
                ).run_next(now=NOW)
                == expected
            )
        finally:
            engine.dispose()
    assert calls == [(1, source.text), (2, source.text)]
    assert gate.calls == 1
    engine = create_engine(mapping_store[0])
    try:
        with Session(engine) as session:
            stored = session.scalars(
                select(RewriteOutputModel).order_by(RewriteOutputModel.output_channel_id)
            ).all()
            assert [
                (row.output_channel_id, row.rewritten_text, row.approval_state) for row in stored
            ] == [(channel, text, "PENDING") for channel, text in drafts.items()]
            assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 2
            assert [
                row.attempts
                for row in session.scalars(select(RewriteJobModel).order_by(RewriteJobModel.id))
            ] == [1, 1]
    finally:
        engine.dispose()


def test_unrelated_integrity_failure_is_not_reported_as_successful_duplicate(mapping_store):
    engine = create_engine(mapping_store[0])
    gate = CountingGate()
    try:
        with Session(engine) as session, pytest.raises(IntegrityError):
            # Actual migrated NOT NULL failure, not a mocked IntegrityError.
            DurableIngestionWorkflow(
                session,
                editorial_gate=gate,
                technical_filter=MappingTechnicalFilter(mapping_id=None, output_channel_id=2),
            ).ingest(
                TelegramMessage("1", str(CHANNEL), 20, "Invalid configuration source"),
                observed_at=NOW,
                sentiment="neutral",
                framing="neutral",
            )
        assert counts(mapping_store) == (0, 0, 0, 0)
        assert gate.calls == 0
    finally:
        engine.dispose()


def test_independent_competing_connections_reserve_only_one_fingerprint_before_editorial(
    mapping_store,
):
    engine = create_engine(mapping_store[0])
    gate = CountingGate()
    barrier = Barrier(2)

    def before_insert(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO mapping_content_fingerprints"):
            barrier.wait(timeout=10)

    sql_event.listen(engine, "before_cursor_execute", before_insert)

    def deliver(number):
        with Session(engine) as session:
            return (
                DurableIngestionWorkflow(
                    session,
                    editorial_gate=gate,
                    technical_filter=MappingTechnicalFilter(
                        mapping_id="concurrent", output_channel_id=2
                    ),
                )
                .ingest(
                    TelegramMessage("1", str(CHANNEL), number, "Concurrent headline"),
                    observed_at=NOW,
                    sentiment="neutral",
                    framing="neutral",
                )
                .status
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(deliver, number) for number in (20, 29)]
            assert sorted(result.result(timeout=20) for result in results) == [
                "REJECTED_DUPLICATE",
                "REWRITE_QUEUED",
            ]
        assert gate.calls == 1
        assert counts(mapping_store) == (1, 1, 1, 1)
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(IncomingPostModel)) == 1
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEventModel)
                    .where(OutboxEventModel.event_type == "rewrite.requested")
                )
                == 1
            )
    finally:
        sql_event.remove(engine, "before_cursor_execute", before_insert)
        engine.dispose()
