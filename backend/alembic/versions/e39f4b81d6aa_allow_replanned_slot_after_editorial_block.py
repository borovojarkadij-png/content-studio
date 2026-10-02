"""allow a re-planned slot after editorial block

Revision ID: e39f4b81d6aa
Revises: d12e5f93a7c4
"""

from alembic import op

revision = "e39f4b81d6aa"
down_revision = "d12e5f93a7c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("planned_publications") as batch:
            batch.drop_constraint("uq_planned_publication_slot", type_="unique")
            batch.create_unique_constraint(
                "uq_planned_publication_slot_state", ["output_channel_id", "scheduled_for", "state"]
            )
        return
    op.drop_constraint("uq_planned_publication_slot", "planned_publications", type_="unique")
    op.create_unique_constraint(
        "uq_planned_publication_slot_state",
        "planned_publications",
        ["output_channel_id", "scheduled_for", "state"],
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("planned_publications") as batch:
            batch.drop_constraint("uq_planned_publication_slot_state", type_="unique")
            batch.create_unique_constraint(
                "uq_planned_publication_slot", ["output_channel_id", "scheduled_for"]
            )
        return
    op.drop_constraint("uq_planned_publication_slot_state", "planned_publications", type_="unique")
    op.create_unique_constraint(
        "uq_planned_publication_slot",
        "planned_publications",
        ["output_channel_id", "scheduled_for"],
    )
