"""add encrypted rewrite provider settings

Revision ID: f3a9c2e84d71
Revises: e7d3a4f810bc
"""

import sqlalchemy as sa

from alembic import op

revision = "f3a9c2e84d71"
down_revision = "e7d3a4f810bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rewrite_provider_settings",
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("encrypted_api_key", sa.String(), nullable=False),
        sa.Column("primary_model", sa.String(length=255), nullable=False),
        sa.Column("fallback_models", sa.String(length=2048), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('OPENAI', 'OPENROUTER')", name="ck_rewrite_provider_setting_provider"
        ),
        sa.PrimaryKeyConstraint("provider"),
    )


def downgrade() -> None:
    op.drop_table("rewrite_provider_settings")
