"""Caller-owned transactional comparison evidence, without ingestion activation."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, SessionTransactionOrigin

from newsflow.domain.intake_selection import (
    ALGORITHM_VERSION,
    IntakeCandidate,
    IntakeSelectionPolicy,
    IntakeSelectionResult,
    select_intake_window,
)
from newsflow.persistence.models import (
    ChannelMappingModel,
)
from newsflow.persistence.models import (
    TelegramIntakeSelectionStreamModel as Stream,
)
from newsflow.persistence.models import (
    TelegramIntakeSelectionWindowModel as Window,
)

_MAX_SEQUENCE = 2**63 - 1
_MAX_PAYLOAD = 262144


@dataclass(frozen=True, slots=True)
class RecordedIntakeWindow:
    stream_id: int
    window_id: int
    sequence: int
    carry_in: int
    result: IntakeSelectionResult
    replayed: bool


class IntakeLedgerConflict(ValueError):
    """A retained binding or window identifies different comparison inputs."""


class IntakeLedgerCorrupt(ValueError):
    """Retained comparison evidence cannot be validated and recomputed."""


def _integer(value, name, minimum=1, maximum=_MAX_SEQUENCE):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {name}")


def _digest(value, name):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError(f"Invalid {name}")


def _utc_time(value):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Expected aware datetime")
    try:
        return value.astimezone(UTC)
    except (ValueError, OverflowError) as error:
        raise ValueError("UTC datetime is outside portable bounds") from error


def _stored_time(value):
    # SQLite DateTime returns naive UTC while PostgreSQL returns aware values.
    if type(value) is not datetime:
        raise ValueError("Invalid stored datetime")
    _utc_time(value.replace(tzinfo=UTC) if value.tzinfo is None else value)


def _json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _bounded(value, maximum):
    if type(value) is not str or len(value) > maximum or not value.isascii() or "\0" in value:
        raise ValueError("Invalid bounded ASCII payload")
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("Nonfinite JSON value")


def _decode(value, maximum):
    _bounded(value, maximum)
    result = json.loads(value, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    if _json(result) != value:
        raise ValueError("Noncanonical JSON")
    return result


def _keys(value, expected):
    if type(value) is not dict or value.keys() != expected:
        raise ValueError("Invalid snapshot object keys")


def _policy_object(policy):
    return {
        "intake_percent": policy.intake_percent,
        "mode": policy.mode,
        "minimum_score": float(policy.minimum_score),
    }


def _policy_evidence(policy):
    payload = _bounded(_json(_policy_object(policy)), 256)
    digest = sha256(
        _json({"algorithm_version": ALGORITHM_VERSION, "policy": _policy_object(policy)}).encode(
            "ascii"
        )
    ).hexdigest()
    return payload, digest


def _policy_from(value):
    _keys(value, {"intake_percent", "mode", "minimum_score"})
    policy = IntakeSelectionPolicy(**value)
    if _json(value) != _json(_policy_object(policy)):
        raise ValueError("Noncanonical policy numbers")
    return policy


def _input_evidence(candidates, policy):
    return _bounded(
        _json(
            {
                "policy": _policy_object(policy),
                "candidates": [
                    {
                        "candidate_id": row.candidate_id,
                        "revision_sha256": row.revision_sha256,
                        "score": None if row.score is None else float(row.score),
                        "eligible": row.eligible,
                    }
                    for row in sorted(candidates, key=lambda row: row.candidate_id)
                ],
            }
        ),
        _MAX_PAYLOAD,
    )


def _validate_stream(stream, mapping_id, binding):
    try:
        _integer(stream.id, "stream id")
        _integer(stream.mapping_id, "mapping id")
        _integer(stream.carry, "carry", 0, 99)
        _integer(stream.next_sequence, "next sequence")
        _digest(stream.policy_binding_sha256, "policy binding")
        _digest(stream.policy_sha256, "policy digest")
        _stored_time(stream.created_at)
        if stream.mapping_id != mapping_id or stream.policy_binding_sha256 != binding:
            raise ValueError("Stream identity mismatch")
        policy = _policy_from(_decode(stream.policy_payload, 256))
        payload, digest = _policy_evidence(policy)
        if (stream.policy_payload, stream.policy_sha256) != (payload, digest):
            raise ValueError("Stream policy evidence mismatch")
        if stream.next_sequence == 1 and stream.carry != 0:
            raise ValueError("Invalid initial carry")
        return policy
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        raise IntakeLedgerCorrupt("Invalid intake stream evidence") from error


def _validate_window(window, stream):
    try:
        _integer(window.id, "window id")
        _integer(window.stream_id, "stream id")
        _integer(window.sequence, "sequence", maximum=_MAX_SEQUENCE - 1)
        _integer(window.carry_in, "carry in", 0, 99)
        _integer(window.carry_out, "carry out", 0, 99)
        _digest(window.window_key, "window key")
        _digest(window.input_sha256, "input digest")
        _stored_time(window.created_at)
        if window.stream_id != stream.id or window.sequence >= stream.next_sequence:
            raise ValueError("Window sequence linkage mismatch")
        if window.sequence == 1 and window.carry_in != 0:
            raise ValueError("First window must start with zero carry")
        if window.sequence == stream.next_sequence - 1 and window.carry_out != stream.carry:
            raise ValueError("Previous window carry mismatch")
        if (
            type(window.algorithm_version) is not str
            or window.algorithm_version != ALGORITHM_VERSION
        ):
            raise ValueError("Unknown algorithm version")
        payload = _decode(window.input_payload, _MAX_PAYLOAD)
        _keys(payload, {"policy", "candidates"})
        policy = _policy_from(payload["policy"])
        if _policy_evidence(policy) != (stream.policy_payload, stream.policy_sha256):
            raise ValueError("Window policy mismatch")
        candidates = payload["candidates"]
        if type(candidates) is not list or len(candidates) > 1000:
            raise ValueError("Invalid candidate snapshot size")
        for row in candidates:
            _keys(row, {"candidate_id", "revision_sha256", "score", "eligible"})
        rows = tuple(IntakeCandidate(**row) for row in candidates)
        result = select_intake_window(
            rows, window_key=window.window_key, policy=policy, carry=window.carry_in
        )
        if _input_evidence(rows, policy) != window.input_payload:
            raise ValueError("Noncanonical candidate snapshot")
        _decode(window.result_payload, _MAX_PAYLOAD)
        if (
            result.input_sha256 != window.input_sha256
            or result.carry_out != window.carry_out
            or _json(asdict(result)) != window.result_payload
        ):
            raise ValueError("Kernel result mismatch")
        return result
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        raise IntakeLedgerCorrupt("Invalid intake window evidence") from error


class DurableIntakeSelectionLedger:
    def __init__(self, session: Session):
        self._session = session

    def _caller_transaction(self):
        session = self._session
        transaction = session.get_transaction()
        if (
            transaction is None
            or transaction.origin is not SessionTransactionOrigin.BEGIN
            or not transaction.is_active
            or not session.is_active
            or session.new
            or session.dirty
            or session.deleted
        ):
            raise ValueError("An explicit active clean caller transaction is required")
        if session.get_bind().dialect.name not in ("sqlite", "postgresql"):
            raise ValueError("Only SQLite and PostgreSQL intake ledgers are supported")

    def _stream(self, mapping_id, binding, *, lock=False):
        statement = select(Stream).where(
            Stream.mapping_id == mapping_id, Stream.policy_binding_sha256 == binding
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def _window(self, stream_id, *, key=None, sequence=None):
        statement = select(Window).where(Window.stream_id == stream_id)
        statement = (
            statement.where(Window.window_key == key)
            if key is not None
            else statement.where(Window.sequence == sequence)
        )
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def record_window(
        self,
        *,
        mapping_id: int,
        policy_binding_sha256: str,
        window_key: str,
        candidates: tuple[IntakeCandidate, ...],
        policy: IntakeSelectionPolicy,
        now: datetime,
    ) -> RecordedIntakeWindow:
        """Flush one comparison and carry advance, leaving commit to the caller."""
        _integer(mapping_id, "mapping id")
        _digest(policy_binding_sha256, "policy binding")
        _digest(window_key, "window key")
        now = _utc_time(now)
        if type(policy) is not IntakeSelectionPolicy:
            raise TypeError("policy must be an exact IntakeSelectionPolicy")
        # The public kernel revalidates frozen objects before any database work.
        select_intake_window(candidates, window_key=window_key, policy=policy)
        input_payload = _input_evidence(candidates, policy)
        policy_payload, policy_digest = _policy_evidence(policy)
        self._caller_transaction()
        session = self._session
        mapping = session.scalar(
            select(ChannelMappingModel)
            .where(ChannelMappingModel.id == mapping_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if mapping is None:
            raise ValueError("Unknown intake mapping")
        stream = self._stream(mapping_id, policy_binding_sha256, lock=True)
        if stream is None:
            stream = Stream(
                mapping_id=mapping_id,
                policy_binding_sha256=policy_binding_sha256,
                policy_sha256=policy_digest,
                policy_payload=policy_payload,
                carry=0,
                next_sequence=1,
                created_at=now,
            )
            session.add(stream)
            session.flush()
        else:
            _validate_stream(stream, mapping_id, policy_binding_sha256)
            if stream.next_sequence == 1:
                if (
                    session.scalar(select(Window.id).where(Window.stream_id == stream.id).limit(1))
                    is not None
                ):
                    raise IntakeLedgerCorrupt("Initial stream already has window history")
            else:
                previous = self._window(stream.id, sequence=stream.next_sequence - 1)
                if previous is None:
                    raise IntakeLedgerCorrupt("Previous intake window is missing")
                _validate_window(previous, stream)
        if (stream.policy_payload, stream.policy_sha256) != (policy_payload, policy_digest):
            raise IntakeLedgerConflict("Policy binding already identifies different settings")
        existing = self._window(stream.id, key=window_key)
        if existing is not None:
            result = _validate_window(existing, stream)
            if existing.input_payload != input_payload:
                raise IntakeLedgerConflict("Window key already identifies different inputs")
            return RecordedIntakeWindow(
                stream.id, existing.id, existing.sequence, existing.carry_in, result, True
            )
        if stream.next_sequence == _MAX_SEQUENCE:
            raise ValueError("Intake stream sequence exhausted")
        carry_in = stream.carry
        result = select_intake_window(
            candidates, window_key=window_key, policy=policy, carry=carry_in
        )
        window = Window(
            stream_id=stream.id,
            sequence=stream.next_sequence,
            window_key=window_key,
            input_sha256=result.input_sha256,
            algorithm_version=result.algorithm_version,
            carry_in=carry_in,
            carry_out=result.carry_out,
            input_payload=input_payload,
            result_payload=_bounded(_json(asdict(result)), _MAX_PAYLOAD),
            created_at=now,
        )
        session.add(window)
        session.flush()
        stream.carry = result.carry_out
        stream.next_sequence += 1
        session.flush()
        return RecordedIntakeWindow(stream.id, window.id, window.sequence, carry_in, result, False)

    def load_window(
        self, *, mapping_id: int, policy_binding_sha256: str, window_key: str
    ) -> RecordedIntakeWindow | None:
        """Read bounded retained evidence and return only a recomputed result."""
        _integer(mapping_id, "mapping id")
        _digest(policy_binding_sha256, "policy binding")
        _digest(window_key, "window key")
        self._caller_transaction()
        # One statement gives a coherent stream/window snapshot even on SQLite
        # legacy transaction control and PostgreSQL READ COMMITTED connections.
        row = self._session.execute(
            select(Stream, Window)
            .outerjoin(Window, and_(Window.stream_id == Stream.id, Window.window_key == window_key))
            .where(
                Stream.mapping_id == mapping_id,
                Stream.policy_binding_sha256 == policy_binding_sha256,
            )
            .execution_options(populate_existing=True)
        ).one_or_none()
        if row is None:
            return None
        stream, window = row
        _validate_stream(stream, mapping_id, policy_binding_sha256)
        if window is None:
            return None
        result = _validate_window(window, stream)
        return RecordedIntakeWindow(
            stream.id, window.id, window.sequence, window.carry_in, result, True
        )
