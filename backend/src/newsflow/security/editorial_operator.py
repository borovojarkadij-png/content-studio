"""Default-disabled dedicated operator authentication for diagnostic policy only."""

import os
import re
from dataclasses import dataclass

from newsflow.security.bounded_bearer import (
    BearerFileUnavailable,
    BearerHeaderUnauthorized,
    read_bearer_file,
    require_bearer,
)


class EditorialOperatorUnavailable(RuntimeError):
    pass


class EditorialOperatorUnauthorized(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class EditorialOperatorPrincipal:
    actor_id: int

    def __post_init__(self):
        if type(self.actor_id) is not int or not 0 < self.actor_id <= 2**63 - 1:
            raise ValueError("Positive configured operator identity required")


def authenticate_editorial_operator(authorization) -> EditorialOperatorPrincipal:
    try:
        configured = os.getenv("NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE", "")
        identity = os.getenv("NEWSFLOW_EDITORIAL_OPERATOR_ID", "")
        if not configured or not re.fullmatch(r"[1-9][0-9]{0,18}", identity):
            raise ValueError
        principal = EditorialOperatorPrincipal(int(identity))
        master = os.getenv("NEWSFLOW_MASTER_KEY_FILE", "").strip()
        reviewer = os.getenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE", "")
        token = read_bearer_file(
            configured, forbidden_paths=tuple(path for path in (master, reviewer) if path)
        )
    except (BearerFileUnavailable, ValueError, OverflowError):
        raise EditorialOperatorUnavailable(
            "Editorial operator authentication unavailable"
        ) from None
    try:
        require_bearer(authorization, token)
    except BearerHeaderUnauthorized:
        raise EditorialOperatorUnauthorized("Editorial operator authentication required") from None
    return principal
