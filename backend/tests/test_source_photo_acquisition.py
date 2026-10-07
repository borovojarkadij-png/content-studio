from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_telegram_photo_download import png

from newsflow.persistence import models
from newsflow.providers.telegram import FakeTelegramProvider, TelegramMessage
from newsflow.services.rewrite_outputs import RewriteOutputService

NOW = datetime(2026, 10, 8, tzinfo=UTC)
CHANNEL = "-1001234567890"
KEY = f"1:{CHANNEL}:20:revision:1"


@pytest.fixture
def source_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'source.db'}")
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory.begin() as session:
        session.add(
            models.TelegramAccount(
                id=1,
                name="Synthetic",
                telegram_user_id=1001,
                encrypted_session="synthetic",
                health_status="CONNECTED",
            )
        )
        session.flush()
        session.add(
            models.OutputChannel(
                id=1, telegram_account_id=1, telegram_channel_id=-1001234567891, title="Synthetic"
            )
        )
        session.add(
            models.IncomingPostModel(
                id=1,
                telegram_account_id="1",
                donor_channel_id=CHANNEL,
                telegram_message_id=20,
                state="RECEIVED",
            )
        )
        session.flush()
        session.add(
            models.ContentRevisionModel(
                incoming_post_id=1,
                revision_number=1,
                source_text="Photo caption",
                media_type="photo",
                media_id="123",
                media_protected=False,
                source_updated_at=NOW,
            )
        )
        session.add(
            models.EditorialDecisionModel(
                content_key=KEY,
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
        )
        session.add(
            models.RewriteJobModel(
                id=1,
                content_key=KEY,
                output_channel_id=1,
                idempotency_key="synthetic-source-photo",
                state="SUCCEEDED",
            )
        )
        session.add(
            models.PublicationCandidateModel(
                id=1,
                content_key=KEY,
                output_channel_id=1,
                state="AWAITING_REWRITE",
                priority=1,
                media_policy="REUSE_SOURCE",
            )
        )
    with factory() as session:
        service = RewriteOutputService(session)
        draft = service.record_succeeded_output(1, "Photo caption")
        service.approve(draft["id"], activate_candidate=True)
    root = tmp_path / "media"
    root.mkdir()
    yield factory, root
    engine.dispose()


class Photos(FakeTelegramProvider):
    def __init__(self, *, change=None, message=None, content=None):
        super().__init__()
        self.calls, self.change = [], change
        self._messages[("1", CHANNEL, 20)] = message or TelegramMessage(
            "1",
            CHANNEL,
            20,
            "Photo caption",
            media_type="photo",
            media_id="123",
            media_protected=False,
            source_updated_at=NOW,
        )
        self._photos[("1", CHANNEL, 20)] = content if content is not None else png()

    def download_photo(self, account_id, donor_identifier, message_id):
        self.calls.append((account_id, donor_identifier, message_id))
        if self.change:
            self.change()
        return super().download_photo(account_id, donor_identifier, message_id)


def acquisition(store, provider):
    from newsflow.services.source_photo import SourcePhotoAcquisition

    factory, root = store
    return SourcePhotoAcquisition(factory, root, provider=provider, clock=lambda: NOW)


def test_source_acquisition_keeps_exact_original_bytes_and_idempotent_explicit_rights(source_store):
    photos = Photos()
    first = acquisition(source_store, photos).acquire(
        1, license_code="PERMISSION", attribution="Owner permission"
    )
    second = acquisition(source_store, photos).acquire(
        1, license_code="PERMISSION", attribution="Owner permission"
    )
    assert first["status"] == "ACQUIRED" and first["illustration"] is False
    assert first["items"][0]["id"] == second["items"][0]["id"]
    asset = first["items"][0]
    assert asset["origin"] == "SOURCE" and asset["source_content_key"] == KEY
    assert asset["license_code"] == "PERMISSION" and asset["attribution"] == "Owner permission"
    assert (source_store[1] / asset["storage_key"]).read_bytes() == png()
    assert photos.calls == [("1", CHANNEL, 20), ("1", CHANNEL, 20)]
    with source_store[0]() as session:
        assert len(session.scalars(select(models.MediaAssetModel)).all()) == 1
    assert not list(source_store[1].glob("source/acquire-*"))


@pytest.mark.parametrize(
    "license_code, credit",
    [("CC0", ""), ("PERMISSION", ""), ("", ""), (None, ""), ("OWNED", "x" * 2049)],
)
def test_missing_or_invalid_source_rights_never_calls_telegram(source_store, license_code, credit):
    photos = Photos()
    with pytest.raises((ValueError, PermissionError)):
        acquisition(source_store, photos).acquire(1, license_code=license_code, attribution=credit)
    assert photos.calls == []


@pytest.mark.parametrize(
    "mutation", ["reject", "review", "source", "policy", "protected", "identity", "session"]
)
def test_revocation_during_photo_rpc_cannot_persist_or_register_source_media(
    source_store, mutation
):
    factory, root = source_store

    def change():
        with factory.begin() as session:
            if mutation == "reject":
                decision = session.scalar(select(models.EditorialDecisionModel))
                decision.status, decision.rewrite_allowed = "REJECT", False
            elif mutation == "review":
                session.scalar(select(models.RewriteOutputModel)).approval_state = "REJECTED"
            elif mutation == "source":
                session.add(
                    models.ContentRevisionModel(
                        incoming_post_id=1, revision_number=2, source_text="Edited"
                    )
                )
            elif mutation == "policy":
                session.get(models.PublicationCandidateModel, 1).media_policy = "LICENSED_LIBRARY"
            elif mutation == "session":
                session.get(models.TelegramAccount, 1).health_status = "SESSION_INVALID"
            else:
                revision = session.scalar(select(models.ContentRevisionModel))
                if mutation == "identity":
                    revision.media_id = "124"
                else:
                    revision.media_protected = True

    with pytest.raises(PermissionError):
        acquisition(source_store, Photos(change=change)).acquire(
            1, license_code="OWNED", attribution=""
        )
    with factory() as session:
        assert session.scalar(select(models.MediaAssetModel)) is None
    assert list(root.iterdir()) == []


def test_foreign_remote_media_identity_never_becomes_the_original_source_photo(source_store):
    photos = Photos()
    photos._messages[("1", CHANNEL, 20)] = replace(
        photos._messages[("1", CHANNEL, 20)], media_id="124"
    )
    with pytest.raises(PermissionError):
        acquisition(source_store, photos).acquire(1, license_code="OWNED", attribution="")
    assert list(source_store[1].iterdir()) == []


def test_broken_image_is_not_left_in_persistent_storage(source_store):
    with pytest.raises(ValueError):
        acquisition(source_store, Photos(content=b"\x89PNG\r\n\x1a\ninvalid")).acquire(
            1, license_code="OWNED", attribution=""
        )
    assert not list(source_store[1].glob("source/*"))
    with source_store[0]() as session:
        assert session.scalar(select(models.MediaAssetModel)) is None


def test_registered_source_bytes_are_never_overwritten_after_corruption(source_store):
    operation = acquisition(source_store, Photos())
    result = operation.acquire(1, license_code="OWNED", attribution="")
    path = source_store[1] / result["items"][0]["storage_key"]
    path.write_bytes(b"original-must-not-be-overwritten")
    with pytest.raises(ValueError):
        operation.acquire(1, license_code="OWNED", attribution="")
    assert path.read_bytes() == b"original-must-not-be-overwritten"


@pytest.mark.parametrize(
    "state", ["reject", "review", "protected", "unknown", "cooldown", "library"]
)
def test_ineligible_source_never_calls_telegram_or_creates_an_acquisition_asset(
    source_store, state
):
    from datetime import timedelta

    factory, root = source_store
    with factory.begin() as session:
        if state == "reject":
            decision = session.scalar(select(models.EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
        elif state == "review":
            session.scalar(select(models.RewriteOutputModel)).approval_state = "REJECTED"
        elif state in {"protected", "unknown"}:
            session.scalar(select(models.ContentRevisionModel)).media_protected = (
                True if state == "protected" else None
            )
        elif state == "cooldown":
            session.get(models.TelegramAccount, 1).cooldown_until = NOW + timedelta(seconds=60)
        else:
            session.get(models.PublicationCandidateModel, 1).media_policy = "LICENSED_LIBRARY"
    photos = Photos()
    with pytest.raises(PermissionError):
        acquisition(source_store, photos).acquire(1, license_code="OWNED", attribution="")
    assert photos.calls == [] and list(root.iterdir()) == []
    with factory() as session:
        assert session.scalar(select(models.MediaAssetModel)) is None
