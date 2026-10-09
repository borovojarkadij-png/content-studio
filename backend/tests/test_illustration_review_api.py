"""Authenticated review writes against real migrated SQL and synthetic media."""

from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from test_illustration_binding import (
    UNSAFE,
    counts,
    mutate,
    resolver,
)
from test_illustration_binding import (
    library_store as _library_store,
)
from test_illustration_binding import (
    mapping_store as _mapping_store,
)

from newsflow.app import app
from newsflow.persistence import models

library_store = _library_store
mapping_store = _mapping_store
TOKEN = "synthetic-test-only-review-token-0001"
URL = "/api/illustration-review/candidates/1"


@pytest.fixture
def review_api(library_store, tmp_path, monkeypatch):
    factory, root, images = library_store
    secret = tmp_path / "synthetic-review-secret"
    secret.write_text(TOKEN, encoding="ascii")
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE", str(secret))
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEWER_ID", "17")
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(root))
    monkeypatch.setattr("newsflow.persistence.database.configured_session_factory", lambda: factory)
    with factory() as session:
        binding = asdict(resolver(session, root).resolve(1))
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        yield client, factory, root, images, binding, secret


def payload(binding, **changes):
    return {
        "displayed_binding": binding,
        "operation_key": "synthetic-review-1",
        "verdict": "APPROVED_ILLUSTRATION",
        "illustration_acknowledged": True,
        "review_note": "Illustration; no event-photo claim",
        **changes,
    }


def total(factory, model):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_authenticated_context_review_replay_and_atomic_audit_persist(review_api):
    client, factory, _, images, binding, _ = review_api
    before = counts(factory)
    context = client.get(URL)
    assert context.status_code == 200
    assert context.json()["binding"] == binding
    assert context.headers["Cache-Control"] == "no-store"
    created = client.post(URL + "/reviews", json=payload(binding))
    assert created.status_code == 200
    result = created.json()
    assert result["reviewer_id"] == 17
    assert result["provenance"] == "AUTHENTICATED_HUMAN_V1"
    assert result["revoked"] is False
    assert client.post(URL + "/reviews", json=payload(binding)).json() == result
    with factory() as reopened:
        record = reopened.get(models.IllustrationReviewRecordModel, result["id"])
        assert record.review_note == "Illustration; no event-photo claim"
        audit = reopened.scalar(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.event_type == "IllustrationReviewRecorded"
            )
        )
        assert audit.aggregate_key == f"illustration-review:{record.id}"
        assert TOKEN not in audit.idempotency_key
    after = counts(factory)
    assert after[:4] == before[:4] and after[5:] == before[5:]
    assert after[4] == before[4] + 1
    assert images.calls == ["search", "download"]


@pytest.mark.parametrize(
    "authorization", [None, "Bearer wrong", "Basic xxx", "Bearer " + "x" * 300]
)
def test_missing_wrong_malformed_credentials_fail_closed(review_api, authorization):
    client, factory, _, _, binding, _ = review_api
    client.headers.pop("Authorization")
    headers = {} if authorization is None else {"Authorization": authorization}
    assert client.get(URL, headers=headers).status_code == 401
    assert client.post(URL + "/reviews", json=payload(binding), headers=headers).status_code == 401
    assert total(factory, models.IllustrationReviewRecordModel) == 0


@pytest.mark.parametrize(
    "damage", ["missing_config", "identity", "missing_file", "oversized", "directory", "malformed"]
)
def test_invalid_server_credentials_fail_closed_without_path_leak(review_api, monkeypatch, damage):
    client, _, _, _, _, secret = review_api
    if damage == "missing_config":
        monkeypatch.delenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE")
    elif damage == "identity":
        monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEWER_ID", "0")
    elif damage == "missing_file":
        secret.unlink()
    elif damage == "oversized":
        secret.write_bytes(b"x" * 4096)
    elif damage == "directory":
        monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE", str(secret.parent))
    else:
        secret.write_bytes(b"invalid\x00token")
    response = client.get(URL)
    assert response.status_code == 503
    assert str(secret) not in response.text and TOKEN not in response.text


@pytest.mark.parametrize("field", ["reviewer_id", "provenance", "reviewed_at", "revoked_at"])
def test_client_identity_provenance_timestamp_are_refused(review_api, field):
    client, factory, _, _, binding, _ = review_api
    assert (
        client.post(URL + "/reviews", json=payload(binding, **{field: "forged"})).status_code == 422
    )
    assert total(factory, models.IllustrationReviewRecordModel) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"illustration_acknowledged": False},
        {"illustration_acknowledged": 1},
        {"review_note": " "},
        {"review_note": "bad\x00note"},
        {"operation_key": " "},
        {"operation_key": "x" * 129},
        {"verdict": "APPROVED"},
    ],
)
def test_invalid_review_is_refused(review_api, changes):
    client, factory, _, _, binding, _ = review_api
    assert client.post(URL + "/reviews", json=payload(binding, **changes)).status_code == 422
    assert total(factory, models.IllustrationReviewRecordModel) == 0


@pytest.mark.parametrize("scenario", UNSAFE)
def test_canonical_gates_refuse_writes_after_display(review_api, scenario):
    client, factory, _, images, binding, _ = review_api
    with factory.begin() as session:
        mutate(session, scenario)
    before = counts(factory)
    assert client.post(URL + "/reviews", json=payload(binding)).status_code == 409
    assert total(factory, models.IllustrationReviewRecordModel) == 0
    assert counts(factory) == before
    assert images.calls == ["search", "download"]


def test_validation_never_echoes_unexpected_secret_values(review_api):
    client, _, _, _, binding, secret = review_api
    response = client.post(
        URL + "/reviews", json=payload(binding, token=TOKEN, secret_file=str(secret))
    )
    assert response.status_code == 422
    assert TOKEN not in response.text and str(secret) not in response.text


@pytest.mark.parametrize(
    "field",
    [
        "candidate_id",
        "output_channel_id",
        "mapping_id",
        "source_revision_id",
        "rewrite_output_id",
        "media_asset_id",
        "content_key",
        "source_sha256",
        "draft_sha256",
        "media_sha256",
        "asset_metadata_sha256",
    ],
)
def test_every_displayed_binding_field_is_an_assertion_only(review_api, field):
    client, factory, _, _, binding, _ = review_api
    altered = dict(binding)
    altered[field] = (
        binding[field] + 1
        if type(binding[field]) is int
        else "0" * 64
        if field.endswith("sha256")
        else "synthetic:forged"
    )
    assert client.post(URL + "/reviews", json=payload(altered)).status_code == 409
    assert total(factory, models.IllustrationReviewRecordModel) == 0


def test_secret_rotation_and_master_file_reuse_fail_closed(review_api, monkeypatch):
    client, _, _, _, _, secret = review_api
    secret.write_text("synthetic-test-only-rotated-token-0002", encoding="ascii")
    assert client.get(URL).status_code == 401
    client.headers["Authorization"] = "Bearer synthetic-test-only-rotated-token-0002"
    assert client.get(URL).status_code == 200
    monkeypatch.setenv("NEWSFLOW_MASTER_KEY_FILE", str(secret))
    assert client.get(URL).status_code == 503


def test_symlink_secret_is_refused(review_api, monkeypatch):
    client, _, _, _, _, secret = review_api
    link = secret.parent / "synthetic-link"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("Host does not permit synthetic symlinks")
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE", str(link))
    assert client.get(URL).status_code == 503


def test_master_secret_hardlink_is_not_a_separate_reviewer_credential(review_api, monkeypatch):
    client, _, _, _, _, secret = review_api
    master = secret.parent / "synthetic-master-link"
    master.hardlink_to(secret)
    monkeypatch.setenv("NEWSFLOW_MASTER_KEY_FILE", str(master))
    assert client.get(URL).status_code == 503


@pytest.mark.parametrize("verdict", ["REJECTED", "UNCERTAIN"])
def test_negative_verdict_replay_never_becomes_approval(review_api, verdict):
    client, _, _, _, binding, _ = review_api
    body = payload(binding, verdict=verdict, illustration_acknowledged=False)
    original = client.post(URL + "/reviews", json=body)
    assert original.status_code == 200 and original.json()["verdict"] == verdict
    assert client.post(URL + "/reviews", json=body).json() == original.json()
    assert client.post(URL + "/reviews", json=payload(binding)).status_code == 409


def test_principal_conflict_and_record_kind_conflict(review_api, monkeypatch):
    client, _, _, _, binding, _ = review_api
    original = client.post(URL + "/reviews", json=payload(binding)).json()
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEWER_ID", "18")
    assert client.post(URL + "/reviews", json=payload(binding)).status_code == 409
    endpoint = f"/api/illustration-review/records/{original['id']}/revocations"
    assert (
        client.post(
            endpoint, json={"operation_key": "synthetic-review-1", "review_note": "withdraw"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            endpoint, json={"operation_key": "revoke-other-principal", "review_note": "withdraw"}
        ).status_code
        == 200
    )


def test_stale_displayed_metadata_and_bytes_cannot_be_reviewed(review_api):
    client, factory, root, _, binding, _ = review_api
    with factory.begin() as session:
        asset = session.get(models.MediaAssetModel, 1)
        asset.attribution += " synthetic changed credit"
        key = asset.storage_key
    assert client.post(URL + "/reviews", json=payload(binding)).status_code == 409
    (root / key).write_bytes(b"damaged synthetic fixture")
    assert client.post(URL + "/reviews", json=payload(binding)).status_code == 409


def test_conflicting_replay_and_revocation_after_reject_preserve_parent(review_api):
    client, factory, _, _, binding, _ = review_api
    original = client.post(URL + "/reviews", json=payload(binding)).json()
    assert (
        client.post(URL + "/reviews", json=payload(binding, review_note="different")).status_code
        == 409
    )
    with factory.begin() as session:
        mutate(session, "reject")
    revocation = {"operation_key": "synthetic-revoke-1", "review_note": "withdrawn"}
    endpoint = f"/api/illustration-review/records/{original['id']}/revocations"
    revoked = client.post(endpoint, json=revocation)
    assert revoked.status_code == 200
    assert revoked.json()["binding"] == binding
    assert client.post(endpoint, json=revocation).json() == revoked.json()
    replay = client.post(URL + "/reviews", json=payload(binding))
    assert replay.status_code == 200 and replay.json()["revoked"] is True
    assert replay.json()["reviewed_at"] == original["reviewed_at"]
    assert (
        client.post(endpoint, json={**revocation, "operation_key": "another-revoke"}).status_code
        == 409
    )
    assert total(factory, models.IllustrationReviewRecordModel) == 2


def test_audit_failure_rolls_back_review_and_reopens_empty(review_api):
    client, factory, _, _, binding, _ = review_api

    def refuse(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO outbox_events"):
            raise RuntimeError("synthetic audit unavailable")

    event.listen(factory.kw["bind"], "before_cursor_execute", refuse)
    try:
        with pytest.raises(RuntimeError, match="synthetic audit"):
            client.post(URL + "/reviews", json=payload(binding))
    finally:
        event.remove(factory.kw["bind"], "before_cursor_execute", refuse)
    assert total(factory, models.IllustrationReviewRecordModel) == 0


def test_photo_replacement_during_review_insert_rolls_back_both_rows(review_api):
    client, factory, root, _, binding, _ = review_api
    before = counts(factory)
    with factory() as session:
        key = session.get(models.MediaAssetModel, 1).storage_key

    def replace_photo(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO illustration_review_records"):
            (root / key).write_bytes(b"synthetic concurrent replacement")

    event.listen(factory.kw["bind"], "before_cursor_execute", replace_photo)
    try:
        assert client.post(URL + "/reviews", json=payload(binding)).status_code == 409
    finally:
        event.remove(factory.kw["bind"], "before_cursor_execute", replace_photo)
    assert total(factory, models.IllustrationReviewRecordModel) == 0
    assert counts(factory) == before


@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_writer_never_commits_pending_caller_work(library_store, pending):
    from newsflow.security.illustration_reviewer import ReviewerPrincipal
    from newsflow.services.illustration_review import IllustrationReviewWriter

    factory, root, _ = library_store
    with factory() as session:
        binding = resolver(session, root).resolve(1)
        row = session.get(models.PublicationCandidateModel, 1)
        if pending == "new":
            session.add(
                models.OutboxEventModel(
                    event_type="synthetic", aggregate_key="caller", idempotency_key="caller"
                )
            )
        elif pending == "dirty":
            row.priority = 999
        else:
            session.delete(row)
        with pytest.raises(ValueError, match="clean session"):
            IllustrationReviewWriter(session, root).review(
                ReviewerPrincipal(17), **payload(binding)
            )
        assert getattr(session, pending)
    assert total(factory, models.IllustrationReviewRecordModel) == 0
