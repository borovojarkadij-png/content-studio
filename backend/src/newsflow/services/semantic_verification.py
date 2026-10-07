"""Guarded evidence transaction seam. Runtime leased execution is separate.

Never hold database locks over an external call. Recheck the immutable binding
afterwards; results obtained for a changed/rejected draft cannot be recorded.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    AutomaticApprovalPolicyModel,
    EditorialDecisionModel,
    RewriteJobModel,
    RewriteOutputModel,
    SemanticEvidenceModel,
    SemanticVerifierReleaseModel,
)
from newsflow.services.automatic_approval import (
    AutomaticApprovalBlocked,
    release_digest,
    release_is_qualified,
)
from newsflow.services.fact_guard import FactGuard
from newsflow.services.semantic_facts import SemanticReport, assess_semantic_facts, text_digest
from newsflow.services.source_revisions import revision_is_latest, source_revision


@dataclass(frozen=True, slots=True)
class VerifierRelease:
    id: int
    provider: str
    model: str
    prompt_version: str
    benchmark_version: str
    report_sha256: str


class SemanticVerifier(Protocol):
    provider: str
    model: str
    prompt_version: str

    def verify(self, source: str, draft: str) -> object: ...


@dataclass(frozen=True, slots=True)
class VerificationBinding:
    output_id: int
    revision_id: int
    source: str
    draft: str
    release: VerifierRelease


def _evidence(session: Session, binding: VerificationBinding) -> SemanticEvidenceModel | None:
    return session.scalar(
        select(SemanticEvidenceModel).where(
            SemanticEvidenceModel.rewrite_output_id == binding.output_id,
            SemanticEvidenceModel.source_revision_id == binding.revision_id,
            SemanticEvidenceModel.release_id == binding.release.id,
            SemanticEvidenceModel.source_sha256 == text_digest(binding.source),
            SemanticEvidenceModel.draft_sha256 == text_digest(binding.draft),
            SemanticEvidenceModel.release_sha256 == release_digest(binding.release),
        )
    )


def _project(evidence: SemanticEvidenceModel) -> dict[str, object]:
    return {
        "id": evidence.id,
        "rewrite_output_id": evidence.rewrite_output_id,
        "verdict": evidence.verdict,
        "reason_codes": evidence.reason_codes.split(",") if evidence.reason_codes else [],
        "release_id": evidence.release_id,
    }


class SemanticVerificationService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        verifier_for_release: Callable[[VerifierRelease], SemanticVerifier],
    ):
        self._factory, self._verifier = session_factory, verifier_for_release

    def verify(self, output_id: int) -> dict[str, object]:
        with self._factory() as session:
            binding = self._binding(session, output_id)
            existing = _evidence(session, binding)
            if existing is not None:
                return _project(existing)
        # Guards precede factory creation/decryption/network; never classify a reject.
        provider = self._verifier(binding.release)
        if (provider.provider, provider.model, provider.prompt_version) != (
            binding.release.provider,
            binding.release.model,
            binding.release.prompt_version,
        ):
            raise AutomaticApprovalBlocked("SEMANTIC_PROVIDER_IDENTITY_MISMATCH")
        try:
            report = assess_semantic_facts(
                binding.source, binding.draft, provider.verify(binding.source, binding.draft)
            )
        except Exception:  # noqa: BLE001 - never persist/log private provider exceptions
            report = SemanticReport("ERROR", ("SEMANTIC_PROVIDER_FAILED",))
        try:
            with self._factory() as session:
                if self._binding(session, output_id) != binding:
                    raise AutomaticApprovalBlocked("SEMANTIC_BINDING_CHANGED")
                existing = _evidence(session, binding)
                if existing is not None:
                    return _project(existing)
                evidence = SemanticEvidenceModel(
                    rewrite_output_id=output_id,
                    source_revision_id=binding.revision_id,
                    release_id=binding.release.id,
                    source_sha256=text_digest(binding.source),
                    draft_sha256=text_digest(binding.draft),
                    release_sha256=release_digest(binding.release),
                    verdict=report.verdict,
                    reason_codes=",".join(report.reason_codes),
                    evidence_json=report.evidence_json,
                )
                session.add(evidence)
                session.flush()
                result = _project(evidence)
                session.commit()
                return result
        except IntegrityError:
            # An injected concurrent executor completed the exact binding first.
            # Runtime must wrap this seam in durable leases before enabling calls.
            with self._factory() as session:
                if self._binding(session, output_id) != binding:
                    raise AutomaticApprovalBlocked("SEMANTIC_BINDING_CHANGED") from None
                existing = _evidence(session, binding)
                if existing is None:
                    raise
                return _project(existing)

    @staticmethod
    def _binding(session: Session, output_id: int) -> VerificationBinding:
        job_id = session.scalar(
            select(RewriteOutputModel.rewrite_job_id).where(RewriteOutputModel.id == output_id)
        )
        job = session.scalar(
            select(RewriteJobModel).where(RewriteJobModel.id == job_id).with_for_update()
        )
        if job is None or job.state != "SUCCEEDED":
            raise AutomaticApprovalBlocked("SEMANTIC_REWRITE_JOB_INVALID")
        editorial = session.scalar(
            select(EditorialDecisionModel)
            .where(EditorialDecisionModel.content_key == job.content_key)
            .with_for_update()
        )
        if not editorial_allows_rewrite(editorial):
            raise AutomaticApprovalBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")
        output = session.scalar(
            select(RewriteOutputModel).where(RewriteOutputModel.id == output_id).with_for_update()
        )
        if (
            output is None
            or output.approval_state != "PENDING"
            or output.content_key != job.content_key
            or output.output_channel_id != job.output_channel_id
        ):
            raise AutomaticApprovalBlocked("SEMANTIC_DRAFT_NOT_PENDING_OR_MISMATCHED")
        source = source_revision(session, output.content_key)
        if source is None or not revision_is_latest(session, source):
            raise AutomaticApprovalBlocked("SOURCE_REVISION_NOT_CURRENT_OR_MISSING")
        FactGuard().require_preserved(source.source_text, output.rewritten_text)
        policy = session.scalar(
            select(AutomaticApprovalPolicyModel)
            .where(AutomaticApprovalPolicyModel.output_channel_id == output.output_channel_id)
            .with_for_update()
        )
        if policy is None or policy.mode != "VERIFIED" or policy.release_id is None:
            raise AutomaticApprovalBlocked("SEMANTIC_AUTOMATIC_POLICY_DISABLED")
        release = session.scalar(
            select(SemanticVerifierReleaseModel)
            .where(SemanticVerifierReleaseModel.id == policy.release_id)
            .with_for_update()
        )
        if not release_is_qualified(release):
            raise AutomaticApprovalBlocked("SEMANTIC_VERIFIER_NOT_QUALIFIED")
        return VerificationBinding(
            output.id,
            source.id,
            source.source_text,
            output.rewritten_text,
            VerifierRelease(
                release.id,
                release.provider,
                release.model,
                release.prompt_version,
                release.benchmark_version,
                release.report_sha256,
            ),
        )
