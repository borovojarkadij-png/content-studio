"""Retained verification history + fresh binding snapshot, never execution authority."""

from datetime import datetime

from sqlalchemy import select

from newsflow.persistence import models
from newsflow.services.automatic_approval import (
    AutomaticApprovalBlocked,
    release_digest,
    release_is_qualified,
)
from newsflow.services.durable_semantic_runner import _utc
from newsflow.services.fact_guard import FactPreservationBlocked
from newsflow.services.semantic_facts import text_digest
from newsflow.services.semantic_verification import SemanticVerificationService

REASONS = frozenset(
    {
        "SEMANTIC_REWRITE_JOB_INVALID",
        "EDITORIAL_HARD_CONSTRAINT_BLOCKED",
        "SEMANTIC_DRAFT_NOT_PENDING_OR_MISMATCHED",
        "SOURCE_REVISION_NOT_CURRENT_OR_MISSING",
        "SEMANTIC_AUTOMATIC_POLICY_DISABLED",
        "SEMANTIC_VERIFIER_NOT_QUALIFIED",
        "FACT_PRESERVATION_BLOCKED",
    }
)


class SemanticJobReader:
    def __init__(self, session):
        self._session = session

    def read(self, output_id, *, now):
        if type(output_id) is not int or output_id <= 0:
            raise ValueError("Canonical positive draft identity required")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Aware diagnostic clock required")
        session = self._session
        output = session.get(models.RewriteOutputModel, output_id, populate_existing=True)
        if output is None:
            raise LookupError("Draft not found")
        binding, reason, gate = None, None, "READY_SNAPSHOT"
        try:
            # Shared worker binding takes only short SQL locks. No provider factory,
            # enqueue, evidence creation, recovery, review or commit is invoked.
            binding = SemanticVerificationService._binding(session, output_id)
        except (AutomaticApprovalBlocked, FactPreservationBlocked, ValueError) as exc:
            reason = str(exc) if str(exc) in REASONS else "CURRENT_SEMANTIC_GUARD_BLOCKED"
            gate = {
                "SEMANTIC_AUTOMATIC_POLICY_DISABLED": "MANUAL",
                "SEMANTIC_DRAFT_NOT_PENDING_OR_MISMATCHED": "NOT_PENDING",
            }.get(reason, "BLOCKED")
        policy = session.get(
            models.AutomaticApprovalPolicyModel, output.output_channel_id, populate_existing=True
        )
        release = (
            session.get(
                models.SemanticVerifierReleaseModel, policy.release_id, populate_existing=True
            )
            if policy and policy.release_id
            else None
        )
        latest = session.scalar(
            select(models.SemanticVerificationJobModel)
            .where(models.SemanticVerificationJobModel.rewrite_output_id == output_id)
            .order_by(models.SemanticVerificationJobModel.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        job = None
        if latest is not None:
            current = None if gate == "NOT_PENDING" else False
            if binding is not None:
                current = (
                    latest.source_revision_id,
                    latest.release_id,
                    latest.source_sha256,
                    latest.draft_sha256,
                    latest.release_sha256,
                ) == (
                    binding.revision_id,
                    binding.release.id,
                    text_digest(binding.source),
                    text_digest(binding.draft),
                    release_digest(binding.release),
                )
            lease = latest.lease_expires_at
            job = {
                "id": latest.id,
                "state": latest.state,
                "attempts": latest.attempts,
                "max_attempts": 2,
                "release_id": latest.release_id,
                "binding_current": current,
                "available_at": _utc(latest.available_at).isoformat(),
                "lease_expires_at": _utc(lease).isoformat() if lease else None,
                "lease_expired": latest.state == "RUNNING"
                and (lease is None or _utc(lease) <= now),
            }
        return {
            "rewrite_output_id": output.id,
            "output_channel_id": output.output_channel_id,
            "approval_state": output.approval_state,
            "current_gate": gate,
            "reason_code": reason,
            "network_checked": False,
            "execution_authorized": False,
            # API environment cannot certify independently configured worker state.
            "worker_enabled": None,
            "policy_mode": policy.mode if policy else "MANUAL",
            "configured_release_id": policy.release_id if policy else None,
            "qualified_release": release_is_qualified(release),
            "latest_job": job,
        }
