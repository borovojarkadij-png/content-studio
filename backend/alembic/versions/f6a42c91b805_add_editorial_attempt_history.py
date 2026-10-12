"""Append-only diagnostic claims and receipts; no worker or approval activation."""

import sqlalchemy as sa

from alembic import op

revision = "f6a42c91b805"
down_revision = "d7b340a92e16"
branch_labels = None
depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Editorial attempt history requires supported storage")
    remaining = "replace(claim_token, '-', '')"
    for char in "0123456789abcdef":
        remaining = f"replace({remaining}, '{char}', '')"
    op.create_table(
        "editorial_classification_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "classification_job_id",
            sa.Integer(),
            sa.ForeignKey("editorial_classification_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("claim_token", sa.String(36), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("classification_job_id", "attempt", name="uq_editorial_claim_attempt"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 2", name="ck_editorial_claim_attempt"),
        sa.CheckConstraint(
            "length(claim_token) = 36 AND substr(claim_token,9,1) = '-' "
            "AND substr(claim_token,14,1) = '-' AND substr(claim_token,19,1) = '-' "
            "AND substr(claim_token,24,1) = '-' AND length(replace(claim_token, '-', '')) = 32 "
            f"AND {remaining} = ''",
            name="ck_editorial_claim_token",
        ),
        *(
            [
                sa.CheckConstraint(
                    "typeof(attempt) = 'integer'", name="ck_editorial_claim_attempt_type"
                )
            ]
            if dialect == "sqlite"
            else []
        ),
    )
    op.create_table(
        "editorial_classification_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "claim_id",
            sa.Integer(),
            sa.ForeignKey("editorial_classification_claims.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("diagnostic_status", sa.String(16)),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("response_model", sa.String(255)),
        sa.Column("usage_observed", sa.Boolean(), nullable=False, server_default=sa.false()),
        *(
            sa.Column(name, sa.Integer())
            for name in ("input_tokens", "cached_tokens", "output_tokens")
        ),
        sa.Column("estimated_cost_usd", sa.Numeric(20, 10)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('REVIEW','REJECT','BLOCKED','FAILED','RETRY','LOST_LEASE')",
            name="ck_editorial_attempt_outcome",
        ),
        sa.CheckConstraint(
            "diagnostic_status IS NULL OR diagnostic_status IN ('PASS','REJECT','MANUAL_REVIEW')",
            name="ck_editorial_attempt_diagnostic",
        ),
        sa.CheckConstraint(
            "response_model IS NULL OR (length(response_model) BETWEEN 1 AND 255 AND length(trim(response_model)) > 0)",
            name="ck_editorial_attempt_model",
        ),
        sa.CheckConstraint(
            "(usage_observed = false AND input_tokens IS NULL AND cached_tokens IS NULL "
            "AND output_tokens IS NULL AND estimated_cost_usd IS NULL) OR "
            "(usage_observed = true AND input_tokens IS NOT NULL AND cached_tokens IS NOT NULL "
            "AND output_tokens IS NOT NULL AND input_tokens >= 0 AND cached_tokens >= 0 "
            "AND output_tokens >= 0 AND cached_tokens <= input_tokens)",
            name="ck_editorial_attempt_usage",
        ),
        sa.CheckConstraint(
            "estimated_cost_usd IS NULL OR (estimated_cost_usd >= 0 AND estimated_cost_usd < 10000000000)",
            name="ck_editorial_attempt_cost",
        ),
        *(
            [
                sa.CheckConstraint(
                    "input_tokens IS NULL OR (typeof(input_tokens) = 'integer' AND typeof(cached_tokens) = 'integer' AND typeof(output_tokens) = 'integer')",
                    name="ck_editorial_attempt_token_types",
                ),
                sa.CheckConstraint(
                    "json_type(reason_codes) = 'array'", name="ck_editorial_attempt_reasons_sqlite"
                ),
                sa.CheckConstraint(
                    "evidence_json IS NULL OR length(CAST(evidence_json AS BLOB)) <= 262144",
                    name="ck_editorial_attempt_evidence_sqlite",
                ),
            ]
            if dialect == "sqlite"
            else [
                sa.CheckConstraint(
                    "json_typeof(reason_codes) = 'array'", name="ck_editorial_attempt_reasons_pg"
                ),
                sa.CheckConstraint(
                    "evidence_json IS NULL OR octet_length(evidence_json) <= 262144",
                    name="ck_editorial_attempt_evidence_pg",
                ),
            ]
        ),
    )
    for table, parent_table, parent_column, unique in (
        (
            "editorial_classification_claims",
            "editorial_classification_jobs",
            "classification_job_id",
            "id = NEW.id OR claim_token = NEW.claim_token OR (classification_job_id = NEW.classification_job_id AND attempt = NEW.attempt)",
        ),
        (
            "editorial_classification_attempts",
            "editorial_classification_claims",
            "claim_id",
            "id = NEW.id OR claim_id = NEW.claim_id",
        ),
    ):
        if dialect == "sqlite":
            op.execute(
                f"CREATE TRIGGER {table}_require_parent BEFORE INSERT ON {table} WHEN NOT EXISTS (SELECT 1 FROM {parent_table} WHERE id = NEW.{parent_column}) BEGIN SELECT RAISE(ABORT, 'Editorial claim history parent required'); END"
            )
            op.execute(
                f"CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE {unique}) BEGIN SELECT RAISE(ABORT, 'Editorial history is append-only'); END"
            )
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Editorial history is append-only'); END"
                )
        else:
            op.execute(
                f"CREATE FUNCTION {table}_refuse_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Editorial history is append-only'; END; $$"
            )
            op.execute(
                f"CREATE TRIGGER {table}_no_mutation BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_refuse_mutation()"
            )
            op.execute(
                f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {table}_refuse_mutation()"
            )


def downgrade():
    connection = op.get_bind()
    tables = ("editorial_classification_attempts", "editorial_classification_claims")
    if connection.dialect.name == "postgresql":
        op.execute(
            "LOCK TABLE editorial_classification_claims, editorial_classification_attempts IN ACCESS EXCLUSIVE MODE"
        )
    else:
        op.execute("UPDATE editorial_classification_claims SET id = id WHERE 1 = 0")
    for table in tables:
        if connection.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError(
                "Refusing downgrade: immutable editorial attempt history is populated"
            )
    for table in tables:
        op.drop_table(table)
        if connection.dialect.name == "postgresql":
            op.execute(f"DROP FUNCTION {table}_refuse_mutation()")
