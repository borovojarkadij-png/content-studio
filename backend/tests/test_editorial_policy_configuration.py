"""Internal policy configuration on migrated synthetic storage; no live providers."""

import json
from dataclasses import replace
from hashlib import sha256
from importlib import import_module
from queue import Queue
from threading import Barrier, Event, Thread

import pytest
import test_editorial_admission as admission_tests
from sqlalchemy import Text, cast, create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from test_durable_editorial_runner import make_runner
from test_editorial_admission import KEY, MESSAGE, NOW, count, ingest

from newsflow.persistence import models
from newsflow.services.editorial_admission import (
    EditorialAdmissionBlocked,
    resolve_editorial_admission,
)
from newsflow.services.editorial_classifier_factory import ConfiguredEditorialClassifierFactory

store = admission_tests.store


def api():
    return import_module("newsflow.services.editorial_policy_configuration")


def read(engine):
    with Session(engine) as session:
        result = api().EditorialPolicyConfigurationService(session).read()
        assert not session.in_transaction()
        return result


def configure(engine, **changes):
    current = read(engine)
    values = {
        "enabled": current["enabled"],
        "provider": current["provider"] or "OPENAI",
        "model": current["model"] or "synthetic-explicit-model",
        "protected_entities": current["protected_entities"],
        "expected_etag": current["etag"],
        "actor_id": 1,
    }
    values.update(changes)
    with Session(engine) as session:
        result = api().EditorialPolicyConfigurationService(session).configure(**values)
        assert not session.in_transaction()
        return result


def missing(engine):
    with Session(engine) as session:
        session.delete(session.get(models.EditorialClassifierPolicyModel, 1))
        session.commit()


def events(engine):
    with Session(engine) as session:
        return session.scalars(
            select(models.OutboxEventModel)
            .where(models.OutboxEventModel.event_type == "EditorialPolicyConfigured")
            .order_by(models.OutboxEventModel.id)
        ).all()


def digest(values):
    return sha256(
        json.dumps(
            values, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def assert_diagnostic(dto):
    assert set(dto) == {
        "configured",
        "enabled",
        "etag",
        "provider",
        "model",
        "policy_version",
        "protected_entities",
        "diagnostic_only",
        "real_model_qualified",
        "execution_authorized",
        "rewrite_allowed",
    }
    assert dto["diagnostic_only"] is True
    for name in ("real_model_qualified", "execution_authorized", "rewrite_allowed"):
        assert dto[name] is False


def test_stale_configuration_cannot_overwrite_migrated_policy(store):
    with Session(store[0]) as session, pytest.raises(api().EditorialPolicyConflict):
        api().EditorialPolicyConfigurationService(session).configure(
            enabled=True,
            provider="OPENAI",
            model="stale-overwrite",
            protected_entities=[],
            expected_etag="0" * 64,
            actor_id=1,
        )
    with Session(store[0]) as session:
        assert (
            session.get(models.EditorialClassifierPolicyModel, 1).model
            == "synthetic-explicit-model"
        )


def test_missing_read_is_pure_and_create_reopens_detached_diagnostic_snapshot(store):
    engine = store[0]
    missing(engine)
    before = read(engine)
    assert before == {
        "configured": False,
        "enabled": False,
        "etag": None,
        "provider": None,
        "model": None,
        "policy_version": None,
        "protected_entities": [],
        "diagnostic_only": True,
        "real_model_qualified": False,
        "execution_authorized": False,
        "rewrite_allowed": False,
    }
    assert events(engine) == []
    entities = [{"entity_id": "Совет", "aliases": ["Ёж", "Еж"]}]
    created = configure(engine, enabled=True, protected_entities=entities, actor_id=2**63 - 1)
    assert_diagnostic(created)
    assert created["policy_version"] == "editorial-policy-v1:" + digest(
        {
            "provider": "OPENAI",
            "model": "synthetic-explicit-model",
            "protected_entities": [{"entity_id": "Совет", "aliases": ["Ёж", "Еж"]}],
        }
    )
    assert created["etag"] == digest(
        {
            name: created[name]
            for name in ("enabled", "provider", "model", "policy_version", "protected_entities")
        }
    )
    reopened = create_engine(engine.url)
    try:
        assert read(reopened) == created
        created["protected_entities"][0]["aliases"].append("mutated response")
        entities[0]["aliases"].append("mutated input")
        assert read(reopened)["protected_entities"] == [
            {"entity_id": "Совет", "aliases": ["Ёж", "Еж"]}
        ]
    finally:
        reopened.dispose()
    with Session(engine) as session:
        for model in (
            models.RewriteJobModel,
            models.EditorialClassificationJobModel,
            models.EditorialClassificationClaimModel,
            models.EditorialClassificationAttemptModel,
            models.EditorialDecisionModel,
        ):
            assert count(session, model) == 0


@pytest.mark.parametrize(
    "provider,model", [("OPENAI", "arbitrary-pinned"), ("OPENROUTER", "synthetic/model:free")]
)
def test_both_accepted_providers_do_not_claim_availability(store, provider, model):
    changed = configure(store[0], provider=provider, model=model)
    assert (changed["provider"], changed["model"]) == (provider, model)
    assert_diagnostic(changed)


def test_legacy_exact_snapshot_noop_sorted_equivalence_and_content_bound_versions(store):
    engine = store[0]
    unsorted = [
        {"entity_id": "z", "aliases": ["Zulu", "Z"]},
        {"entity_id": "a", "aliases": ["Alpha"]},
    ]
    with Session(engine) as session:
        session.get(models.EditorialClassifierPolicyModel, 1).protected_entities = unsorted
        session.commit()
    legacy = read(engine)
    assert legacy["policy_version"] == "synthetic-v1"
    sorted_entities = [
        {"entity_id": "a", "aliases": ["Alpha"]},
        {"entity_id": "z", "aliases": ["Z", "Zulu"]},
    ]
    assert configure(engine, protected_entities=sorted_entities) == legacy
    assert events(engine) == []
    toggled = configure(engine, enabled=False, protected_entities=sorted_entities)
    assert toggled["policy_version"] == legacy["policy_version"]
    assert toggled["protected_entities"] == unsorted
    assert toggled["etag"] != legacy["etag"]
    changed = configure(engine, model="new-pinned-model", protected_entities=sorted_entities)
    assert changed["protected_entities"] == sorted_entities
    assert changed["policy_version"] != legacy["policy_version"]
    changed_version = changed["policy_version"]
    configure(engine, model="another-pinned-model")
    restored = configure(engine, model="new-pinned-model")
    assert restored["policy_version"] == changed_version
    assert configure(engine) == restored
    assert len(events(engine)) == 4


@pytest.mark.parametrize(
    "change",
    [
        {"enabled": 1},
        {"enabled": "true"},
        {"enabled": None},
        {"actor_id": True},
        {"actor_id": 0},
        {"actor_id": -1},
        {"actor_id": 2**63},
        {"actor_id": "1"},
        {"actor_id": None},
        {"actor_id": 1.0},
        {"provider": "openai"},
        {"provider": " OPENAI"},
        {"provider": []},
        {"provider": None},
        {"model": None},
        {"model": 1},
        {"model": ""},
        {"model": " "},
        {"model": " model"},
        {"model": "model "},
        {"model": "a,b"},
        {"model": "x" * 256},
        {"model": "\ud800"},
        {"provider": "OPENROUTER", "model": "synthetic/paid"},
        {"provider": "OPENROUTER", "model": "openrouter/free"},
        {"provider": "OPENROUTER", "model": "openrouter/model:free"},
        {"provider": "OPENROUTER", "model": "a:free:free"},
        {"provider": "OPENROUTER", "model": "a:free,b:free"},
        {"protected_entities": None},
        {"protected_entities": {}},
        {"protected_entities": ()},
        {"protected_entities": ["x"]},
        {"protected_entities": [{"entity_id": "x", "aliases": ["x"], "extra": 1}]},
        {"protected_entities": [{"entity_id": "x", "aliases": "x"}]},
        {"protected_entities": [{"entity_id": "x", "aliases": []}]},
        {"protected_entities": [{"entity_id": "x", "aliases": ["x"] * 17}]},
        {"protected_entities": [{"entity_id": "x" * 129, "aliases": ["x"]}]},
        {"protected_entities": [{"entity_id": "", "aliases": ["x"]}]},
        {"protected_entities": [{"entity_id": 1, "aliases": ["x"]}]},
        {"protected_entities": [{"entity_id": "x", "aliases": [""]}]},
        {"protected_entities": [{"entity_id": "x", "aliases": [" "]}]},
        {"protected_entities": [{"entity_id": "x", "aliases": [1]}]},
        {"protected_entities": [{"entity_id": "x", "aliases": ["x" * 256]}]},
        {"protected_entities": [{"entity_id": "x", "aliases": ["\ud800"]}]},
        {
            "protected_entities": [
                {"entity_id": "x", "aliases": ["a"]},
                {"entity_id": "x", "aliases": ["b"]},
            ]
        },
        {
            "protected_entities": [
                {"entity_id": "x", "aliases": ["Ａ"]},
                {"entity_id": "y", "aliases": ["a"]},
            ]
        },
        {"protected_entities": [{"entity_id": str(n), "aliases": [str(n)]} for n in range(65)]},
        {
            "protected_entities": [
                {"entity_id": str(n), "aliases": [str(n) + "Я" * 250] * 16} for n in range(64)
            ]
        },
        {"expected_etag": "A" * 64},
        {"expected_etag": "a" * 63},
        {"expected_etag": "a" * 65},
        {"expected_etag": "g" * 64},
        {"expected_etag": 1},
        {"expected_etag": True},
        {"expected_etag": []},
    ],
)
def test_complete_invalid_input_never_writes_and_errors_are_static(store, change):
    engine = store[0]
    original = read(engine)
    with pytest.raises(api().EditorialPolicyInvalid, match="^EDITORIAL_POLICY_INVALID$"):
        configure(engine, **change)
    assert read(engine) == original
    assert events(engine) == []


def test_entity_character_and_aggregate_byte_bounds_accept_exact_limits(store):
    entities = [
        {"entity_id": str(n).ljust(128, "x"), "aliases": [str(n).ljust(255, "Я")]}
        for n in range(64)
    ]
    assert configure(store[0], protected_entities=entities)["protected_entities"] == sorted(
        entities, key=lambda item: item["entity_id"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"protected_entities": "bad"},
        {"protected_entities": [{"entity_id": "x", "aliases": []}]},
        {"protected_entities": [{"entity_id": "x", "aliases": ["x"], "bad": 1}]},
        {"provider": "OPENROUTER", "model": "synthetic/paid"},
        {"model": "bad,model"},
        {"policy_version": " "},
        {"policy_version": "\ud800"},
    ],
)
def test_corrupt_stored_policy_fails_visibly_without_repair(store, change):
    with Session(store[0]) as session:
        row = session.get(models.EditorialClassifierPolicyModel, 1)
        for name, value in change.items():
            setattr(row, name, value)
        if change.get("policy_version") in {" ", "\ud800"}:
            # DB constraints/UTF-8 prevent these corrupt commits. Inject only the
            # freshly loaded storage boundary; service still owns real SQL scope.
            session.rollback()

            def corrupt(target, context):
                target.policy_version = change["policy_version"]

            event.listen(models.EditorialClassifierPolicyModel, "load", corrupt)
        else:
            session.commit()
    try:
        with pytest.raises(api().EditorialPolicyInvalid, match="^EDITORIAL_POLICY_INVALID$"):
            read(store[0])
        with pytest.raises(api().EditorialPolicyInvalid):
            configure(store[0], model="replacement")
        assert events(store[0]) == []
    finally:
        if change.get("policy_version") in {" ", "\ud800"}:
            event.remove(models.EditorialClassifierPolicyModel, "load", corrupt)


@pytest.mark.parametrize("expected", [None, "0" * 64])
def test_existing_policy_rejects_create_only_and_stale_expected_etag(store, expected):
    before = read(store[0])
    with pytest.raises(api().EditorialPolicyConflict, match="^EDITORIAL_POLICY_CONFLICT$"):
        configure(store[0], expected_etag=expected, model="overwrite")
    assert read(store[0]) == before
    assert events(store[0]) == []


def test_missing_policy_rejects_update_etag(store):
    missing(store[0])
    with pytest.raises(api().EditorialPolicyConflict):
        configure(store[0], expected_etag="a" * 64)
    assert read(store[0])["configured"] is False
    assert events(store[0]) == []


@pytest.mark.parametrize("method", ["read", "configure"])
@pytest.mark.parametrize("state", ["new", "dirty", "deleted", "raw"])
def test_non_pristine_session_refuses_before_sql_without_touching_caller(store, method, state):
    engine = store[0]
    values = read(engine)
    with Session(engine) as session:
        if state == "new":
            session.add(
                models.OutboxEventModel(
                    event_type="caller", aggregate_key="caller", idempotency_key="caller"
                )
            )
        elif state == "dirty":
            session.get(models.EditorialClassifierPolicyModel, 1).model = "caller-pending"
        elif state == "deleted":
            session.delete(session.get(models.EditorialClassifierPolicyModel, 1))
        else:
            session.execute(text("UPDATE editorial_classifier_policy SET model='caller-raw'"))
        pending = (set(session.new), set(session.dirty), set(session.deleted))
        transaction = session.get_transaction()

        def forbidden(*args):
            pytest.fail("non-pristine configuration touched SQL")

        event.listen(engine, "before_cursor_execute", forbidden)
        try:
            service = api().EditorialPolicyConfigurationService(session)
            with pytest.raises(
                api().EditorialPolicyInvalid, match="^EDITORIAL_POLICY_SESSION_NOT_PRISTINE$"
            ):
                if method == "read":
                    service.read()
                else:
                    service.configure(
                        enabled=False,
                        provider="OPENAI",
                        model="new",
                        protected_entities=[],
                        expected_etag=values["etag"],
                        actor_id=1,
                    )
            assert session.get_transaction() is transaction
            assert (set(session.new), set(session.dirty), set(session.deleted)) == pending
        finally:
            event.remove(engine, "before_cursor_execute", forbidden)
        if state == "raw":
            assert (
                session.scalar(text("SELECT model FROM editorial_classifier_policy"))
                == "caller-raw"
            )
        session.rollback()
    assert read(engine) == values


def test_retained_identity_map_is_refreshed_and_snapshot_mutations_are_detached(store):
    engine = store[0]
    with Session(engine, expire_on_commit=False) as session:
        retained = session.get(models.EditorialClassifierPolicyModel, 1)
        session.commit()
        configure(engine, model="external-model")
        result = api().EditorialPolicyConfigurationService(session).read()
        assert result["model"] == retained.model == "external-model"
        result["protected_entities"][0]["aliases"].append("changed")
        assert retained.protected_entities[0]["aliases"] == ["Civic Council"]


def test_sqlite_corrupt_raw_boolean_is_not_coerced_into_valid_configuration(store):
    engine = store[0]
    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite raw Boolean corruption; PostgreSQL rejects non-Boolean storage")
    with engine.begin() as connection:
        connection.execute(text("UPDATE editorial_classifier_policy SET enabled=2"))
    with Session(engine) as session:
        assert session.get(models.EditorialClassifierPolicyModel, 1).enabled is True
    with pytest.raises(api().EditorialPolicyInvalid, match="^EDITORIAL_POLICY_INVALID$"):
        read(engine)
    with Session(engine) as session:
        assert session.scalar(text("SELECT enabled FROM editorial_classifier_policy")) == 2
    assert events(engine) == []


def test_events_are_metadata_only_and_repeated_etag_cycles_have_distinct_operation_ids(store):
    engine = store[0]
    before = read(engine)
    off = configure(engine, enabled=False)
    on = configure(engine, enabled=True)
    assert on == before
    configure(engine, enabled=False)
    records = events(engine)
    assert [row.aggregate_key for row in records] == [
        f"editorial-policy:1:{before['etag']}:{off['etag']}",
        f"editorial-policy:1:{off['etag']}:{before['etag']}",
        f"editorial-policy:1:{before['etag']}:{off['etag']}",
    ]
    assert len({row.idempotency_key for row in records}) == 3
    for row in records:
        suffix = row.idempotency_key.removeprefix("editorial-policy-update:")
        assert len(suffix) == 32 and set(suffix) <= set("0123456789abcdef")
        assert "Civic Council" not in row.aggregate_key + row.idempotency_key


@pytest.mark.parametrize("create", [True, False])
@pytest.mark.parametrize("operation", ["policy_insert", "outbox_insert", "commit"])
def test_storage_failures_roll_back_policy_and_event_without_acknowledgement(
    store, create, operation
):
    engine = store[0]
    if operation == "policy_insert" and not create:
        pytest.skip("policy INSERT applies only to create")
    if create:
        missing(engine)
    before = read(engine)

    def fail(connection, cursor, statement, parameters, context, many):
        wanted = "outbox_events" if operation == "outbox_insert" else "editorial_classifier_policy"
        if statement.lower().lstrip().startswith("insert into " + wanted):
            raise IntegrityError("PRIVATE_SQL", {}, RuntimeError("PRIVATE_PROVIDER"))

    def fail_commit(session):
        raise IntegrityError("PRIVATE_COMMIT", {}, RuntimeError("PRIVATE_PROVIDER"))

    if operation == "commit":
        event.listen(Session, "before_commit", fail_commit)
    else:
        event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(IntegrityError):
            configure(engine, model="changed-model")
    finally:
        if operation == "commit":
            event.remove(Session, "before_commit", fail_commit)
        else:
            event.remove(engine, "before_cursor_execute", fail)
    assert read(engine) == before
    assert events(engine) == []


def test_sql_cas_matches_exact_stored_json_and_detects_same_etag_raw_change(store):
    engine = store[0]
    before = read(engine)
    raw = '[ { "entity_id" : "synthetic-council", "aliases" : [ "Civic Council" ] } ]'
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE editorial_classifier_policy SET protected_entities=:raw"), {"raw": raw}
        )
    assert read(engine) == before
    assert configure(engine, enabled=False)["enabled"] is False
    current = read(engine)
    injected = False

    def change_raw(connection, cursor, statement, parameters, context, many):
        nonlocal injected
        if not injected and statement.lower().lstrip().startswith(
            "update editorial_classifier_policy"
        ):
            injected = True
            connection.execute(
                text("UPDATE editorial_classifier_policy SET protected_entities=:raw"),
                {"raw": json.dumps(before["protected_entities"])},
            )

    event.listen(engine, "before_cursor_execute", change_raw)
    try:
        with pytest.raises(api().EditorialPolicyConflict):
            configure(engine, enabled=True)
    finally:
        event.remove(engine, "before_cursor_execute", change_raw)
    assert injected
    assert read(engine) == current
    assert len(events(engine)) == 1
    with Session(engine) as session:
        assert (
            session.scalar(
                select(cast(models.EditorialClassifierPolicyModel.protected_entities, Text))
            )
            == raw
        )


@pytest.mark.parametrize("change", ["disable", "model", "entities"])
def test_configuration_blocks_stale_diagnostic_before_factory_and_preserves_decisions(
    store, change, monkeypatch
):
    engine, mapping = store
    ingest(store)
    ingest(
        store,
        replace(MESSAGE, message_id=8, text="Synthetic protected bad report"),
        protected_entities=["synthetic"],
        sentiment="negative",
        framing="hostile",
    )
    with Session(engine) as session:
        binding = resolve_editorial_admission(session, content_key=KEY, mapping_id=mapping)
        before = [
            (row.content_key, row.status, row.rewrite_allowed)
            for row in session.scalars(select(models.EditorialDecisionModel)).all()
        ]
        assert any(status == "REJECT" for _, status, _ in before)
        job = session.scalar(select(models.EditorialClassificationJobModel))
        job_id = job.id
    calls = {"decrypt": 0, "construct": 0, "rewrite": 0}

    class Cipher:
        def decrypt(self, value):
            calls["decrypt"] += 1
            pytest.fail("stale configuration decrypted credentials")

    def construct(*args, **kwargs):
        calls["construct"] += 1
        pytest.fail("stale configuration constructed provider")

    def rewrite(*args, **kwargs):
        calls["rewrite"] += 1
        pytest.fail("diagnostic configuration rewrote source")

    factory_module = import_module("newsflow.services.editorial_classifier_factory")
    monkeypatch.setattr(factory_module, "OpenAIEditorialClassifier", construct)
    monkeypatch.setattr(factory_module, "FreeOpenRouterEditorialClassifier", construct)
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", rewrite)
    monkeypatch.setattr(StructuredFreeOpenRouterProvider, "rewrite", rewrite)
    changes = {
        "disable": {"enabled": False},
        "model": {"model": "new-model"},
        "entities": {"protected_entities": []},
    }[change]
    configure(engine, **changes)
    with Session(engine) as session:
        assert count(session, models.EditorialClassificationJobModel) == 1
        assert count(session, models.EditorialClassificationClaimModel) == 0
        assert count(session, models.EditorialClassificationAttemptModel) == 0
        assert session.get(models.EditorialClassificationJobModel, job_id).state == "QUEUED"
        if change == "disable":
            with pytest.raises(EditorialAdmissionBlocked):
                resolve_editorial_admission(session, content_key=KEY, mapping_id=mapping)
        else:
            assert (
                resolve_editorial_admission(session, content_key=KEY, mapping_id=mapping) != binding
            )
    factory = ConfiguredEditorialClassifierFactory(sessionmaker(engine), cipher=Cipher())
    with pytest.raises(EditorialAdmissionBlocked):
        factory(binding)
    assert make_runner(engine, factory=factory).run_next(now=NOW) == "BLOCKED"
    with Session(engine) as session:
        assert [
            (row.content_key, row.status, row.rewrite_allowed)
            for row in session.scalars(select(models.EditorialDecisionModel)).all()
        ] == before
        assert count(session, models.RewriteJobModel) == 0
        assert session.get(models.EditorialClassificationJobModel, job_id).attempts == 0
    assert calls == {"decrypt": 0, "construct": 0, "rewrite": 0}


@pytest.mark.parametrize("create", [True, False])
def test_postgres_two_connection_create_and_stale_update_arbitration(store, create):
    engine = store[0]
    if engine.dialect.name != "postgresql":
        pytest.skip("strict opt-in PostgreSQL: actual singleton locking/unique arbitration")
    if create:
        missing(engine)
    expected = read(engine)["etag"]
    barrier = Barrier(2, timeout=10)
    results = Queue()
    connections = Queue()

    def both_read(connection, cursor, statement, parameters, context, many):
        if (
            create
            and statement.lstrip().lower().startswith("select editorial_classifier_policy.id")
            and "FOR UPDATE" in statement
        ):
            connections.put(id(connection))
            barrier.wait()

    event.listen(engine, "after_cursor_execute", both_read)

    def save(model):
        try:
            if not create:
                barrier.wait()
            with Session(engine) as session:
                result = (
                    api()
                    .EditorialPolicyConfigurationService(session)
                    .configure(
                        enabled=True,
                        provider="OPENAI",
                        model=model,
                        protected_entities=[],
                        expected_etag=expected,
                        actor_id=1,
                    )
                )
            results.put(("saved", result))
        except api().EditorialPolicyConflict:
            results.put(("conflict", None))
        except BaseException as error:  # noqa: BLE001 - transfer worker failure to main assertion
            results.put(("error", repr(error)))

    threads = [Thread(target=save, args=(model,), daemon=True) for model in ("first", "second")]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
        assert not any(thread.is_alive() for thread in threads), "bounded PostgreSQL race timed out"
    finally:
        event.remove(engine, "after_cursor_execute", both_read)
    outcomes = [results.get_nowait() for _ in range(2)]
    assert sorted(kind for kind, _ in outcomes) == ["conflict", "saved"], outcomes
    saved = next(value for kind, value in outcomes if kind == "saved")
    assert read(engine) == saved
    assert len(events(engine)) == 1
    if create:
        assert connections.get_nowait() != connections.get_nowait()


def test_postgres_existing_singleton_lock_blocks_other_connection_until_release(store):
    engine = store[0]
    if engine.dialect.name != "postgresql":
        pytest.skip("strict opt-in PostgreSQL: actual row lock")
    entered, done = Event(), Event()
    result = Queue()
    expected = read(engine)["etag"]

    def selecting(connection, cursor, statement, parameters, context, many):
        if "FOR UPDATE" in statement and "editorial_classifier_policy" in statement:
            entered.set()

    def save():
        try:
            result.put(configure(engine, model="after-lock", expected_etag=expected))
        except BaseException as error:  # noqa: BLE001 - transfer worker failure to main assertion
            result.put(error)
        finally:
            done.set()

    with Session(engine) as owner:
        owner.scalar(select(models.EditorialClassifierPolicyModel).with_for_update())
        event.listen(engine, "before_cursor_execute", selecting)
        thread = Thread(target=save, daemon=True)
        try:
            thread.start()
            assert entered.wait(10)
            assert not done.wait(0.2)
        finally:
            owner.rollback()
            thread.join(15)
            event.remove(engine, "before_cursor_execute", selecting)
    assert not thread.is_alive()
    saved = result.get_nowait()
    assert isinstance(saved, dict), saved
    assert saved["model"] == "after-lock"
