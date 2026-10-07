"""PostgreSQL semantic jobs, committed budgets, bounded leases and fencing."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from newsflow.persistence.models import (
    AutomaticApprovalPolicyModel,
    RewriteOutputModel,
    SemanticVerificationJobModel,
    SemanticVerificationUsageModel,
    SemanticVerifierReleaseModel,
)
from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid, RewriteUsage
from newsflow.services.automatic_approval import AutomaticApprovalBlocked, release_digest
from newsflow.services.fact_guard import FactPreservationBlocked
from newsflow.services.rewrite_outputs import RewriteOutputBlocked, RewriteOutputService
from newsflow.services.semantic_facts import text_digest
from newsflow.services.semantic_verification import SemanticVerificationService


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _aware(value):
    if value.tzinfo is None:
        raise ValueError("Verification time must be timezone-aware")


class SemanticLeaseLost(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class SemanticClaim:
    job_id: int
    token: str
    attempt: int


class DurableSemanticRunner:
    def __init__(self, session_factory, *, verifier_for_release, clock=lambda: datetime.now(UTC)):
        self._factory, self._verifier, self._clock = session_factory, verifier_for_release, clock

    def enqueue_pending(self, *, now: datetime, limit: int = 100) -> int:
        _aware(now)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Verification enqueue limit must be between 1 and 100")
        with self._factory() as session:
            ids = session.scalars(
                select(RewriteOutputModel.id)
                .join(
                    AutomaticApprovalPolicyModel,
                    AutomaticApprovalPolicyModel.output_channel_id
                    == RewriteOutputModel.output_channel_id,
                )
                .join(
                    SemanticVerifierReleaseModel,
                    SemanticVerifierReleaseModel.id == AutomaticApprovalPolicyModel.release_id,
                )
                .where(
                    RewriteOutputModel.approval_state == "PENDING",
                    AutomaticApprovalPolicyModel.mode == "VERIFIED",
                    SemanticVerifierReleaseModel.active.is_(True),
                    ~select(SemanticVerificationJobModel.id)
                    .where(
                        SemanticVerificationJobModel.rewrite_output_id == RewriteOutputModel.id,
                        SemanticVerificationJobModel.release_id
                        == AutomaticApprovalPolicyModel.release_id,
                    )
                    .exists(),
                )
                .order_by(RewriteOutputModel.id)
                .limit(limit)
            ).all()
        created = 0
        for output_id in ids:
            try:
                with self._factory() as session:
                    binding = SemanticVerificationService._binding(session, output_id)
                    fields = {
                        "rewrite_output_id": output_id,
                        "source_revision_id": binding.revision_id,
                        "release_id": binding.release.id,
                        "source_sha256": text_digest(binding.source),
                        "draft_sha256": text_digest(binding.draft),
                        "release_sha256": release_digest(binding.release),
                    }
                    if (
                        session.scalar(select(SemanticVerificationJobModel.id).filter_by(**fields))
                        is not None
                    ):
                        continue
                    session.add(
                        SemanticVerificationJobModel(**fields, state="QUEUED", available_at=now)
                    )
                    session.commit()
                    created += 1
            except (AutomaticApprovalBlocked, FactPreservationBlocked, IntegrityError, ValueError):
                continue  # Reject/manual/unqualified/stale drafts never queue verification.
        return created

    def claim_next(self, *, now: datetime) -> SemanticClaim | None:
        _aware(now)
        with self._factory() as session:
            job = session.scalar(
                select(SemanticVerificationJobModel)
                .where(
                    or_(
                        and_(
                            SemanticVerificationJobModel.state == "QUEUED",
                            SemanticVerificationJobModel.available_at <= now,
                        ),
                        and_(
                            SemanticVerificationJobModel.state == "RUNNING",
                            SemanticVerificationJobModel.lease_expires_at <= now,
                        ),
                    )
                )
                .order_by(SemanticVerificationJobModel.id)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            if job.attempts >= 2:
                job.state, job.claim_token, job.lease_expires_at = "FAILED", None, None
                job.last_error_code = "SEMANTIC_ATTEMPTS_EXHAUSTED"
                session.commit()
                return None
            job.state, job.claim_token = "RUNNING", str(uuid4())
            job.lease_expires_at = now + timedelta(seconds=60)
            job.attempts += 1
            claim = SemanticClaim(job.id, job.claim_token, job.attempts)
            session.commit()
            return claim

    def run_next(self, *, now: datetime) -> str:
        claim = self.claim_next(now=now)
        return "IDLE" if claim is None else self.execute(claim)

    def _owned(self, session, claim):
        now = self._clock()
        _aware(now)
        job = session.scalar(
            select(SemanticVerificationJobModel)
            .where(SemanticVerificationJobModel.id == claim.job_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if (
            job is None
            or job.state != "RUNNING"
            or job.claim_token != claim.token
            or job.attempts != claim.attempt
            or job.lease_expires_at is None
            or _utc(job.lease_expires_at) <= now
        ):
            raise SemanticLeaseLost("SEMANTIC_LEASE_LOST")
        return job

    def _guard(self, session, claim):
        # Lock verification job first, then the common job/editorial/draft gates.
        job = self._owned(session, claim)
        binding = SemanticVerificationService._binding(session, job.rewrite_output_id)
        if (
            job.source_revision_id,
            job.release_id,
            job.source_sha256,
            job.draft_sha256,
            job.release_sha256,
        ) != (
            binding.revision_id,
            binding.release.id,
            text_digest(binding.source),
            text_digest(binding.draft),
            release_digest(binding.release),
        ):
            raise AutomaticApprovalBlocked("SEMANTIC_JOB_BINDING_CHANGED")

    def execute(self, claim: SemanticClaim) -> str:
        provider = []

        def factory(release):
            instance = self._verifier(release)
            provider.append(instance)
            return instance

        try:
            with self._factory() as session:
                output_id = self._owned(session, claim).rewrite_output_id
            result = SemanticVerificationService(
                self._factory, verifier_for_release=factory
            ).verify(output_id, execution_guard=lambda session: self._guard(session, claim))
            if result["verdict"] != "PRESERVED":
                return self._finish(
                    claim,
                    "FAILED" if result["verdict"] == "ERROR" else "REVIEW",
                    evidence_id=result["id"],
                )
            with self._factory() as session:

                def complete(transaction):
                    job = self._owned(transaction, claim)
                    job.state, job.evidence_id = "SUCCEEDED", result["id"]
                    job.claim_token, job.lease_expires_at = None, None

                RewriteOutputService(session).auto_approve(
                    output_id, activate_candidate=True, execution_guard=complete
                )
            return "SUCCEEDED"
        except SemanticLeaseLost:
            return "LOST_LEASE"
        except (AutomaticApprovalBlocked, FactPreservationBlocked, RewriteOutputBlocked):
            return self._finish(claim, "BLOCKED", error="SEMANTIC_GUARD_BLOCKED")
        except ProviderConfigurationInvalid:
            return self._finish(claim, "FAILED", error="SEMANTIC_CONFIGURATION_INVALID")
        finally:
            if provider:
                usage = getattr(provider[-1], "last_usage", None)
                if isinstance(usage, RewriteUsage):
                    self._record_usage(claim, usage)

    def _finish(self, claim, state, *, evidence_id=None, error=None):
        try:
            with self._factory() as session:
                job = self._owned(session, claim)
                job.state, job.evidence_id, job.last_error_code = state, evidence_id, error
                job.claim_token, job.lease_expires_at = None, None
                session.commit()
            return state
        except SemanticLeaseLost:
            return "LOST_LEASE"

    def _record_usage(self, claim, usage):
        with self._factory() as session:
            if (
                session.scalar(
                    select(SemanticVerificationUsageModel.id).where(
                        SemanticVerificationUsageModel.verification_job_id == claim.job_id,
                        SemanticVerificationUsageModel.attempt == claim.attempt,
                    )
                )
                is None
            ):
                session.add(
                    SemanticVerificationUsageModel(
                        verification_job_id=claim.job_id,
                        attempt=claim.attempt,
                        provider=usage.provider,
                        model=usage.model,
                        input_tokens=usage.input_tokens,
                        cached_tokens=usage.cached_tokens,
                        output_tokens=usage.output_tokens,
                        estimated_cost_usd=usage.estimated_cost_usd,
                    )
                )
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()  # Idempotent usage: never overwrite a prior attempt.
