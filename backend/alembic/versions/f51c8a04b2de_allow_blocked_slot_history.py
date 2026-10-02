"""allow blocked publication-slot history while preserving active exclusivity

Revision ID: f51c8a04b2de
Revises: e39f4b81d6aa
"""

from alembic import op
import sqlalchemy as sa


revision = "f51c8a04b2de"
down_revision = "e39f4b81d6aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("planned_publications") as batch:
            batch.drop_constraint("uq_planned_publication_slot_state", type_="unique")
        op.create_index(
            "uq_planned_publication_active_slot",
            "planned_publications",
            ["output_channel_id", "scheduled_for"],
            unique=True,
            sqlite_where=sa.text("state = 'PLANNED'"),
        )
        return
    op.drop_constraint("uq_planned_publication_slot_state", "planned_publications", type_="unique")
    op.create_index(
        "uq_planned_publication_active_slot",
        "planned_publications",
        ["output_channel_id", "scheduled_for"],
        unique=True,
        postgresql_where=sa.text("state = 'PLANNED'"),
    )


def downgrade() -> None:
    conflicts = op.get_bind().execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT output_channel_id, scheduled_for FROM planned_publications "
            "WHERE state = 'BLOCKED_EDITORIAL' "
            "GROUP BY output_channel_id, scheduled_for HAVING COUNT(*) > 1"
            ") AS blocked_slot_conflicts"
        )
    ).scalar_one()
    if conflicts:
        raise RuntimeError("Unsafe downgrade: multiple blocked reservations share a historical slot")
    op.drop_index("uq_planned_publication_active_slot", table_name="planned_publications")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("planned_publications") as batch:
            batch.create_unique_constraint(
                "uq_planned_publication_slot_state", ["output_channel_id", "scheduled_for", "state"]
            )
        return
    op.create_unique_constraint(
        "uq_planned_publication_slot_state",
        "planned_publications",
        ["output_channel_id", "scheduled_for", "state"],
    )
