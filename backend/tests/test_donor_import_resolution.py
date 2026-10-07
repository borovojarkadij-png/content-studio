from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from telethon.tl.types import Channel, ChatPhotoEmpty, User

from newsflow.persistence.models import Base, DonorChannel, DonorImportModel, TelegramAccount
from newsflow.providers.telegram import FakeTelegramProvider, TelethonTelegramProvider
from newsflow.services.telegram_configuration import TelegramConfigurationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def test_read_only_username_resolution_requires_full_channel_hash_and_identity():
    from test_telegram_peers import PeerClient

    class Client(PeerClient):
        async def get_entity(self, identifier):
            assert identifier == "@synthetic_donor"
            return Channel(
                1234567890,
                "Synthetic donor",
                ChatPhotoEmpty(),
                NOW,
                broadcast=True,
                access_hash=987654321,
                username="synthetic_donor",
            )

    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: Client(),
    )
    resolved = provider.resolve_channel("1", "@synthetic_donor")
    assert resolved.peer.channel_id == -1001234567890
    assert resolved.peer.account_id == "1"
    assert resolved.title == "Synthetic donor"


@pytest.mark.parametrize("shape", ["user", "min", "wrong_username", "missing_hash"])
def test_unusable_username_resolution_never_becomes_an_operational_donor(shape):
    from test_telegram_peers import PeerClient

    class Client(PeerClient):
        async def get_entity(self, identifier):
            if shape == "user":
                return User(1234567890, username="synthetic_donor", access_hash=987654321)
            return Channel(
                1234567890,
                "Synthetic",
                ChatPhotoEmpty(),
                NOW,
                broadcast=True,
                min=shape == "min",
                access_hash=None if shape == "missing_hash" else 987654321,
                username="foreign_donor" if shape == "wrong_username" else "synthetic_donor",
            )

    client = Client()
    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
    )
    with pytest.raises(ValueError):
        provider.resolve_channel("1", "@synthetic_donor")
    assert client.disconnected == 1


@pytest.fixture
def imports(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'imports.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as session:
        config = TelegramConfigurationService(session)
        account = config.create_account("Synthetic", 1001)
        config.bulk_import_donors(account["id"], "@synthetic_donor\n@alias_donor")
        session.get(TelegramAccount, account["id"]).encrypted_session = "synthetic-only"
        session.commit()
    yield sessions
    engine.dispose()


def provider():
    result = FakeTelegramProvider()
    for name in ("@synthetic_donor", "@alias_donor"):
        result.seed_channel("1", name, -1001234567890, "Synthetic donor")
    return result


def test_two_alias_imports_resolve_to_one_immutable_donor_across_restart(imports):
    from newsflow.services.donor_import_resolution import DonorImportResolutionRunner

    runtime = DonorImportResolutionRunner(imports, provider=provider(), clock=lambda: NOW)
    assert runtime.run_import(1, now=NOW) == "RESOLVED"
    assert (
        DonorImportResolutionRunner(imports, provider=provider(), clock=lambda: NOW).run_import(
            2, now=NOW
        )
        == "RESOLVED"
    )
    assert runtime.run_import(1, now=NOW) == "IDLE"
    with imports() as session:
        donors = session.scalars(select(DonorChannel)).all()
        assert len(donors) == 1
        assert donors[0].telegram_channel_id == -1001234567890
        assert set(session.scalars(select(DonorImportModel.status))) == {"RESOLVED"}


def test_expired_import_owner_cannot_resolve_or_mutate_donor(imports):
    from newsflow.services.donor_import_resolution import DonorImportResolutionRunner

    first = DonorImportResolutionRunner(imports, provider=provider(), clock=lambda: NOW)
    claim = first.claim(1, now=NOW)
    later = NOW + timedelta(seconds=61)
    next_runtime = DonorImportResolutionRunner(imports, provider=provider(), clock=lambda: later)
    replacement = next_runtime.claim(1, now=later)
    assert first.execute(claim) == "STALE_CLAIM"
    with imports() as session:
        assert session.scalar(select(DonorChannel)) is None
    assert next_runtime.execute(replacement) == "RESOLVED"


def test_import_floodwait_is_persisted_and_blocks_other_account_work(imports):
    from newsflow.services.donor_import_resolution import DonorImportResolutionRunner

    limited = provider()
    limited.seed_floodwait("1", 120)
    runtime = DonorImportResolutionRunner(imports, provider=limited, clock=lambda: NOW)
    assert runtime.run_import(1, now=NOW) == "COOLDOWN"
    assert runtime.run_import(2, now=NOW) == "IDLE"
    with imports() as session:
        account = session.get(TelegramAccount, 1)
        assert account.cooldown_until.replace(tzinfo=UTC) == NOW + timedelta(seconds=120)
        assert session.scalar(select(DonorChannel)) is None


def test_unprovisioned_import_does_not_construct_provider_or_create_donor(imports):
    from newsflow.services.donor_import_resolution import DonorImportResolutionRunner

    with imports.begin() as session:
        session.get(TelegramAccount, 1).encrypted_session = ""

    class Forbidden:
        def resolve_channel(self, *args):
            raise AssertionError("No RPC before manual authorization")

    assert (
        DonorImportResolutionRunner(imports, provider=Forbidden(), clock=lambda: NOW).run_import(
            1, now=NOW
        )
        == "IDLE"
    )
    with imports() as session:
        assert session.scalar(select(DonorChannel)) is None


def test_existing_user_donor_title_is_not_replaced_by_import(imports):
    from newsflow.services.donor_import_resolution import DonorImportResolutionRunner

    with imports() as session:
        TelegramConfigurationService(session).create_donor(1, -1001234567890, "My manual title")
    assert (
        DonorImportResolutionRunner(imports, provider=provider(), clock=lambda: NOW).run_import(
            1, now=NOW
        )
        == "RESOLVED"
    )
    with imports() as session:
        assert session.scalar(select(DonorChannel)).title == "My manual title"


def test_import_cannot_store_result_after_session_was_replaced_during_rpc(imports):
    from newsflow.services.donor_import_resolution import DonorImportResolutionRunner

    wrapped = provider()
    original = wrapped.resolve_channel

    def replace(account, identifier):
        with imports.begin() as session:
            session.get(TelegramAccount, 1).encrypted_session = "new manual session"
        return original(account, identifier)

    wrapped.resolve_channel = replace
    assert (
        DonorImportResolutionRunner(imports, provider=wrapped, clock=lambda: NOW).run_import(
            1, now=NOW
        )
        == "STALE_CLAIM"
    )
    with imports() as session:
        assert session.scalar(select(DonorChannel)) is None


def test_resolution_worker_is_disabled_without_database_or_rpc_access():
    from newsflow.worker import run_donor_resolution_tick

    def forbidden():
        raise AssertionError("Disabled worker must not read database")

    assert run_donor_resolution_tick(forbidden, enabled=False, cipher=None, now=NOW) == ()


def test_resolution_worker_handles_pending_imports_with_the_injected_provider(imports):
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.worker import run_donor_resolution_tick

    outcomes = run_donor_resolution_tick(
        imports,
        enabled=True,
        cipher=SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="),
        now=NOW,
        provider=provider(),
    )
    assert outcomes == ((1, "RESOLVED"), (2, "RESOLVED"))


def test_resolved_import_emits_exactly_one_durable_identity_event(imports):
    from newsflow.persistence.models import OutboxEventModel
    from newsflow.services.donor_import_resolution import DonorImportResolutionRunner

    runtime = DonorImportResolutionRunner(imports, provider=provider(), clock=lambda: NOW)
    assert runtime.run_import(1, now=NOW) == "RESOLVED"
    assert runtime.run_import(1, now=NOW) == "IDLE"
    with imports() as session:
        events = session.scalars(select(OutboxEventModel)).all()
        assert len(events) == 1
        assert events[0].event_type == "donor.import.resolved"
        assert events[0].idempotency_key == "donor.import.resolved:1"


def test_resolution_requires_a_validated_immutable_peer_contract():
    from types import SimpleNamespace

    from newsflow.providers.telegram import TelegramChannelResolution

    with pytest.raises(TypeError):
        TelegramChannelResolution(
            "@synthetic_donor", SimpleNamespace(account_id="1", channel_id=0), "Synthetic"
        )


def test_factory_username_resolution_persists_peer_for_later_numeric_reads(imports):
    from test_telegram_peers import PeerClient

    from newsflow.persistence.models import TelegramPeerModel
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with imports.begin() as session:
        session.get(TelegramAccount, 1).encrypted_session = cipher.encrypt("synthetic session")

    class Client(PeerClient):
        async def get_entity(self, identifier):
            return Channel(
                1234567890,
                "Synthetic",
                ChatPhotoEmpty(),
                NOW,
                broadcast=True,
                access_hash=987654321,
                username="synthetic_donor",
            )

    client = Client()
    configured = ConfiguredTelegramProvider(
        imports, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    assert configured.resolve_channel("1", "@synthetic_donor").peer.channel_id == -1001234567890
    with imports() as session:
        stored = session.get(TelegramPeerModel, (1, -1001234567890))
        assert "987654321" not in stored.encrypted_peer
    assert configured.history("1", "-1001234567890", after_id=0, limit=5)[0].message_id == 1
    assert client.dialog_reads == 0
