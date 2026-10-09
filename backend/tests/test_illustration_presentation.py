"""Protected reviewer presentation uses current SQL and exact bounded bytes."""

from hashlib import sha256

import pytest
from test_illustration_binding import DRAFT, SOURCE, UNSAFE, counts, mutate
from test_illustration_review_api import library_store as _library_store
from test_illustration_review_api import mapping_store as _mapping_store
from test_illustration_review_api import payload
from test_illustration_review_api import review_api as _review_api

from newsflow.persistence import models

URL = "/api/illustration-review/candidates/1"
library_store = _library_store
mapping_store = _mapping_store
review_api = _review_api


def test_presentation_and_exact_private_photo(review_api):
    client, factory, _, images, binding, _ = review_api
    before = counts(factory)
    response = client.get(URL + "/presentation")
    assert response.status_code == 200
    value = response.json()
    assert value["binding"] == binding
    assert value["source_text"] == SOURCE and value["draft_text"] == DRAFT
    assert value["channel"]["id"] == 1
    assert value["license_code"] in {"CC0", "CC-BY"}
    assert value["latest_review"] is None
    assert "storage_key" not in response.text
    etag = response.headers["ETag"]
    assert etag.startswith('"') and len(etag) == 66
    photo = client.get(URL + "/photo", headers={"If-Match": etag})
    assert photo.status_code == 200
    assert photo.headers["ETag"] == etag
    assert photo.headers["Cache-Control"] == "no-store"
    assert photo.headers["Content-Type"] == value["mime_type"]
    assert sha256(photo.content).hexdigest() == binding["media_sha256"]
    assert counts(factory) == before and images.calls == ["search", "download"]


@pytest.mark.parametrize("suffix", ["/presentation", "/photo", "/latest-review"])
@pytest.mark.parametrize("auth", [None, "Bearer wrong"])
def test_presentation_reads_require_reviewer(review_api, suffix, auth):
    client, *_ = review_api
    client.headers.pop("Authorization")
    assert (
        client.get(
            URL + suffix, headers={} if auth is None else {"Authorization": auth}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("validator", [None, "*", 'W/"abc"', '"' + "0" * 64 + '"'])
def test_photo_requires_exact_strong_validator(review_api, validator):
    client, *_ = review_api
    assert (
        client.get(
            URL + "/photo", headers={} if validator is None else {"If-Match": validator}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("scenario", UNSAFE)
def test_current_presentation_and_preview_refuse_mutated_gates(review_api, scenario):
    client, factory, _, _, _, _ = review_api
    etag = client.get(URL + "/presentation").headers.get("ETag", '"absent"')
    with factory.begin() as session:
        mutate(session, scenario)
    assert client.get(URL + "/presentation").status_code == 409
    assert client.get(URL + "/photo", headers={"If-Match": etag}).status_code == 409


@pytest.mark.parametrize("damage", ["credit", "file", "channel", "review"])
def test_photo_refuses_stale_display_validator(review_api, damage):
    client, factory, root, _, binding, _ = review_api
    etag = client.get(URL + "/presentation").headers.get("ETag", '"absent"')
    if damage == "review":
        assert client.post(URL + "/reviews", json=payload(binding)).status_code == 200
        assert client.get(URL + "/photo", headers={"If-Match": etag}).status_code == 409
        return
    with factory.begin() as session:
        asset = session.get(models.MediaAssetModel, 1)
        if damage == "credit":
            asset.attribution += " changed credit"
        elif damage == "channel":
            session.get(models.OutputChannel, 1).title += " changed title"
        else:
            (root / asset.storage_key).write_bytes(b"damaged synthetic photo")
    assert client.get(URL + "/photo", headers={"If-Match": etag}).status_code == 409


def test_latest_review_remains_readable_and_revocable_after_editorial_reject(review_api):
    client, factory, _, _, binding, _ = review_api
    original = client.post(URL + "/reviews", json=payload(binding)).json()
    with factory.begin() as session:
        mutate(session, "reject")
    assert client.get(URL + "/presentation").status_code == 409
    assert client.get(URL + "/latest-review").json() == {"latest_review": original}
    revoked = client.post(
        f"/api/illustration-review/records/{original['id']}/revocations",
        json={"operation_key": "presentation-revoke", "review_note": "withdraw"},
    )
    assert revoked.status_code == 200
    latest = client.get(URL + "/latest-review").json()["latest_review"]
    assert latest["id"] == original["id"] and latest["revoked"] is True


@pytest.mark.parametrize("damage", ["file", "source", "credit"])
def test_mutation_during_private_byte_read_refuses_response(review_api, monkeypatch, damage):
    from newsflow.services.media_selection import LocalMediaSelectionService

    client, factory, root, _, _, _ = review_api
    etag = client.get(URL + "/presentation").headers["ETag"]
    original = LocalMediaSelectionService._photo_content
    reads = 0

    def change(self, key):
        nonlocal reads
        result = original(self, key)
        reads += 1
        # _current resolve twice reads four times; mutate the exact response-byte read.
        if reads == 5:
            if damage == "file":
                (root / key).write_bytes(b"synthetic concurrent replacement")
            else:
                with factory.begin() as session:
                    if damage == "source":
                        mutate(session, "reject")
                    else:
                        session.get(models.MediaAssetModel, 1).attribution += " changed"
        return result

    monkeypatch.setattr(LocalMediaSelectionService, "_photo_content", change)
    assert client.get(URL + "/photo", headers={"If-Match": etag}).status_code == 409


def test_latest_read_does_not_require_media_root_but_still_requires_auth(review_api, monkeypatch):
    client, _, _, _, binding, _ = review_api
    original = client.post(URL + "/reviews", json=payload(binding)).json()
    monkeypatch.delenv("NEWSFLOW_MEDIA_ROOT")
    assert client.get(URL + "/latest-review").json()["latest_review"] == original
    assert client.get(URL + "/presentation").status_code == 503
    assert client.get(URL + "/photo", headers={"If-Match": '"' + "a" * 64 + '"'}).status_code == 503
