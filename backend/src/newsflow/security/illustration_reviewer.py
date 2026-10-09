"""Default-disabled single human authentication; never creates a credential."""

import hmac
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path


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
        path = Path(configured)
        master = os.getenv("NEWSFLOW_MASTER_KEY_FILE", "")
        if master and (
            path.resolve() == Path(master).resolve()
            or (Path(master).exists() and os.path.samefile(path, master))
        ):
            raise ValueError
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size > 130
            or getattr(before, "st_file_attributes", 0) & 0x400  # Windows reparse point
        ):
            raise ValueError
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (
                opened.st_dev,
                opened.st_ino,
            ):
                raise ValueError
            token = stream.read(131)
        if token.endswith(b"\n"):
            token = token[:-1]
        if not re.fullmatch(rb"[A-Za-z0-9_-]{32,128}", token):
            raise ValueError
    except (OSError, ValueError, OverflowError):
        raise ReviewerUnavailable("Illustration reviewer authentication unavailable") from None
    if (
        type(authorization) is not str
        or not re.fullmatch(r"Bearer [A-Za-z0-9_-]{32,128}", authorization)
        or not hmac.compare_digest(authorization[7:].encode("ascii"), token)
    ):
        raise ReviewerUnauthorized("Illustration reviewer authentication required")
    return principal
