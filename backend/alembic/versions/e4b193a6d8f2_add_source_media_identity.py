"""Preserve media identity/protection; legacy unknowns are never fabricated."""

import sqlalchemy as sa

from alembic import op

revision = "e4b193a6d8f2"
down_revision = "d3a085f4c7e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("incoming_post_revisions", sa.Column("media_id", sa.String(20), nullable=True))
    op.add_column(
        "incoming_post_revisions", sa.Column("media_protected", sa.Boolean(), nullable=True)
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM incoming_post_revisions WHERE media_id IS NOT NULL OR media_protected IS NOT NULL"
        )
    ):
        raise RuntimeError("Refusing to discard source media identity")
    op.drop_column("incoming_post_revisions", "media_protected")
    op.drop_column("incoming_post_revisions", "media_id")
