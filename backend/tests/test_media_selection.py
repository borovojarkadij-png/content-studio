"""Offline media selection: only authorized source files or a licensed local library."""

from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
    TelegramAccount,
)

KEY = "source:@donor:1:revision:1"


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
                content_key=KEY,
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
        )
        candidate = PublicationCandidateModel(
            output_channel_id=channel.id,
            content_key=KEY,
            priority=10,
            state="AWAITING_REWRITE",
            media_policy="REUSE_SOURCE",
        )
        session.add(candidate)
        source = IncomingPostModel(
            telegram_account_id="source",
            donor_channel_id="@donor",
            telegram_message_id=1,
            state="RECEIVED",
        )
        session.add(source)
        session.flush()
        session.add(
            ContentRevisionModel(
                incoming_post_id=source.id,
                revision_number=1,
                source_text="Synthetic source photo",
                media_type="photo",
            )
        )
        job = RewriteJobModel(
            content_key=KEY,
            output_channel_id=channel.id,
            idempotency_key="synthetic-media-rewrite",
            state="SUCCEEDED",
        )
        session.add(job)
        session.commit()
        from newsflow.services.rewrite_outputs import RewriteOutputService

        review = RewriteOutputService(session)
        output = review.record_succeeded_output(job.id, "Synthetic source photo")
        review.approve(output["id"], activate_candidate=True)
        yield session, root, candidate.id
    engine.dispose()


def photo(root, name, color="navy"):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color).save(buffer, format="PNG")
    data = buffer.getvalue()
    (root / name).write_bytes(data)
    return sha256(data).hexdigest()


def service(session, root):
    from newsflow.services.media_selection import LocalMediaSelectionService

    return LocalMediaSelectionService(session, root)


@pytest.mark.parametrize(
    "content", [b"\x89PNG\r\n\x1a\nnot-a-real-image", b"\xff\xd8\xffnot-a-real-image"]
)
def test_valid_signature_is_not_proof_of_a_decodable_photo(media_store, content):
    from sqlalchemy import select

    from newsflow.persistence.models import MediaAssetModel

    session, root, _ = media_store
    key = "bad.png" if content.startswith(b"\x89PNG") else "bad.jpg"
    (root / key).write_bytes(content)
    with pytest.raises(ValueError, match="decode"):
        service(session, root).register_asset(
            key, origin="LICENSED_LIBRARY", license_code="CC0", attribution="", tags=()
        )
    assert session.scalar(select(MediaAssetModel)) is None


def test_animated_png_cannot_masquerade_as_single_source_photo(media_store):
    session, root, _ = media_store
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "red").save(
        buffer,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (4, 4), "blue")],
        duration=100,
        loop=0,
    )
    (root / "animated.png").write_bytes(buffer.getvalue())
    with pytest.raises(ValueError, match="decode"):
        service(session, root).register_asset(
            "animated.png", origin="LICENSED_LIBRARY", license_code="CC0", attribution="", tags=()
        )


def test_local_photo_pixel_bound_is_checked_before_pixel_allocation(media_store):
    import struct
    import zlib

    session, root, _ = media_store
    photo(root, "too-large.png")
    content = bytearray((root / "too-large.png").read_bytes())
    content[16:24] = struct.pack(">II", 5001, 5001)
    content[29:33] = struct.pack(">I", zlib.crc32(content[12:29]))
    (root / "too-large.png").write_bytes(content)
    with pytest.raises(ValueError, match="decode"):
        service(session, root).register_asset(
            "too-large.png", origin="LICENSED_LIBRARY", license_code="CC0", attribution="", tags=()
        )


def test_cached_editorial_row_cannot_hide_an_external_media_revocation(media_store):
    from sqlalchemy import select

    session, root, candidate_id = media_store
    selector = service(session, root)
    old = session.scalar(select(EditorialDecisionModel))
    assert old.rewrite_allowed
    with Session(session.get_bind()) as other:
        row = other.get(EditorialDecisionModel, old.id)
        row.status, row.rewrite_allowed = "REJECT", False
        other.commit()
    with pytest.raises(PermissionError, match="EDITORIAL"):
        selector.select_for_candidate(candidate_id, query="")


def test_media_selection_requires_latest_source_and_current_review(media_store):
    from sqlalchemy import select

    from newsflow.persistence.models import RewriteOutputModel

    session, root, candidate_id = media_store
    selector = service(session, root)
    output = session.scalar(select(RewriteOutputModel))
    with Session(session.get_bind()) as other:
        other.get(RewriteOutputModel, output.id).approval_state = "PENDING"
        other.commit()
    with pytest.raises(PermissionError, match="APPROVAL"):
        selector.select_for_candidate(candidate_id, query="")
    with Session(session.get_bind()) as other:
        other.get(RewriteOutputModel, output.id).approval_state = "APPROVED"
        other.add(
            ContentRevisionModel(
                incoming_post_id=1,
                revision_number=2,
                source_text="Changed source photo",
                media_type="photo",
            )
        )
        other.commit()
    with pytest.raises(PermissionError, match="SOURCE"):
        selector.select_for_candidate(candidate_id, query="")


@pytest.mark.parametrize("change", ["editorial", "source", "review", "policy"])
def test_media_binding_is_rechecked_after_decoding(media_store, monkeypatch, change):
    from sqlalchemy import select

    from newsflow.persistence.models import RewriteOutputModel

    session, root, candidate_id = media_store
    photo(root, "source.png")
    selector = service(session, root)
    selector.register_asset(
        "source.png",
        origin="SOURCE",
        license_code="OWNED",
        attribution="",
        tags=(),
        source_content_key=KEY,
    )
    original = selector._read_photo

    def revoke_while_decoding(storage_key):
        result = original(storage_key)
        with Session(session.get_bind()) as other:
            if change == "editorial":
                decision = other.scalar(select(EditorialDecisionModel))
                decision.status, decision.rewrite_allowed = "REJECT", False
            elif change == "source":
                other.add(
                    ContentRevisionModel(
                        incoming_post_id=1, revision_number=2, source_text="Edited source"
                    )
                )
            elif change == "review":
                other.scalar(select(RewriteOutputModel)).approval_state = "PENDING"
            else:
                other.get(PublicationCandidateModel, candidate_id).media_policy = "LICENSED_LIBRARY"
            other.commit()
        return result

    monkeypatch.setattr(selector, "_read_photo", revoke_while_decoding)
    with pytest.raises(PermissionError):
        selector.select_for_candidate(candidate_id, query="")


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
        source_content_key=KEY,
    )
    selector.register_asset(
        "other.png",
        origin="SOURCE",
        license_code="PERMISSION",
        attribution="@other",
        tags=("космос",),
        source_content_key="source:@donor:1:revision:2",
    )
    selected = selector.select_for_candidate(candidate_id, query="Космос")
    assert selected["status"] == "SELECTED"
    assert [asset["storage_key"] for asset in selected["items"]] == ["source.png"]
    assert selected["items"][0]["license_code"] == "PERMISSION"
    with Image.open(root / "source.png") as source:
        assert source.size == (4, 4) and source.getpixel((0, 0)) == (0, 0, 128)


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
            source_content_key=KEY if origin == "SOURCE" else None,
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
        source_content_key=KEY,
    )
    photo(root, "source.png", "red")
    with pytest.raises(ValueError, match="integrity"):
        selector.select_for_candidate(candidate_id, query="")
    (root / "source.png").unlink()
    with pytest.raises(ValueError, match="unavailable"):
        selector.select_for_candidate(candidate_id, query="")


def test_later_editorial_reject_blocks_media_selection_and_creates_no_new_jobs(media_store):
    session, root, candidate_id = media_store
    from sqlalchemy import func, select

    from newsflow.persistence.models import EditorialDecisionModel, RewriteJobModel

    # This fixture has a legitimate prior succeeded rewrite. Revocation must
    # block new work without erasing the historical job.
    prior_jobs = session.scalar(select(func.count()).select_from(RewriteJobModel))
    decision = session.scalar(select(EditorialDecisionModel))
    decision.status, decision.rewrite_allowed = "REJECT", False
    session.commit()
    with pytest.raises(PermissionError, match="EDITORIAL"):
        service(session, root).select_for_candidate(candidate_id, query="")
    assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == prior_jobs


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
