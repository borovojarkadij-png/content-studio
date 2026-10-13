"""Bounded durable aggregate sampling; committed leases fence external IO."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select

from newsflow.domain.engagement import (
    TelegramEngagementObservation,
    utc_timestamp,
    validate_engagement_request,
)
from newsflow.domain.engagement_sampling import advance_sampling
from newsflow.persistence.models import (
    ChannelMappingModel,
    ContentRevisionModel,
    DonorChannel,
    IncomingPostModel,
    TelegramAccount,
)
from newsflow.persistence.models import (
    TelegramEngagementSamplingJobModel as Job,
)
from newsflow.providers.telegram import FloodWait, SessionUnavailable
from newsflow.services.source_revisions import (
    source_identity_deleted,
    source_identity_sync_blocked,
)
from newsflow.services.telegram_engagement_history import TelegramEngagementHistory


@dataclass(frozen=True, slots=True)
class EngagementSamplingAdmission:
    cursor: int
    queued_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class EngagementSamplingClaim:
    incoming_post_id: int
    account_id: str
    donor_identifier: str
    message_id: int
    step: int
    token: str = field(repr=False)
    lease_expires_at: datetime
    expected_user_id: int
    session_digest: str = field(repr=False)


def _id(value, *, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value < 2**63:
        raise ValueError("Invalid sampling identifier")


class TelegramEngagementSamplingRunner:
    def __init__(self, session_factory, *, provider, clock):
        self._sessions = session_factory
        self._provider = provider
        self._clock = clock

    def enqueue_window(self, *, now, after_id=0, limit=16):
        now = utc_timestamp(now)
        _id(after_id, zero=True)
        if type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("Invalid bounded sampling window")
        with self._sessions() as session:
            ids = tuple(
                session.scalars(
                    select(IncomingPostModel.id)
                    .where(IncomingPostModel.id > after_id)
                    .order_by(IncomingPostModel.id)
                    .limit(limit)
                )
            )
            if not ids and after_id:
                ids = tuple(
                    session.scalars(
                        select(IncomingPostModel.id).order_by(IncomingPostModel.id).limit(limit)
                    )
                )
        queued = []
        for post_id in ids:
            with self._sessions() as session, session.begin():
                post = self._post(session, post_id, skip=True)
                if post is None or session.get(Job, post_id) is not None:
                    continue
                created = self._utc(session, post.created_at)
                if not timedelta(0) <= now - created <= timedelta(minutes=60):
                    continue
                account, status = self._current(session, post, now)
                if status or account.health_status != "CONNECTED":
                    continue
                session.add(
                    Job(
                        incoming_post_id=post_id,
                        state="QUEUED",
                        step=0,
                        attempts=0,
                        missed_windows=0,
                        available_at=now,
                        created_at=now,
                    )
                )
                queued.append(post_id)
        return EngagementSamplingAdmission(ids[-1] if ids else 0, tuple(queued))

    def claim_next(self, *, now):
        now = utc_timestamp(now)
        due = or_(
            and_(Job.state == "QUEUED", Job.available_at <= now),
            and_(Job.state == "RUNNING", Job.lease_expires_at <= now),
        )
        # No job lock is held while looking for the incoming row to lock first.
        with self._sessions() as session:
            ids = tuple(
                session.scalars(
                    select(Job.incoming_post_id)
                    .where(due)
                    .order_by(Job.available_at, Job.incoming_post_id)
                    .limit(16)
                )
            )
        for post_id in ids:
            with self._sessions() as session, session.begin():
                post = self._post(session, post_id, skip=True)
                if post is None:
                    continue
                job = session.scalar(
                    select(Job)
                    .where(Job.incoming_post_id == post_id, due)
                    .with_for_update(skip_locked=True)
                )
                if job is None:
                    continue
                if job.attempts >= 3:
                    self._finish(job, "FAILED", "ATTEMPTS_EXHAUSTED")
                    continue
                account, status = self._current(session, post, now, skip=True)
                if status == "LOCKED":
                    continue
                if status:
                    self._permission(job, account, status, now, session)
                    continue
                try:
                    expiry = now + timedelta(seconds=60)
                except OverflowError:
                    self._finish(job, "FAILED", "INVALID_SCHEDULE")
                    continue
                job.state = "RUNNING"
                job.available_at = max(now, self._utc(session, job.created_at))
                job.claim_token = str(uuid4())
                job.lease_expires_at = expiry
                job.expected_user_id = account.telegram_user_id
                job.session_digest = sha256(account.encrypted_session.encode()).hexdigest()
                job.attempts += 1
                job.last_error_code = None
                return EngagementSamplingClaim(
                    post.id,
                    post.telegram_account_id,
                    post.donor_channel_id,
                    post.telegram_message_id,
                    job.step,
                    job.claim_token,
                    expiry,
                    job.expected_user_id,
                    job.session_digest,
                )
        return None

    def run_next(self, *, now):
        claim = self.claim_next(now=now)
        return "IDLE" if claim is None else self.execute(claim)

    @staticmethod
    def _validate_claim(claim):
        if not isinstance(claim, EngagementSamplingClaim):
            raise ValueError("Validated sampling claim required")  # noqa: TRY004
        _id(claim.incoming_post_id)
        _id(claim.expected_user_id)
        expiry = validate_engagement_request(
            claim.account_id, claim.donor_identifier, claim.message_id, claim.lease_expires_at
        )
        if type(claim.step) is not int or not 0 <= claim.step <= 6:
            raise ValueError("Invalid sampling step")
        if not isinstance(claim.token, str):
            raise ValueError("Invalid sampling token")  # noqa: TRY004
        try:
            valid_token = str(UUID(claim.token)) == claim.token
        except ValueError:
            valid_token = False
        if (
            not valid_token
            or not isinstance(claim.session_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", claim.session_digest) is None
        ):
            raise ValueError("Invalid sampling claim identity")
        # Reconstruct rather than trusting frozen objects or normalization side effects.
        return EngagementSamplingClaim(
            claim.incoming_post_id,
            claim.account_id,
            claim.donor_identifier,
            claim.message_id,
            claim.step,
            claim.token,
            expiry,
            claim.expected_user_id,
            claim.session_digest,
        )

    def execute(self, claim):
        claim = self._validate_claim(claim)
        with self._sessions() as session, session.begin():
            owned = self._owned(session, claim)
            if owned is None:
                return "STALE_CLAIM"
            _post, job, account, status, now = owned
            if status:
                return self._permission(job, account, status, now, session)
        observed = utc_timestamp(self._clock())
        if observed < now or not self._within(claim, observed):
            return "STALE_CLAIM"
        try:
            value = self._provider.fetch_engagement(
                claim.account_id, claim.donor_identifier, claim.message_id, observed_at=observed
            )
            if not isinstance(value, TelegramEngagementObservation):
                raise TypeError("Invalid aggregate observation")
            value = TelegramEngagementObservation(
                value.account_id,
                value.donor_identifier,
                value.message_id,
                value.published_at,
                value.observed_at,
                value.views,
                value.forwards,
                value.reactions,
            )
            if (value.account_id, value.donor_identifier, value.message_id, value.observed_at) != (
                claim.account_id,
                claim.donor_identifier,
                claim.message_id,
                observed,
            ):
                raise ValueError("Mismatched aggregate observation")
        except FloodWait as error:
            return self._failure(claim, "FLOOD_WAIT", observed=observed, seconds=error.seconds)
        except SessionUnavailable:
            return self._failure(claim, "SESSION_UNAVAILABLE", observed=observed)
        except (TimeoutError, ConnectionError, OSError):
            return self._failure(claim, "RETRY_PROVIDER", observed=observed)
        except LookupError:
            return self._failure(claim, "SOURCE_UNAVAILABLE", observed=observed)
        except Exception:  # noqa: BLE001 -- provider boundary must not expose private failures
            # Provider exceptions are private; SQL failures remain outside this boundary.
            return self._failure(claim, "INVALID_OBSERVATION", observed=observed)
        with self._sessions() as session, session.begin():
            owned = self._owned(session, claim)
            if owned is None:
                return "STALE_CLAIM"
            _post, job, account, status, now = owned
            if now < observed:
                return "STALE_CLAIM"
            if status:
                return self._permission(job, account, status, now, session)
            try:
                advance = advance_sampling(
                    value.published_at,
                    value.observed_at,
                    step=job.step,
                    missed_windows=job.missed_windows,
                )
            except (ValueError, OverflowError):
                self._finish(job, "FAILED", "INVALID_SCHEDULE")
                return "FAILED"
            try:
                # History validates conflicts before writing. One outer transaction
                # keeps source, snapshot and job atomic, including SQLite legacy mode.
                TelegramEngagementHistory(session).record(value)
            except (ValueError, LookupError, TypeError):
                self._finish(job, "BLOCKED", "INVALID_OBSERVATION")
                return "BLOCKED"
            self._finish(job, "SUCCEEDED" if advance.step == 7 else "QUEUED")
            job.step = advance.step
            job.available_at = max(advance.available_at, self._utc(session, job.created_at))
            job.attempts = 0
            job.missed_windows = advance.missed_windows
            return "SUCCEEDED" if advance.step == 7 else "SAMPLED"

    def _owned(self, session, claim):
        post = self._post(session, claim.incoming_post_id)
        if post is None:
            return None
        job = session.scalar(
            select(Job)
            .where(Job.incoming_post_id == post.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        account, status = self._current(session, post, None)
        # Sample after all final locks, including waits on account ownership.
        now = utc_timestamp(self._clock())
        if (
            job is None
            or job.state != "RUNNING"
            or job.claim_token != claim.token
            or job.step != claim.step
            or job.expected_user_id != claim.expected_user_id
            or job.session_digest != claim.session_digest
            or self._utc(session, job.lease_expires_at) != claim.lease_expires_at
            or not self._within(claim, now)
            or (post.telegram_account_id, post.donor_channel_id, post.telegram_message_id)
            != (claim.account_id, claim.donor_identifier, claim.message_id)
        ):
            return None
        if account is not None and (
            account.telegram_user_id != claim.expected_user_id
            or sha256(account.encrypted_session.encode()).hexdigest() != claim.session_digest
        ):
            return None
        if account is not None:
            health = self._health(session, account, now)
            status = health if health == "SESSION_UNAVAILABLE" else status or health
        return post, job, account, status, now

    def _failure(self, claim, code, *, observed, seconds=30):
        with self._sessions() as session, session.begin():
            owned = self._owned(session, claim)
            if owned is None:
                return "STALE_CLAIM"
            _post, job, account, status, now = owned
            if now < observed:
                return "STALE_CLAIM"
            if status and not (code == "FLOOD_WAIT" and status == "WAIT_COOLDOWN"):
                return self._permission(job, account, status, now, session)
            if code == "SESSION_UNAVAILABLE":
                account.health_status = "SESSION_INVALID"
                account.health_checked_at = max(
                    now,
                    self._utc(session, account.health_checked_at)
                    if account.health_checked_at
                    else now,
                )
                self._finish(job, "BLOCKED", code)
                return "BLOCKED"
            if code in {"SOURCE_UNAVAILABLE", "INVALID_OBSERVATION"}:
                self._finish(job, "BLOCKED", code)
                return "BLOCKED"
            try:
                if type(seconds) is not int or seconds < 0:
                    raise ValueError("Invalid provider delay")
                future = now + timedelta(seconds=seconds)
                if code == "FLOOD_WAIT":
                    future = max(
                        future,
                        self._utc(session, account.cooldown_until)
                        if account.cooldown_until
                        else now,
                    )
            except (ValueError, OverflowError):
                self._finish(job, "FAILED", "INVALID_SCHEDULE")
                return "FAILED"
            if code == "FLOOD_WAIT":
                account.health_status = "COOLDOWN"
                account.cooldown_until = future
                account.health_checked_at = max(
                    now,
                    self._utc(session, account.health_checked_at)
                    if account.health_checked_at
                    else now,
                )
            if job.attempts >= 3:
                self._finish(job, "FAILED", "ATTEMPTS_EXHAUSTED")
                return "FAILED"
            self._finish(job, "QUEUED", code)
            job.available_at = max(future, self._utc(session, job.created_at))
            return code

    @staticmethod
    def _within(claim, now):
        try:
            return claim.lease_expires_at - timedelta(seconds=60) <= now < claim.lease_expires_at
        except OverflowError:
            return False

    @staticmethod
    def _utc(session, value):
        if value.tzinfo is None and session.get_bind().dialect.name == "sqlite":
            return value.replace(tzinfo=UTC)
        return utc_timestamp(value)

    @staticmethod
    def _post(session, post_id, *, skip=False):
        return session.scalar(
            select(IncomingPostModel)
            .where(IncomingPostModel.id == post_id)
            .with_for_update(skip_locked=skip)
            .execution_options(populate_existing=True)
        )

    def _current(self, session, post, now, *, skip=False):
        try:
            validate_engagement_request(
                post.telegram_account_id,
                post.donor_channel_id,
                post.telegram_message_id,
                datetime(2000, 1, 1, tzinfo=UTC),
            )
        except ValueError:
            return None, "SOURCE_UNAVAILABLE"
        account = session.scalar(
            select(TelegramAccount)
            .where(TelegramAccount.id == int(post.telegram_account_id))
            .with_for_update(skip_locked=skip)
            .execution_options(populate_existing=True)
        )
        if account is None:
            # Distinguish an absent account from one skipped due to another owner.
            exists = session.get(TelegramAccount, int(post.telegram_account_id)) if skip else None
            return None, "LOCKED" if exists is not None else "SESSION_UNAVAILABLE"
        donor = session.scalar(
            select(DonorChannel.id)
            .join(ChannelMappingModel, ChannelMappingModel.donor_channel_id == DonorChannel.id)
            .where(
                DonorChannel.telegram_account_id == account.id,
                DonorChannel.telegram_channel_id == int(post.donor_channel_id),
            )
            .limit(1)
        )
        revision = session.scalar(
            select(ContentRevisionModel.id)
            .where(ContentRevisionModel.incoming_post_id == post.id)
            .limit(1)
        )
        if (
            donor is None
            or revision is None
            or source_identity_deleted(
                session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
            )
        ):
            return account, "SOURCE_UNAVAILABLE"
        if (
            not isinstance(account.encrypted_session, str)
            or not account.encrypted_session
            or type(account.telegram_user_id) is not int
            or not 0 < account.telegram_user_id < 2**63
        ):
            return account, "SESSION_UNAVAILABLE"
        health = self._health(session, account, now) if now is not None else None
        if health:
            return account, health
        if source_identity_sync_blocked(session, post.telegram_account_id, post.donor_channel_id):
            return account, "WAIT_SYNC"
        return account, None

    def _health(self, session, account, now):
        if account.health_status not in {"CONNECTED", "COOLDOWN"}:
            return "SESSION_UNAVAILABLE"
        if account.cooldown_until is not None and self._utc(session, account.cooldown_until) > now:
            return "WAIT_COOLDOWN"
        return None

    def _permission(self, job, account, status, now, session):
        if status in {"WAIT_SYNC", "WAIT_COOLDOWN"}:
            try:
                future = now + timedelta(seconds=30)
                if account is not None and account.cooldown_until:
                    future = max(future, self._utc(session, account.cooldown_until))
            except OverflowError:
                self._finish(job, "FAILED", "INVALID_SCHEDULE")
                return "FAILED"
            self._finish(job, "QUEUED", status)
            job.available_at = max(future, self._utc(session, job.created_at))
            return status
        self._finish(job, "BLOCKED", status)
        return "BLOCKED"

    @staticmethod
    def _finish(job, state, code=None):
        job.state = state
        job.last_error_code = code
        job.claim_token = job.lease_expires_at = None
        job.expected_user_id = job.session_digest = None
