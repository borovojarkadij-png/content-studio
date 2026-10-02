"""SQLAlchemy persistence schema.

The application service remains the primary protection. These row-local checks
make an accidental invalid state impossible even when a caller bypasses it.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
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
    __table_args__ = (UniqueConstraint("telegram_account_id", "telegram_channel_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), nullable=False
    )
    telegram_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)


class ChannelMappingModel(Base):
    __tablename__ = "channel_mappings"
    __table_args__ = (
        UniqueConstraint("donor_channel_id", "output_channel_id"),
        CheckConstraint("intake_percent BETWEEN 0 AND 100"),
        CheckConstraint("target_mix_percent BETWEEN 0 AND 100"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    donor_channel_id: Mapped[int] = mapped_column(ForeignKey("donor_channels.id"), nullable=False)
    output_channel_id: Mapped[int] = mapped_column(ForeignKey("output_channels.id"), nullable=False)
    intake_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    target_mix_percent: Mapped[int] = mapped_column(Integer, nullable=False)


class DonorImportModel(Base):
    """Unresolved identifiers are not fabricated operational Telegram channels."""

    __tablename__ = "donor_imports"
    __table_args__ = (UniqueConstraint("telegram_account_id", "identifier"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id"), nullable=False
    )
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class PublicationPlanModel(Base):
    """Per-output policy for manual or automatic daily planning."""

    __tablename__ = "publication_plans"
    __table_args__ = (
        CheckConstraint("mode IN ('MANUAL', 'AUTOMATIC')", name="ck_publication_plan_mode"),
        CheckConstraint("daily_limit BETWEEN 1 AND 24", name="ck_publication_plan_daily_limit"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    output_channel_id: Mapped[int] = mapped_column(
        ForeignKey("output_channels.id"), unique=True, nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    slot_minutes: Mapped[str] = mapped_column(String(128), nullable=False)


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
    content_key: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_key: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_key: Mapped[str] = mapped_column(String(255), nullable=False)
    output_channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("output_channels.id"), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
