"""Preserve authenticated exact response observations across status-commit crash."""

import sqlalchemy as sa

from alembic import op

revision = "c8f537eabc26"
down_revision = "b7e426d9ab15"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "publication_delivery_observations",
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("publication_jobs.id"), primary_key=True),
        sa.Column("encrypted_receipt", sa.Text(), nullable=False),
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(encrypted_receipt) BETWEEN 1 AND 4096", name="ck_publication_observation_size"
        ),
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM publication_jobs")) or connection.scalar(
        sa.text("SELECT COUNT(*) FROM publication_delivery_observations")
    ):
        raise RuntimeError("Refusing to discard publication intent/acknowledgement history")
    op.drop_table("publication_delivery_observations")
