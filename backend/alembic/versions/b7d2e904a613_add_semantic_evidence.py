"""Add semantic evidence and default-manual automatic approval policy."""

import sqlalchemy as sa

from alembic import op

revision = "b7d2e904a613"
down_revision = "a91c73bd204e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("rewrite_outputs") as batch:
        batch.add_column(
            sa.Column("approval_method", sa.String(16), nullable=False, server_default="MANUAL")
        )
        batch.create_check_constraint(
            "ck_rewrite_approval_method", "approval_method IN ('MANUAL', 'AUTOMATIC')"
        )
    op.create_table(
        "semantic_verifier_releases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("benchmark_version", sa.String(64), nullable=False),
        sa.Column("report_sha256", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("provider IN ('OPENAI', 'OPENROUTER')"),
        sa.CheckConstraint("length(report_sha256) = 64"),
        sa.UniqueConstraint(
            "provider", "model", "prompt_version", "benchmark_version", "report_sha256"
        ),
    )
    op.create_table(
        "automatic_approval_policies",
        sa.Column(
            "output_channel_id", sa.Integer(), sa.ForeignKey("output_channels.id"), primary_key=True
        ),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column(
            "release_id",
            sa.Integer(),
            sa.ForeignKey("semantic_verifier_releases.id"),
            nullable=True,
        ),
        sa.CheckConstraint("mode IN ('MANUAL', 'VERIFIED')"),
        sa.CheckConstraint("mode <> 'VERIFIED' OR release_id IS NOT NULL"),
    )
    op.create_table(
        "semantic_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "rewrite_output_id", sa.Integer(), sa.ForeignKey("rewrite_outputs.id"), nullable=False
        ),
        sa.Column(
            "source_revision_id",
            sa.Integer(),
            sa.ForeignKey("incoming_post_revisions.id"),
            nullable=False,
        ),
        sa.Column(
            "release_id",
            sa.Integer(),
            sa.ForeignKey("semantic_verifier_releases.id"),
            nullable=False,
        ),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("draft_sha256", sa.String(64), nullable=False),
        sa.Column("release_sha256", sa.String(64), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("reason_codes", sa.String(1024), nullable=False),
        sa.Column("evidence_json", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "rewrite_output_id",
            "release_id",
            "source_sha256",
            "draft_sha256",
            name="uq_semantic_evidence_binding",
        ),
        sa.CheckConstraint("verdict IN ('PRESERVED', 'CHANGED', 'UNCERTAIN', 'ERROR')"),
        sa.CheckConstraint("length(source_sha256) = 64 AND length(draft_sha256) = 64"),
        sa.CheckConstraint("length(release_sha256) = 64"),
    )
    op.create_index(
        "ix_semantic_evidence_rewrite_output_id", "semantic_evidence", ["rewrite_output_id"]
    )


def downgrade():
    connection = op.get_bind()
    if any(
        connection.scalar(sa.text(query))
        for query in (
            "SELECT COUNT(*) FROM semantic_evidence",
            "SELECT COUNT(*) FROM semantic_verifier_releases",
            "SELECT COUNT(*) FROM automatic_approval_policies WHERE mode <> 'MANUAL'",
            "SELECT COUNT(*) FROM rewrite_outputs WHERE approval_method <> 'MANUAL'",
        )
    ):
        raise RuntimeError(
            "Refusing to discard semantic evidence, releases or automatic approval state"
        )
    op.drop_index("ix_semantic_evidence_rewrite_output_id", table_name="semantic_evidence")
    op.drop_table("semantic_evidence")
    op.drop_table("automatic_approval_policies")
    op.drop_table("semantic_verifier_releases")
    with op.batch_alter_table("rewrite_outputs") as batch:
        batch.drop_constraint("ck_rewrite_approval_method", type_="check")
        batch.drop_column("approval_method")
