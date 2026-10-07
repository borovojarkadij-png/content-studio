"""Durable bounded read-only donor import resolution."""

import sqlalchemy as sa

from alembic import op

revision = "d3a085f4c7e6"
down_revision = "c29f74e3b6d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "donor_import_resolution_jobs",
        sa.Column("donor_import_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("resolved_donor_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["donor_import_id"], ["donor_imports.id"]),
        sa.ForeignKeyConstraint(["resolved_donor_id"], ["donor_channels.id"]),
        sa.PrimaryKeyConstraint("donor_import_id"),
        sa.CheckConstraint("state IN ('QUEUED', 'RUNNING', 'RETRY', 'RESOLVED', 'INVALID')"),
        sa.CheckConstraint(
            "(claim_token IS NULL AND lease_expires_at IS NULL) OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
        sa.CheckConstraint(
            "(state = 'RESOLVED' AND resolved_donor_id IS NOT NULL) OR (state <> 'RESOLVED' AND resolved_donor_id IS NULL)"
        ),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM donor_import_resolution_jobs")):
        raise RuntimeError("Refusing to discard durable donor resolution history")
    op.drop_table("donor_import_resolution_jobs")
