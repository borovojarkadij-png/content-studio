"""Durable read-only import resolution; no fabricated IDs, join, login or send."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select

from newsflow.persistence.models import (
    DonorChannel,
    DonorImportModel,
    DonorImportResolutionJobModel,
    OutboxEventModel,
    TelegramAccount,
)
from newsflow.providers.telegram import FloodWait, SessionUnavailable, TelegramChannelResolution


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _time(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Resolution time must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class DonorResolutionClaim:
    import_id: int
    account_id: int
    identifier: str
    token: str
    session_digest: str = field(repr=False)


class DonorImportResolutionRunner:
    def __init__(self, session_factory, *, provider, clock=lambda: datetime.now(UTC)):
        self._sessions, self._provider, self._clock = session_factory, provider, clock

    def claim(self, import_id, *, now):
        now = _time(now)
        with self._sessions() as session, session.begin():
            item = session.scalar(
                select(DonorImportModel)
                .where(DonorImportModel.id == import_id)
                .with_for_update(skip_locked=True)
            )
            if item is None or item.status != "PENDING_RESOLUTION":
                return None
            account = session.get(TelegramAccount, item.telegram_account_id)
            if (
                account is None
                or not account.encrypted_session
                or account.health_status == "SESSION_INVALID"
            ):
                return None
            if account.cooldown_until is not None and _utc(account.cooldown_until) > now:
                return None
            job = session.get(DonorImportResolutionJobModel, import_id, with_for_update=True)
            if job is None:
                job = DonorImportResolutionJobModel(
                    donor_import_id=import_id, state="QUEUED", available_at=now
                )
                session.add(job)
            if job.state in {"RESOLVED", "INVALID"} or _utc(job.available_at) > now:
                return None
            if job.lease_expires_at is not None and _utc(job.lease_expires_at) > now:
                return None
            job.state, job.claim_token = "RUNNING", str(uuid4())
            job.lease_expires_at = now + timedelta(seconds=60)
            job.last_error_code = None
            return DonorResolutionClaim(
                import_id,
                item.telegram_account_id,
                item.identifier,
                job.claim_token,
                sha256(account.encrypted_session.encode()).hexdigest(),
            )

    def _owned(self, session, claim):
        item = session.scalar(
            select(DonorImportModel)
            .where(DonorImportModel.id == claim.import_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        job = session.get(
            DonorImportResolutionJobModel,
            claim.import_id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            item is None
            or item.status != "PENDING_RESOLUTION"
            or item.identifier != claim.identifier
            or item.telegram_account_id != claim.account_id
            or job is None
            or job.state != "RUNNING"
            or job.claim_token != claim.token
            or job.lease_expires_at is None
            or _utc(job.lease_expires_at) <= _time(self._clock())
        ):
            return None
        account = session.get(
            TelegramAccount, claim.account_id, populate_existing=True, with_for_update=True
        )
        if (
            account is None
            or sha256(account.encrypted_session.encode()).hexdigest() != claim.session_digest
        ):
            return None
        return item, job

    def run_import(self, import_id, *, now):
        claim = self.claim(import_id, now=now)
        return "IDLE" if claim is None else self.execute(claim)

    def execute(self, claim):
        with self._sessions() as session, session.begin():
            if self._owned(session, claim) is None:
                return "STALE_CLAIM"
        try:
            resolved = self._provider.resolve_channel(str(claim.account_id), claim.identifier)
        except FloodWait as exc:
            return self._failure(claim, "COOLDOWN", delay=max(1, exc.seconds), health="COOLDOWN")
        except SessionUnavailable:
            return self._failure(claim, "SESSION_INVALID", delay=300, health="SESSION_INVALID")
        except (TimeoutError, ConnectionError, OSError):
            return self._failure(claim, "RETRY_PROVIDER", delay=30)
        except (TypeError, ValueError, LookupError):
            return self._failure(claim, "INVALID_SOURCE", invalid=True)
        if (
            not isinstance(resolved, TelegramChannelResolution)
            or resolved.identifier != claim.identifier
            or resolved.peer.account_id != str(claim.account_id)
        ):
            return self._failure(claim, "INVALID_PROVIDER_IDENTITY", invalid=True)
        with self._sessions() as session, session.begin():
            owned = self._owned(session, claim)
            if owned is None:
                return "STALE_CLAIM"
            item, job = owned
            # Serializes aliases of one channel without an identity-replacing
            # upsert. User-configured titles on existing donors are preserved.
            donor = session.scalar(
                select(DonorChannel).where(
                    DonorChannel.telegram_account_id == claim.account_id,
                    DonorChannel.telegram_channel_id == resolved.peer.channel_id,
                )
            )
            if donor is None:
                donor = DonorChannel(
                    telegram_account_id=claim.account_id,
                    telegram_channel_id=resolved.peer.channel_id,
                    title=resolved.title,
                )
                session.add(donor)
                session.flush()
            item.status, job.state, job.resolved_donor_id = "RESOLVED", "RESOLVED", donor.id
            job.claim_token = job.lease_expires_at = job.last_error_code = None
            session.add(
                OutboxEventModel(
                    event_type="donor.import.resolved",
                    aggregate_key=str(claim.import_id),
                    idempotency_key=f"donor.import.resolved:{claim.import_id}",
                )
            )
        return "RESOLVED"

    def _failure(self, claim, code, *, delay=30, health=None, invalid=False):
        now = _time(self._clock())
        with self._sessions() as session, session.begin():
            owned = self._owned(session, claim)
            if owned is None:
                return "STALE_CLAIM"
            item, job = owned
            job.state = "INVALID" if invalid else "RETRY"
            if invalid:
                item.status = "INVALID_SOURCE"
            job.available_at, job.last_error_code = now + timedelta(seconds=delay), code
            job.claim_token = job.lease_expires_at = None
            if health is not None:
                account = session.scalar(
                    select(TelegramAccount)
                    .where(TelegramAccount.id == claim.account_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if health == "SESSION_INVALID":
                    account.health_status, account.health_checked_at = health, now
                elif account.health_status != "SESSION_INVALID":
                    account.health_status, account.health_checked_at = health, now
                    account.cooldown_until = max(
                        _utc(account.cooldown_until) if account.cooldown_until else now,
                        now + timedelta(seconds=delay),
                    )
        return code
