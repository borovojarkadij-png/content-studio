"""PostgreSQL rewrite claims/retries with editorial and draft boundaries.

Provider construction is injected; the scheduler does not yet enable network
execution. PostgreSQL SKIP LOCKED + per-attempt fencing prevents stale completion.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from newsflow.domain.editorial import EditorialDecision, EditorialStatus, editorial_allows_rewrite
from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutboxEventModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteUsageModel,
)
from newsflow.providers.openai_rewrite import (
    ProviderConfigurationInvalid,
    ProviderResponseInvalid,
    RewriteUsage,
)
from newsflow.providers.openrouter import ProviderUnavailable
from newsflow.services.fact_guard import FactGuard, FactPreservationBlocked
from newsflow.services.rewrite import RewriteService, TextRewriteProvider
from newsflow.services.rewrite_outputs import RewriteOutputService


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _clock(now: datetime) -> None:
    if now.tzinfo is None:
        raise ValueError("Rewrite clock must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RewriteClaim:
    job_id: int
    token: str


class DurableRewriteRunner:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        provider_for_channel: Callable[[int], TextRewriteProvider],
        max_attempts: int = 3,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
            raise ValueError("Rewrite attempts must be between 1 and 5")
        self._factory = session_factory
        self._provider = provider_for_channel
        self._max_attempts = max_attempts
        self._clock = clock or (lambda: datetime.now(UTC))

    def claim_next(self, *, now: datetime) -> RewriteClaim | None:
        _clock(now)
        with self._factory() as session, session.begin():
            job = session.scalar(
                select(RewriteJobModel)
                .where(
                    or_(
                        and_(
                            RewriteJobModel.state.in_(("DISPATCHED", "RETRY")),
                            or_(
                                RewriteJobModel.available_at.is_(None),
                                RewriteJobModel.available_at <= now,
                            ),
                        ),
                        and_(
                            RewriteJobModel.state == "RUNNING",
                            RewriteJobModel.lease_expires_at <= now,
                        ),
                    )
                )
                .order_by(RewriteJobModel.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            job.claim_token = str(uuid4())
            job.lease_expires_at = now + timedelta(seconds=60)
            job.state = "RUNNING"
            # Consume budget durably before any possible external side effect.
            if job.attempts >= self._max_attempts:
                job.last_error_code = "ATTEMPT_LIMIT"
            else:
                job.attempts += 1
                job.last_error_code = None
            return RewriteClaim(job.id, job.claim_token)

    def run_next(self, *, now: datetime) -> str:
        claimed = self.claim_next(now=now)
        return "IDLE" if claimed is None else self.execute_claim(claimed, now=now)

    def execute_claim(self, claimed: RewriteClaim, *, now: datetime) -> str:
        _clock(now)
        # Lock order matches review: job -> editorial -> output/candidate.
        # The editorial lock is retained during the bounded provider operation.
        with self._factory() as session:
            job = session.scalar(
                select(RewriteJobModel)
                .where(RewriteJobModel.id == claimed.job_id)
                .with_for_update()
            )
            if (
                job is None
                or job.state != "RUNNING"
                or job.claim_token != claimed.token
                or job.lease_expires_at is None
                or _utc(job.lease_expires_at) <= now
            ):
                return "STALE_CLAIM"
            decision = session.scalar(
                select(EditorialDecisionModel)
                .where(EditorialDecisionModel.content_key == job.content_key)
                .with_for_update()
            )
            if not self._editorial_pass(decision):
                return self._finish(session, job, "BLOCKED_EDITORIAL", "EDITORIAL_REWRITE_BLOCKED")
            if job.output_channel_id is None:
                return self._finish(session, job, "SUPERSEDED", "OUTPUT_REQUIRED")
            candidate = session.scalar(
                select(PublicationCandidateModel)
                .where(
                    PublicationCandidateModel.content_key == job.content_key,
                    PublicationCandidateModel.output_channel_id == job.output_channel_id,
                )
                .with_for_update()
            )
            if candidate is None or candidate.state != "AWAITING_REWRITE":
                return self._finish(session, job, "SUPERSEDED", "CANDIDATE_NOT_ELIGIBLE")
            revision = self._source_revision(session, job.content_key)
            if revision is None:
                return self._finish(session, job, "FAILED_SOURCE", "SOURCE_REVISION_MISSING")
            if not self._latest(session, revision):
                return self._finish(session, job, "SUPERSEDED", "SOURCE_REVISION_SUPERSEDED")
            if job.last_error_code == "ATTEMPT_LIMIT":
                return self._finish(session, job, "FAILED", "ATTEMPT_LIMIT")
            snapshot = EditorialDecision(
                EditorialStatus.PASS,
                True,
                (),
                tuple(decision.protected_entities.split(",")),
                decision.sentiment,
                decision.framing,
            )
            try:
                FactGuard().validate_source(revision.source_text)
                provider = self._provider(job.output_channel_id)
                try:
                    rewritten = RewriteService(provider).rewrite(revision.source_text, snapshot)
                finally:
                    usage = getattr(provider, "last_usage", None)
                    if isinstance(usage, RewriteUsage):
                        session.add(
                            RewriteUsageModel(
                                rewrite_job_id=job.id,
                                attempt=job.attempts,
                                provider=usage.provider,
                                model=usage.model,
                                style=usage.style,
                                input_tokens=usage.input_tokens,
                                cached_tokens=usage.cached_tokens,
                                output_tokens=usage.output_tokens,
                                estimated_cost_usd=usage.estimated_cost_usd,
                            )
                        )
            except (ProviderConfigurationInvalid, ProviderResponseInvalid) as exc:
                if not self._live_lease(job, claimed, now):
                    session.commit()  # Preserve known usage, not an expired owner's result.
                    return "STALE_CLAIM"
                state = (
                    "FAILED_CONFIGURATION"
                    if isinstance(exc, ProviderConfigurationInvalid)
                    else "FAILED_RESPONSE"
                )
                return self._finish(session, job, state, state)
            except FactPreservationBlocked:
                if not self._live_lease(job, claimed, now):
                    session.commit()
                    return "STALE_CLAIM"
                return self._finish(session, job, "FAILED_FACTS", "FACT_PRESERVATION_BLOCKED")
            except ProviderUnavailable:
                if not self._live_lease(job, claimed, now):
                    session.commit()
                    return "STALE_CLAIM"
                state = "FAILED" if job.attempts >= self._max_attempts else "RETRY"
                job.available_at = now + timedelta(seconds=30 * job.attempts)
                return self._finish(session, job, state, "PROVIDER_UNAVAILABLE")
            except ValueError:
                if not self._live_lease(job, claimed, now):
                    session.commit()
                    return "STALE_CLAIM"
                return self._finish(
                    session, job, "FAILED_SOURCE", "SOURCE_OR_CONFIGURATION_INVALID"
                )
            # Recheck after the external boundary, before durable result creation.
            if not self._live_lease(job, claimed, now):
                session.commit()
                return "STALE_CLAIM"
            session.refresh(decision)
            if not self._editorial_pass(decision):
                return self._finish(session, job, "BLOCKED_EDITORIAL", "EDITORIAL_REWRITE_BLOCKED")
            if not self._latest(session, revision):
                return self._finish(session, job, "SUPERSEDED", "SOURCE_REVISION_SUPERSEDED")
            job.state, job.claim_token, job.lease_expires_at = "SUCCEEDED", None, None
            job.last_error_code, job.available_at = None, None
            session.add(
                OutboxEventModel(
                    event_type="rewrite.completed",
                    aggregate_key=job.content_key,
                    idempotency_key=f"rewrite.completed:{job.id}",
                )
            )
            # This commits draft + succeeded state + outbox atomically; no activation.
            RewriteOutputService(session).record_succeeded_output(job.id, rewritten)
            return "SUCCEEDED"

    def _live_lease(self, job: RewriteJobModel, claimed: RewriteClaim, now: datetime) -> bool:
        completed_at = self._clock()
        _clock(completed_at)
        return (
            job.state == "RUNNING"
            and job.claim_token == claimed.token
            and job.lease_expires_at is not None
            and _utc(job.lease_expires_at) > max(now, completed_at)
        )

    @staticmethod
    def _finish(session: Session, job: RewriteJobModel, state: str, reason: str) -> str:
        job.state, job.last_error_code = state, reason
        job.claim_token, job.lease_expires_at = None, None
        session.commit()
        return state

    @staticmethod
    def _editorial_pass(decision: EditorialDecisionModel | None) -> bool:
        return editorial_allows_rewrite(decision)

    @staticmethod
    def _source_revision(session: Session, content_key: str) -> ContentRevisionModel | None:
        # Join immutable identities instead of ambiguously splitting delimiter strings.
        key = (
            IncomingPostModel.telegram_account_id
            + ":"
            + IncomingPostModel.donor_channel_id
            + ":"
            + cast(IncomingPostModel.telegram_message_id, String)
            + ":revision:"
            + cast(ContentRevisionModel.revision_number, String)
        )
        rows = session.scalars(
            select(ContentRevisionModel).join(IncomingPostModel).where(key == content_key).limit(2)
        ).all()
        return rows[0] if len(rows) == 1 else None

    @staticmethod
    def _latest(session: Session, revision: ContentRevisionModel) -> bool:
        return (
            session.scalar(
                select(func.max(ContentRevisionModel.revision_number)).where(
                    ContentRevisionModel.incoming_post_id == revision.incoming_post_id
                )
            )
            == revision.revision_number
        )
