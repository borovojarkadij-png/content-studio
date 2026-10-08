"""Retain observed hidden destinations; legacy metadata is unknown, not empty."""

import sqlalchemy as sa

from alembic import op

revision = "a8d310f62c94"
down_revision = "eab7590cde48"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "incoming_post_revisions",
        sa.Column("link_destinations", sa.JSON(none_as_null=True), nullable=True),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM incoming_post_revisions WHERE link_destinations IS NOT NULL")
    ):
        raise RuntimeError("Refusing to discard observed source link metadata")
    op.drop_column("incoming_post_revisions", "link_destinations")
