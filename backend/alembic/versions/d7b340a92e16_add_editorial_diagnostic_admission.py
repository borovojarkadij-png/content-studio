"""Retain diagnostic classification bindings; no runtime provider activation."""

import sqlalchemy as sa

from alembic import op

revision = "d7b340a92e16"
down_revision = "c5e81b29a704"
branch_labels = None
depends_on = None

BINDING = (
    "content_key",
    "source_revision_id",
    "mapping_id",
    "editorial_decision_id",
    "source_sha256",
    "policy_sha256",
    "mapping_sha256",
    "prompt_version",
    "provider",
    "model",
    "idempotency_key",
)


def _digest(column):
    remaining = column
    for character in "0123456789abcdef":
        remaining = f"replace({remaining}, '{character}', '')"
    return f"length({column}) = 64 AND {remaining} = ''"


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Editorial diagnostic admission requires supported storage")
    op.add_column("mapping_content_fingerprints", sa.Column("content_key", sa.String(255)))
    op.create_table(
        "editorial_classifier_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("policy_version", sa.String(255), nullable=False),
        sa.Column("protected_entities", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_editorial_policy_singleton"),
        sa.CheckConstraint(
            "provider IN ('OPENAI', 'OPENROUTER')", name="ck_editorial_policy_provider"
        ),
        sa.CheckConstraint(
            "length(model) BETWEEN 1 AND 255 AND length(trim(model)) > 0",
            name="ck_editorial_policy_model",
        ),
        sa.CheckConstraint(
            "length(policy_version) BETWEEN 1 AND 255 AND length(trim(policy_version)) > 0",
            name="ck_editorial_policy_version",
        ),
    )
    op.create_table(
        "editorial_classification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_key", sa.String(255), nullable=False),
        sa.Column(
            "source_revision_id",
            sa.Integer(),
            sa.ForeignKey("incoming_post_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mapping_id",
            sa.Integer(),
            sa.ForeignKey("channel_mappings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "editorial_decision_id",
            sa.Integer(),
            sa.ForeignKey("editorial_decisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        *(
            sa.Column(name, sa.String(64), nullable=False)
            for name in ("source_sha256", "policy_sha256", "mapping_sha256", "prompt_version")
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(64)),
        sa.UniqueConstraint(
            "source_revision_id",
            "mapping_id",
            "policy_sha256",
            "mapping_sha256",
            "provider",
            "model",
            "prompt_version",
            name="uq_editorial_job_binding",
        ),
        sa.CheckConstraint(
            "state IN ('QUEUED', 'RUNNING', 'REVIEW', 'REJECT', 'BLOCKED', 'FAILED')",
            name="ck_editorial_job_state",
        ),
        sa.CheckConstraint(
            "provider IN ('OPENAI', 'OPENROUTER')", name="ck_editorial_job_provider"
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 2", name="ck_editorial_job_attempts"),
        sa.CheckConstraint(
            "(state = 'RUNNING' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(state <> 'RUNNING' AND claim_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_editorial_job_lease",
        ),
        sa.CheckConstraint(
            "length(content_key) BETWEEN 1 AND 255 AND length(trim(content_key)) > 0",
            name="ck_editorial_job_content",
        ),
        sa.CheckConstraint(
            "length(model) BETWEEN 1 AND 255 AND length(trim(model)) > 0",
            name="ck_editorial_job_model",
        ),
        sa.CheckConstraint(
            "length(prompt_version) BETWEEN 1 AND 64 AND length(trim(prompt_version)) > 0",
            name="ck_editorial_job_prompt",
        ),
        sa.CheckConstraint(
            "claim_token IS NULL OR length(claim_token) = 36", name="ck_editorial_job_token"
        ),
        sa.CheckConstraint(
            "last_error_code IS NULL OR length(last_error_code) BETWEEN 1 AND 64",
            name="ck_editorial_job_error",
        ),
        *(
            sa.CheckConstraint(_digest(name), name=f"ck_editorial_job_{name}")
            for name in ("source_sha256", "policy_sha256", "mapping_sha256", "idempotency_key")
        ),
    )
    if dialect == "sqlite":
        changed = " OR ".join(f"NEW.{name} IS NOT OLD.{name}" for name in BINDING)
        op.execute(
            "CREATE TRIGGER editorial_job_binding_immutable BEFORE UPDATE ON "
            "editorial_classification_jobs WHEN "
            + changed
            + " BEGIN SELECT RAISE(ABORT, 'Editorial diagnostic binding is immutable'); END"
        )
    else:
        changed = " OR ".join(f"NEW.{name} IS DISTINCT FROM OLD.{name}" for name in BINDING)
        op.execute(
            "CREATE FUNCTION editorial_job_binding_immutable() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN IF "
            + changed
            + " THEN RAISE EXCEPTION 'Editorial diagnostic binding is immutable'; "
            "END IF; RETURN NEW; END $$"
        )
        op.execute(
            "CREATE TRIGGER editorial_job_binding_immutable BEFORE UPDATE ON "
            "editorial_classification_jobs FOR EACH ROW "
            "EXECUTE FUNCTION editorial_job_binding_immutable()"
        )


def downgrade():
    connection = op.get_bind()
    # Check BOTH tables before any DDL. Even a disabled policy is retained history.
    for table in ("editorial_classification_jobs", "editorial_classifier_policy"):
        if connection.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError("Refusing downgrade: editorial diagnostic history is populated")
    op.drop_table("editorial_classification_jobs")
    if connection.dialect.name == "postgresql":
        op.execute("DROP FUNCTION editorial_job_binding_immutable()")
    op.drop_table("editorial_classifier_policy")
    # Only on an isolated copy: owned fingerprint evidence is lost on downgrade.
    op.drop_column("mapping_content_fingerprints", "content_key")
