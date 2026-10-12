"""Leased, diagnostic-only classifier execution with immutable attempt fencing."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.models import (
    EditorialClassificationAttemptModel as Attempt,
)
from newsflow.persistence.models import (
    EditorialClassificationClaimModel as ClaimHistory,
)
from newsflow.persistence.models import (
    EditorialClassificationJobModel as Job,
)
from newsflow.persistence.models import (
    OutboxEventModel,
)
from newsflow.providers.openai_rewrite import (
    ProviderConfigurationInvalid,
    ProviderResponseInvalid,
    RewriteUsage,
)
from newsflow.providers.openrouter import ProviderUnavailable
from newsflow.services.editorial_admission import (
    EditorialAdmissionBlocked,
    resolve_editorial_admission,
)
from newsflow.services.editorial_classification import assess_editorial_classification


@dataclass(frozen=True, slots=True)
class EditorialClaim:
    job_id: int
    token: str
    attempt: int


class EditorialLeaseLost(PermissionError):
    pass


def _time(value):
    try:
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError
        value = value.astimezone(UTC)
        if not math.isfinite(value.timestamp()):
            raise ValueError
        # The lease and retry instants must also be representable, before writes.
        value + timedelta(seconds=60)
        return value
    except (TypeError, ValueError, OverflowError):
        raise ValueError("EDITORIAL_TIME_INVALID") from None


def _persisted_time(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _claim_input(claim):
    if (
        type(claim) is not EditorialClaim
        or type(claim.job_id) is not int
        or claim.job_id <= 0
        or type(claim.attempt) is not int
        or not 1 <= claim.attempt <= 2
        or type(claim.token) is not str
    ):
        raise ValueError("EDITORIAL_CLAIM_INVALID")
    try:
        if str(UUID(claim.token)) != claim.token:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("EDITORIAL_CLAIM_INVALID") from None


def _binding(session, job):
    binding = resolve_editorial_admission(
        session, content_key=job.content_key, mapping_id=job.mapping_id
    )
    expected = (
        job.source_revision_id,
        job.mapping_id,
        job.editorial_decision_id,
        job.content_key,
        job.source_sha256,
        job.policy_sha256,
        job.mapping_sha256,
        job.provider,
        job.model,
        job.prompt_version,
    )
    actual = (
        binding.revision_id,
        binding.mapping_id,
        binding.decision_id,
        binding.request.content_key,
        binding.request.source_sha256,
        binding.request.policy_sha256,
        binding.mapping_sha256,
        binding.provider,
        binding.model,
        binding.request.prompt_version,
    )
    if actual != expected:
        raise EditorialAdmissionBlocked("EDITORIAL_BINDING_CHANGED")
    return binding


def _history(session, claim):
    return session.scalar(
        select(ClaimHistory).where(
            ClaimHistory.classification_job_id == claim.job_id,
            ClaimHistory.claim_token == claim.token,
            ClaimHistory.attempt == claim.attempt,
        )
    )


def _owned(job, claim, now):
    return (
        job is not None
        and job.state == "RUNNING"
        and job.claim_token == claim.token
        and job.attempts == claim.attempt
        and job.lease_expires_at is not None
        and _persisted_time(job.lease_expires_at) > now
    )


def _usage(value):
    if value is None:
        return {}, []
    if type(value) is RewriteUsage:
        counts = (value.input_tokens, value.cached_tokens, value.output_tokens)
        cost = value.estimated_cost_usd
        if (
            type(value.provider) is str
            and value.provider in {"OPENAI", "OPENROUTER"}
            and type(value.model) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", value.model)
            and all(type(item) is int and 0 <= item <= 2147483647 for item in counts)
            and value.cached_tokens <= value.input_tokens
            and (
                cost is None
                or (type(cost) is Decimal and cost.is_finite() and 0 <= cost < Decimal(10000000000))
            )
        ):
            return {
                "usage_observed": True,
                "input_tokens": counts[0],
                "cached_tokens": counts[1],
                "output_tokens": counts[2],
                "estimated_cost_usd": cost,
            }, []
    return {}, ["EDITORIAL_USAGE_INVALID"]


def _evidence(value):
    if type(value) is not str:
        return None, "EDITORIAL_EVIDENCE_MISSING" if value is None else "EDITORIAL_EVIDENCE_INVALID"
    try:
        if len(value.encode("utf-8")) <= 262144:
            return value, None
    except UnicodeError:
        return None, "EDITORIAL_EVIDENCE_INVALID"
    return None, "EDITORIAL_EVIDENCE_TOO_LARGE"


class DurableEditorialRunner:
    def __init__(self, session_factory, *, classifier_for_binding, clock=lambda: datetime.now(UTC)):
        self._factory = session_factory
        self._classifier = classifier_for_binding
        self._clock = clock

    def claim_next(self, *, now: datetime, limit: int = 16) -> EditorialClaim | None:
        return self._claim_next(now=now, limit=limit)[0]

    def _claim_next(self, *, now, limit):
        now = _time(now)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("EDITORIAL_LIMIT_INVALID")
        eligible = or_(
            and_(Job.state == "QUEUED", Job.available_at <= now),
            and_(Job.state == "RUNNING", Job.lease_expires_at <= now),
        )
        state = "IDLE"
        with self._factory() as session, session.begin():
            ids = session.scalars(
                select(Job.id).where(eligible).order_by(Job.id).limit(limit)
            ).all()
            for identity in ids:
                job = session.scalar(
                    select(Job)
                    .where(Job.id == identity, eligible)
                    .with_for_update(skip_locked=True)
                )
                if job is None:
                    continue
                try:
                    _binding(session, job)
                except EditorialAdmissionBlocked as exc:
                    self._transition(job, "BLOCKED", exc.reason_code)
                    state = "BLOCKED"
                    continue
                if (
                    job.state == "RUNNING"
                    and _history(session, EditorialClaim(job.id, job.claim_token, job.attempts))
                    is None
                ):
                    self._transition(job, "FAILED", "EDITORIAL_CLAIM_HISTORY_MISSING")
                    state = "FAILED"
                    continue
                if job.attempts >= 2:
                    self._transition(job, "FAILED", "EDITORIAL_ATTEMPTS_EXHAUSTED")
                    state = "FAILED"
                    continue
                job.attempts += 1
                job.state, job.claim_token = "RUNNING", str(uuid4())
                job.lease_expires_at = now + timedelta(seconds=60)
                job.last_error_code = None
                session.add(
                    ClaimHistory(
                        classification_job_id=job.id,
                        attempt=job.attempts,
                        claim_token=job.claim_token,
                        created_at=now,
                    )
                )
                session.flush()
                return EditorialClaim(job.id, job.claim_token, job.attempts), "RUNNING"
        return None, state

    def run_next(self, *, now: datetime) -> str:
        claim, state = self._claim_next(now=now, limit=16)
        return state if claim is None else self.execute(claim)

    def _check(self, claim):
        now = _time(self._clock())
        with self._factory() as session:
            history = _history(session, claim)
            if history is None:
                raise EditorialLeaseLost
            receipt = session.scalar(select(Attempt).where(Attempt.claim_id == history.id))
            if receipt is not None:
                return None, receipt.outcome
            job = session.get(Job, claim.job_id)
            if not _owned(job, claim, now):
                raise EditorialLeaseLost
            return _binding(session, job), None

    def execute(self, claim: EditorialClaim) -> str:
        _claim_input(claim)
        # Validate the clock even for forged/replayed claims, before any SQL side effect.
        _time(self._clock())
        client = None
        error = None
        attempted = False
        try:
            binding, replay = self._check(claim)
            if replay is not None:
                return replay
        except EditorialLeaseLost:
            return self._finish(claim, error="EDITORIAL_LEASE_LOST")
        except EditorialAdmissionBlocked as exc:
            return self._finish(claim, error=exc.reason_code)
        try:
            client = self._classifier(binding)
            if (client.provider, client.model, client.prompt_version) != (
                binding.provider,
                binding.model,
                binding.request.prompt_version,
            ):
                raise ProviderConfigurationInvalid
            # Construction may have raced with an independent committed canonical change.
            binding, replay = self._check(claim)
            if replay is not None:
                return replay
            attempted = True
            client.classify(binding.request)
        except EditorialLeaseLost:
            error = "EDITORIAL_LEASE_LOST"
        except EditorialAdmissionBlocked as exc:
            error = exc.reason_code
        except ProviderUnavailable:
            error = "EDITORIAL_PROVIDER_UNAVAILABLE"
        except ProviderConfigurationInvalid:
            error = "EDITORIAL_PROVIDER_CONFIGURATION_INVALID"
        except ProviderResponseInvalid:
            error = "EDITORIAL_PROVIDER_RESPONSE_INVALID"
        except SQLAlchemyError:
            raise
        except Exception:  # noqa: BLE001 - injected provider failures must become sanitized codes
            error = "EDITORIAL_PROVIDER_FAILED"
        # Access adapter diagnostics outside SQL as well; untrusted properties can fail.
        try:
            evidence = getattr(client, "last_evidence_json", None) if attempted else None
            usage = getattr(client, "last_usage", None) if attempted else None
            response_model = getattr(client, "last_response_model", None) if attempted else None
        except Exception:  # noqa: BLE001 - adapter properties are an untrusted diagnostic boundary
            evidence, usage, response_model = None, None, None
            error = "EDITORIAL_PROVIDER_RESPONSE_INVALID"
        return self._finish(
            claim, error=error, evidence=evidence, usage=usage, response_model=response_model
        )

    def _finish(self, claim, *, error=None, evidence=None, usage=None, response_model=None):
        now = _time(self._clock())
        raw, evidence_error = _evidence(evidence)
        observed, usage_reasons = _usage(usage)
        if (
            type(response_model) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", response_model) is None
        ):
            response_model = None
        with self._factory() as session, session.begin():
            job = session.scalar(select(Job).where(Job.id == claim.job_id).with_for_update())
            history = _history(session, claim)
            if history is None:
                return "LOST_LEASE"
            receipt = session.scalar(select(Attempt).where(Attempt.claim_id == history.id))
            if receipt is not None:
                return receipt.outcome
            allowed_models = (job.model,)
            if job.provider == "OPENROUTER":
                allowed_models += (job.model.removesuffix(":free"),)
            if response_model is not None and response_model not in allowed_models:
                response_model = None
                error = "EDITORIAL_RETURNED_MODEL_INVALID"
            diagnostic = None
            if not _owned(job, claim, now):
                state, reasons = "LOST_LEASE", ["EDITORIAL_LEASE_LOST"]
            else:
                try:
                    binding = _binding(session, job)
                except EditorialAdmissionBlocked as exc:
                    state, reasons = "BLOCKED", [exc.reason_code]
                else:
                    if error:
                        state = (
                            "RETRY"
                            if error == "EDITORIAL_PROVIDER_UNAVAILABLE" and claim.attempt < 2
                            else "FAILED"
                        )
                        reasons = [error]
                    elif evidence_error:
                        state, reasons = "FAILED", [evidence_error]
                    else:
                        report = assess_editorial_classification(binding.request, raw)
                        diagnostic = report.diagnostic_status
                        state = "REJECT" if report.decision.status.value == "REJECT" else "REVIEW"
                        reasons = list(report.reason_codes)
                self._transition(
                    job, "QUEUED" if state == "RETRY" else state, reasons[0] if reasons else None
                )
                if state == "RETRY":
                    job.available_at = now + timedelta(seconds=60)
            session.add(
                Attempt(
                    claim_id=history.id,
                    outcome=state,
                    diagnostic_status=diagnostic,
                    reason_codes=reasons + usage_reasons,
                    evidence_json=raw,
                    response_model=response_model,
                    created_at=now,
                    **observed,
                )
            )
            session.add(
                OutboxEventModel(
                    event_type="editorial.classification.attempted",
                    aggregate_key=job.content_key,
                    idempotency_key=f"editorial.classification.attempted:{claim.job_id}:{claim.attempt}",
                    created_at=now,
                )
            )
            session.flush()
            return state

    @staticmethod
    def _transition(job, state, reason):
        job.state, job.last_error_code = state, reason
        job.claim_token = job.lease_expires_at = None
