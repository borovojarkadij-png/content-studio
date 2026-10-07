"""add mapping delivery, priority and media policies

Revision ID: b8e2c1f4d930
Revises: f3a9c2e84d71
"""

import sqlalchemy as sa

from alembic import op

revision = "b8e2c1f4d930"
down_revision = "f3a9c2e84d71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The prior table has unnamed SQLite checks. batch_alter_table recreates it,
    # so restate and name them or the upgrade would silently weaken validation.
    with op.batch_alter_table(
        "channel_mappings",
        table_args=(
            sa.CheckConstraint(
                "intake_percent BETWEEN 0 AND 100", name="ck_mapping_intake_percent"
            ),
            sa.CheckConstraint(
                "target_mix_percent BETWEEN 0 AND 100",
                name="ck_mapping_target_mix_percent",
            ),
        ),
    ) as batch:
        batch.add_column(
            sa.Column(
                "eligibility_mode",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'IMMEDIATE'"),
            )
        )
        batch.add_column(
            sa.Column(
                "delay_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")
            )
        )
        batch.add_column(
            sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch.add_column(
            sa.Column(
                "media_policy",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'REUSE_SOURCE'"),
            )
        )
        batch.create_check_constraint(
            "ck_mapping_eligibility_mode",
            "eligibility_mode IN ('IMMEDIATE', 'DELAYED')",
        )
        batch.create_check_constraint(
            "ck_mapping_delay_minutes",
            "delay_minutes BETWEEN 0 AND 10080",
        )
        batch.create_check_constraint(
            "ck_immediate_mapping_has_no_delay",
            "eligibility_mode <> 'IMMEDIATE' OR delay_minutes = 0",
        )
        batch.create_check_constraint("ck_mapping_priority", "priority BETWEEN -1000 AND 1000")
        batch.create_check_constraint(
            "ck_mapping_media_policy",
            "media_policy IN ('REUSE_SOURCE', 'LICENSED_LIBRARY')",
        )


def downgrade() -> None:
    with op.batch_alter_table("channel_mappings") as batch:
        batch.drop_constraint("ck_mapping_media_policy", type_="check")
        batch.drop_constraint("ck_mapping_priority", type_="check")
        batch.drop_constraint("ck_immediate_mapping_has_no_delay", type_="check")
        batch.drop_constraint("ck_mapping_delay_minutes", type_="check")
        batch.drop_constraint("ck_mapping_eligibility_mode", type_="check")
        batch.drop_column("media_policy")
        batch.drop_column("priority")
        batch.drop_column("delay_minutes")
        batch.drop_column("eligibility_mode")
