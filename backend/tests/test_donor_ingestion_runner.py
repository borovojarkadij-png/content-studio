from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.telegram import FakeTelegramProvider, TelegramMessage
from newsflow.services.telegram_configuration import TelegramConfigurationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture
def donor_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'donor.db'}")
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as session:
        config = TelegramConfigurationService(session)
        account = config.create_account("synthetic", 1001)
        donor = config.create_donor(account["id"], -1001234567890, "Donor")
        for n in (1, 2):
            output = config.create_output(account["id"], -1001234567890 - n, str(n))
            config.create_mapping(donor["id"], output["id"], 100, 50)
    yield factory
    engine.dispose()


def runner(factory, provider):
    from newsflow.services.donor_ingestion_runner import DonorIngestionRunner

    return DonorIngestionRunner(factory, provider=provider, clock=lambda: NOW)


def test_poll_persists_inbox_and_cursor_across_sessions_without_inventing_classification(
    donor_store,
):
    provider = FakeTelegramProvider()
    provider.seed_message("1", "-1001234567890", 1, "Unclassified news")
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "POLL_COMPLETE"
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "POLL_COMPLETE"
    with donor_store() as session:
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 1
        assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 1
        assert session.scalars(select(models.RewriteJobModel)).all() == []
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert decision.status == "MANUAL_REVIEW"
        assert decision.rewrite_allowed is False


def test_expired_poll_owner_cannot_touch_source_or_advance_cursor(donor_store):
    provider = FakeTelegramProvider()
    provider.seed_message("1", "-1001234567890", 1, "Unclassified news")
    old = runner(donor_store, provider).claim(1, now=NOW)
    assert old is not None
    replacement_runner = runner(donor_store, provider)
    replacement_runner._clock = lambda: NOW + timedelta(seconds=61)
    replacement = replacement_runner.claim(1, now=NOW + timedelta(seconds=61))
    assert replacement is not None
    assert runner(donor_store, provider).execute(old) == "STALE_CLAIM"
    with donor_store() as session:
        assert session.scalars(select(models.IncomingPostModel)).all() == []
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 0
    assert replacement_runner.execute(replacement) == "POLL_COMPLETE"


def test_crash_after_mapping_commit_replays_source_without_losing_other_mapping(
    donor_store, monkeypatch
):
    provider = FakeTelegramProvider()
    provider.seed_message("1", "-1001234567890", 1, "Synthetic permitted news")
    original = DurableIngestionWorkflow.ingest
    calls = 0

    def synthetic_annotated_ingest(self, event, **kwargs):
        nonlocal calls
        result = original(self, event, sentiment="neutral", framing="neutral", **kwargs)
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("simulated process exit after first commit")
        return result

    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", synthetic_annotated_ingest)
    with pytest.raises(KeyboardInterrupt):
        runner(donor_store, provider).run_donor(1, now=NOW)
    with donor_store() as session:
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 0
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1
    restarted = runner(donor_store, provider)
    restarted._clock = lambda: NOW + timedelta(seconds=61)
    assert restarted.run_donor(1, now=NOW + timedelta(seconds=61)) == "POLL_COMPLETE"
    with donor_store() as session:
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 1
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 2
        assert len(session.scalars(select(models.PublicationCandidateModel)).all()) == 2


def test_poll_floodwait_is_durable_and_repeated_poll_does_not_contact_provider(donor_store):
    provider = FakeTelegramProvider()
    provider.seed_floodwait("1", 120)
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "COOLDOWN"
    assert runner(donor_store, provider).run_donor(1, now=NOW + timedelta(seconds=30)) == "IDLE"
    assert provider.session_probe_count("1") == 1
    with donor_store() as session:
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 0
        assert session.get(models.TelegramAccount, 1).health_status == "COOLDOWN"


def test_foreign_provider_source_is_rejected_before_ingestion_and_cursor_advance(donor_store):
    class WrongSourceProvider(FakeTelegramProvider):
        def history(self, account_id, donor_identifier, *, after_id, limit):
            return (TelegramMessage("another-account", donor_identifier, 1, "Foreign"),)

    assert (
        runner(donor_store, WrongSourceProvider()).run_donor(1, now=NOW)
        == "FAILED_PROVIDER_CONTRACT"
    )
    with donor_store() as session:
        assert session.scalars(select(models.IncomingPostModel)).all() == []
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 0


def test_zero_intake_does_not_create_editorial_or_rewrite(donor_store):
    with donor_store() as session:
        for mapping in session.scalars(select(models.ChannelMappingModel)):
            mapping.intake_percent = 0
        session.commit()
    provider = FakeTelegramProvider()
    provider.seed_message("1", "-1001234567890", 1, "Ignored news")
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "POLL_COMPLETE"
    with donor_store() as session:
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 1
        assert session.scalars(select(models.EditorialDecisionModel)).all() == []
        assert session.scalars(select(models.RewriteJobModel)).all() == []


def test_lease_expiring_during_history_request_cannot_persist_provider_response(donor_store):
    poller = None

    class SlowProvider(FakeTelegramProvider):
        def history(self, account_id, donor_identifier, *, after_id, limit):
            poller._clock = lambda: NOW + timedelta(seconds=61)
            return (TelegramMessage(account_id, donor_identifier, 1, "Late response"),)

    poller = runner(donor_store, SlowProvider())
    assert poller.run_donor(1, now=NOW) == "STALE_CLAIM"
    with donor_store() as session:
        assert session.scalars(select(models.IncomingPostModel)).all() == []
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 0


@pytest.mark.parametrize("ids", [(2, 1), (1, 1), (0,), (True,)])
def test_invalid_history_order_or_identity_cannot_advance_cursor(donor_store, ids):
    class InvalidProvider(FakeTelegramProvider):
        def history(self, account_id, donor_identifier, *, after_id, limit):
            return tuple(TelegramMessage(account_id, donor_identifier, n, "Invalid") for n in ids)

    assert (
        runner(donor_store, InvalidProvider()).run_donor(1, now=NOW) == "FAILED_PROVIDER_CONTRACT"
    )
    with donor_store() as session:
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 0


def test_poll_pages_do_not_skip_messages_or_duplicate_observation_history(donor_store):
    from newsflow.services.donor_ingestion_runner import DonorIngestionRunner

    provider = FakeTelegramProvider()
    for n in range(1, 6):
        provider.seed_message("1", "-1001234567890", n, f"News {n}")
    poller = DonorIngestionRunner(donor_store, provider=provider, clock=lambda: NOW, page_size=2)
    for expected in (2, 4, 5, 5):
        assert poller.run_donor(1, now=NOW) == "POLL_COMPLETE"
        with donor_store() as session:
            assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == expected
            assert len(session.scalars(select(models.IncomingPostModel)).all()) == expected


def test_unavailable_session_does_not_repeat_authentication_attempts(donor_store):
    provider = FakeTelegramProvider()
    provider.seed_session_unavailable("1")
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "SESSION_INVALID"
    assert runner(donor_store, provider).run_donor(1, now=NOW + timedelta(minutes=10)) == "IDLE"
    assert provider.session_probe_count("1") == 1


def test_naive_time_fails_without_database_or_provider_activity():
    from newsflow.services.donor_ingestion_runner import DonorIngestionRunner

    def forbidden_session():
        raise AssertionError("No database access allowed")

    with pytest.raises(ValueError, match="timezone-aware"):
        DonorIngestionRunner(forbidden_session, provider=FakeTelegramProvider()).run_donor(
            1, now=NOW.replace(tzinfo=None)
        )


def test_disabled_ingestion_tick_does_not_read_database_credentials_or_session():
    from newsflow.worker import run_ingestion_tick

    def forbidden_session():
        raise AssertionError("Disabled ingestion touched database")

    assert run_ingestion_tick(forbidden_session, enabled=False, cipher=None, now=NOW) == ()


def test_enabled_ingestion_requires_stable_cipher_before_reading_configuration():
    from newsflow.worker import run_ingestion_tick

    def forbidden_session():
        raise AssertionError("Missing cipher touched database")

    with pytest.raises(ValueError, match="cipher"):
        run_ingestion_tick(forbidden_session, enabled=True, cipher=None, now=NOW)


def test_enabled_worker_polls_real_configured_donor_and_keeps_unknown_source_in_review(donor_store):
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.worker import run_ingestion_tick

    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with donor_store() as session:
        session.get(models.TelegramAccount, 1).encrypted_session = cipher.encrypt("synthetic")
        session.commit()
    provider = FakeTelegramProvider()
    provider.seed_message("1", "-1001234567890", 1, "Unclassified worker news")
    assert run_ingestion_tick(
        donor_store, enabled=True, cipher=cipher, provider=provider, now=datetime.now(UTC)
    ) == ((1, "POLL_COMPLETE"),)
    with donor_store() as session:
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 1
        assert session.scalar(select(models.EditorialDecisionModel)).status == "MANUAL_REVIEW"
        assert session.scalars(select(models.RewriteJobModel)).all() == []
