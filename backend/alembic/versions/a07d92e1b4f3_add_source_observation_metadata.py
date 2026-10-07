"""Source media/album/update identity; legacy media is unknown, not fabricated."""

import sqlalchemy as sa

from alembic import op

revision = "a07d92e1b4f3"
down_revision = "f04c8b31d9a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "incoming_post_revisions",
        sa.Column("media_type", sa.String(32), nullable=False, server_default="unknown"),
    )
    op.add_column("incoming_post_revisions", sa.Column("album_id", sa.String(100), nullable=True))
    op.add_column(
        "incoming_post_revisions",
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM incoming_post_revisions WHERE media_type <> 'unknown' OR album_id IS NOT NULL OR source_updated_at IS NOT NULL"
        )
    ):
        raise RuntimeError("Refusing to discard source observation identity")
    op.drop_column("incoming_post_revisions", "source_updated_at")
    op.drop_column("incoming_post_revisions", "album_id")
    op.drop_column("incoming_post_revisions", "media_type")
