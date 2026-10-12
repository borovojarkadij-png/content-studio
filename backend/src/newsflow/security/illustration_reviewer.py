"""Default-disabled single human authentication; never creates a credential."""

import os
import re
from dataclasses import dataclass

from newsflow.security.bounded_bearer import (
    BearerFileUnavailable,
    BearerHeaderUnauthorized,
    read_bearer_file,
    require_bearer,
)


class ReviewerUnavailable(RuntimeError):
    pass


class ReviewerUnauthorized(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewerPrincipal:
    """Trusted internal principal; only the authenticated dependency supplies it."""

    reviewer_id: int

    def __post_init__(self):
        if type(self.reviewer_id) is not int or not 0 < self.reviewer_id <= 2**63 - 1:
            raise ValueError("Positive configured reviewer identity required")


def authenticate_reviewer(authorization: str | None) -> ReviewerPrincipal:
    """Reopen bounded dedicated file per request, so explicit rotation takes effect."""
    try:
        configured = os.getenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE", "")
        identity = os.getenv("NEWSFLOW_ILLUSTRATION_REVIEWER_ID", "")
        if not configured or not re.fullmatch(r"[1-9][0-9]{0,18}", identity):
            raise ValueError
        principal = ReviewerPrincipal(int(identity))
        master = os.getenv("NEWSFLOW_MASTER_KEY_FILE", "").strip()
        token = read_bearer_file(configured, forbidden_paths=(master,) if master else ())
    except (BearerFileUnavailable, ValueError, OverflowError):
        raise ReviewerUnavailable("Illustration reviewer authentication unavailable") from None
    try:
        require_bearer(authorization, token)
    except BearerHeaderUnauthorized:
        raise ReviewerUnauthorized("Illustration reviewer authentication required") from None
    return principal
