"""Qualification and immutable evidence gates; no network or transport here."""

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    AutomaticApprovalPolicyModel,
    EditorialDecisionModel,
    OutputChannel,
    RewriteJobModel,
    RewriteOutputModel,
    SemanticEvidenceModel,
    SemanticVerifierReleaseModel,
)
from newsflow.services.semantic_facts import (
    BENCHMARK_VERSION,
    PROMPT_VERSION,
    assess_semantic_facts,
    parse_semantic_evidence,
    text_digest,
)
from newsflow.services.source_revisions import (
    revision_is_latest,
    source_is_current,
    source_revision,
)


class AutomaticApprovalBlocked(PermissionError):
    pass


def release_digest(release) -> str:
    return text_digest(
        json.dumps(
            {
                "id": release.id,
                "provider": release.provider,
                "model": release.model,
                "prompt_version": release.prompt_version,
                "benchmark_version": release.benchmark_version,
                "report_sha256": release.report_sha256,
            },
            sort_keys=True,
        )
    )


def release_is_qualified(release: SemanticVerifierReleaseModel | None) -> bool:
    return bool(
        release is not None
        and release.active is True
        and release.provider in {"OPENAI", "OPENROUTER"}
        and release.model != "openrouter/free"
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", release.model)
        and (release.provider != "OPENROUTER" or release.model.endswith(":free"))
        and release.prompt_version == PROMPT_VERSION
        and release.benchmark_version == BENCHMARK_VERSION
        and re.fullmatch(r"[a-f0-9]{64}", release.report_sha256)
    )


def automatic_evidence_is_current(session: Session, output: RewriteOutputModel) -> bool:
    policy = session.scalar(
        select(AutomaticApprovalPolicyModel)
        .where(AutomaticApprovalPolicyModel.output_channel_id == output.output_channel_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if policy is None or policy.mode != "VERIFIED" or policy.release_id is None:
        return False
    release = session.scalar(
        select(SemanticVerifierReleaseModel)
        .where(SemanticVerifierReleaseModel.id == policy.release_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if not release_is_qualified(release):
        return False
    source = source_revision(session, output.content_key)
    if source is None or not revision_is_latest(session, source):
        return False
    evidence = session.scalar(
        select(SemanticEvidenceModel)
        .where(
            SemanticEvidenceModel.rewrite_output_id == output.id,
            SemanticEvidenceModel.source_revision_id == source.id,
            SemanticEvidenceModel.release_id == release.id,
            SemanticEvidenceModel.source_sha256 == text_digest(source.source_text),
            SemanticEvidenceModel.draft_sha256 == text_digest(output.rewritten_text),
            SemanticEvidenceModel.release_sha256 == release_digest(release),
            SemanticEvidenceModel.verdict == "PRESERVED",
            SemanticEvidenceModel.reason_codes == "",
        )
        .execution_options(populate_existing=True)
    )
    if evidence is None:
        return False
    try:
        # Re-parse the evidence, not just a stored PASS bit, at every use.
        return assess_semantic_facts(
            source.source_text,
            output.rewritten_text,
            parse_semantic_evidence(evidence.evidence_json),
        ).eligible
    except (ValueError, TypeError):
        return False


def approval_is_current(session: Session, output: RewriteOutputModel) -> bool:
    if output.approval_state != "APPROVED":
        return False
    job = session.scalar(
        select(RewriteJobModel)
        .where(RewriteJobModel.id == output.rewrite_job_id)
        .execution_options(populate_existing=True)
    )
    decision = session.scalar(
        select(EditorialDecisionModel)
        .where(EditorialDecisionModel.content_key == output.content_key)
        .execution_options(populate_existing=True)
    )
    if (
        job is None
        or job.state != "SUCCEEDED"
        or job.content_key != output.content_key
        or job.output_channel_id != output.output_channel_id
        or not editorial_allows_rewrite(decision)
        or not source_is_current(session, output.content_key)
    ):
        return False
    return (
        output.approval_method == "MANUAL"
        or output.approval_method == "AUTOMATIC"
        and automatic_evidence_is_current(session, output)
    )


class AutomaticApprovalPolicyService:
    def __init__(self, session: Session):
        self._session = session

    def get_policy(self, channel_id: int) -> dict[str, object]:
        if self._session.get(OutputChannel, channel_id) is None:
            raise LookupError("Output channel was not found")
        policy = self._session.get(AutomaticApprovalPolicyModel, channel_id)
        return {
            "output_channel_id": channel_id,
            "mode": policy.mode if policy else "MANUAL",
            "release_id": policy.release_id if policy else None,
            "qualified_releases": [
                {
                    "id": release.id,
                    "provider": release.provider,
                    "model": release.model,
                    "prompt_version": release.prompt_version,
                    "benchmark_version": release.benchmark_version,
                }
                for release in self._session.scalars(
                    select(SemanticVerifierReleaseModel).order_by(SemanticVerifierReleaseModel.id)
                )
                if release_is_qualified(release)
            ],
        }

    def configure(
        self, channel_id: int, mode: str, release_id: int | None = None
    ) -> dict[str, object]:
        try:
            if (
                mode not in {"MANUAL", "VERIFIED"}
                or release_id is not None
                and (type(release_id) is not int or release_id < 1)
            ):
                raise ValueError("AUTOMATIC_POLICY_INVALID")
            channel = self._session.scalar(
                select(OutputChannel).where(OutputChannel.id == channel_id).with_for_update()
            )
            if channel is None:
                raise LookupError("Output channel was not found")
            policy = self._session.scalar(
                select(AutomaticApprovalPolicyModel)
                .where(AutomaticApprovalPolicyModel.output_channel_id == channel_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
            if mode == "VERIFIED":
                release = self._session.scalar(
                    select(SemanticVerifierReleaseModel)
                    .where(SemanticVerifierReleaseModel.id == release_id)
                    .execution_options(populate_existing=True)
                    .with_for_update()
                )
                if not release_is_qualified(release):
                    raise AutomaticApprovalBlocked("SEMANTIC_VERIFIER_NOT_QUALIFIED")
            if policy is None:
                policy = AutomaticApprovalPolicyModel(output_channel_id=channel_id)
                self._session.add(policy)
            policy.mode, policy.release_id = mode, release_id if mode == "VERIFIED" else None
            self._session.flush()
            result = self.get_policy(channel_id)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise
