"""Bounded read-only diagnostic receipts; never an execution permission source."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from newsflow.persistence import models
from newsflow.services.source_revisions import source_revision

INPUT_INVALID = "EDITORIAL_HISTORY_INPUT_INVALID"
HISTORY_INVALID = "EDITORIAL_HISTORY_INVALID"
NOT_FOUND = "EDITORIAL_HISTORY_NOT_FOUND"

# Only codes emitted by the accepted assessor, admission resolver and runner.
_REASONS = frozenset(
    [
        "REAL_MODEL_NOT_QUALIFIED",
        "PROTECTED_ENTITY_NEGATIVE",
        "CLASSIFICATION_REQUIRED",
        "REQUEST_INVALID",
        "EVIDENCE_TYPE_INVALID",
        "EVIDENCE_ENCODING_INVALID",
        "EVIDENCE_BYTE_LIMIT",
        "EVIDENCE_DEPTH_LIMIT",
        "EVIDENCE_DUPLICATE_KEY",
        "EVIDENCE_JSON_INVALID",
        "EVIDENCE_SCHEMA_INVALID",
        "CONTENT_BINDING_MISMATCH",
        "SOURCE_BINDING_MISMATCH",
        "POLICY_BINDING_MISMATCH",
        "PROMPT_BINDING_MISMATCH",
        "SOURCE_INCOMPLETE",
        "CLASSIFICATION_AMBIGUOUS",
        "ENTITY_UNKNOWN",
        "ENTITY_FINDING_DUPLICATE",
        "SOURCE_QUOTE_NOT_FOUND",
        "QUOTE_ALIAS_MISSING",
        "ENTITY_FINDING_MISSING",
        "ADMISSION_INPUT_INVALID",
        "ADMISSION_POLICY_DISABLED",
        "ADMISSION_MAPPING_INVALID",
        "ADMISSION_OWNERSHIP_INVALID",
        "ADMISSION_SOURCE_INVALID",
        "ADMISSION_SOURCE_NOT_CURRENT",
        "ADMISSION_EDITORIAL_HELD",
        "ADMISSION_POLICY_OR_SOURCE_INVALID",
        "ADMISSION_TECHNICAL_HELD",
        "ADMISSION_FINGERPRINT_UNOWNED",
        "EDITORIAL_BINDING_CHANGED",
        "EDITORIAL_CLAIM_HISTORY_MISSING",
        "EDITORIAL_ATTEMPTS_EXHAUSTED",
        "EDITORIAL_LEASE_LOST",
        "EDITORIAL_PROVIDER_UNAVAILABLE",
        "EDITORIAL_PROVIDER_CONFIGURATION_INVALID",
        "EDITORIAL_PROVIDER_RESPONSE_INVALID",
        "EDITORIAL_PROVIDER_FAILED",
        "EDITORIAL_RETURNED_MODEL_INVALID",
        "EDITORIAL_EVIDENCE_MISSING",
        "EDITORIAL_EVIDENCE_INVALID",
        "EDITORIAL_EVIDENCE_TOO_LARGE",
        "EDITORIAL_USAGE_INVALID",
    ]
)
_STATES = {"QUEUED", "RUNNING", "REVIEW", "REJECT", "BLOCKED", "FAILED"}
_OUTCOMES = {"REVIEW", "REJECT", "BLOCKED", "FAILED", "RETRY", "LOST_LEASE"}


def _require(condition):
    if not condition:
        raise ValueError(HISTORY_INVALID)


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _choice(value, choices):
    return type(value) is str and value in choices


def _timestamp(value):
    _require(type(value) is datetime)
    try:
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        ).isoformat()
    except (ValueError, OverflowError, TypeError):
        raise ValueError(HISTORY_INVALID) from None


def _token(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


class EditorialHistoryReader:
    def __init__(self, session):
        self.session = session

    def read(self, content_key, mapping_id, *, limit=25, before_job_id=None):
        try:
            valid = (
                type(content_key) is str
                and 1 <= len(content_key) <= 255
                and bool(content_key.strip())
                and type(mapping_id) is int
                and mapping_id > 0
                and _integer(limit, 1, 25)
                and (before_job_id is None or (type(before_job_id) is int and before_job_id > 0))
            )
            if not valid:
                raise ValueError
            content_key.encode("utf-8")
        except (ValueError, UnicodeError):
            raise ValueError(INPUT_INVALID) from None
        session = self.session
        _require(not (session.new or session.dirty or session.deleted))
        if mapping_id > 9223372036854775807:
            raise LookupError(NOT_FOUND)
        # Reject pending objects before SQL, even on a caller's autoflush-enabled session.
        with session.no_autoflush:
            revision = source_revision(session, content_key)
            mapping = session.get(models.ChannelMappingModel, mapping_id, populate_existing=True)
            if revision is None or mapping is None:
                raise LookupError(NOT_FOUND)
            donor = session.get(
                models.DonorChannel, mapping.donor_channel_id, populate_existing=True
            )
            output = session.get(
                models.OutputChannel, mapping.output_channel_id, populate_existing=True
            )
            if donor is None or output is None:
                raise LookupError(NOT_FOUND)
            donor_owner = session.get(
                models.TelegramAccount, donor.telegram_account_id, populate_existing=True
            )
            output_owner = session.get(
                models.TelegramAccount, output.telegram_account_id, populate_existing=True
            )
            post = session.get(
                models.IncomingPostModel, revision.incoming_post_id, populate_existing=True
            )
            if (
                donor_owner is None
                or output_owner is None
                or post is None
                or post.telegram_account_id != str(donor_owner.id)
                or post.donor_channel_id != str(donor.telegram_channel_id)
            ):
                raise LookupError(NOT_FOUND)
            query = select(models.EditorialClassificationJobModel).where(
                models.EditorialClassificationJobModel.content_key == content_key,
                models.EditorialClassificationJobModel.source_revision_id == revision.id,
                models.EditorialClassificationJobModel.mapping_id == mapping_id,
            )
            if before_job_id is not None and before_job_id <= 9223372036854775807:
                query = query.where(models.EditorialClassificationJobModel.id < before_job_id)
            jobs = session.scalars(
                query.order_by(models.EditorialClassificationJobModel.id.desc())
                .limit(limit + 1)
                .execution_options(populate_existing=True)
            ).all()
            items = [self._job(job, content_key) for job in jobs[:limit]]
        return {
            "content_key": content_key,
            "mapping_id": mapping_id,
            "diagnostic_only": True,
            "execution_authorized": False,
            "rewrite_allowed": False,
            "network_checked": False,
            "worker_enabled": None,
            "real_model_qualified": False,
            "items": items,
            "next_before_job_id": items[-1]["job_id"] if len(jobs) > limit else None,
        }

    def _job(self, job, content_key):
        _require(
            _integer(job.id, 1, 9223372036854775807)
            and _integer(job.editorial_decision_id, 1, 9223372036854775807)
            and _integer(job.source_revision_id, 1, 9223372036854775807)
            and _integer(job.mapping_id, 1, 9223372036854775807)
            and _choice(job.state, _STATES)
            and _integer(job.attempts, 0, 2)
            and _choice(job.provider, {"OPENAI", "OPENROUTER"})
            and type(job.model) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", job.model) is not None
            and (
                job.provider != "OPENROUTER"
                or (
                    job.model.endswith(":free")
                    and ":" not in job.model[:-5]
                    and not job.model.lower().startswith("openrouter/")
                )
            )
            and (job.last_error_code is None or _choice(job.last_error_code, _REASONS))
        )
        running = job.state == "RUNNING"
        _require(
            (
                running
                and job.attempts > 0
                and _token(job.claim_token)
                and job.lease_expires_at is not None
            )
            or (not running and job.claim_token is None and job.lease_expires_at is None)
        )
        decision = self.session.get(
            models.EditorialDecisionModel, job.editorial_decision_id, populate_existing=True
        )
        _require(decision is not None and decision.content_key == content_key)
        claims = self.session.scalars(
            select(models.EditorialClassificationClaimModel)
            .where(models.EditorialClassificationClaimModel.classification_job_id == job.id)
            .order_by(models.EditorialClassificationClaimModel.attempt)
            .limit(3)
            .execution_options(populate_existing=True)
        ).all()
        _require(len(claims) == job.attempts and len(claims) <= 2)
        receipts = []
        for number, claim in enumerate(claims, 1):
            _require(
                type(claim.attempt) is int and claim.attempt == number and _token(claim.claim_token)
            )
            _timestamp(claim.created_at)
            if running and number == job.attempts:
                _require(claim.claim_token == job.claim_token)
            rows = self.session.scalars(
                select(models.EditorialClassificationAttemptModel)
                .where(models.EditorialClassificationAttemptModel.claim_id == claim.id)
                .limit(2)
                .execution_options(populate_existing=True)
            ).all()
            _require(len(rows) <= 1)
            if rows:
                receipt = self._receipt(rows[0], number)
                if receipt["outcome"] in {"REVIEW", "REJECT"}:
                    _require(number == job.attempts and job.state == receipt["outcome"])
                if receipt["outcome"] == "RETRY":
                    _require(number == 1)
                if running and number == job.attempts:
                    _require(receipt["outcome"] == "LOST_LEASE")
                receipts.append(receipt)
        if job.state in {"REVIEW", "REJECT"}:
            _require(
                bool(receipts)
                and receipts[-1]["attempt"] == job.attempts
                and receipts[-1]["outcome"] == job.state
            )
        return {
            "job_id": job.id,
            "state": job.state,
            "attempts": job.attempts,
            "max_attempts": 2,
            "provider": job.provider,
            "model": job.model,
            "created_at": _timestamp(job.created_at),
            "available_at": _timestamp(job.available_at),
            "lease_expires_at": _timestamp(job.lease_expires_at) if running else None,
            "reason_code": job.last_error_code,
            "receipts": receipts,
        }

    @staticmethod
    def _receipt(row, attempt):
        _require(
            _choice(row.outcome, _OUTCOMES)
            and (
                row.diagnostic_status is None
                or _choice(row.diagnostic_status, {"PASS", "REJECT", "MANUAL_REVIEW"})
            )
            and (
                (row.outcome == "REVIEW" and row.diagnostic_status in {"PASS", "MANUAL_REVIEW"})
                or (row.outcome == "REJECT" and row.diagnostic_status == "REJECT")
                or (row.outcome not in {"REVIEW", "REJECT"} and row.diagnostic_status is None)
            )
            and type(row.reason_codes) is list
            and 1 <= len(row.reason_codes) <= 2
            and all(type(code) is str and code in _REASONS for code in row.reason_codes)
            and type(row.usage_observed) is bool
        )
        counts = (row.input_tokens, row.cached_tokens, row.output_tokens)
        cost = row.estimated_cost_usd
        if row.usage_observed:
            _require(all(_integer(value, 0, 2147483647) for value in counts))
            _require(row.cached_tokens <= row.input_tokens)
            _require(
                cost is None
                or (type(cost) is Decimal and cost.is_finite() and 0 <= cost < Decimal(10000000000))
            )
        else:
            _require(all(value is None for value in counts) and cost is None)
        return {
            "attempt": attempt,
            "outcome": row.outcome,
            "diagnostic_status": row.diagnostic_status,
            "reason_codes": list(row.reason_codes),
            "usage_observed": row.usage_observed,
            "input_tokens": row.input_tokens,
            "cached_tokens": row.cached_tokens,
            "output_tokens": row.output_tokens,
            "estimated_cost_usd": format(cost, "f") if cost is not None else None,
            "created_at": _timestamp(row.created_at),
        }
