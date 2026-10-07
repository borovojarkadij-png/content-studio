"""add immutable local media identities, rights and search metadata

Revision ID: e82a9c7b3061
Revises: d7a1e4c2b805
"""

import sqlalchemy as sa

from alembic import op

revision = "e82a9c7b3061"
down_revision = "d7a1e4c2b805"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(32), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("source_content_key", sa.String(255), nullable=True),
        sa.Column("license_code", sa.String(16), nullable=False),
        sa.Column("attribution", sa.String(2048), nullable=False),
        sa.Column("tags", sa.String(2048), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "origin IN ('SOURCE', 'LICENSED_LIBRARY')", name="ck_media_asset_origin"
        ),
        sa.CheckConstraint(
            "license_code IN ('OWNED', 'PERMISSION', 'CC0', 'CC-BY')", name="ck_media_asset_license"
        ),
        sa.CheckConstraint("mime_type IN ('image/png', 'image/jpeg')", name="ck_media_asset_mime"),
        sa.CheckConstraint(
            "origin <> 'SOURCE' OR (source_content_key IS NOT NULL AND license_code IN ('OWNED', 'PERMISSION'))",
            name="ck_media_source_rights",
        ),
        sa.CheckConstraint(
            "origin <> 'LICENSED_LIBRARY' OR source_content_key IS NULL",
            name="ck_media_library_source",
        ),
        sa.CheckConstraint(
            "license_code NOT IN ('PERMISSION', 'CC-BY') OR length(attribution) > 0",
            name="ck_media_asset_attribution",
        ),
    )
    op.create_index("ix_media_assets_origin", "media_assets", ["origin"])
    op.create_index("ix_media_assets_source_content_key", "media_assets", ["source_content_key"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM media_assets")):
        raise RuntimeError(
            "Cannot downgrade populated media registry; preserve rights metadata first"
        )
    op.drop_index("ix_media_assets_source_content_key", table_name="media_assets")
    op.drop_index("ix_media_assets_origin", table_name="media_assets")
    op.drop_table("media_assets")
