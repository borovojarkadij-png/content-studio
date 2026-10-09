"""Encrypted exact request history. Reading it never authorizes another send."""

import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta

from newsflow.domain.illustration_relevance import IllustrationBinding
from newsflow.persistence.models import PublicationJobModel, PublicationRequestSnapshotModel
from newsflow.security.session_cipher import SessionDecryptionUnavailable
from newsflow.services.durable_semantic_runner import _aware
from newsflow.services.publication import PublicationBlocked
from newsflow.services.publication_preflight import PublicationEnvelope


@dataclass(frozen=True, slots=True)
class PublicationRequestSnapshot:
    envelope: PublicationEnvelope
    request_nonce: int


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate snapshot field")
        result[key] = value
    return result


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _decode(payload, job, row):
    value = json.loads(payload, object_pairs_hook=_unique_object)
    if (
        type(value) is not dict
        or set(value) != {"version", "request_nonce", "envelope"}
        or type(value["version"]) is not int
        or value["version"] not in {1, 2}
    ):
        raise ValueError("Invalid snapshot version")
    nonce, data = value["request_nonce"], value["envelope"]
    if (
        type(nonce) is not int
        or not 0 < nonce < 2**63
        or type(data) is not dict
        or set(data)
        != (
            {field.name for field in fields(PublicationEnvelope)}
            - (
                {"illustration_review_id", "illustration_binding"}
                if value["version"] == 1
                else set()
            )
        )
    ):
        raise ValueError("Invalid snapshot schema")
    if value["version"] == 1:
        data["illustration_review_id"] = data["illustration_binding"] = None
    review_id, binding = data["illustration_review_id"], data["illustration_binding"]
    if review_id is None:
        if binding is not None:
            raise ValueError("Unexpected illustration binding")
    else:
        if (
            type(review_id) is not int
            or not 0 < review_id <= 2**63 - 1
            or type(binding) is not dict
        ):
            raise ValueError("Invalid illustration review identity")
        binding = IllustrationBinding(**binding)
        if any(
            getattr(binding, key) != data[key]
            for key in (
                "candidate_id",
                "output_channel_id",
                "content_key",
                "rewrite_output_id",
                "media_asset_id",
                "media_sha256",
            )
        ):
            raise ValueError("Inconsistent illustration binding")
        data["illustration_binding"] = binding
    for key in (
        "planned_id",
        "candidate_id",
        "account_id",
        "user_id",
        "output_channel_id",
        "rewrite_output_id",
    ):
        if type(data[key]) is not int or data[key] <= 0:
            raise ValueError("Invalid snapshot identity")
    if (
        type(data["telegram_channel_id"]) is not int
        or not -(2**63) < data["telegram_channel_id"] < -1000000000000
    ):
        raise ValueError("Invalid channel")
    if not isinstance(data["content_key"], str) or not 1 <= len(data["content_key"]) <= 255:
        raise ValueError("Invalid content identity")
    if not isinstance(data["text"], str) or not data["text"].strip():
        raise ValueError("Missing request text")
    if data["media_asset_id"] is None:
        if data["media_sha256"] is not None:
            raise ValueError("Unexpected media digest")
        limit = 4096
    else:
        if (
            type(data["media_asset_id"]) is not int
            or data["media_asset_id"] <= 0
            or not _digest(data["media_sha256"])
        ):
            raise ValueError("Invalid media identity")
        limit = 1024
    if len(data["text"].encode("utf-16-le")) // 2 > limit or not _digest(data["binding_sha256"]):
        raise ValueError("Invalid request text/binding")
    for key in ("scheduled_for", "expires_at"):
        if not isinstance(data[key], str):
            raise TypeError("Invalid request timestamp")
        data[key] = datetime.fromisoformat(data[key])
        _aware(data[key])
    if data["expires_at"] - data["scheduled_for"] != timedelta(hours=6):
        raise ValueError("Invalid request expiry")
    if (
        data["planned_id"],
        data["account_id"],
        data["telegram_channel_id"],
        nonce,
        data["binding_sha256"],
    ) != (
        job.planned_id,
        job.telegram_account_id,
        job.telegram_channel_id,
        job.request_nonce,
        job.binding_sha256,
    ) or row.binding_sha256 != job.binding_sha256:
        raise ValueError("Snapshot binding changed")
    return PublicationRequestSnapshot(PublicationEnvelope(**data), nonce)


class PublicationRequestSnapshots:
    def __init__(self, session_factory, *, cipher):
        self._factory, self._cipher = session_factory, cipher

    def record(self, session, job, envelope):
        """Insert once in the same transaction as the intent and queued outbox."""
        data = asdict(envelope)
        for key in ("scheduled_for", "expires_at"):
            _aware(data[key])
            data[key] = data[key].isoformat()
        payload = json.dumps(
            {"version": 2, "request_nonce": job.request_nonce, "envelope": data},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        encrypted = self._cipher.encrypt(payload)
        row = PublicationRequestSnapshotModel(
            job_id=job.id, binding_sha256=job.binding_sha256, encrypted_envelope=encrypted
        )
        if len(encrypted) > 32768:
            raise PublicationBlocked("PUBLICATION_REQUEST_SNAPSHOT_INVALID")
        try:
            _decode(payload, job, row)
        except (ValueError, TypeError, KeyError, OverflowError):
            raise PublicationBlocked("PUBLICATION_REQUEST_SNAPSHOT_INVALID") from None
        session.add(row)

    def read(self, job_id):
        if type(job_id) is not int or job_id <= 0:
            raise PublicationBlocked("PUBLICATION_REQUEST_SNAPSHOT_UNAVAILABLE")
        with self._factory() as session:
            job = session.get(PublicationJobModel, job_id)
            row = session.get(PublicationRequestSnapshotModel, job_id)
            if job is None or row is None or not 1 <= len(row.encrypted_envelope) <= 32768:
                raise PublicationBlocked("PUBLICATION_REQUEST_SNAPSHOT_UNAVAILABLE")
            try:
                return _decode(self._cipher.decrypt(row.encrypted_envelope), job, row)
            except (
                SessionDecryptionUnavailable,
                ValueError,
                TypeError,
                KeyError,
                OverflowError,
                RecursionError,
            ):
                raise PublicationBlocked("PUBLICATION_REQUEST_SNAPSHOT_UNAVAILABLE") from None
