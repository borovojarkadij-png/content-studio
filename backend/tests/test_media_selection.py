"""Offline media selection: only authorized source files or a licensed local library."""

from hashlib import sha256

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutputChannel,
    PublicationCandidateModel,
    TelegramAccount,
)


@pytest.fixture
def media_store(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    root = tmp_path / "media"
    root.mkdir()
    with Session(engine) as session:
        account = TelegramAccount(name="Synthetic", telegram_user_id=1001, encrypted_session="")
        session.add(account)
        session.flush()
        channel = OutputChannel(
            telegram_account_id=account.id, telegram_channel_id=-1001234567890, title="Synthetic"
        )
        session.add(channel)
        session.flush()
        session.add(
            EditorialDecisionModel(
                content_key="source:revision:1",
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
        )
        candidate = PublicationCandidateModel(
            output_channel_id=channel.id,
            content_key="source:revision:1",
            priority=10,
            state="READY",
            media_policy="REUSE_SOURCE",
        )
        session.add(candidate)
        session.commit()
        yield session, root, candidate.id
    engine.dispose()


def photo(root, name):
    data = b"\x89PNG\r\n\x1a\n" + b"synthetic-only-photo"
    (root / name).write_bytes(data)
    return sha256(data).hexdigest()


def service(session, root):
    from newsflow.services.media_selection import LocalMediaSelectionService

    return LocalMediaSelectionService(session, root)


def test_source_reuse_never_substitutes_other_revision_or_library(media_store):
    session, root, candidate_id = media_store
    photo(root, "source.png")
    photo(root, "other.png")
    selector = service(session, root)
    selector.register_asset(
        "source.png",
        origin="SOURCE",
        license_code="PERMISSION",
        attribution="@authorized_source",
        tags=("космос",),
        source_content_key="source:revision:1",
    )
    selector.register_asset(
        "other.png",
        origin="SOURCE",
        license_code="PERMISSION",
        attribution="@other",
        tags=("космос",),
        source_content_key="source:revision:2",
    )
    selected = selector.select_for_candidate(candidate_id, query="Космос")
    assert selected["status"] == "SELECTED"
    assert [asset["storage_key"] for asset in selected["items"]] == ["source.png"]
    assert selected["items"][0]["license_code"] == "PERMISSION"
    assert (root / "source.png").read_bytes().endswith(b"synthetic-only-photo")


def test_library_ranking_is_local_deterministic_and_preserves_attribution(media_store):
    session, root, candidate_id = media_store
    selector = service(session, root)
    for name, tags in (
        ("low.png", ("космос",)),
        ("best.png", ("космос", "марс")),
        ("unrelated.png", ("спорт",)),
    ):
        photo(root, name)
        selector.register_asset(
            name,
            origin="LICENSED_LIBRARY",
            license_code="CC-BY",
            attribution="Synthetic author · https://example.org/license",
            tags=tags,
        )
    candidate = session.get(PublicationCandidateModel, candidate_id)
    candidate.media_policy = "LICENSED_LIBRARY"
    session.commit()
    result = selector.select_for_candidate(candidate_id, query="Марс и космос", limit=1)
    assert [asset["storage_key"] for asset in result["items"]] == ["best.png"]
    assert result["items"][0]["attribution"] == "Synthetic author · https://example.org/license"
    assert (
        selector.select_for_candidate(candidate_id, query="Без совпадений")["status"] == "NO_MATCH"
    )


@pytest.mark.parametrize(
    "storage_key",
    [
        "../outside.png",
        "C:/outside.png",
        "/outside.png",
        "https://example.org/photo.png",
        "folder\\outside.png",
    ],
)
def test_media_paths_cannot_escape_root_or_trigger_remote_fetch(media_store, storage_key):
    session, root, _ = media_store
    with pytest.raises(ValueError, match="storage key"):
        service(session, root).register_asset(
            storage_key, origin="LICENSED_LIBRARY", license_code="CC0", attribution="", tags=()
        )


@pytest.mark.parametrize(
    "origin,license_code,attribution",
    [
        ("SOURCE", "CC0", "author"),
        ("LICENSED_LIBRARY", "UNKNOWN", "author"),
        ("LICENSED_LIBRARY", "CC-BY", ""),
    ],
)
def test_unproven_rights_or_missing_required_credit_are_rejected(
    media_store, origin, license_code, attribution
):
    session, root, _ = media_store
    photo(root, "asset.png")
    with pytest.raises(ValueError, match="rights"):
        service(session, root).register_asset(
            "asset.png",
            origin=origin,
            license_code=license_code,
            attribution=attribution,
            tags=(),
            source_content_key="source:revision:1" if origin == "SOURCE" else None,
        )


def test_missing_and_modified_media_fail_visibly_without_replacing_original(media_store):
    session, root, candidate_id = media_store
    photo(root, "source.png")
    selector = service(session, root)
    selector.register_asset(
        "source.png",
        origin="SOURCE",
        license_code="OWNED",
        attribution="",
        tags=(),
        source_content_key="source:revision:1",
    )
    (root / "source.png").write_bytes(b"\x89PNG\r\n\x1a\nmodified")
    with pytest.raises(ValueError, match="integrity"):
        selector.select_for_candidate(candidate_id, query="")
    (root / "source.png").unlink()
    with pytest.raises(ValueError, match="unavailable"):
        selector.select_for_candidate(candidate_id, query="")


def test_current_editorial_reject_blocks_media_selection_and_creates_no_jobs(media_store):
    session, root, candidate_id = media_store
    from sqlalchemy import func, select

    from newsflow.persistence.models import EditorialDecisionModel, RewriteJobModel

    decision = session.scalar(select(EditorialDecisionModel))
    decision.status, decision.rewrite_allowed = "REJECT", False
    session.commit()
    with pytest.raises(PermissionError, match="EDITORIAL"):
        service(session, root).select_for_candidate(candidate_id, query="")
    assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 0


def test_registration_retry_preserves_original_metadata_and_rejects_conflicting_license(
    media_store,
):
    session, root, _ = media_store
    photo(root, "library.png")
    selector = service(session, root)
    first = selector.register_asset(
        "library.png", origin="LICENSED_LIBRARY", license_code="CC0", attribution="", tags=("Марс",)
    )
    assert (
        selector.register_asset(
            "library.png",
            origin="LICENSED_LIBRARY",
            license_code="CC0",
            attribution="",
            tags=("марс",),
        )
        == first
    )
    with pytest.raises(ValueError, match="already registered"):
        selector.register_asset(
            "library.png",
            origin="LICENSED_LIBRARY",
            license_code="CC-BY",
            attribution="new author",
            tags=("марс",),
        )


@pytest.mark.parametrize("content", [b"<html>not an image</html>", b"\xff\xd8\xffwrong-extension"])
def test_media_registration_rejects_disguised_or_wrong_format_photos(media_store, content):
    session, root, _ = media_store
    (root / "invalid.png").write_bytes(content)
    with pytest.raises(ValueError, match="signature"):
        service(session, root).register_asset(
            "invalid.png", origin="LICENSED_LIBRARY", license_code="CC0", attribution="", tags=()
        )
