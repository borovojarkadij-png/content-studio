"""Protected diagnostic policy HTTP boundary on isolated migrated storage."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_editorial_admission as admission_tests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from test_durable_editorial_runner import make_runner
from test_editorial_admission import KEY, MESSAGE, NOW, count, ingest

from newsflow.app import app
from newsflow.persistence import models
from newsflow.providers.editorial_classifier import (
    FreeOpenRouterEditorialClassifier,
    OpenAIEditorialClassifier,
)
from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.editorial_admission import (
    EditorialAdmissionBlocked,
    resolve_editorial_admission,
)
from newsflow.services.editorial_classifier_factory import ConfiguredEditorialClassifierFactory

URL = "/api/settings/editorial-policy"
TOKEN = "synthetic-operator-only-token-000001"
REVIEW_TOKEN = "synthetic-reviewer-only-token-00001"
store = admission_tests.store
AUTH_ENV = (
    "NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE",
    "NEWSFLOW_EDITORIAL_OPERATOR_ID",
    "NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE",
    "NEWSFLOW_ILLUSTRATION_REVIEWER_ID",
    "NEWSFLOW_MASTER_KEY_FILE",
)


@pytest.fixture(autouse=True)
def isolated_auth(monkeypatch):
    for name in AUTH_ENV:
        monkeypatch.delenv(name, raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Policy boundary constructed a provider, decrypted or rewrote")

    for cls in (OpenAIEditorialClassifier, FreeOpenRouterEditorialClassifier):
        monkeypatch.setattr(cls, "__init__", forbidden)
    for cls in (OpenAIRewriteProvider, StructuredFreeOpenRouterProvider):
        monkeypatch.setattr(cls, "rewrite", forbidden)
    monkeypatch.setattr(SessionCipher, "decrypt", forbidden)


@pytest.fixture
def operator(tmp_path, monkeypatch):
    secret = tmp_path / "synthetic-operator-secret"
    secret.write_bytes(TOKEN.encode("ascii"))
    reviewer = tmp_path / "synthetic-reviewer-secret"
    reviewer.write_bytes(REVIEW_TOKEN.encode("ascii"))
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE", str(secret))
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_OPERATOR_ID", "29")
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE", str(reviewer))
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEWER_ID", "17")
    return secret, reviewer


@pytest.fixture
def policy_api(store, operator, monkeypatch):
    engine, _ = store
    monkeypatch.setattr(
        "newsflow.persistence.database.configured_session_factory", lambda: sessionmaker(engine)
    )
    with TestClient(app, headers={"Authorization": "Bearer " + TOKEN}) as client:
        yield client, engine


def payload(current, **changes):
    return {
        "enabled": False,
        "provider": "OPENAI",
        "model": "synthetic-model",
        "protected_entities": [],
        "expected_etag": current["etag"],
        **changes,
    }


def checked(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    if status >= 400:
        assert set(response.json()) == {"detail"}
        assert type(response.json()["detail"]) is str
        assert not any(value in response.text for value in (TOKEN, REVIEW_TOKEN, "PRIVATE"))
    return response.json()


def policy_events(engine):
    with Session(engine) as session:
        return session.scalars(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.event_type == "EditorialPolicyConfigured"
            )
        ).all()


def test_unprovisioned_policy_route_fails_closed_before_storage(monkeypatch):
    from newsflow.persistence import database

    def forbidden():
        pytest.fail("Unauthenticated policy request obtained storage")

    monkeypatch.setattr(database, "configured_session_factory", forbidden)
    response = TestClient(app).get(URL)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Bearer wrong",
        "bearer " + TOKEN,
        "Bearer  " + TOKEN,
        "Bearer " + TOKEN + " ",
        "Basic " + TOKEN,
        "Bearer " + REVIEW_TOKEN,
    ],
)
@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_unauthorized_requests_never_obtain_storage(operator, monkeypatch, header, method):
    def forbidden():
        pytest.fail("Unauthenticated policy request obtained storage")

    monkeypatch.setattr("newsflow.persistence.database.configured_session_factory", forbidden)
    headers = {} if header is None else {"Authorization": header}
    response = TestClient(app, cookies={"token": TOKEN}).request(
        method, URL + "?token=" + TOKEN, headers=headers, json={}
    )
    checked(response, 401)
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "identity", ["", "0", "01", "-1", "+1", " 1", "1 ", "1.0", "True", "١", str(2**63)]
)
def test_malformed_identity_is_unavailable_before_storage(operator, monkeypatch, identity):
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_OPERATOR_ID", identity)
    monkeypatch.setattr(
        "newsflow.persistence.database.configured_session_factory",
        lambda: pytest.fail("Invalid identity obtained storage"),
    )
    checked(TestClient(app).get(URL, headers={"Authorization": "Bearer " + TOKEN}), 503)


@pytest.mark.parametrize("identity", ["1", str(2**63 - 1)])
def test_positive_signed_64_bit_operator_identity(operator, monkeypatch, identity):
    from newsflow.security.editorial_operator import authenticate_editorial_operator

    monkeypatch.setenv("NEWSFLOW_EDITORIAL_OPERATOR_ID", identity)
    principal = authenticate_editorial_operator("Bearer " + TOKEN)
    assert principal.actor_id == int(identity)


@pytest.mark.parametrize(
    "kind",
    ["missing", "empty", "short", "oversized", "crlf", "nonascii", "directory", "nul", "loop"],
)
def test_invalid_secret_path_and_contents_fail_privately(operator, monkeypatch, kind):
    secret, _ = operator
    configured = str(secret)
    if kind == "missing":
        configured = str(secret.parent / "PRIVATE-missing")
    elif kind == "directory":
        configured = str(secret.parent)
    elif kind == "nul":
        from newsflow.security.bounded_bearer import BearerFileUnavailable, read_bearer_file

        with pytest.raises(BearerFileUnavailable, match="^Bearer file unavailable$"):
            read_bearer_file("PRIVATE\x00path")
        return
    elif kind == "loop":

        def loop(*args, **kwargs):
            raise RuntimeError("PRIVATE symlink loop")

        monkeypatch.setattr(Path, "resolve", loop)
    else:
        secret.write_bytes(
            {
                "empty": b"",
                "short": b"a" * 31,
                "oversized": b"a" * 131,
                "crlf": TOKEN.encode() + b"\r\n",
                "nonascii": b"\xff" * 32,
            }[kind]
        )
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE", configured)
    checked(TestClient(app).get(URL, headers={"Authorization": "Bearer " + TOKEN}), 503)


@pytest.mark.parametrize("excluded", ["master", "reviewer"])
@pytest.mark.parametrize("alias", ["same", "resolved", "hardlink"])
def test_operator_cannot_reuse_master_or_reviewer_file(operator, monkeypatch, excluded, alias):
    secret, _ = operator
    path = secret
    if alias == "resolved":
        path = secret.parent / ".." / secret.parent.name / secret.name
    elif alias == "hardlink":
        path = secret.parent / "synthetic-hardlink"
        path.hardlink_to(secret)
    setting = (
        "NEWSFLOW_MASTER_KEY_FILE"
        if excluded == "master"
        else "NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE"
    )
    monkeypatch.setenv(setting, " \t" + str(path) + " \r\n" if excluded == "master" else str(path))
    checked(TestClient(app).get(URL, headers={"Authorization": "Bearer " + TOKEN}), 503)


def test_reviewer_and_operator_authorities_are_separate_and_rotation_is_reopened(
    operator, monkeypatch
):
    from newsflow.security.editorial_operator import (
        EditorialOperatorUnauthorized,
        authenticate_editorial_operator,
    )
    from newsflow.security.illustration_reviewer import ReviewerUnauthorized, authenticate_reviewer

    assert authenticate_editorial_operator("Bearer " + TOKEN).actor_id == 29
    assert authenticate_reviewer("Bearer " + REVIEW_TOKEN).reviewer_id == 17
    with pytest.raises(ReviewerUnauthorized):
        authenticate_reviewer("Bearer " + TOKEN)
    with pytest.raises(EditorialOperatorUnauthorized):
        authenticate_editorial_operator("Bearer " + REVIEW_TOKEN)
    operator[0].write_bytes(b"synthetic-operator-rotated-token-002\n")
    with pytest.raises(EditorialOperatorUnauthorized):
        authenticate_editorial_operator("Bearer " + TOKEN)
    assert (
        authenticate_editorial_operator("Bearer synthetic-operator-rotated-token-002").actor_id
        == 29
    )
    # Separate files permit equal bytes; authentication cannot infer byte independence.
    operator[0].write_bytes(REVIEW_TOKEN.encode())
    assert authenticate_editorial_operator("Bearer " + REVIEW_TOKEN).actor_id == 29


def test_bounded_file_reader_refuses_unreadable_reparse_and_opened_inode_change(
    operator, monkeypatch
):
    from newsflow.security import bounded_bearer

    secret, _ = operator
    original_lstat = Path.lstat
    actual = original_lstat(secret)
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda self: SimpleNamespace(
            st_mode=actual.st_mode,
            st_size=actual.st_size,
            st_file_attributes=0x400,
        ),
    )
    with pytest.raises(bounded_bearer.BearerFileUnavailable):
        bounded_bearer.read_bearer_file(secret)
    monkeypatch.setattr(Path, "lstat", original_lstat)
    original_fstat = bounded_bearer.os.fstat
    monkeypatch.setattr(
        bounded_bearer.os,
        "fstat",
        lambda fd: SimpleNamespace(
            st_mode=actual.st_mode,
            st_dev=actual.st_dev,
            st_ino=actual.st_ino + 1,
        ),
    )
    with pytest.raises(bounded_bearer.BearerFileUnavailable):
        bounded_bearer.read_bearer_file(secret)
    monkeypatch.setattr(bounded_bearer.os, "fstat", original_fstat)

    def unreadable(*args):
        raise PermissionError("PRIVATE unreadable path")

    monkeypatch.setattr(bounded_bearer.os, "open", unreadable)
    with pytest.raises(bounded_bearer.BearerFileUnavailable, match="^Bearer file unavailable$"):
        bounded_bearer.read_bearer_file(secret)


def test_shared_reader_limits_read_and_accepts_only_bounded_ascii_optional_lf(
    operator, monkeypatch
):
    from newsflow.security import bounded_bearer

    secret, _ = operator
    original_fdopen = bounded_bearer.os.fdopen
    sizes = []

    class BoundedStream:
        def __init__(self, fd, mode):
            self.stream = original_fdopen(fd, mode)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            sizes.append(size)
            return self.stream.read(size)

    monkeypatch.setattr(bounded_bearer.os, "fdopen", BoundedStream)
    for length in (32, 128):
        secret.write_bytes(b"a" * length + b"\n")
        assert bounded_bearer.read_bearer_file(secret) == b"a" * length
    assert sizes == [131, 131]


def test_symlink_secret_is_unavailable(operator, monkeypatch):
    secret, _ = operator
    link = secret.parent / "synthetic-symlink"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("Host does not permit synthetic symlinks")
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE", str(link))
    checked(TestClient(app).get(URL, headers={"Authorization": "Bearer " + TOKEN}), 503)


def test_get_legacy_update_noop_stale_and_reopened_metadata_audit(policy_api):
    client, engine = policy_api
    before = checked(client.get(URL), 200)
    assert before["configured"] is True and before["policy_version"] == "synthetic-v1"
    assert before["diagnostic_only"] is True
    assert all(
        before[name] is False
        for name in ("real_model_qualified", "execution_authorized", "rewrite_allowed")
    )
    assert set(before) == {
        "configured",
        "enabled",
        "provider",
        "model",
        "policy_version",
        "protected_entities",
        "etag",
        "diagnostic_only",
        "real_model_qualified",
        "execution_authorized",
        "rewrite_allowed",
    }
    entities = [
        {"entity_id": "z", "aliases": ["Zulu", "Zebra"]},
        {"entity_id": "a", "aliases": ["Alpha"]},
    ]
    body = payload(before, protected_entities=entities)
    after = checked(client.put(URL, json=body), 200)
    assert after["protected_entities"] == [
        {"entity_id": "a", "aliases": ["Alpha"]},
        {"entity_id": "z", "aliases": ["Zebra", "Zulu"]},
    ]
    checked(client.put(URL, json=body), 409)
    checked(client.put(URL, json=payload(after, expected_etag=None)), 409)
    assert checked(client.put(URL, json=payload(after, protected_entities=entities)), 200) == after
    reopened = create_engine(engine.url)
    try:
        with Session(reopened) as session:
            row = session.get(models.EditorialClassifierPolicyModel, 1)
            assert row.model == "synthetic-model" and row.enabled is False
            assert row.protected_entities == after["protected_entities"]
            for model in (
                models.EditorialDecisionModel,
                models.RewriteJobModel,
                models.EditorialClassificationJobModel,
                models.EditorialClassificationClaimModel,
                models.EditorialClassificationAttemptModel,
            ):
                assert count(session, model) == 0
    finally:
        reopened.dispose()
    records = policy_events(engine)
    assert len(records) == 1
    assert records[0].aggregate_key == f"editorial-policy:29:{before['etag']}:{after['etag']}"
    assert not any(
        value in records[0].aggregate_key + records[0].idempotency_key
        for value in (TOKEN, "Zulu", "synthetic-model")
    )


@pytest.mark.parametrize(
    "provider,model", [("OPENAI", "synthetic-model"), ("OPENROUTER", "synthetic/model:free")]
)
def test_missing_policy_read_create_and_update_are_persistent(policy_api, provider, model):
    client, engine = policy_api
    with Session(engine) as session:
        session.delete(session.get(models.EditorialClassifierPolicyModel, 1))
        session.commit()
    missing = checked(client.get(URL), 200)
    assert missing == {
        "configured": False,
        "enabled": False,
        "provider": None,
        "model": None,
        "policy_version": None,
        "protected_entities": [],
        "etag": None,
        "diagnostic_only": True,
        "real_model_qualified": False,
        "execution_authorized": False,
        "rewrite_allowed": False,
    }
    checked(client.put(URL, json=payload(missing, expected_etag="0" * 64)), 409)
    created = checked(client.put(URL, json=payload(missing, provider=provider, model=model)), 200)
    assert (created["provider"], created["model"]) == (provider, model)
    assert checked(client.get(URL), 200) == created
    assert len(policy_events(engine)) == 1


INVALID = [
    {"enabled": 1},
    {"enabled": "false"},
    {"provider": True},
    {"provider": "openai"},
    {"provider": " OPENAI"},
    {"model": 1},
    {"model": " model "},
    {"model": ""},
    {"provider": "OPENROUTER", "model": "paid/model"},
    {"expected_etag": False},
    {"expected_etag": "PRIVATE"},
    {"protected_entities": {}},
    {"protected_entities": ["PRIVATE"]},
    {"protected_entities": [{"entity_id": 1, "aliases": ["PRIVATE"]}]},
    {"protected_entities": [{"entity_id": "PRIVATE", "aliases": "PRIVATE"}]},
    {"protected_entities": [{"entity_id": "PRIVATE", "aliases": [True]}]},
    {"protected_entities": [{"entity_id": "PRIVATE", "aliases": []}]},
    {"protected_entities": [{"entity_id": "PRIVATE", "aliases": [" "]}]},
    {"protected_entities": [{"entity_id": "PRIVATE", "aliases": ["a"], "actor_id": 1}]},
    {
        "protected_entities": [
            {"entity_id": "a", "aliases": ["same"]},
            {"entity_id": "b", "aliases": ["SAME"]},
        ]
    },
    {"actor_id": 1},
    {"policy_version": "PRIVATE"},
    {"rewrite_allowed": True},
    {"execution_authorized": True},
    {"diagnostic_only": False},
    {"unknown": "PRIVATE"},
    {"protected_entities": [{"entity_id": str(i), "aliases": [str(i)]} for i in range(65)]},
    {"protected_entities": [{"entity_id": "PRIVATE", "aliases": ["x" * 256]}]},
    {"protected_entities": [{"entity_id": "PRIVATE", "aliases": [str(i) for i in range(17)]}]},
]


@pytest.mark.parametrize("changes", INVALID)
def test_strict_complete_invalid_input_is_private_and_cannot_write(policy_api, changes):
    client, engine = policy_api
    before = checked(client.get(URL), 200)
    checked(client.put(URL, json=payload(before, **changes)), 422)
    assert checked(client.get(URL), 200) == before
    assert policy_events(engine) == []


@pytest.mark.parametrize(
    "field", ["enabled", "provider", "model", "protected_entities", "expected_etag"]
)
def test_every_put_field_is_required(policy_api, field):
    client, _ = policy_api
    body = payload(checked(client.get(URL), 200))
    del body[field]
    checked(client.put(URL, json=body), 422)


def test_malformed_json_uses_static_validation_response(policy_api):
    client, _ = policy_api
    checked(
        client.put(URL, content='{"model":"PRIVATE', headers={"Content-Type": "application/json"}),
        422,
    )


def test_policy_byte_limit_is_validated_by_existing_service(policy_api):
    client, engine = policy_api
    entities = [
        {
            "entity_id": str(i) + "e" * 125,
            "aliases": [f"{i:02}-{j:02}" + "a" * 250 for j in range(16)],
        }
        for i in range(64)
    ]
    assert len(json.dumps(entities, ensure_ascii=False, separators=(",", ":")).encode()) > 262144
    before = checked(client.get(URL), 200)
    checked(client.put(URL, json=payload(before, protected_entities=entities)), 422)
    assert checked(client.get(URL), 200) == before
    assert policy_events(engine) == []


def test_malformed_stored_json_is_private_validation_failure(policy_api):
    client, engine = policy_api
    if engine.dialect.name != "sqlite":
        pytest.skip("PostgreSQL JSON storage rejects malformed JSON before persistence")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE editorial_classifier_policy SET protected_entities=:value"),
            {"value": "PRIVATE invalid JSON"},
        )
    checked(client.get(URL), 422)
    checked(client.put(URL, json=payload({"etag": None})), 422)
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT protected_entities FROM editorial_classifier_policy"))
            == "PRIVATE invalid JSON"
        )
    assert policy_events(engine) == []


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_corrupt_persisted_policy_is_not_defaulted_or_overwritten(policy_api, method):
    client, engine = policy_api
    before = checked(client.get(URL), 200)
    with Session(engine) as session:
        session.get(models.EditorialClassifierPolicyModel, 1).protected_entities = [
            {"PRIVATE": "PRIVATE"}
        ]
        session.commit()
    checked(client.request(method, URL, json=payload(before)), 422)
    with Session(engine) as session:
        assert session.get(models.EditorialClassifierPolicyModel, 1).protected_entities == [
            {"PRIVATE": "PRIVATE"}
        ]
    assert policy_events(engine) == []


@pytest.mark.parametrize("fault", ["outbox", "commit"])
def test_sql_failure_rolls_back_and_explicit_retry_commits_once(policy_api, fault):
    client, engine = policy_api
    before = checked(client.get(URL), 200)
    body = payload(before)

    def refuse_sql(connection, cursor, statement, parameters, context, many):
        if statement.lower().lstrip().startswith("insert into outbox_events"):
            raise IntegrityError("PRIVATE SQL", {}, RuntimeError("PRIVATE credential"))

    def refuse_commit(session):
        raise IntegrityError("PRIVATE COMMIT", {}, RuntimeError("PRIVATE path"))

    target, name, listener = (
        (Session, "before_commit", refuse_commit)
        if fault == "commit"
        else (engine, "before_cursor_execute", refuse_sql)
    )
    event.listen(target, name, listener)
    try:
        checked(client.put(URL, json=body), 503)
    finally:
        event.remove(target, name, listener)
    assert checked(client.get(URL), 200) == before
    assert policy_events(engine) == []
    after = checked(client.put(URL, json=body), 200)
    assert after["etag"] != before["etag"]
    assert len(policy_events(engine)) == 1


def test_missing_storage_and_unmigrated_storage_are_unavailable(operator, tmp_path, monkeypatch):
    client = TestClient(app, headers={"Authorization": "Bearer " + TOKEN})
    monkeypatch.setattr("newsflow.persistence.database.configured_session_factory", lambda: None)
    checked(client.get(URL), 503)
    checked(client.put(URL, json=payload({"etag": None})), 503)
    engine = create_engine(f"sqlite:///{tmp_path / 'unmigrated.db'}")
    monkeypatch.setattr(
        "newsflow.persistence.database.configured_session_factory", lambda: sessionmaker(engine)
    )
    try:
        checked(client.get(URL), 503)
        checked(client.put(URL, json=payload({"etag": None})), 503)
    finally:
        engine.dispose()


def test_no_store_covers_framework_errors_redirect_and_leaves_unrelated_routes_alone():
    client = TestClient(app, follow_redirects=False)
    for response, status in [(client.post(URL), 405), (client.get(URL + "/"), 307)]:
        assert response.status_code == status
        assert response.headers["cache-control"] == "no-store"
    assert "cache-control" not in client.get("/healthz").headers
    assert "cache-control" not in client.get(URL + "/unrelated").headers


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_unexpected_policy_failure_is_private_no_store_and_rolls_back(policy_api, method):
    client, engine = policy_api
    before = checked(client.get(URL), 200)

    def unexpected(connection, cursor, statement, parameters, context, many):
        sql = statement.lower().lstrip()
        if (
            method == "GET" and sql.startswith("select") and "editorial_classifier_policy" in sql
        ) or (method == "PUT" and sql.startswith("insert into outbox_events")):
            raise RuntimeError("PRIVATE unexpected SQL path " + TOKEN)

    event.listen(engine, "before_cursor_execute", unexpected)
    try:
        with TestClient(
            app, raise_server_exceptions=False, headers={"Authorization": "Bearer " + TOKEN}
        ) as safe_client:
            checked(safe_client.request(method, URL, json=payload(before)), 500)
    finally:
        event.remove(engine, "before_cursor_execute", unexpected)
    assert checked(client.get(URL), 200) == before
    assert policy_events(engine) == []


def test_unrelated_uncaught_error_keeps_existing_framework_behavior(monkeypatch):
    route = next(route for route in app.routes if getattr(route, "path", None) == "/healthz")

    def unexpected():
        raise RuntimeError("PRIVATE unrelated failure")

    monkeypatch.setattr(route.dependant, "call", unexpected)
    response = TestClient(app, raise_server_exceptions=False).get("/healthz")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "cache-control" not in response.headers


@pytest.mark.parametrize("change", ["disable", "model", "entities"])
def test_http_configuration_preserves_reject_and_blocks_stale_diagnostics(
    policy_api, store, change
):
    client, engine = policy_api
    ingest(store)
    ingest(
        store,
        replace(MESSAGE, message_id=8, text="Synthetic protected bad report"),
        protected_entities=["synthetic"],
        sentiment="negative",
        framing="hostile",
    )
    with Session(engine) as session:
        binding = resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        before = [
            (row.content_key, row.status, row.rewrite_allowed)
            for row in session.scalars(select(models.EditorialDecisionModel))
        ]
        assert any(status == "REJECT" for _, status, _ in before)
        jobs = count(session, models.EditorialClassificationJobModel)
    changes = (
        {"enabled": False}
        if change == "disable"
        else {"enabled": True, "model": "changed-model"}
        if change == "model"
        else {"enabled": True, "protected_entities": []}
    )
    current = checked(client.get(URL), 200)
    body = payload(
        current, model=current["model"], protected_entities=current["protected_entities"]
    )
    body.update(changes)
    checked(client.put(URL, json=body), 200)
    factory = sessionmaker(engine)
    with pytest.raises(EditorialAdmissionBlocked):
        ConfiguredEditorialClassifierFactory(factory, cipher=SessionCipher.__new__(SessionCipher))(
            binding
        )
    runner = make_runner(
        engine, factory=lambda binding: pytest.fail("Stale diagnostic reached provider")
    )
    assert runner.run_next(now=NOW) == "BLOCKED"
    with Session(engine) as session:
        assert [
            (row.content_key, row.status, row.rewrite_allowed)
            for row in session.scalars(select(models.EditorialDecisionModel))
        ] == before
        assert count(session, models.EditorialClassificationJobModel) == jobs
        for model in (
            models.RewriteJobModel,
            models.EditorialClassificationClaimModel,
            models.EditorialClassificationAttemptModel,
        ):
            assert count(session, model) == 0
