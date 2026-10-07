from pathlib import Path

import pytest
from sqlalchemy import select
from test_commons_images import metadata, png, provider

from newsflow.persistence.models import (
    EditorialDecisionModel,
    MediaAssetModel,
    PublicationCandidateModel,
)
from newsflow.services.rewrite_outputs import RewriteOutputService


class Images:
    def __init__(self, *, change=None):
        actual, _ = provider([metadata()])
        self.result = actual.search("factory")[0]
        self.calls, self.change = [], change

    def search(self, text, *, limit=5):
        self.calls.append("search")
        return [self.result]

    def download(self, result):
        self.calls.append("download")
        if self.change:
            self.change()
        return png()


def setup(factory):
    with factory() as session:
        RewriteOutputService(session).approve(1, activate_candidate=True)
        session.get(PublicationCandidateModel, 1).media_policy = "LICENSED_LIBRARY"
        session.commit()


def acquisition(factory, root, images):
    from newsflow.services.internet_media import InternetMediaAcquisition

    return InternetMediaAcquisition(factory, root, provider=images)


def test_internet_acquisition_persists_licensed_bytes_and_provenance(semantic_store, tmp_path):
    setup(semantic_store)
    images = Images()
    operation = acquisition(semantic_store, tmp_path, images)
    first = operation.acquire(1)
    second = operation.acquire(1)
    assert first["items"][0]["id"] == second["items"][0]["id"]
    asset = first["items"][0]
    assert asset["license_code"] == "CC-BY" and "commons.wikimedia.org" in asset["attribution"]
    assert (tmp_path / asset["storage_key"]).read_bytes() == png()
    with semantic_store() as session:
        assert len(session.scalars(select(MediaAssetModel)).all()) == 1


def test_rejected_candidate_or_source_reuse_never_searches_internet(semantic_store, tmp_path):
    images = Images()
    operation = acquisition(semantic_store, tmp_path, images)
    with pytest.raises(PermissionError):
        operation.acquire(1)
    setup(semantic_store)
    with semantic_store() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    with pytest.raises(PermissionError):
        operation.acquire(1)
    assert images.calls == []


def test_editorial_change_during_download_cannot_register_or_select_photo(semantic_store, tmp_path):
    setup(semantic_store)

    def reject():
        with semantic_store() as session:
            decision = session.scalar(select(EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
            session.commit()

    images = Images(change=reject)
    with pytest.raises(PermissionError):
        acquisition(semantic_store, tmp_path, images).acquire(1)
    with semantic_store() as session:
        assert session.scalar(select(MediaAssetModel)) is None
    assert list(tmp_path.glob("internet/*")) == []


def test_untrusted_provider_filename_never_controls_storage_path(semantic_store, tmp_path):
    setup(semantic_store)
    images = Images()
    assert Path(
        acquisition(semantic_store, tmp_path, images).acquire(1)["items"][0]["storage_key"]
    ).name.endswith(".png")
    assert not list(tmp_path.glob("internet/*.tmp"))


def test_existing_damaged_asset_is_not_overwritten(semantic_store, tmp_path):
    from newsflow.services.media_selection import MediaUnavailable

    setup(semantic_store)
    operation = acquisition(semantic_store, tmp_path, Images())
    asset = operation.acquire(1)["items"][0]
    path = tmp_path / asset["storage_key"]
    path.write_bytes(b"existing-asset-must-not-be-overwritten")
    with pytest.raises(MediaUnavailable):
        operation.acquire(1)
    assert path.read_bytes() == b"existing-asset-must-not-be-overwritten"


def test_source_edit_during_download_cannot_register_photo(semantic_store, tmp_path):
    from newsflow.persistence.models import ContentRevisionModel

    setup(semantic_store)

    def edit():
        with semantic_store() as session:
            session.add(
                ContentRevisionModel(incoming_post_id=1, revision_number=2, source_text="Edited")
            )
            session.commit()

    with pytest.raises(PermissionError):
        acquisition(semantic_store, tmp_path, Images(change=edit)).acquire(1)
    with semantic_store() as session:
        assert session.scalar(select(MediaAssetModel)) is None
