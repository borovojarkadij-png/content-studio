"""snapshot mapping delivery policy on publication candidates

Revision ID: c4e6b2a891d3
Revises: b8e2c1f4d930
"""

import sqlalchemy as sa

from alembic import op

revision = "c4e6b2a891d3"
down_revision = "b8e2c1f4d930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("publication_candidates") as batch:
        batch.add_column(sa.Column("mapping_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "eligible_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            )
        )
        batch.add_column(
            sa.Column(
                "media_policy",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'REUSE_SOURCE'"),
            )
        )
        batch.create_foreign_key(
            "fk_publication_candidate_mapping",
            "channel_mappings",
            ["mapping_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_candidate_media_policy",
            "media_policy IN ('REUSE_SOURCE', 'LICENSED_LIBRARY')",
        )
    op.create_index(
        op.f("ix_publication_candidates_mapping_id"),
        "publication_candidates",
        ["mapping_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_publication_candidates_mapping_id"), table_name="publication_candidates")
    with op.batch_alter_table("publication_candidates") as batch:
        batch.drop_constraint("ck_candidate_media_policy", type_="check")
        batch.drop_constraint("fk_publication_candidate_mapping", type_="foreignkey")
        batch.drop_column("media_policy")
        batch.drop_column("eligible_at")
        batch.drop_column("mapping_id")
