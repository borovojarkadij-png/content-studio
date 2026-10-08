"""One leased, deletion-first pts chunk. No fabricated bootstrap or blind reset.

Remote reads are outside transactions. Deletions commit first; message fan-out is
at least once. Progress commits only after the complete chunk/current mappings.
There is no public cursor initializer, worker activation, login or sending here.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import (
    ChannelDifferenceCursorModel,
    ChannelMappingModel,
    DonorChannel,
    MappingFilterPolicyModel,
    TelegramAccount,
)
from newsflow.providers.telegram import (
    FloodWait,
    SessionUnavailable,
    TelegramChannelDifference,
    validate_difference_request,
)
from newsflow.providers.telegram_difference import ChannelDifferenceGapUnresolved
from newsflow.services.source_deletions import SourceDeletionClaimLost, SourceDeletionService


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Difference clock must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ChannelDifferenceClaim:
    donor_id: int
    account_id: int
    user_id: int
    channel_id: int
    pts: int
    token: str
    session_digest: str = field(repr=False)


class ChannelDifferenceRunner:
    def __init__(self, session_factory, *, provider, clock=lambda: datetime.now(UTC), page_size=50):
        if type(page_size) is not int or not 10 <= page_size <= 100:
            raise ValueError("Difference page size must be between 10 and 100")
        self._sessions, self._provider, self._clock, self._size = (
            session_factory,
            provider,
            clock,
            page_size,
        )

    @staticmethod
    def _healthy(account, now):
        return (
            account is not None
            and account.health_status == "CONNECTED"
            and bool(account.encrypted_session)
            and (account.cooldown_until is None or _utc(account.cooldown_until) <= now)
        )

    def claim(self, donor_id, *, now):
        now = _clock(now)
        if type(donor_id) is not int or donor_id <= 0:
            raise ValueError("Invalid donor identity")
        with self._sessions.begin() as session:
            donor = session.scalar(
                select(DonorChannel)
                .where(DonorChannel.id == donor_id)
                .with_for_update(skip_locked=True)
            )
            if donor is None:
                return None
            cursor = session.scalar(
                select(ChannelDifferenceCursorModel)
                .where(ChannelDifferenceCursorModel.donor_channel_id == donor_id)
                .with_for_update(skip_locked=True)
            )
            if (
                cursor is None
                or _utc(cursor.available_at) > now
                or (cursor.lease_expires_at is not None and _utc(cursor.lease_expires_at) > now)
            ):
                return None
            account = session.get(
                TelegramAccount,
                donor.telegram_account_id,
                populate_existing=True,
                with_for_update=True,
            )
            if not self._healthy(account, now) or (
                cursor.telegram_account_id,
                cursor.telegram_user_id,
                cursor.telegram_channel_id,
            ) != (donor.telegram_account_id, account.telegram_user_id, donor.telegram_channel_id):
                return None
            if not self._mapping_ids(session, donor_id):
                return None
            validate_difference_request(
                str(account.id), str(donor.telegram_channel_id), cursor.pts, self._size
            )
            cursor.claim_token, cursor.lease_expires_at = str(uuid4()), now + timedelta(seconds=60)
            if cursor.last_error_code != "GAP_UNRESOLVED":
                cursor.last_error_code = None
            return ChannelDifferenceClaim(
                donor_id,
                account.id,
                account.telegram_user_id,
                donor.telegram_channel_id,
                cursor.pts,
                cursor.claim_token,
                sha256(account.encrypted_session.encode()).hexdigest(),
            )

    def _owned(self, session, claim):
        now = _clock(self._clock())
        donor = session.get(
            DonorChannel, claim.donor_id, populate_existing=True, with_for_update=True
        )
        cursor = session.get(
            ChannelDifferenceCursorModel,
            claim.donor_id,
            populate_existing=True,
            with_for_update=True,
        )
        if (
            donor is None
            or cursor is None
            or cursor.claim_token != claim.token
            or cursor.pts != claim.pts
            or cursor.lease_expires_at is None
            or _utc(cursor.lease_expires_at) <= now
        ):
            return None
        account = session.get(
            TelegramAccount, claim.account_id, populate_existing=True, with_for_update=True
        )
        if (
            not self._healthy(account, now)
            or (
                donor.telegram_account_id,
                donor.telegram_channel_id,
                cursor.telegram_account_id,
                cursor.telegram_user_id,
                cursor.telegram_channel_id,
            )
            != (
                claim.account_id,
                claim.channel_id,
                claim.account_id,
                claim.user_id,
                claim.channel_id,
            )
            or account.telegram_user_id != claim.user_id
            or sha256(account.encrypted_session.encode()).hexdigest() != claim.session_digest
        ):
            return None
        return cursor

    @staticmethod
    def _mapping_ids(session, donor_id):
        ids = tuple(
            session.scalars(
                select(ChannelMappingModel.id)
                .where(ChannelMappingModel.donor_channel_id == donor_id)
                .order_by(ChannelMappingModel.id)
                .limit(101)
            )
        )
        if len(ids) > 100:
            raise ValueError("Difference mapping fan-out exceeds bound")
        return ids

    @staticmethod
    def _mapping_snapshot(session, donor_id, *, lock=False):
        query = (
            select(ChannelMappingModel)
            .where(ChannelMappingModel.donor_channel_id == donor_id)
            .order_by(ChannelMappingModel.id)
            .limit(101)
            .execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update()
        rows = session.scalars(query).all()
        if len(rows) > 100:
            raise ValueError("Difference mapping fan-out exceeds bound")
        bindings = []
        for row in rows:
            policy = session.get(
                MappingFilterPolicyModel, row.id, populate_existing=True, with_for_update=lock
            )
            bindings.append(
                (
                    row.id,
                    row.output_channel_id,
                    row.intake_percent,
                    row.target_mix_percent,
                    row.eligibility_mode,
                    row.delay_minutes,
                    row.priority,
                    row.media_policy,
                    None
                    if policy is None
                    else (policy.allowed_media_types, policy.blocked_domains, policy.ad_markers),
                )
            )
        return tuple(row.id for row in rows), sha256(
            json.dumps(bindings, sort_keys=True).encode()
        ).hexdigest()

    def run_donor(self, donor_id, *, now):
        _clock(now)
        with self._sessions() as session:
            if session.get(ChannelDifferenceCursorModel, donor_id) is None:
                return "BOOTSTRAP_REQUIRED"
        claim = self.claim(donor_id, now=now)
        return "IDLE" if claim is None else self.execute(claim)

    def execute(self, claim):
        if not isinstance(claim, ChannelDifferenceClaim):
            raise TypeError("Validated difference claim required")
        with self._sessions.begin() as session:
            if self._owned(session, claim) is None:
                return "STALE_CLAIM"
        try:
            difference = self._provider.channel_difference(
                str(claim.account_id), str(claim.channel_id), pts=claim.pts, limit=self._size
            )
            if not isinstance(difference, TelegramChannelDifference):
                raise TypeError("Malformed difference")
            difference.__post_init__()
            if (difference.account_id, difference.donor_identifier, difference.start_pts) != (
                str(claim.account_id),
                str(claim.channel_id),
                claim.pts,
            ) or len(difference.messages) + len(difference.deleted_message_ids) > self._size:
                raise ValueError("Foreign or oversized difference chunk")
        except ChannelDifferenceGapUnresolved:
            return self._failure(claim, "GAP_UNRESOLVED", delay=300)
        except FloodWait as exc:
            if type(exc.seconds) is not int or not 1 <= exc.seconds <= 2147483647:
                return self._failure(claim, "FAILED_PROVIDER_CONTRACT")
            return self._failure(claim, "COOLDOWN", delay=exc.seconds, health="COOLDOWN")
        except SessionUnavailable:
            return self._failure(claim, "SESSION_INVALID", health="SESSION_INVALID")
        except (TimeoutError, ConnectionError, OSError):
            return self._failure(claim, "RETRY_PROVIDER")
        except (ValueError, TypeError, LookupError):
            return self._failure(claim, "FAILED_PROVIDER_CONTRACT")
        try:
            SourceDeletionService(self._sessions).record(
                difference,
                observed_at=_clock(self._clock()),
                transaction_guard=lambda current: self._owned(current, claim) is not None,
            )
            with self._sessions() as session:
                mappings, mapping_binding = self._mapping_snapshot(session, claim.donor_id)
            if not mappings:
                return self._failure(claim, "MAPPING_REMOVED")
            for event in difference.messages:
                for mapping_id in mappings:
                    with self._sessions() as session:
                        result = DurableIngestionWorkflow(
                            session,
                            configured_mapping_id=mapping_id,
                            transaction_guard=lambda current: (
                                self._owned(current, claim) is not None
                            ),
                        ).ingest(event, observed_at=_clock(self._clock()))
                        if result.status == "STALE_CLAIM":
                            return "STALE_CLAIM"
                        if result.status == "MAPPING_REMOVED":
                            return self._failure(claim, "MAPPING_CHANGED")
                    with self._sessions.begin() as session:
                        cursor = self._owned(session, claim)
                        if cursor is None:
                            return "STALE_CLAIM"
                        cursor.lease_expires_at = _clock(self._clock()) + timedelta(seconds=60)
            with self._sessions.begin() as session:
                cursor = self._owned(session, claim)
                if cursor is None:
                    return "STALE_CLAIM"
                if self._mapping_snapshot(session, claim.donor_id, lock=True) != (
                    mappings,
                    mapping_binding,
                ):
                    if cursor.last_error_code != "GAP_UNRESOLVED":
                        cursor.last_error_code = "MAPPING_CHANGED"
                    cursor.available_at = _clock(self._clock()) + timedelta(seconds=30)
                    cursor.claim_token = cursor.lease_expires_at = None
                    return "MAPPING_CHANGED"
                cursor.pts = difference.next_pts
                cursor.available_at = _clock(self._clock()) + timedelta(
                    seconds=difference.retry_after_seconds if difference.final else 0
                )
                cursor.claim_token = cursor.lease_expires_at = None
                if difference.final or cursor.last_error_code != "GAP_UNRESOLVED":
                    cursor.last_error_code = None
            return "DIFFERENCE_COMPLETE" if difference.final else "DIFFERENCE_CONTINUE"
        except SourceDeletionClaimLost:
            return "STALE_CLAIM"
        except (SQLAlchemyError, ValueError, TypeError, LookupError):
            return self._failure(claim, "RETRY_PIPELINE")

    def _failure(self, claim, code, *, delay=30, health=None):
        now = _clock(self._clock())
        with self._sessions.begin() as session:
            cursor = self._owned(session, claim)
            if cursor is None:
                return "STALE_CLAIM"
            cursor.available_at = now + timedelta(seconds=delay)
            if cursor.last_error_code != "GAP_UNRESOLVED":
                cursor.last_error_code = code
            cursor.claim_token = cursor.lease_expires_at = None
            if health is not None:
                account = session.get(
                    TelegramAccount, claim.account_id, populate_existing=True, with_for_update=True
                )
                account.health_status = health
                account.health_checked_at = max(
                    _utc(account.health_checked_at) if account.health_checked_at else now, now
                )
                if health == "COOLDOWN":
                    account.cooldown_until = max(
                        _utc(account.cooldown_until) if account.cooldown_until else now,
                        now + timedelta(seconds=delay),
                    )
        return code
