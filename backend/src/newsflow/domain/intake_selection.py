"""Pure selection evidence; no editorial or publication permission."""

import json
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite

ALGORITHM_VERSION = "intake-selection-v1"


def _validate_hash(value: str, name: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"Invalid {name}: expected lowercase SHA256")


def _validate_score(value: float, name: str) -> None:
    # Bounds precede isfinite so an arbitrarily large int cannot overflow float conversion.
    if type(value) not in (int, float) or not 0 <= value <= 100 or not isfinite(value):
        raise ValueError(f"Invalid {name}: expected finite score in [0, 100]")


@dataclass(frozen=True, slots=True)
class IntakeCandidate:
    """Frozen comparison evidence, independent of editorial approval."""

    candidate_id: int
    revision_sha256: str
    score: float | int | None
    eligible: bool = True

    def __post_init__(self) -> None:
        if type(self.candidate_id) is not int or not 0 < self.candidate_id < 2**63:
            raise ValueError("Invalid candidate_id: expected positive signed64 integer")
        _validate_hash(self.revision_sha256, "revision_sha256")
        if self.score is not None:
            _validate_score(self.score, "score")
        if type(self.eligible) is not bool:
            raise ValueError("Invalid eligible: expected exact bool")


@dataclass(frozen=True, slots=True)
class IntakeSelectionPolicy:
    intake_percent: int = 100
    mode: str = "HYBRID"
    minimum_score: float | int = 0

    def __post_init__(self) -> None:
        if type(self.intake_percent) is not int or not 0 <= self.intake_percent <= 100:
            raise ValueError("Invalid intake_percent: expected integer in [0, 100]")
        if type(self.mode) is not str or self.mode not in ("RANDOM", "TOP_SCORE", "HYBRID"):
            raise ValueError("Invalid mode: expected RANDOM, TOP_SCORE or HYBRID")
        _validate_score(self.minimum_score, "minimum_score")


@dataclass(frozen=True, slots=True)
class IntakeSelectionDecision:
    candidate_id: int
    selected: bool
    reason: str


@dataclass(frozen=True, slots=True)
class IntakeSelectionResult:
    algorithm_version: str
    input_sha256: str
    selected_ids: tuple[int, ...]
    decisions: tuple[IntakeSelectionDecision, ...]
    eligible_count: int
    quota: int
    carry_out: int


def select_intake_window(
    candidates: tuple[IntakeCandidate, ...],
    *,
    window_key: str,
    policy: IntakeSelectionPolicy | None = None,
    carry: int = 0,
) -> IntakeSelectionResult:
    """Compare a bounded frozen window; the caller owns membership and durable carry.

    A selected decision grants no rewrite or publication permission. The digest
    identifies input evidence, not source authenticity or authorization.
    """
    if type(candidates) is not tuple:
        raise TypeError("candidates must be an exact tuple")
    if len(candidates) > 1000:
        raise ValueError("Window exceeds 1000 candidates")
    _validate_hash(window_key, "window_key")
    if type(carry) is not int or not 0 <= carry <= 99:
        raise ValueError("Invalid carry: expected integer in [0, 99]")
    if policy is None:
        policy = IntakeSelectionPolicy()
    if type(policy) is not IntakeSelectionPolicy:
        raise TypeError("policy must be an exact IntakeSelectionPolicy")
    policy.__post_init__()
    seen_ids = set()
    for candidate in candidates:
        if type(candidate) is not IntakeCandidate:
            raise TypeError("Each candidate must be an exact IntakeCandidate")
        candidate.__post_init__()
        if candidate.candidate_id in seen_ids:
            raise ValueError("Duplicate candidate_id")
        seen_ids.add(candidate.candidate_id)

    ordered = sorted(candidates, key=lambda candidate: candidate.candidate_id)
    payload = {
        "algorithm_version": ALGORITHM_VERSION,
        "window_key": window_key,
        "carry": carry,
        "policy": {
            "intake_percent": policy.intake_percent,
            "mode": policy.mode,
            "minimum_score": float(policy.minimum_score),
        },
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "revision_sha256": candidate.revision_sha256,
                "score": None if candidate.score is None else float(candidate.score),
                "eligible": candidate.eligible,
            }
            for candidate in ordered
        ],
    }
    input_sha256 = sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()

    reasons = {}
    pool = []
    for candidate in ordered:
        if not candidate.eligible:
            reasons[candidate.candidate_id] = "EXCLUDED"
        elif candidate.score is None:
            reasons[candidate.candidate_id] = "UNKNOWN_SCORE"
        elif candidate.score < policy.minimum_score:
            reasons[candidate.candidate_id] = "BELOW_THRESHOLD"
        else:
            pool.append(candidate)
            reasons[candidate.candidate_id] = "NOT_SELECTED"
    quota, carry_out = divmod(len(pool) * policy.intake_percent + carry, 100)

    selected_ids = []
    if policy.mode in ("TOP_SCORE", "HYBRID"):
        top_count = quota if policy.mode == "TOP_SCORE" else (4 * quota + 4) // 5
        top = sorted(pool, key=lambda candidate: (-candidate.score, candidate.candidate_id))
        for candidate in top[:top_count]:
            selected_ids.append(candidate.candidate_id)
            reasons[candidate.candidate_id] = "SELECTED_TOP"
    if policy.mode in ("RANDOM", "HYBRID"):
        remaining = [
            candidate for candidate in pool if reasons[candidate.candidate_id] == "NOT_SELECTED"
        ]
        random_order = sorted(
            remaining,
            key=lambda candidate: (
                sha256(
                    f"{window_key}:{candidate.candidate_id}:{candidate.revision_sha256}".encode(
                        "ascii"
                    )
                ).digest(),
                candidate.candidate_id,
            ),
        )
        for candidate in random_order[: quota - len(selected_ids)]:
            selected_ids.append(candidate.candidate_id)
            reasons[candidate.candidate_id] = "SELECTED_RANDOM"

    return IntakeSelectionResult(
        algorithm_version=ALGORITHM_VERSION,
        input_sha256=input_sha256,
        selected_ids=tuple(selected_ids),
        decisions=tuple(
            IntakeSelectionDecision(
                candidate.candidate_id,
                reasons[candidate.candidate_id] in ("SELECTED_TOP", "SELECTED_RANDOM"),
                reasons[candidate.candidate_id],
            )
            for candidate in ordered
        ),
        eligible_count=len(pool),
        quota=quota,
        carry_out=carry_out,
    )
