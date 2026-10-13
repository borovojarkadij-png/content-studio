"""Synthetic durable comparison contracts; no ingestion or source permission."""

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker
from test_intake_selection_ledger_migration import assert_old_rows, seed_old_rows

from alembic import command
from newsflow.domain.intake_selection import IntakeCandidate, IntakeSelectionPolicy
from newsflow.persistence import models
from newsflow.services.intake_selection_ledger import (
    DurableIntakeSelectionLedger,
    IntakeLedgerConflict,
    IntakeLedgerCorrupt,
)

NOW = datetime(2030, 1, 1, tzinfo=UTC)
BINDING = "c" * 64
KEY = "a" * 64
REVISION = "b" * 64


@pytest.fixture(autouse=True)
def zero_rewrite_calls(monkeypatch):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter import OpenRouterRewriteProvider

    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("Comparison ledger invoked rewrite provider")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(OpenRouterRewriteProvider, "rewrite", forbidden)
    yield
    assert calls == []


@pytest.fixture
def factory(tmp_path):
    url = f"sqlite:///{tmp_path / 'ledger.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    seed_old_rows(engine)
    try:
        yield sessionmaker(engine)
    finally:
        with engine.connect() as connection:
            assert_old_rows(connection)
        engine.dispose()


def test_literal_hybrid_decision_commits_first_sequence(factory):
    rows = tuple(IntakeCandidate(i, REVISION, i) for i in range(1, 11))
    with factory.begin() as session:
        value = DurableIntakeSelectionLedger(session).record_window(
            mapping_id=1,
            policy_binding_sha256=BINDING,
            window_key=KEY,
            candidates=rows,
            policy=IntakeSelectionPolicy(50, "HYBRID"),
            now=NOW,
        )
        assert value.result.selected_ids == (10, 9, 8, 7, 3)
        assert value.sequence == 1 and value.replayed is False


def rows(count=10):
    return tuple(IntakeCandidate(i, REVISION, i % 101) for i in range(1, count + 1))


def record(session, **overrides):
    arguments = {
        "mapping_id": 1,
        "policy_binding_sha256": BINDING,
        "window_key": KEY,
        "candidates": rows(),
        "policy": IntakeSelectionPolicy(50),
        "now": NOW,
    }
    arguments.update(overrides)
    return DurableIntakeSelectionLedger(session).record_window(**arguments)


def load(session, **overrides):
    arguments = {"mapping_id": 1, "policy_binding_sha256": BINDING, "window_key": KEY}
    arguments.update(overrides)
    return DurableIntakeSelectionLedger(session).load_window(**arguments)


def history(factory):
    with factory() as session:
        return tuple(
            tuple(session.execute(text(f"SELECT * FROM {table} ORDER BY id")).all())
            for table in (
                "telegram_intake_selection_streams",
                "telegram_intake_selection_windows",
            )
        )


@pytest.mark.parametrize(
    "mode,expected",
    [("HYBRID", (10, 9, 8, 7, 3)), ("TOP_SCORE", (10, 9, 8, 7, 6)), ("RANDOM", (8, 3, 7, 2, 1))],
)
def test_modes_persist_literal_result_and_recompute_on_load(factory, mode, expected):
    with factory.begin() as session:
        first = record(session, policy=IntakeSelectionPolicy(50, mode))
        assert first.result.selected_ids == expected
        assert (first.result.eligible_count, first.result.quota, first.result.carry_out) == (
            10,
            5,
            0,
        )
        assert first.carry_in == 0
        with pytest.raises(FrozenInstanceError):
            first.sequence = 9
    with factory.begin() as session:
        loaded = load(session)
        assert loaded.result == first.result
        assert (loaded.stream_id, loaded.window_id, loaded.sequence, loaded.replayed) == (
            first.stream_id,
            first.window_id,
            1,
            True,
        )


def test_best_thirty_of_one_hundred_survive_reopen(factory):
    candidates = tuple(IntakeCandidate(i, REVISION, i - 1) for i in range(1, 101))
    with factory.begin() as session:
        first = record(
            session, candidates=candidates, policy=IntakeSelectionPolicy(30, "TOP_SCORE")
        )
    factory.kw["bind"].dispose()
    with factory.begin() as session:
        value = load(session)
        assert value.result.selected_ids == (
            100,
            99,
            98,
            97,
            96,
            95,
            94,
            93,
            92,
            91,
            90,
            89,
            88,
            87,
            86,
            85,
            84,
            83,
            82,
            81,
            80,
            79,
            78,
            77,
            76,
            75,
            74,
            73,
            72,
            71,
        )
        assert (value.result.quota, value.result.carry_out) == (30, 0)
        assert value.result == first.result


def test_fractional_carry_is_durable_and_old_replay_never_advances(factory):
    values = []
    for number in range(1, 5):
        with factory.begin() as session:
            values.append(
                record(
                    session,
                    window_key=f"{number:064x}",
                    candidates=rows(1),
                    policy=IntakeSelectionPolicy(30),
                )
            )
    assert [value.sequence for value in values] == [1, 2, 3, 4]
    assert [value.carry_in for value in values] == [0, 30, 60, 90]
    assert [value.result.quota for value in values] == [0, 0, 0, 1]
    assert [value.result.carry_out for value in values] == [30, 60, 90, 20]
    before = history(factory)
    with factory.begin() as session:
        replay = record(
            session, window_key=f"{1:064x}", candidates=rows(1), policy=IntakeSelectionPolicy(30)
        )
        assert (
            replay.sequence,
            replay.carry_in,
            replay.result.quota,
            replay.result.carry_out,
            replay.replayed,
        ) == (1, 0, 0, 30, True)
    assert history(factory) == before


def test_reordered_int_float_equivalents_replay_exact_evidence(factory):
    with factory.begin() as session:
        first = record(session)
    before = history(factory)
    with factory.begin() as session:
        again = record(
            session,
            candidates=tuple(IntakeCandidate(i, REVISION, float(i)) for i in range(10, 0, -1)),
            policy=IntakeSelectionPolicy(50, "HYBRID", 0.0),
        )
        assert again.result == first.result
        assert (again.window_id, again.sequence, again.replayed) == (first.window_id, 1, True)
    assert history(factory) == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"candidates": (IntakeCandidate(1, "d" * 64, 1),)},
        {"candidates": (IntakeCandidate(1, REVISION, 2),)},
        {"candidates": (IntakeCandidate(1, REVISION, 1, False),)},
        {"policy": IntakeSelectionPolicy(30)},
        {"policy": IntakeSelectionPolicy(50, "RANDOM")},
        {"policy": IntakeSelectionPolicy(50, "HYBRID", 1)},
    ],
)
def test_changed_input_or_bound_policy_conflicts_without_history_change(factory, overrides):
    with factory.begin() as session:
        record(session, candidates=rows(1))
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerConflict):
        arguments = {"candidates": rows(1)}
        arguments.update(overrides)
        record(session, **arguments)
    assert history(factory) == before


def test_new_policy_requires_distinct_binding(factory):
    with factory.begin() as session:
        first = record(session)
        other = record(session, policy_binding_sha256="d" * 64, policy=IntakeSelectionPolicy(30))
        assert other.stream_id != first.stream_id
        assert (other.sequence, other.result.quota) == (1, 3)


@pytest.mark.parametrize(
    "candidates",
    [
        (),
        (IntakeCandidate(1, REVISION, None),),
        (IntakeCandidate(1, REVISION, 99, False),),
        (IntakeCandidate(1, REVISION, 0),),
    ],
)
def test_empty_blocked_unknown_and_below_threshold_preserve_carry(factory, candidates):
    with factory.begin() as session:
        record(session, candidates=rows(1), policy=IntakeSelectionPolicy(30, "HYBRID", 1))
        value = record(
            session,
            window_key="e" * 64,
            candidates=candidates,
            policy=IntakeSelectionPolicy(30, "HYBRID", 1),
        )
        assert (value.sequence, value.carry_in, value.result.quota, value.result.carry_out) == (
            2,
            30,
            0,
            30,
        )


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("fault", [False, True])
def test_caller_rollback_and_fault_after_insert_leave_no_advancement(factory, existing, fault):
    if existing:
        with factory.begin() as session:
            record(session)
    before = history(factory)
    engine = factory.kw["bind"]

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE telegram_intake_selection_streams"):
            raise RuntimeError("synthetic interruption after window insertion")

    if fault:
        event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError), factory.begin() as session:
            record(session, window_key="e" * 64)
            raise RuntimeError("caller rollback")
    finally:
        if fault:
            event.remove(engine, "before_cursor_execute", fail)
    assert history(factory) == before
    with factory.begin() as session:
        value = record(session, window_key="e" * 64)
        assert value.sequence == (2 if existing else 1)


def test_load_missing_is_read_only_and_record_missing_mapping_is_invalid(factory):
    before = history(factory)
    with factory.begin() as session:
        assert load(session) is None
        assert load(session, mapping_id=999) is None
        with pytest.raises(ValueError):
            record(session, mapping_id=999)
    assert history(factory) == before


@pytest.mark.parametrize("state", ["inactive", "autobegin", "pending", "dirty", "deleted"])
@pytest.mark.parametrize("operation", ["record", "load"])
def test_explicit_clean_caller_transaction_is_required(factory, state, operation):
    with factory() as session:
        if state != "inactive":
            if state != "autobegin":
                session.begin()
            mapping = session.get(models.ChannelMappingModel, 1)
            if state == "pending":
                session.add(models.TelegramAccount(name="unrelated", encrypted_session=""))
            elif state == "dirty":
                mapping.intake_percent = 99
            elif state == "deleted":
                session.delete(mapping)
        with pytest.raises(ValueError):
            record(session) if operation == "record" else load(session)
        session.rollback()
    assert history(factory) == ((), ())


@pytest.mark.parametrize(
    "overrides",
    [
        {"mapping_id": True},
        {"mapping_id": 0},
        {"mapping_id": 2**63},
        {"policy_binding_sha256": "C" * 64},
        {"policy_binding_sha256": b"c" * 64},
        {"window_key": "a" * 63},
        {"now": datetime(2030, 1, 1)},
        {"now": "2030-01-01"},
        {"candidates": []},
        {"policy": None},
        {"candidates": (IntakeCandidate(1, REVISION, 1), IntakeCandidate(1, REVISION, 2))},
    ],
)
def test_invalid_arguments_fail_before_any_sql(factory, overrides):
    statements = []
    engine = factory.kw["bind"]

    def observe(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with factory.begin() as session, pytest.raises((ValueError, TypeError)):
            record(session, **overrides)
        assert statements == []
    finally:
        event.remove(engine, "before_cursor_execute", observe)


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("candidate", "candidate_id", True),
        ("candidate", "score", float("nan")),
        ("candidate", "eligible", 1),
        ("candidate", "revision_sha256", "bad"),
        ("policy", "intake_percent", True),
        ("policy", "mode", "BAD"),
        ("policy", "minimum_score", float("inf")),
    ],
)
def test_tampered_frozen_dataclasses_are_revalidated(factory, target, field, value):
    candidate, policy = IntakeCandidate(1, REVISION, 1), IntakeSelectionPolicy()
    object.__setattr__(candidate if target == "candidate" else policy, field, value)
    with factory.begin() as session, pytest.raises(ValueError):
        record(session, candidates=(candidate,), policy=policy)
    assert history(factory) == ((), ())


def test_aware_offset_normalizes_to_utc_and_flushed_transaction_is_reusable(factory):
    with factory.begin() as session:
        mapping = session.get(models.ChannelMappingModel, 1)
        mapping.intake_percent = 31
        session.flush()
        record(session, now=datetime(2030, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))))
        assert load(session).sequence == 1
    with factory() as session:
        assert session.scalar(
            select(models.TelegramIntakeSelectionWindowModel.created_at)
        ) == NOW.replace(tzinfo=None)


def test_thousand_candidates_and_statement_budgets_are_independent_of_size(factory):
    statements = []
    engine = factory.kw["bind"]

    def observe(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with factory.begin() as session:
            value = record(
                session, candidates=rows(1000), policy=IntakeSelectionPolicy(1, "TOP_SCORE")
            )
            assert (value.result.eligible_count, value.result.quota) == (1000, 10)
        assert len(statements) <= 12
        statements.clear()
        with factory.begin() as session:
            record(
                session,
                window_key="e" * 64,
                candidates=rows(1000),
                policy=IntakeSelectionPolicy(1, "TOP_SCORE"),
            )
        assert len(statements) <= 10
        statements.clear()
        with factory.begin() as session:
            assert load(session).result.quota == 10
        assert len(statements) <= 2 and all(
            statement.startswith("SELECT") for statement in statements
        )
        statements.clear()
        with factory.begin() as session, pytest.raises(ValueError):
            record(session, candidates=rows(1001))
        assert statements == []
    finally:
        event.remove(engine, "before_cursor_execute", observe)


@pytest.fixture
def corrupt_factory(tmp_path):
    # Isolated metadata fixture has no migration guards. Raw corruption is a
    # decoder fault model, never a claim of bypassing the public migrated API.
    engine = create_engine(f"sqlite:///{tmp_path / 'isolated-corruption.db'}")
    models.Base.metadata.create_all(engine)
    seed_old_rows(engine)
    factory = sessionmaker(engine)
    with factory.begin() as session:
        record(session)
        record(session, window_key="e" * 64)
    try:
        yield factory
    finally:
        with engine.connect() as connection:
            assert_old_rows(connection)
        engine.dispose()


@pytest.mark.parametrize(
    "column,value",
    [
        ("input_payload", "{}"),
        ("input_payload", '{"policy":{},"policy":{},"candidates":[]}'),
        ("input_payload", '{"policy":NaN,"candidates":[]}'),
        ("input_payload", "[" * 2000 + "]" * 2000),
        ("input_payload", "é"),
        ("input_payload", "x" * 262145),
        ("result_payload", "{}"),
        ("result_payload", "null"),
        ("result_payload", "x" * 262145),
        ("input_sha256", "d" * 64),
        ("algorithm_version", "intake-selection-v2"),
        ("carry_out", 99),
        ("carry_in", 99),
    ],
    ids=[
        "missing-input",
        "duplicate-key",
        "nonfinite",
        "deep-json",
        "non-ascii",
        "oversized-input",
        "missing-result",
        "null-result",
        "oversized-result",
        "wrong-hash",
        "wrong-version",
        "wrong-carry-out",
        "wrong-carry-in",
    ],
)
@pytest.mark.parametrize("operation", ["record", "load"])
def test_corrupt_window_evidence_fails_closed_without_history_change(
    corrupt_factory, column, value, operation
):
    factory = corrupt_factory
    with factory.kw["bind"].begin() as connection:
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            text(f"UPDATE telegram_intake_selection_windows SET {column}=:value WHERE sequence=2"),
            {"value": value},
        )
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerCorrupt):
        record(session, window_key="f" * 64) if operation == "record" else load(
            session, window_key="e" * 64
        )
    assert history(factory) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("quota", 4),
        ("eligible_count", 9),
        ("selected_ids", [10]),
        ("carry_out", 30),
        ("algorithm_version", "other"),
        ("input_sha256", "d" * 64),
        ("decisions", [{"candidate_id": 1, "selected": True, "reason": "SELECTED_TOP"}]),
        ("quota", 5.0),
        ("extra", 0),
    ],
)
def test_every_stored_result_field_must_equal_recomputed_kernel(corrupt_factory, field, value):
    factory = corrupt_factory
    with factory.kw["bind"].begin() as connection:
        payload = json.loads(
            connection.scalar(
                text(
                    "SELECT result_payload FROM telegram_intake_selection_windows WHERE sequence=2"
                )
            )
        )
        payload[field] = value
        connection.execute(
            text(
                "UPDATE telegram_intake_selection_windows SET result_payload=:value WHERE sequence=2"
            ),
            {"value": json.dumps(payload, sort_keys=True, separators=(",", ":"))},
        )
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerCorrupt):
        load(session, window_key="e" * 64)
    assert history(factory) == before


@pytest.mark.parametrize(
    "column,value",
    [
        ("policy_payload", "{}"),
        ("policy_sha256", "d" * 64),
        ("carry", 1),
        ("next_sequence", 1),
        ("next_sequence", 4),
    ],
)
def test_corrupt_stream_policy_or_previous_link_never_consumes_carry(
    corrupt_factory, column, value
):
    factory = corrupt_factory
    with factory.kw["bind"].begin() as connection:
        connection.execute(
            text(f"UPDATE telegram_intake_selection_streams SET {column}=:value"), {"value": value}
        )
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerCorrupt):
        record(session, window_key="f" * 64)
    assert history(factory) == before


def test_missing_previous_window_fails_closed(corrupt_factory):
    factory = corrupt_factory
    with factory.kw["bind"].begin() as connection:
        connection.execute(text("DELETE FROM telegram_intake_selection_windows WHERE sequence=2"))
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerCorrupt):
        record(session, window_key="f" * 64)
    assert history(factory) == before


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "candidate_extra",
        "candidate_missing",
        "duplicate_id",
        "too_many",
        "bool_id",
        "int_eligible",
        "noncanonical_score",
        "wrong_policy",
        "reverse",
        "whitespace",
    ],
)
def test_snapshot_shape_types_and_canonical_form_are_verified(corrupt_factory, mutation):
    factory = corrupt_factory
    with factory.kw["bind"].begin() as connection:
        payload = json.loads(
            connection.scalar(
                text("SELECT input_payload FROM telegram_intake_selection_windows WHERE sequence=2")
            )
        )
        if mutation == "extra":
            payload["extra"] = 0
        elif mutation == "missing":
            del payload["policy"]
        elif mutation == "candidate_extra":
            payload["candidates"][0]["extra"] = 0
        elif mutation == "candidate_missing":
            del payload["candidates"][0]["score"]
        elif mutation == "duplicate_id":
            payload["candidates"][1]["candidate_id"] = 1
        elif mutation == "too_many":
            payload["candidates"] *= 101
        elif mutation == "bool_id":
            payload["candidates"][0]["candidate_id"] = True
        elif mutation == "int_eligible":
            payload["candidates"][0]["eligible"] = 1
        elif mutation == "noncanonical_score":
            payload["candidates"][0]["score"] = 1
        elif mutation == "wrong_policy":
            payload["policy"]["intake_percent"] = 30
        elif mutation == "reverse":
            payload["candidates"].reverse()
        value = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if mutation == "whitespace":
            value += " "
        connection.execute(
            text(
                "UPDATE telegram_intake_selection_windows SET input_payload=:value WHERE sequence=2"
            ),
            {"value": value},
        )
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerCorrupt):
        load(session, window_key="e" * 64)
    assert history(factory) == before


def test_exhausted_sequence_refuses_before_window_insert(corrupt_factory):
    factory = corrupt_factory
    # Isolated fixture places a valid last window at the signed64 boundary.
    with factory.kw["bind"].begin() as connection:
        connection.execute(
            text(
                "UPDATE telegram_intake_selection_windows SET sequence=9223372036854775806 WHERE sequence=2"
            )
        )
        connection.execute(
            text("UPDATE telegram_intake_selection_streams SET next_sequence=9223372036854775807")
        )
    before = history(factory)
    with factory.begin() as session, pytest.raises(ValueError, match="exhaust"):
        record(session, window_key="f" * 64)
    assert history(factory) == before


def test_load_never_combines_stream_and_window_from_different_commits(factory):
    with factory.begin() as session:
        record(session)
    engine = factory.kw["bind"]

    def append_between_reads(connection, cursor, statement, parameters, context, executemany):
        if (
            connection.info.get("ledger_reader")
            and "FROM telegram_intake_selection_windows" in statement
        ):
            with factory.begin() as writer:
                record(writer, window_key="e" * 64)

    event.listen(engine, "before_cursor_execute", append_between_reads)
    try:
        with factory.begin() as reader:
            connection = reader.connection()
            connection.info["ledger_reader"] = True
            try:
                value = load(reader, window_key="e" * 64)
                # A coherent snapshot may precede or follow the competing commit.
                assert value is None or (value.sequence, value.replayed) == (2, True)
            finally:
                connection.info.pop("ledger_reader", None)
    finally:
        event.remove(engine, "before_cursor_execute", append_between_reads)


def test_canonical_policy_and_candidate_snapshot_have_literal_bytes(factory):
    with factory.begin() as session:
        record(session, candidates=(IntakeCandidate(1, REVISION, 1),))
    policy = '{"intake_percent":50,"minimum_score":0.0,"mode":"HYBRID"}'
    expected_hash = sha256(
        ('{"algorithm_version":"intake-selection-v1","policy":' + policy + "}").encode("ascii")
    ).hexdigest()
    with factory() as session:
        stream = session.scalar(select(models.TelegramIntakeSelectionStreamModel))
        window = session.scalar(select(models.TelegramIntakeSelectionWindowModel))
        assert (stream.policy_payload, stream.policy_sha256) == (policy, expected_hash)
        assert window.input_payload == (
            '{"candidates":[{"candidate_id":1,"eligible":true,"revision_sha256":"'
            + REVISION
            + '","score":1.0}],"policy":'
            + policy
            + "}"
        )


def test_sqlite_writer_contention_propagates_for_caller_retry(factory):
    engine = factory.kw["bind"]
    competing = create_engine(engine.url, connect_args={"timeout": 0})
    contender_factory = sessionmaker(competing)
    try:
        with factory.begin() as owner:
            first = record(owner)
            with contender_factory.begin() as contender, pytest.raises(DBAPIError, match="locked"):
                record(contender, window_key="e" * 64)
        with contender_factory.begin() as contender:
            next_value = record(contender, window_key="e" * 64)
            assert (first.sequence, next_value.sequence) == (1, 2)
    finally:
        competing.dispose()


def test_unrelated_integrity_error_is_not_hidden_or_retried(factory):
    engine = factory.kw["bind"]

    def inject_constraint_failure(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO telegram_intake_selection_windows"):
            connection.exec_driver_sql(
                "INSERT INTO telegram_accounts (id,name,encrypted_session) VALUES (1,'duplicate','')"
            )

    event.listen(engine, "before_cursor_execute", inject_constraint_failure)
    try:
        with factory.begin() as session, pytest.raises(IntegrityError):
            record(session)
    finally:
        event.remove(engine, "before_cursor_execute", inject_constraint_failure)
    assert history(factory) == ((), ())


def test_initial_stream_with_noninitial_retained_window_is_corrupt(corrupt_factory):
    factory = corrupt_factory
    with factory.kw["bind"].begin() as connection:
        connection.execute(text("DELETE FROM telegram_intake_selection_windows WHERE sequence=1"))
        connection.execute(text("UPDATE telegram_intake_selection_streams SET next_sequence=1"))
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerCorrupt):
        record(session, window_key="f" * 64)
    assert history(factory) == before


@pytest.mark.parametrize(
    "now", [datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC)]
)
def test_portable_utc_time_boundaries_are_accepted(factory, now):
    with factory.begin() as session:
        record(session, now=now)
        assert load(session).sequence == 1


@pytest.mark.parametrize(
    "now",
    [
        datetime.min.replace(tzinfo=timezone(timedelta(hours=1))),
        datetime.max.replace(tzinfo=timezone(timedelta(hours=-1))),
    ],
)
def test_utc_conversion_overflow_is_rejected_before_sql(factory, now):
    with factory.begin() as session, pytest.raises(ValueError):
        record(session, now=now)
    assert history(factory) == ((), ())


@pytest.mark.parametrize("operation", ["record", "load"])
def test_unsupported_dialect_fails_visibly_without_writing(factory, operation):
    engine = factory.kw["bind"]
    original = engine.dialect.name
    engine.dialect.name = "unsupported"
    try:
        with factory.begin() as session, pytest.raises(ValueError, match="SQLite and PostgreSQL"):
            record(session) if operation == "record" else load(session)
    finally:
        engine.dialect.name = original
    assert history(factory) == ((), ())


@pytest.mark.parametrize(
    "field,value",
    [
        ("reason", "SELECTED_RANDOM"),
        ("selected", True),
        ("candidate_id", 99),
    ],
)
def test_each_decision_field_is_checked_against_recomputation(corrupt_factory, field, value):
    factory = corrupt_factory
    with factory.kw["bind"].begin() as connection:
        payload = json.loads(
            connection.scalar(
                text(
                    "SELECT result_payload FROM telegram_intake_selection_windows WHERE sequence=2"
                )
            )
        )
        payload["decisions"][0][field] = value
        connection.execute(
            text(
                "UPDATE telegram_intake_selection_windows SET result_payload=:value WHERE sequence=2"
            ),
            {"value": json.dumps(payload, sort_keys=True, separators=(",", ":"))},
        )
    before = history(factory)
    with factory.begin() as session, pytest.raises(IntakeLedgerCorrupt):
        load(session, window_key="e" * 64)
    assert history(factory) == before
