import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def test_configuration_schema_upgrade_creates_pending_import_storage(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'configuration-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {
            "donor_imports",
            "publication_plans",
            "publication_candidates",
            "planned_publications",
            "rewrite_provider_settings",
            "rewrite_outputs",
            "media_assets",
        } <= set(inspector.get_table_names())
        columns = {column["name"] for column in inspector.get_columns("donor_imports")}
        assert columns == {"id", "telegram_account_id", "identifier", "status"}
        assert any(
            index["column_names"] == ["telegram_account_id"]
            for index in inspector.get_indexes("donor_imports")
        )
        assert any(
            index["column_names"] == ["output_channel_id"]
            for index in inspector.get_indexes("publication_plans")
        )
        rewrite_job_columns = {column["name"] for column in inspector.get_columns("rewrite_jobs")}
        assert "output_channel_id" in rewrite_job_columns
        assert any(
            index["column_names"] == ["output_channel_id"]
            for index in inspector.get_indexes("rewrite_jobs")
        )
        provider_columns = {
            column["name"] for column in inspector.get_columns("rewrite_provider_settings")
        }
        assert provider_columns == {
            "provider",
            "encrypted_api_key",
            "primary_model",
            "fallback_models",
            "updated_at",
        }
        mapping_columns = {column["name"] for column in inspector.get_columns("channel_mappings")}
        assert {
            "eligibility_mode",
            "delay_minutes",
            "priority",
            "media_policy",
        } <= mapping_columns
        candidate_columns = {
            column["name"] for column in inspector.get_columns("publication_candidates")
        }
        assert {"mapping_id", "eligible_at", "media_policy"} <= candidate_columns
        rewrite_output_columns = {
            column["name"] for column in inspector.get_columns("rewrite_outputs")
        }
        assert {
            "rewrite_job_id",
            "output_channel_id",
            "content_key",
            "rewritten_text",
            "approval_state",
        } <= rewrite_output_columns
    finally:
        engine.dispose()

    command.downgrade(config, "a2c5e8f1b7d4")
    command.upgrade(config, "head")


def test_rewrite_job_scope_migration_preserves_a_legacy_unmapped_job(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'rewrite-job-scope.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "f51c8a04b2de")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO rewrite_jobs (content_key, idempotency_key, state) "
                    "VALUES ('legacy:1', 'rewrite.requested:legacy:1', 'DISPATCHED')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT content_key, output_channel_id FROM rewrite_jobs")
            ).one()
        assert row == ("legacy:1", None)
    finally:
        engine.dispose()

    command.downgrade(config, "f51c8a04b2de")


@pytest.mark.parametrize(
    "decision,second_state,outputs",
    [
        (("PASS", True, "", "neutral", "neutral"), "AWAITING_REWRITE", [1, 2]),
        (("REJECT", False, "", "neutral", "neutral"), "AWAITING_REWRITE", []),
        (("MANUAL_REVIEW", False, "", "unknown", "unknown"), "AWAITING_REWRITE", []),
        (None, "AWAITING_REWRITE", []),
        (("PASS", True, "protected", "negative", "hostile"), "AWAITING_REWRITE", []),
        (("PASS", True, "", "unknown", "neutral"), "AWAITING_REWRITE", []),
        (("PASS", False, "", "neutral", "neutral"), "AWAITING_REWRITE", []),
        (("PASS", True, "", "neutral", "neutral"), "BLOCKED_EDITORIAL", [1]),
    ],
)
def test_rewrite_job_scope_migration_requeues_each_legacy_fanout_output(
    tmp_path, decision, second_state, outputs
) -> None:
    database_url = f"sqlite:///{tmp_path / 'rewrite-job-fanout.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "f51c8a04b2de")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO telegram_accounts "
                    "(id, name, telegram_user_id, encrypted_session, health_status) "
                    "VALUES (1, 'Primary', 1001, '', 'DISCONNECTED')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO output_channels "
                    "(id, telegram_account_id, telegram_channel_id, title) VALUES "
                    "(1, 1, -1001234567890, 'First'), (2, 1, -1009876543210, 'Second')"
                )
            )
            for output_channel_id in (1, 2):
                connection.execute(
                    text(
                        "INSERT INTO publication_candidates "
                        "(output_channel_id, content_key, priority, state) "
                        "VALUES (:output_channel_id, 'legacy:fanout', 0, :state)"
                    ),
                    {
                        "output_channel_id": output_channel_id,
                        "state": "AWAITING_REWRITE" if output_channel_id == 1 else second_state,
                    },
                )
            if decision is not None:
                connection.execute(
                    text(
                        "INSERT INTO editorial_decisions "
                        "(content_key,status,rewrite_allowed,reason_codes,protected_entities,"
                        "sentiment,framing) VALUES ('legacy:fanout',:status,:allowed,'',"
                        ":entities,:sentiment,:framing)"
                    ),
                    dict(zip(("status", "allowed", "entities", "sentiment", "framing"), decision)),
                )
            connection.execute(
                text(
                    "INSERT INTO rewrite_jobs (content_key, idempotency_key, state) "
                    "VALUES ('legacy:fanout', 'rewrite.requested:legacy:fanout', 'SUCCEEDED')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO outbox_events (event_type, aggregate_key, idempotency_key) "
                    "VALUES ('rewrite.requested', 'legacy:fanout', 'rewrite.requested:legacy:fanout')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            jobs = connection.execute(
                text(
                    "SELECT output_channel_id, state FROM rewrite_jobs "
                    "WHERE content_key = 'legacy:fanout' ORDER BY output_channel_id"
                )
            ).all()
            events = connection.execute(
                text(
                    "SELECT event_type, idempotency_key FROM outbox_events "
                    "WHERE aggregate_key = 'legacy:fanout' ORDER BY idempotency_key"
                )
            ).all()
        assert jobs == [(None, "SUPERSEDED"), *[(value, "DISPATCHED") for value in outputs]]
        assert events == [
            ("rewrite.superseded", "rewrite.requested:legacy:fanout"),
            *[
                ("rewrite.requested", f"rewrite.requested:legacy:fanout:{value}")
                for value in outputs
            ],
        ]
    finally:
        engine.dispose()

    if outputs:
        with pytest.raises(RuntimeError, match="Unsafe downgrade"):
            command.downgrade(config, "f51c8a04b2de")


def test_mapping_policy_migration_keeps_existing_percentage_constraints(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'mapping-policy-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "f3a9c2e84d71")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO telegram_accounts "
                    "(id, name, telegram_user_id, encrypted_session, health_status) "
                    "VALUES (1, 'Primary', 1001, '', 'DISCONNECTED')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO donor_channels "
                    "(id, telegram_account_id, telegram_channel_id, title) "
                    "VALUES (1, 1, -1001234567890, 'Source')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO output_channels "
                    "(id, telegram_account_id, telegram_channel_id, title) "
                    "VALUES (1, 1, -1009876543210, 'Destination')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO channel_mappings "
                    "(id, donor_channel_id, output_channel_id, intake_percent, target_mix_percent) "
                    "VALUES (1, 1, 1, 50, 50)"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                text("UPDATE channel_mappings SET intake_percent = 101 WHERE id = 1")
            )
    finally:
        engine.dispose()
