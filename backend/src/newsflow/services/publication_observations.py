"""Trusted direct-response receipt ledger, not guessed history or retry authority.

Configured transports validate exact random-ID/channel/message/content updates
before returning PublicationReceipt. This is a trusted internal adapter boundary;
there is no public endpoint for recording or forging receipt observations.
"""

import json
from dataclasses import asdict, dataclass

from newsflow.persistence.models import PublicationDeliveryObservationModel, PublicationJobModel
from newsflow.security.session_cipher import SessionDecryptionUnavailable
from newsflow.services.publication import PublicationBlocked
from newsflow.services.publication_request_snapshot import (
    PublicationRequestSnapshots,
    _unique_object,
)


@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    account_id: int
    telegram_channel_id: int
    request_nonce: int
    message_id: int


@dataclass(frozen=True, slots=True)
class PublicationObservedReceipt:
    receipt: PublicationReceipt
    attempt: int


def receipt_matches(receipt, envelope, nonce):
    return (
        isinstance(receipt, PublicationReceipt)
        and all(
            type(value) is int
            for value in (
                receipt.account_id,
                receipt.telegram_channel_id,
                receipt.request_nonce,
                receipt.message_id,
            )
        )
        and (receipt.account_id, receipt.telegram_channel_id, receipt.request_nonce)
        == (envelope.account_id, envelope.telegram_channel_id, nonce)
        and 0 < receipt.message_id <= 2**31 - 1
    )


class PublicationObservations:
    def __init__(self, session_factory, *, cipher):
        self._factory, self._cipher = session_factory, cipher
        self._snapshots = PublicationRequestSnapshots(session_factory, cipher=cipher)

    def _decode(self, row, job, snapshot):
        if not 1 <= len(row.encrypted_receipt) <= 4096:
            raise ValueError("Invalid observation size")
        value = json.loads(
            self._cipher.decrypt(row.encrypted_receipt), object_pairs_hook=_unique_object
        )
        if type(value) is not dict or set(value) != {
            "version",
            "provenance",
            "job_id",
            "attempt",
            "binding_sha256",
            "receipt",
        }:
            raise ValueError("Invalid observation schema")
        if (
            type(value["version"]) is not int
            or value["version"] != 1
            or value["provenance"] != "DIRECT_RESPONSE"
            or type(value["job_id"]) is not int
            or value["job_id"] != job.id
            or type(value["attempt"]) is not int
            or not 1 <= value["attempt"] <= 2
            or value["attempt"] != job.attempts
            or value["binding_sha256"] != snapshot.envelope.binding_sha256
        ):
            raise ValueError("Invalid observation binding")
        data = value["receipt"]
        if type(data) is not dict or set(data) != {
            "account_id",
            "telegram_channel_id",
            "request_nonce",
            "message_id",
        }:
            raise ValueError("Invalid receipt schema")
        receipt = PublicationReceipt(**data)
        if not receipt_matches(receipt, snapshot.envelope, snapshot.request_nonce):
            raise ValueError("Invalid receipt binding")
        return PublicationObservedReceipt(receipt, value["attempt"])

    def record(self, claim, receipt, envelope, nonce):
        if not receipt_matches(receipt, envelope, nonce):
            raise PublicationBlocked("PUBLICATION_RECEIPT_INVALID")
        original = self._snapshots.read(claim.job_id)
        if original.envelope != envelope or original.request_nonce != nonce:
            raise PublicationBlocked("PUBLICATION_OBSERVATION_BINDING_CHANGED")
        with self._factory() as session:
            job = session.get(PublicationJobModel, claim.job_id, with_for_update=True)
            if (
                job is None
                or job.attempts != claim.attempt
                or (
                    job.binding_sha256,
                    job.request_nonce,
                    job.telegram_account_id,
                    job.telegram_channel_id,
                    job.planned_id,
                )
                != (
                    envelope.binding_sha256,
                    nonce,
                    envelope.account_id,
                    envelope.telegram_channel_id,
                    envelope.planned_id,
                )
                or not (
                    (job.state == "SENDING" and job.claim_token == claim.token)
                    or (
                        job.state == "NEEDS_RECONCILIATION"
                        and job.last_error_code == "PUBLICATION_SEND_OUTCOME_UNKNOWN"
                    )
                )
            ):
                raise PublicationBlocked("PUBLICATION_OBSERVATION_OWNERSHIP_LOST")
            row = session.get(PublicationDeliveryObservationModel, job.id)
            if row is not None:
                if self._decode(row, job, original) != PublicationObservedReceipt(
                    receipt, claim.attempt
                ):
                    # Two different exact IDs for the same nonce are not a
                    # license to choose either. Preserve the first observation
                    # and fence automatic reconciliation as well as resend.
                    job.state, job.last_error_code = (
                        "NEEDS_RECONCILIATION",
                        "PUBLICATION_OBSERVATION_CONFLICT",
                    )
                    job.claim_token, job.lease_expires_at = None, None
                    session.commit()
                    raise PublicationBlocked("PUBLICATION_OBSERVATION_CONFLICT")
                return
            payload = json.dumps(
                {
                    "version": 1,
                    "provenance": "DIRECT_RESPONSE",
                    "job_id": job.id,
                    "attempt": claim.attempt,
                    "binding_sha256": envelope.binding_sha256,
                    "receipt": asdict(receipt),
                },
                separators=(",", ":"),
            )
            session.add(
                PublicationDeliveryObservationModel(
                    job_id=job.id, encrypted_receipt=self._cipher.encrypt(payload)
                )
            )
            session.commit()

    def read(self, job_id):
        snapshot = self._snapshots.read(job_id)
        with self._factory() as session:
            job = session.get(PublicationJobModel, job_id)
            row = session.get(PublicationDeliveryObservationModel, job_id)
            if job is None or row is None:
                raise PublicationBlocked("PUBLICATION_OBSERVATION_UNAVAILABLE")
            try:
                observation = self._decode(row, job, snapshot)
                if (
                    job.binding_sha256,
                    job.request_nonce,
                    job.telegram_account_id,
                    job.telegram_channel_id,
                    job.planned_id,
                ) != (
                    snapshot.envelope.binding_sha256,
                    snapshot.request_nonce,
                    snapshot.envelope.account_id,
                    snapshot.envelope.telegram_channel_id,
                    snapshot.envelope.planned_id,
                ):
                    raise ValueError("Observation job changed")
                return snapshot, observation
            except (
                SessionDecryptionUnavailable,
                ValueError,
                TypeError,
                KeyError,
                OverflowError,
                RecursionError,
            ):
                raise PublicationBlocked("PUBLICATION_OBSERVATION_UNAVAILABLE") from None
