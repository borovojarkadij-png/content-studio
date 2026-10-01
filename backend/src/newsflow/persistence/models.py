"""SQLAlchemy persistence schema.

The application service remains the primary protection. These row-local checks
make an accidental invalid state impossible even when a caller bypasses it.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
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
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    encrypted_session: Mapped[str] = mapped_column(String, nullable=False)
    health_status: Mapped[str] = mapped_column(String(32), default="DISCONNECTED", nullable=False)


class DonorChannel(Base):
    __tablename__ = "donor_channels"
    __table_args__ = (UniqueConstraint("telegram_account_id", "telegram_channel_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(ForeignKey("telegram_accounts.id"), nullable=False)
    telegram_channel_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)


class OutputChannel(Base):
    __tablename__ = "output_channels"
    __table_args__ = (UniqueConstraint("telegram_account_id", "telegram_channel_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(ForeignKey("telegram_accounts.id"), nullable=False)
    telegram_channel_id: Mapped[int] = mapped_column(Integer, nullable=False)
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

    id: Mapped[int] = mapped_column(primary_key=True)
    content_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
