"""Encrypted exact requests; legacy intent history is never fabricated."""

import sqlalchemy as sa

from alembic import op

revision = "b7e426d9ab15"
down_revision = "a6d315c8fa04"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "publication_request_snapshots",
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("publication_jobs.id"), primary_key=True),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("encrypted_envelope", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(binding_sha256) = 64", name="ck_publication_snapshot_binding"),
        sa.CheckConstraint(
            "length(encrypted_envelope) BETWEEN 1 AND 32768", name="ck_publication_snapshot_size"
        ),
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM publication_jobs")) or connection.scalar(
        sa.text("SELECT COUNT(*) FROM publication_request_snapshots")
    ):
        raise RuntimeError("Refusing to discard publication intent/acknowledgement history")
    op.drop_table("publication_request_snapshots")
