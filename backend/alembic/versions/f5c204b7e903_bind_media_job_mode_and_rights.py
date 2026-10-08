"""Bind source-photo jobs to explicit rights; legacy jobs remain illustrations."""

import sqlalchemy as sa

from alembic import op

revision = "f5c204b7e903"
down_revision = "e4b193a6d8f2"
branch_labels = None
depends_on = None


def _copy_table():
    if op.get_bind().dialect.name != "sqlite":
        return None
    table = sa.Table("media_acquisition_jobs", sa.MetaData(), autoload_with=op.get_bind())
    # SQLite batch reflection otherwise silently drops legacy unnamed checks.
    checks = sorted(
        (
            constraint
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint)
        ),
        key=lambda constraint: str(constraint.sqltext),
    )
    for index, constraint in enumerate(checks):
        if constraint.name is None:
            constraint.name = f"ck_media_job_legacy_{index}"
    return table


def upgrade():
    op.create_table(
        "mapping_source_rights",
        sa.Column(
            "mapping_id", sa.Integer(), sa.ForeignKey("channel_mappings.id"), primary_key=True
        ),
        sa.Column("license_code", sa.String(16), nullable=False),
        sa.Column("attribution", sa.String(2048), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_source_rights_revision"),
        sa.CheckConstraint(
            "license_code IN ('UNDECLARED', 'OWNED', 'PERMISSION')", name="ck_source_rights_license"
        ),
        sa.CheckConstraint(
            "length(attribution) <= 2048 AND (license_code <> 'PERMISSION' OR length(trim(attribution)) > 0) "
            "AND (license_code <> 'UNDECLARED' OR attribution = '')",
            name="ck_source_rights_attribution",
        ),
    )
    with op.batch_alter_table("media_acquisition_jobs", copy_from=_copy_table()) as batch:
        batch.add_column(
            sa.Column(
                "acquisition_mode", sa.String(32), nullable=False, server_default="LICENSED_LIBRARY"
            )
        )
        batch.add_column(sa.Column("license_code", sa.String(16), nullable=True))
        batch.add_column(sa.Column("attribution", sa.String(2048), nullable=True))
        batch.create_check_constraint(
            "ck_media_job_mode", "acquisition_mode IN ('LICENSED_LIBRARY', 'REUSE_SOURCE')"
        )
        batch.create_check_constraint(
            "ck_media_job_rights",
            "(acquisition_mode = 'LICENSED_LIBRARY' AND license_code IS NULL AND attribution IS NULL) OR "
            "(acquisition_mode = 'REUSE_SOURCE' AND license_code IS NOT NULL AND attribution IS NOT NULL "
            "AND license_code IN ('OWNED', 'PERMISSION') AND length(attribution) <= 2048 "
            "AND (license_code <> 'PERMISSION' OR length(trim(attribution)) > 0))",
        )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM mapping_source_rights")):
        raise RuntimeError("Refusing to discard source-photo rights/history")
    if op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM media_acquisition_jobs WHERE acquisition_mode <> 'LICENSED_LIBRARY' OR license_code IS NOT NULL OR attribution IS NOT NULL"
        )
    ):
        raise RuntimeError("Refusing to discard source-photo job rights/history")
    with op.batch_alter_table("media_acquisition_jobs", copy_from=_copy_table()) as batch:
        batch.drop_constraint("ck_media_job_rights", type_="check")
        batch.drop_constraint("ck_media_job_mode", type_="check")
        batch.drop_column("attribution")
        batch.drop_column("license_code")
        batch.drop_column("acquisition_mode")
    op.drop_table("mapping_source_rights")
