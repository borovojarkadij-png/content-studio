"""SQLAlchemy persistence schema.

The application service remains the primary protection. These row-local checks
make an accidental invalid state impossible even when a caller bypasses it.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ContentRevision(Base):
    __tablename__ = "content_revisions"
    __table_args__ = (
        CheckConstraint(
            "editorial_status <> 'REJECT' OR rewrite_allowed = false",
            name="ck_rejected_revision_disables_rewrite",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    editorial_status: Mapped[str] = mapped_column(String(32), nullable=False)
    rewrite_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    encrypted_session: Mapped[str] = mapped_column(String, nullable=False)
    health_status: Mapped[str] = mapped_column(String(32), default="DISCONNECTED", nullable=False)
    health_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TelegramPeerModel(Base):
    """Account-scoped encrypted input channel; never projected by public APIs."""

    __tablename__ = "telegram_peers"
    __table_args__ = (CheckConstraint("telegram_channel_id < -1000000000000"),)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), primary_key=True
    )
    telegram_channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    encrypted_peer: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DonorChannel(Base):
    __tablename__ = "donor_channels"
    __table_args__ = (UniqueConstraint("telegram_account_id", "telegram_channel_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), nullable=False
    )
    telegram_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)


class OutputChannel(Base):
    __tablename__ = "output_channels"
    __table_args__ = (
        UniqueConstraint("telegram_account_id", "telegram_channel_id"),
        CheckConstraint("rewrite_style IN ('NEUTRAL', 'TABLOID')", name="ck_channel_rewrite_style"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), nullable=False
    )
    telegram_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rewrite_style: Mapped[str] = mapped_column(
        String(16), nullable=False, default="NEUTRAL", server_default="NEUTRAL"
    )


class MappingFilterPolicyModel(Base):
    __tablename__ = "mapping_filter_policies"
    mapping_id: Mapped[int] = mapped_column(ForeignKey("channel_mappings.id"), primary_key=True)
    allowed_media_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    blocked_domains: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    ad_markers: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class DonorIngestionCursorModel(Base):
    """A bounded history poll lease and its committed high-water mark."""

    __tablename__ = "donor_ingestion_cursors"
    __table_args__ = (
        CheckConstraint("last_message_id >= 0"),
        CheckConstraint(
            "(claim_token IS NULL AND lease_expires_at IS NULL) OR "
            "(claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
    )
    donor_channel_id: Mapped[int] = mapped_column(ForeignKey("donor_channels.id"), primary_key=True)
    last_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ChannelDifferenceCursorModel(Base):
    """Trusted channel baseline; never initialized from message IDs or TooLong."""

    __tablename__ = "channel_difference_cursors"
    __table_args__ = (
        CheckConstraint("pts BETWEEN 1 AND 2147483647", name="ck_difference_pts"),
        CheckConstraint(
            "telegram_account_id > 0 AND telegram_user_id > 0", name="ck_difference_account"
        ),
        CheckConstraint("telegram_channel_id < -1000000000000", name="ck_difference_channel"),
        CheckConstraint(
            "(claim_token IS NULL AND lease_expires_at IS NULL) OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_difference_lease",
        ),
    )
    donor_channel_id: Mapped[int] = mapped_column(ForeignKey("donor_channels.id"), primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), nullable=False
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pts: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ChannelMappingModel(Base):
    __tablename__ = "channel_mappings"
    __table_args__ = (
        UniqueConstraint("donor_channel_id", "output_channel_id"),
        CheckConstraint("intake_percent BETWEEN 0 AND 100", name="ck_mapping_intake_percent"),
        CheckConstraint(
            "target_mix_percent BETWEEN 0 AND 100", name="ck_mapping_target_mix_percent"
        ),
        CheckConstraint(
            "eligibility_mode IN ('IMMEDIATE', 'DELAYED')",
            name="ck_mapping_eligibility_mode",
        ),
        CheckConstraint("delay_minutes BETWEEN 0 AND 10080"),
        CheckConstraint(
            "eligibility_mode <> 'IMMEDIATE' OR delay_minutes = 0",
            name="ck_immediate_mapping_has_no_delay",
        ),
        CheckConstraint("priority BETWEEN -1000 AND 1000"),
        CheckConstraint(
            "media_policy IN ('REUSE_SOURCE', 'LICENSED_LIBRARY')",
            name="ck_mapping_media_policy",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    donor_channel_id: Mapped[int] = mapped_column(ForeignKey("donor_channels.id"), nullable=False)
    output_channel_id: Mapped[int] = mapped_column(ForeignKey("output_channels.id"), nullable=False)
    intake_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    target_mix_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    eligibility_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="IMMEDIATE")
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="REUSE_SOURCE")


class MappingSourceRightsModel(Base):
    """Explicit human declaration. Absence never implies donor media permission."""

    __tablename__ = "mapping_source_rights"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_source_rights_revision"),
        CheckConstraint(
            "license_code IN ('UNDECLARED', 'OWNED', 'PERMISSION')", name="ck_source_rights_license"
        ),
        CheckConstraint(
            "length(attribution) <= 2048 AND (license_code <> 'PERMISSION' OR length(trim(attribution)) > 0) "
            "AND (license_code <> 'UNDECLARED' OR attribution = '')",
            name="ck_source_rights_attribution",
        ),
    )
    mapping_id: Mapped[int] = mapped_column(ForeignKey("channel_mappings.id"), primary_key=True)
    license_code: Mapped[str] = mapped_column(String(16), nullable=False)
    attribution: Mapped[str] = mapped_column(String(2048), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)


class DonorImportModel(Base):
    """Unresolved identifiers are not fabricated operational Telegram channels."""

    __tablename__ = "donor_imports"
    __table_args__ = (UniqueConstraint("telegram_account_id", "identifier"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), nullable=False, index=True
    )
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class DonorImportResolutionJobModel(Base):
    __tablename__ = "donor_import_resolution_jobs"
    __table_args__ = (
        CheckConstraint("state IN ('QUEUED', 'RUNNING', 'RETRY', 'RESOLVED', 'INVALID')"),
        CheckConstraint(
            "(claim_token IS NULL AND lease_expires_at IS NULL) OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
        CheckConstraint(
            "(state = 'RESOLVED' AND resolved_donor_id IS NOT NULL) OR (state <> 'RESOLVED' AND resolved_donor_id IS NULL)"
        ),
    )
    donor_import_id: Mapped[int] = mapped_column(ForeignKey("donor_imports.id"), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_donor_id: Mapped[int | None] = mapped_column(
        ForeignKey("donor_channels.id"), nullable=True
    )


class PublicationPlanModel(Base):
    """Per-output policy for manual or automatic daily planning."""

    __tablename__ = "publication_plans"
    __table_args__ = (
        UniqueConstraint("output_channel_id"),
        CheckConstraint("mode IN ('MANUAL', 'AUTOMATIC')", name="ck_publication_plan_mode"),
        CheckConstraint("daily_limit BETWEEN 1 AND 24", name="ck_publication_plan_daily_limit"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    output_channel_id: Mapped[int] = mapped_column(
        ForeignKey("output_channels.id"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    slot_minutes: Mapped[str] = mapped_column(String(128), nullable=False)


class RewriteProviderSettingModel(Base):
    """Encrypted provider credential and rewrite-model policy, never projected raw."""

    __tablename__ = "rewrite_provider_settings"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('OPENAI', 'OPENROUTER')", name="ck_rewrite_provider_setting_provider"
        ),
    )
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    encrypted_api_key: Mapped[str] = mapped_column(String, nullable=False)
    primary_model: Mapped[str] = mapped_column(String(255), nullable=False)
    fallback_models: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PublicationCandidateModel(Base):
    """Durable candidate eligible for planning, not a publication instruction."""

    __tablename__ = "publication_candidates"
    __table_args__ = (
        UniqueConstraint(
            "output_channel_id", "content_key", name="uq_publication_candidate_content"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    output_channel_id: Mapped[int] = mapped_column(
        ForeignKey("output_channels.id"), nullable=False, index=True
    )
    mapping_id: Mapped[int | None] = mapped_column(
        ForeignKey("channel_mappings.id"), nullable=True, index=True
    )
    content_key: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    media_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="REUSE_SOURCE")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MediaAssetModel(Base):
    """Immutable local media identity/rights; bytes live on persistent storage."""

    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint("origin IN ('SOURCE', 'LICENSED_LIBRARY')", name="ck_media_asset_origin"),
        CheckConstraint(
            "license_code IN ('OWNED', 'PERMISSION', 'CC0', 'CC-BY')", name="ck_media_asset_license"
        ),
        CheckConstraint("mime_type IN ('image/png', 'image/jpeg')", name="ck_media_asset_mime"),
        CheckConstraint(
            "origin <> 'SOURCE' OR (source_content_key IS NOT NULL AND license_code IN ('OWNED', 'PERMISSION'))",
            name="ck_media_source_rights",
        ),
        CheckConstraint(
            "origin <> 'LICENSED_LIBRARY' OR source_content_key IS NULL",
            name="ck_media_library_source",
        ),
        CheckConstraint(
            "license_code NOT IN ('PERMISSION', 'CC-BY') OR length(attribution) > 0",
            name="ck_media_asset_attribution",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_content_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    license_code: Mapped[str] = mapped_column(String(16), nullable=False)
    attribution: Mapped[str] = mapped_column(String(2048), nullable=False)
    tags: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MediaAcquisitionJobModel(Base):
    """Mode-bound acquisition; rights and selected bytes survive worker restarts."""

    __tablename__ = "media_acquisition_jobs"
    __table_args__ = (
        UniqueConstraint("candidate_id", "binding_sha256", name="uq_media_job_binding"),
        CheckConstraint(
            "state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'NO_MATCH', 'BLOCKED', 'FAILED')"
        ),
        CheckConstraint("attempts BETWEEN 0 AND 2"),
        CheckConstraint("length(binding_sha256) = 64"),
        CheckConstraint(
            "state <> 'RUNNING' OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
        CheckConstraint("state <> 'SUCCEEDED' OR selected_asset_id IS NOT NULL"),
        CheckConstraint(
            "acquisition_mode IN ('LICENSED_LIBRARY', 'REUSE_SOURCE')",
            name="ck_media_job_mode",
        ),
        CheckConstraint(
            "(acquisition_mode = 'LICENSED_LIBRARY' AND license_code IS NULL AND attribution IS NULL) OR "
            "(acquisition_mode = 'REUSE_SOURCE' AND license_code IS NOT NULL AND attribution IS NOT NULL "
            "AND license_code IN ('OWNED', 'PERMISSION') AND length(attribution) <= 2048 "
            "AND (license_code <> 'PERMISSION' OR length(trim(attribution)) > 0))",
            name="ck_media_job_rights",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("publication_candidates.id"), nullable=False, index=True
    )
    binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    acquisition_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="LICENSED_LIBRARY", server_default="LICENSED_LIBRARY"
    )
    license_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    attribution: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    selected_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id"), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PlannedPublicationModel(Base):
    """An idempotent reserved slot; a later publication worker still approves it."""

    __tablename__ = "planned_publications"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_planned_publication_candidate"),
        Index(
            "uq_planned_publication_active_slot",
            "output_channel_id",
            "scheduled_for",
            unique=True,
            sqlite_where=text("state = 'PLANNED'"),
            postgresql_where=text("state = 'PLANNED'"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("publication_candidates.id"), nullable=False
    )
    output_channel_id: Mapped[int] = mapped_column(ForeignKey("output_channels.id"), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PublicationJobModel(Base):
    """Durable send intent. Unknown remote outcomes cannot be automatically retried."""

    __tablename__ = "publication_jobs"
    __table_args__ = (
        UniqueConstraint("planned_id", name="uq_publication_job_plan"),
        UniqueConstraint("telegram_account_id", "request_nonce", name="uq_publication_job_nonce"),
        CheckConstraint(
            "state IN ('QUEUED', 'CLAIMED', 'SENDING', 'SUCCEEDED', 'BLOCKED', 'FAILED', 'NEEDS_RECONCILIATION')",
            name="ck_publication_job_state",
        ),
        CheckConstraint("attempts BETWEEN 0 AND 2", name="ck_publication_job_attempts"),
        CheckConstraint("length(binding_sha256) = 64", name="ck_publication_job_binding"),
        CheckConstraint(
            "request_nonce > 0 AND request_nonce <= 9223372036854775807 AND telegram_channel_id < -1000000000000",
            name="ck_publication_job_identity",
        ),
        CheckConstraint(
            "(state IN ('CLAIMED', 'SENDING') AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL AND attempts > 0) OR (state NOT IN ('CLAIMED', 'SENDING') AND claim_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_publication_job_lease",
        ),
        CheckConstraint(
            "(state = 'SUCCEEDED' AND sent_message_id IS NOT NULL AND sent_message_id > 0 AND completed_at IS NOT NULL AND attempts > 0) OR (state <> 'SUCCEEDED' AND sent_message_id IS NULL AND completed_at IS NULL)",
            name="ck_publication_job_receipt",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    planned_id: Mapped[int] = mapped_column(ForeignKey("planned_publications.id"), nullable=False)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), nullable=False
    )
    telegram_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_nonce: Mapped[int] = mapped_column(BigInteger, nullable=False)
    binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PublicationRequestSnapshotModel(Base):
    """Encrypted immutable request history, not permission to publish."""

    __tablename__ = "publication_request_snapshots"
    __table_args__ = (
        CheckConstraint("length(binding_sha256) = 64", name="ck_publication_snapshot_binding"),
        CheckConstraint(
            "length(encrypted_envelope) BETWEEN 1 AND 32768",
            name="ck_publication_snapshot_size",
        ),
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("publication_jobs.id"), primary_key=True)
    binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_envelope: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PublicationDeliveryObservationModel(Base):
    """Trusted exact acknowledgement observed before terminal status commit."""

    __tablename__ = "publication_delivery_observations"
    __table_args__ = (
        CheckConstraint(
            "length(encrypted_receipt) BETWEEN 1 AND 4096", name="ck_publication_observation_size"
        ),
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("publication_jobs.id"), primary_key=True)
    encrypted_receipt: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_key: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceDeletionModel(Base):
    """Permanent source tombstone, including identities not ingested yet."""

    __tablename__ = "source_deletions"
    __table_args__ = (
        CheckConstraint(
            "length(telegram_account_id) BETWEEN 1 AND 100", name="ck_source_deletion_account"
        ),
        CheckConstraint(
            "length(donor_channel_id) BETWEEN 1 AND 100", name="ck_source_deletion_channel"
        ),
        CheckConstraint(
            "telegram_message_id BETWEEN 1 AND 2147483647", name="ck_source_deletion_message"
        ),
        CheckConstraint("latest_pts BETWEEN 1 AND 2147483647", name="ck_source_deletion_pts"),
    )
    telegram_account_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    donor_channel_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    telegram_message_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_pts: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IncomingPostModel(Base):
    __tablename__ = "incoming_posts"
    __table_args__ = (
        UniqueConstraint(
            "telegram_account_id",
            "donor_channel_id",
            "telegram_message_id",
            name="uq_incoming_posts_source_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    donor_channel_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ContentRevisionModel(Base):
    __tablename__ = "incoming_post_revisions"
    __table_args__ = (
        UniqueConstraint("incoming_post_id", "revision_number", name="uq_revision_number_per_post"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    incoming_post_id: Mapped[int] = mapped_column(
        ForeignKey("incoming_posts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_text: Mapped[str] = mapped_column(String, nullable=False)
    link_destinations: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True, default=list
    )
    media_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="text", server_default="unknown"
    )
    album_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    media_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    media_protected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MappingContentFingerprintModel(Base):
    __tablename__ = "mapping_content_fingerprints"
    __table_args__ = (
        UniqueConstraint("mapping_id", "fingerprint", name="uq_mapping_content_fingerprint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mapping_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EditorialDecisionModel(Base):
    __tablename__ = "editorial_decisions"
    __table_args__ = (
        CheckConstraint(
            "status <> 'REJECT' OR rewrite_allowed = false",
            name="ck_editorial_reject_disables_rewrite",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rewrite_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_codes: Mapped[str] = mapped_column(String, nullable=False, default="")
    protected_entities: Mapped[str] = mapped_column(String, nullable=False, default="")
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False)
    framing: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RewriteJobModel(Base):
    __tablename__ = "rewrite_jobs"
    __table_args__ = (
        UniqueConstraint("content_key", "output_channel_id", name="uq_rewrite_job_content_output"),
        CheckConstraint("attempts >= 0", name="ck_rewrite_attempts_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_key: Mapped[str] = mapped_column(String(255), nullable=False)
    output_channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("output_channels.id"), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RewriteOutputModel(Base):
    """Per-channel rewrite text and its independent editorial approval state."""

    __tablename__ = "rewrite_outputs"
    __table_args__ = (
        UniqueConstraint("rewrite_job_id", name="uq_rewrite_output_job"),
        CheckConstraint(
            "approval_state IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_rewrite_output_approval_state",
        ),
        CheckConstraint(
            "approval_method IN ('MANUAL', 'AUTOMATIC')", name="ck_rewrite_approval_method"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rewrite_job_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_jobs.id"), nullable=False, index=True
    )
    output_channel_id: Mapped[int] = mapped_column(
        ForeignKey("output_channels.id"), nullable=False, index=True
    )
    content_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rewritten_text: Mapped[str] = mapped_column(String, nullable=False)
    approval_state: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="MANUAL", server_default="MANUAL"
    )


class SemanticVerifierReleaseModel(Base):
    """Trusted evaluation registry. No public mutation/API-generated qualifications."""

    __tablename__ = "semantic_verifier_releases"
    __table_args__ = (
        CheckConstraint("provider IN ('OPENAI', 'OPENROUTER')"),
        CheckConstraint("length(report_sha256) = 64"),
        UniqueConstraint(
            "provider", "model", "prompt_version", "benchmark_version", "report_sha256"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(64), nullable=False)
    report_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AutomaticApprovalPolicyModel(Base):
    __tablename__ = "automatic_approval_policies"
    __table_args__ = (
        CheckConstraint("mode IN ('MANUAL', 'VERIFIED')"),
        CheckConstraint("mode <> 'VERIFIED' OR release_id IS NOT NULL"),
    )
    output_channel_id: Mapped[int] = mapped_column(
        ForeignKey("output_channels.id"), primary_key=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")
    release_id: Mapped[int | None] = mapped_column(
        ForeignKey("semantic_verifier_releases.id"), nullable=True
    )


class SemanticEvidenceModel(Base):
    __tablename__ = "semantic_evidence"
    __table_args__ = (
        UniqueConstraint(
            "rewrite_output_id",
            "release_id",
            "source_sha256",
            "draft_sha256",
            name="uq_semantic_evidence_binding",
        ),
        CheckConstraint("verdict IN ('PRESERVED', 'CHANGED', 'UNCERTAIN', 'ERROR')"),
        CheckConstraint("length(source_sha256) = 64 AND length(draft_sha256) = 64"),
        CheckConstraint("length(release_sha256) = 64"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    rewrite_output_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_outputs.id"), nullable=False, index=True
    )
    source_revision_id: Mapped[int] = mapped_column(
        ForeignKey("incoming_post_revisions.id"), nullable=False
    )
    release_id: Mapped[int] = mapped_column(
        ForeignKey("semantic_verifier_releases.id"), nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    release_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_codes: Mapped[str] = mapped_column(String(1024), nullable=False)
    evidence_json: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SemanticVerificationJobModel(Base):
    __tablename__ = "semantic_verification_jobs"
    __table_args__ = (
        UniqueConstraint(
            "rewrite_output_id",
            "release_id",
            "source_sha256",
            "draft_sha256",
            "release_sha256",
            name="uq_semantic_job_binding",
        ),
        CheckConstraint(
            "state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'REVIEW', 'BLOCKED', 'FAILED')"
        ),
        CheckConstraint("attempts BETWEEN 0 AND 2"),
        CheckConstraint(
            "state <> 'RUNNING' OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    rewrite_output_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_outputs.id"), nullable=False, index=True
    )
    source_revision_id: Mapped[int] = mapped_column(
        ForeignKey("incoming_post_revisions.id"), nullable=False
    )
    release_id: Mapped[int] = mapped_column(
        ForeignKey("semantic_verifier_releases.id"), nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    release_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("semantic_evidence.id"), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SemanticVerificationUsageModel(Base):
    __tablename__ = "semantic_verification_usage"
    __table_args__ = (
        UniqueConstraint("verification_job_id", "attempt", name="uq_semantic_usage_attempt"),
        CheckConstraint("attempt BETWEEN 1 AND 2 AND input_tokens >= 0 AND output_tokens >= 0"),
        CheckConstraint("cached_tokens >= 0 AND cached_tokens <= input_tokens"),
        CheckConstraint("estimated_cost_usd IS NULL OR estimated_cost_usd >= 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    verification_job_id: Mapped[int] = mapped_column(
        ForeignKey("semantic_verification_jobs.id"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RewriteUsageModel(Base):
    """Known provider usage per persisted attempt; unknown charges are not zero."""

    __tablename__ = "rewrite_usage"
    __table_args__ = (
        UniqueConstraint("rewrite_job_id", "attempt", name="uq_rewrite_usage_attempt"),
        CheckConstraint("attempt >= 1 AND input_tokens >= 0 AND output_tokens >= 0"),
        CheckConstraint("cached_tokens >= 0 AND cached_tokens <= input_tokens"),
        CheckConstraint("estimated_cost_usd IS NULL OR estimated_cost_usd >= 0"),
        CheckConstraint("style IN ('NEUTRAL', 'TABLOID')"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    rewrite_job_id: Mapped[int] = mapped_column(ForeignKey("rewrite_jobs.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    style: Mapped[str] = mapped_column(String(16), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def _illustration_digest_check(column: str) -> str:
    remaining = column
    for character in "0123456789abcdef":
        remaining = f"replace({remaining}, '{character}', '')"
    return f"length({column}) = 64 AND {remaining} = ''"


class IllustrationReviewRecordModel(Base):
    """Append-only human-review/revocation history; never authentication by itself.

    Alembic installs database UPDATE/DELETE refusal. No application writer/API
    or permission consumer exists yet. Synthetic rows cannot qualify a model,
    attest an event photograph or remove the library publication hold.
    """

    __tablename__ = "illustration_review_records"
    __table_args__ = (
        UniqueConstraint("operation_key", name="uq_illustration_review_operation"),
        UniqueConstraint("revokes_review_id", name="uq_illustration_review_revocation"),
        CheckConstraint(
            "id > 0 AND reviewer_id > 0 AND candidate_id > 0 AND output_channel_id > 0 "
            "AND mapping_id > 0 AND source_revision_id > 0 "
            "AND rewrite_output_id > 0 AND media_asset_id > 0",
            name="ck_illustration_review_ids",
        ),
        CheckConstraint(
            "provenance = 'AUTHENTICATED_HUMAN_V1'", name="ck_illustration_review_provenance"
        ),
        CheckConstraint(
            "typeof(reviewer_id) = 'integer'", name="ck_illustration_review_reviewer_type"
        ).ddl_if(dialect="sqlite"),
        CheckConstraint(
            "illustration_acknowledged IS NULL OR illustration_acknowledged IN (false, true)",
            name="ck_illustration_review_ack",
        ),
        CheckConstraint(
            "length(operation_key) BETWEEN 1 AND 128 AND length(trim(operation_key)) > 0",
            name="ck_illustration_review_operation",
        ),
        CheckConstraint(
            "length(content_key) BETWEEN 1 AND 255 AND length(trim(content_key)) > 0",
            name="ck_illustration_review_content",
        ),
        CheckConstraint(
            "length(review_note) BETWEEN 1 AND 2048 AND length(trim(review_note)) > 0",
            name="ck_illustration_review_note",
        ),
        CheckConstraint(
            "(record_kind = 'REVIEW' AND revokes_review_id IS NULL "
            "AND verdict IS NOT NULL AND verdict IN "
            "('APPROVED_ILLUSTRATION', 'REJECTED', 'UNCERTAIN') "
            "AND illustration_acknowledged IS NOT NULL "
            "AND (verdict <> 'APPROVED_ILLUSTRATION' OR illustration_acknowledged = true)) "
            "OR (record_kind = 'REVOCATION' AND revokes_review_id IS NOT NULL "
            "AND revokes_review_id < id AND verdict IS NULL "
            "AND illustration_acknowledged IS NULL)",
            name="ck_illustration_review_kind",
        ),
        *(
            CheckConstraint(
                _illustration_digest_check(column), name=f"ck_illustration_review_{column}"
            )
            for column in (
                "source_sha256",
                "draft_sha256",
                "media_sha256",
                "asset_metadata_sha256",
            )
        ),
        Index("ix_illustration_review_candidate", "candidate_id", "id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    record_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    revokes_review_id: Mapped[int | None] = mapped_column(
        ForeignKey("illustration_review_records.id"), nullable=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("publication_candidates.id"), nullable=False
    )
    output_channel_id: Mapped[int] = mapped_column(ForeignKey("output_channels.id"), nullable=False)
    mapping_id: Mapped[int] = mapped_column(ForeignKey("channel_mappings.id"), nullable=False)
    content_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_revision_id: Mapped[int] = mapped_column(
        ForeignKey("incoming_post_revisions.id"), nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rewrite_output_id: Mapped[int] = mapped_column(ForeignKey("rewrite_outputs.id"), nullable=False)
    draft_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_asset_id: Mapped[int] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
    media_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_metadata_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    illustration_acknowledged: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
