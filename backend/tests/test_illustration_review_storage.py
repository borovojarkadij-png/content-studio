"""Append-only migrated synthetic review history is NOT reviewer authentication."""

from dataclasses import asdict

import pytest
from alembic.config import Config
from sqlalchemy import Connection, delete, inspect, select, text, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import DBAPIError
from test_illustration_binding import NOW
from test_illustration_binding import library_store as _library_store
from test_mapping_fanout_dedup import mapping_store as _mapping_store

from alembic import command
from newsflow.persistence import models
from newsflow.services.illustration_binding import IllustrationBindingResolver

library_store = _library_store
mapping_store = _mapping_store


def record(factory, root, **changes):
    # Owned fixture rows only. There is deliberately no application writer/API
    # that turns this synthetic provenance label into authenticated approval.
    with factory() as session:
        binding = IllustrationBindingResolver(session, root).resolve(1)
    values = {
        **asdict(binding),
        "operation_key": "synthetic-illustration-review-1",
        "record_kind": "REVIEW",
        "revokes_review_id": None,
        "reviewer_id": 41,
        "provenance": "AUTHENTICATED_HUMAN_V1",
        "verdict": "APPROVED_ILLUSTRATION",
        "illustration_acknowledged": True,
        "review_note": "Synthetic topic illustration, not an event photograph",
        "reviewed_at": NOW,
    }
    values.update(changes)
    return models.IllustrationReviewRecordModel(**values)


def test_review_and_revocation_preserve_exact_history_on_sql_reopen(library_store):
    factory, root, _ = library_store
    original = record(factory, root)
    expected_note = original.review_note
    with factory.begin() as session:
        session.add(original)
    revocation = record(
        factory,
        root,
        operation_key="synthetic-illustration-revoke-1",
        record_kind="REVOCATION",
        revokes_review_id=1,
        verdict=None,
        illustration_acknowledged=None,
        reviewer_id=42,
        review_note="Synthetic human revocation",
    )
    with factory.begin() as session:
        session.add(revocation)
    with factory() as session:
        rows = session.scalars(
            select(models.IllustrationReviewRecordModel).order_by(
                models.IllustrationReviewRecordModel.id
            )
        ).all()
        assert [row.record_kind for row in rows] == ["REVIEW", "REVOCATION"]
        assert rows[0].verdict == "APPROVED_ILLUSTRATION"
        assert rows[0].reviewer_id == 41 and rows[1].reviewer_id == 42
        assert rows[1].revokes_review_id == rows[0].id
        assert rows[0].asset_metadata_sha256 == rows[1].asset_metadata_sha256
        assert rows[0].draft_sha256 == rows[1].draft_sha256
        assert rows[0].review_note == expected_note


@pytest.mark.parametrize("conflict", ["id", "operation_key", "revokes_review_id"])
def test_native_insert_replace_cannot_erase_existing_history(library_store, conflict):
    factory, root, _ = library_store
    with factory.begin() as session:
        session.add(record(factory, root))
    replacement = record(factory, root, review_note="Replacement attempt")
    retained_id = 1
    expected_note = "Synthetic topic illustration, not an event photograph"
    if conflict == "revokes_review_id":
        revocation = record(
            factory,
            root,
            record_kind="REVOCATION",
            revokes_review_id=1,
            verdict=None,
            illustration_acknowledged=None,
            operation_key="first-revocation",
            review_note="Synthetic revocation",
        )
        with factory.begin() as session:
            session.add(revocation)
        replacement = record(
            factory,
            root,
            record_kind="REVOCATION",
            revokes_review_id=1,
            verdict=None,
            illustration_acknowledged=None,
            operation_key="replacement-revocation",
            review_note="Replacement attempt",
        )
        retained_id, expected_note = 2, "Synthetic revocation"
    values = {
        column.name: getattr(replacement, column.name)
        for column in models.IllustrationReviewRecordModel.__table__.columns
        if column.name not in {"id", "created_at"}
    }
    if conflict == "id":
        values.update(id=1, operation_key="different-operation-key")
    with factory() as session:
        table = models.IllustrationReviewRecordModel.__table__
        if session.get_bind().dialect.name == "sqlite":
            statement = table.insert().prefix_with("OR REPLACE").values(**values)
        else:
            statement = (
                postgres_insert(table)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[conflict], set_={"review_note": "Replacement attempt"}
                )
            )
        with pytest.raises(DBAPIError):
            session.execute(statement)
        session.rollback()
    with factory() as session:
        assert (
            session.get(models.IllustrationReviewRecordModel, retained_id).review_note
            == expected_note
        )


@pytest.mark.parametrize("operation", ["orm_update", "raw_update", "orm_delete", "raw_delete"])
def test_committed_review_cannot_be_overwritten_or_deleted(library_store, operation):
    factory, root, _ = library_store
    with factory.begin() as session:
        session.add(record(factory, root))
    model = models.IllustrationReviewRecordModel
    with factory() as session:
        with pytest.raises(DBAPIError):
            if operation == "orm_update":
                session.get(model, 1).verdict = "REJECTED"
            elif operation == "raw_update":
                session.execute(update(model).values(review_note="Overwrite attempt"))
            elif operation == "orm_delete":
                session.delete(session.get(model, 1))
            else:
                session.execute(delete(model))
            session.flush()
        session.rollback()
    with factory() as session:
        retained = session.get(model, 1)
        assert retained is not None and retained.verdict == "APPROVED_ILLUSTRATION"
        assert retained.review_note == "Synthetic topic illustration, not an event photograph"


@pytest.mark.parametrize(
    "changes",
    [
        {"reviewer_id": 0},
        {"candidate_id": 0},
        {"output_channel_id": 0},
        {"mapping_id": 0},
        {"source_revision_id": 0},
        {"rewrite_output_id": 0},
        {"media_asset_id": 0},
        {"record_kind": "MODEL_APPROVAL"},
        {"provenance": "CLIENT_CLAIM"},
        {"verdict": "PASS"},
        {"verdict": None},
        {"illustration_acknowledged": False},
        {"review_note": "   "},
        {"review_note": "x" * 2049},
        {"operation_key": ""},
        {"source_sha256": "bad"},
        {"source_sha256": "z" * 64},
        {"draft_sha256": "A" * 64},
        {"draft_sha256": "bad"},
        {"media_sha256": "bad"},
        {"asset_metadata_sha256": "bad"},
        {"revokes_review_id": 1},
        {"record_kind": "REVOCATION"},
        {
            "record_kind": "REVOCATION",
            "revokes_review_id": 1,
            "verdict": None,
            "illustration_acknowledged": None,
        },
    ],
)
def test_migrated_review_row_constraints_refuse_invalid_evidence(library_store, changes):
    factory, root, _ = library_store
    value = record(factory, root, **changes)
    with factory() as session:
        session.add(value)
        with pytest.raises(DBAPIError):
            session.flush()
        session.rollback()
    with factory() as session:
        assert session.scalar(select(models.IllustrationReviewRecordModel)) is None


def test_downgrade_refuses_to_erase_populated_review_history(library_store):
    factory, root, _ = library_store
    with factory.begin() as session:
        session.add(record(factory, root))
    config = Config("alembic.ini")
    with pytest.raises(RuntimeError, match="illustration review history"):
        command.downgrade(config, "a8d310f62c94")
    with factory() as session:
        assert session.get(models.IllustrationReviewRecordModel, 1).reviewer_id == 41
        assert "illustration_review_records" in inspect(session.get_bind()).get_table_names()


def test_review_insert_rollback_never_leaves_partial_history(library_store):
    factory, root, _ = library_store
    value = record(factory, root)
    with factory() as session:
        session.add(value)
        session.flush()
        session.rollback()
    with factory() as session:
        assert session.scalar(select(models.IllustrationReviewRecordModel)) is None


def test_downgrade_locks_empty_history_before_count_and_drop(library_store, monkeypatch):
    factory, root, _ = library_store
    pending = record(factory, root)
    original_scalar = Connection.scalar
    observed = []

    def after_empty_count(connection, statement, *args, **kwargs):
        count = original_scalar(connection, statement, *args, **kwargs)
        if str(statement).strip() == "SELECT COUNT(*) FROM illustration_review_records":
            assert count == 0
            with factory() as writer:
                if writer.get_bind().dialect.name == "sqlite":
                    writer.connection().exec_driver_sql("PRAGMA busy_timeout=0")
                else:
                    writer.execute(text("SET LOCAL lock_timeout = '100ms'"))
                writer.add(pending)
                try:
                    writer.commit()
                except DBAPIError:
                    writer.rollback()
                    observed.append("blocked")
                else:
                    observed.append("committed")
        return count

    monkeypatch.setattr(Connection, "scalar", after_empty_count)
    command.downgrade(Config("alembic.ini"), "a8d310f62c94")
    assert observed == ["blocked"]
    with factory() as session:
        assert "illustration_review_records" not in inspect(session.get_bind()).get_table_names()
    # Empty history can be upgraded again without changing existing canonical
    # source/draft/media state. No production migration or row is used here.
    command.upgrade(Config("alembic.ini"), "head")
    with factory() as session:
        assert IllustrationBindingResolver(session, root).resolve(1).candidate_id == 1


def test_postgresql_truncate_cannot_clear_owned_review_history(library_store):
    factory, root, _ = library_store
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Real TRUNCATE requires the strict isolated PostgreSQL CI namespace")
    with factory.begin() as session:
        session.add(record(factory, root))
    with factory() as session:
        with pytest.raises(DBAPIError):
            session.execute(text("TRUNCATE TABLE illustration_review_records"))
        session.rollback()
    with factory() as session:
        assert session.get(models.IllustrationReviewRecordModel, 1).reviewer_id == 41


@pytest.mark.parametrize(
    "mismatch",
    ["source_sha256", "draft_sha256", "asset_metadata_sha256", "mapping_id", "parent_kind"],
)
def test_revocation_requires_exact_original_review_binding(library_store, mismatch):
    factory, root, _ = library_store
    with factory.begin() as session:
        session.add(record(factory, root))
    changes = {}
    parent = 1
    if mismatch == "parent_kind":
        with factory.begin() as session:
            session.add(
                record(
                    factory,
                    root,
                    record_kind="REVOCATION",
                    revokes_review_id=1,
                    verdict=None,
                    illustration_acknowledged=None,
                    operation_key="synthetic-first-revocation",
                )
            )
        parent = 2
    else:
        changes[mismatch] = 2 if mismatch == "mapping_id" else "0" * 64
    value = record(
        factory,
        root,
        record_kind="REVOCATION",
        revokes_review_id=parent,
        verdict=None,
        illustration_acknowledged=None,
        operation_key="mismatched-revocation",
        **changes,
    )
    with factory() as session:
        session.add(value)
        with pytest.raises(DBAPIError):
            session.flush()
        session.rollback()


@pytest.mark.parametrize(
    "reference",
    [
        "candidate_id",
        "output_channel_id",
        "mapping_id",
        "source_revision_id",
        "rewrite_output_id",
        "media_asset_id",
    ],
)
def test_review_insert_refuses_dangling_positive_canonical_reference(library_store, reference):
    factory, root, _ = library_store
    value = record(factory, root, **{reference: 9999})
    with factory() as session:
        session.add(value)
        with pytest.raises(DBAPIError):
            session.flush()
        session.rollback()
    with factory() as session:
        assert session.scalar(select(models.IllustrationReviewRecordModel)) is None


@pytest.mark.parametrize("verdict", ["REJECTED", "UNCERTAIN"])
@pytest.mark.parametrize("acknowledgment", [2, -1])
def test_raw_nonboolean_acknowledgment_cannot_be_reinterpreted_as_true(
    library_store, verdict, acknowledgment
):
    factory, root, _ = library_store
    with factory.begin() as session:
        session.add(record(factory, root))
    columns = [
        column.name
        for column in models.IllustrationReviewRecordModel.__table__.columns
        if column.name not in {"id", "created_at"}
    ]
    selected = [
        {
            "operation_key": ":operation",
            "verdict": ":verdict",
            "illustration_acknowledged": ":ack",
        }.get(column, column)
        for column in columns
    ]
    # Raw SQL deliberately bypasses SQLAlchemy Boolean's input validation.
    # The table must refuse invalid persisted booleans before any ORM decode.
    statement = text(
        f"INSERT INTO illustration_review_records ({', '.join(columns)}) "
        f"SELECT {', '.join(selected)} FROM illustration_review_records WHERE id = 1"
    )
    with factory() as session:
        with pytest.raises(DBAPIError):
            session.execute(
                statement,
                {"operation": "invalid-raw-ack", "verdict": verdict, "ack": acknowledgment},
            )
        session.rollback()
    with factory() as session:
        assert [
            row.id for row in session.scalars(select(models.IllustrationReviewRecordModel))
        ] == [1]


@pytest.mark.parametrize("reviewer", ["anonymous", "0.5", "1.5"])
def test_raw_noninteger_reviewer_cannot_enter_immutable_history(library_store, reviewer):
    factory, root, _ = library_store
    with factory.begin() as session:
        session.add(record(factory, root))
    columns = [
        column.name
        for column in models.IllustrationReviewRecordModel.__table__.columns
        if column.name not in {"id", "created_at"}
    ]
    selected = [
        {"operation_key": ":operation", "reviewer_id": ":reviewer"}.get(column, column)
        for column in columns
    ]
    # SQLite integer affinity does not itself exclude text or fractional values.
    # Exercise actual raw persisted input, not SQLAlchemy's input conversion.
    statement = text(
        f"INSERT INTO illustration_review_records ({', '.join(columns)}) "
        f"SELECT {', '.join(selected)} FROM illustration_review_records WHERE id = 1"
    )
    with factory() as session:
        with pytest.raises(DBAPIError):
            session.execute(statement, {"operation": "invalid-reviewer", "reviewer": reviewer})
        session.rollback()
    with factory() as session:
        assert [
            row.reviewer_id for row in session.scalars(select(models.IllustrationReviewRecordModel))
        ] == [41]
