"""Canonical diagnostic admission only. Caller owns every transaction and side effect."""

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    ChannelMappingModel,
    DonorChannel,
    EditorialClassificationJobModel,
    EditorialClassifierPolicyModel,
    EditorialDecisionModel,
    IncomingPostModel,
    MappingContentFingerprintModel,
    OutboxEventModel,
    OutputChannel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage, validate_media_observation
from newsflow.services.editorial_classification import (
    EditorialClassificationRequest,
    ProtectedEntity,
)
from newsflow.services.mapping_filters import mapping_filter
from newsflow.services.source_revisions import revision_is_latest, source_revision


class EditorialAdmissionBlocked(ValueError):
    """A sanitized, stable reason; never stores source, policy or model text."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class EditorialAdmissionBinding:
    revision_id: int
    mapping_id: int
    decision_id: int
    request: EditorialClassificationRequest
    mapping_sha256: str
    provider: str
    model: str


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _inputs(content_key, mapping_id):
    if (
        type(content_key) is not str
        or not content_key.strip()
        or len(content_key) > 255
        or type(mapping_id) is not int
        or mapping_id <= 0
    ):
        raise EditorialAdmissionBlocked("ADMISSION_INPUT_INVALID")
    try:
        content_key.encode("utf-8")
    except UnicodeError:
        raise EditorialAdmissionBlocked("ADMISSION_INPUT_INVALID") from None


def _policy_request(policy, content_key, source_text):
    try:
        if (
            type(policy.model) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", policy.model) is None
            or policy.provider not in {"OPENAI", "OPENROUTER"}
            or (
                policy.provider == "OPENROUTER"
                and (
                    not policy.model.endswith(":free")
                    or ":" in policy.model[:-5]
                    or policy.model.lower().startswith("openrouter/")
                )
            )
        ):
            raise ValueError
        raw = _canonical(policy.protected_entities)
        if len(raw) > 262144 or type(policy.protected_entities) is not list:
            raise ValueError
        entities = []
        for item in policy.protected_entities:
            if (
                type(item) is not dict
                or set(item) != {"entity_id", "aliases"}
                or type(item["aliases"]) is not list
            ):
                raise ValueError
            entities.append(ProtectedEntity(item["entity_id"], tuple(item["aliases"])))
        return EditorialClassificationRequest(
            content_key, source_text, policy.policy_version, tuple(entities)
        )
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise EditorialAdmissionBlocked("ADMISSION_POLICY_OR_SOURCE_INVALID") from None


def resolve_editorial_admission(
    session: Session, *, content_key: str, mapping_id: int
) -> EditorialAdmissionBinding:
    _inputs(content_key, mapping_id)
    policy = session.get(EditorialClassifierPolicyModel, 1, populate_existing=True)
    if policy is None or policy.enabled is not True:
        raise EditorialAdmissionBlocked("ADMISSION_POLICY_DISABLED")
    mapping = session.get(ChannelMappingModel, mapping_id, populate_existing=True)
    if mapping is None:
        raise EditorialAdmissionBlocked("ADMISSION_MAPPING_INVALID")
    donor = session.get(DonorChannel, mapping.donor_channel_id, populate_existing=True)
    output = session.get(OutputChannel, mapping.output_channel_id, populate_existing=True)
    if donor is None or output is None:
        raise EditorialAdmissionBlocked("ADMISSION_MAPPING_INVALID")
    donor_owner = session.get(TelegramAccount, donor.telegram_account_id, populate_existing=True)
    output_owner = session.get(TelegramAccount, output.telegram_account_id, populate_existing=True)
    if donor_owner is None or output_owner is None:
        raise EditorialAdmissionBlocked("ADMISSION_OWNERSHIP_INVALID")
    revision = source_revision(session, content_key)
    if revision is None:
        raise EditorialAdmissionBlocked("ADMISSION_SOURCE_INVALID")
    post = session.get(IncomingPostModel, revision.incoming_post_id, populate_existing=True)
    if (
        post is None
        or post.telegram_account_id != str(donor_owner.id)
        or post.donor_channel_id != str(donor.telegram_channel_id)
    ):
        raise EditorialAdmissionBlocked("ADMISSION_OWNERSHIP_INVALID")
    if not revision_is_latest(session, revision):
        raise EditorialAdmissionBlocked("ADMISSION_SOURCE_NOT_CURRENT")
    decision = session.scalar(
        select(EditorialDecisionModel)
        .where(EditorialDecisionModel.content_key == content_key)
        .execution_options(populate_existing=True)
    )
    if (
        decision is None
        or decision.status != "MANUAL_REVIEW"
        or decision.rewrite_allowed is not False
        or session.scalar(
            select(RewriteJobModel.id).where(RewriteJobModel.content_key == content_key).limit(1)
        )
        is not None
    ):
        raise EditorialAdmissionBlocked("ADMISSION_EDITORIAL_HELD")
    request = _policy_request(policy, content_key, revision.source_text)
    try:
        if (
            revision.media_type not in {"text", "photo"}
            or revision.album_id is not None
            or (
                revision.link_destinations is not None
                and type(revision.link_destinations) is not list
            )
        ):
            raise ValueError
        updated_at = revision.source_updated_at
        # SQLite stores aware DateTime columns without offset; persisted instants are UTC.
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        message = TelegramMessage(
            post.telegram_account_id,
            post.donor_channel_id,
            post.telegram_message_id,
            revision.source_text,
            media_type=revision.media_type,
            album_id=revision.album_id,
            source_updated_at=updated_at,
            media_id=revision.media_id,
            media_protected=revision.media_protected,
            link_destinations=tuple(revision.link_destinations)
            if revision.link_destinations is not None
            else None,
        )
        validate_media_observation(message)
        technical = mapping_filter(session, mapping, intake=True)
        if not technical.evaluate(message).accepted:
            raise ValueError
    except (TypeError, ValueError, UnicodeError, OverflowError):
        raise EditorialAdmissionBlocked("ADMISSION_TECHNICAL_HELD") from None
    fingerprint = sha256(revision.source_text.strip().casefold().encode("utf-8")).hexdigest()
    owner = session.scalar(
        select(MappingContentFingerprintModel)
        .where(
            MappingContentFingerprintModel.mapping_id == str(mapping.id),
            MappingContentFingerprintModel.fingerprint == fingerprint,
        )
        .execution_options(populate_existing=True)
    )
    if owner is None or owner.content_key != content_key:
        raise EditorialAdmissionBlocked("ADMISSION_FINGERPRINT_UNOWNED")
    identity = {
        "mapping_id": mapping.id,
        "donor": {
            "id": donor.id,
            "channel": donor.telegram_channel_id,
            "account": donor_owner.id,
            "user": donor_owner.telegram_user_id,
        },
        "output": {
            "id": output.id,
            "channel": output.telegram_channel_id,
            "account": output_owner.id,
            "user": output_owner.telegram_user_id,
            "rewrite_style": output.rewrite_style,
        },
        **{
            name: getattr(mapping, name)
            for name in (
                "intake_percent",
                "target_mix_percent",
                "eligibility_mode",
                "delay_minutes",
                "priority",
                "media_policy",
            )
        },
        "technical": {
            "allowed_media_types": sorted(technical.allowed_media_types),
            "blocked_domains": sorted(technical.blocked_domains),
            "ad_markers": sorted(set(technical.ad_markers)),
            "intake_percent": technical.intake_percent,
        },
    }
    try:
        mapping_sha256 = sha256(_canonical(identity)).hexdigest()
    except (TypeError, ValueError, UnicodeError):
        raise EditorialAdmissionBlocked("ADMISSION_MAPPING_INVALID") from None
    return EditorialAdmissionBinding(
        revision.id,
        mapping.id,
        decision.id,
        request,
        mapping_sha256,
        policy.provider,
        policy.model,
    )


def enqueue_editorial_classification(
    session: Session, *, content_key: str, mapping_id: int, now: datetime
) -> EditorialClassificationJobModel | None:
    try:
        if (
            type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset() is None
            or not math.isfinite(now.timestamp())
        ):
            raise EditorialAdmissionBlocked("ADMISSION_TIME_INVALID")
        observed_at = now.astimezone(UTC)
    except (EditorialAdmissionBlocked, ValueError, OverflowError):
        return None
    try:
        binding = resolve_editorial_admission(
            session, content_key=content_key, mapping_id=mapping_id
        )
    except EditorialAdmissionBlocked:
        return None
    request = binding.request
    values = {
        "content_key": request.content_key,
        "source_revision_id": binding.revision_id,
        "mapping_id": binding.mapping_id,
        "editorial_decision_id": binding.decision_id,
        "source_sha256": request.source_sha256,
        "policy_sha256": request.policy_sha256,
        "mapping_sha256": binding.mapping_sha256,
        "provider": binding.provider,
        "model": binding.model,
        "prompt_version": request.prompt_version,
    }
    identity = sha256(_canonical(values)).hexdigest()
    existing = session.scalar(
        select(EditorialClassificationJobModel)
        .where(EditorialClassificationJobModel.idempotency_key == identity)
        .execution_options(populate_existing=True)
    )
    if existing is not None:
        return existing
    job = EditorialClassificationJobModel(
        **values,
        idempotency_key=identity,
        state="QUEUED",
        attempts=0,
        available_at=observed_at,
        created_at=observed_at,
    )
    session.add(job)
    session.flush()
    session.add(
        OutboxEventModel(
            event_type="editorial.classification.requested",
            aggregate_key=content_key,
            idempotency_key="editorial.classification.requested:" + identity,
            created_at=observed_at,
        )
    )
    session.flush()
    return job
