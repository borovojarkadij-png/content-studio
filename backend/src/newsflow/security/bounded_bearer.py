"""Bounded dedicated bearer files and headers; no configuration or secret creation."""

import hmac
import os
import re
import stat
from pathlib import Path


class BearerFileUnavailable(RuntimeError):
    pass


class BearerHeaderUnauthorized(PermissionError):
    pass


def read_bearer_file(path, *, forbidden_paths=()) -> bytes:
    """Reopen a regular file, refusing aliases to excluded credential files."""
    try:
        path = Path(path)
        for forbidden in forbidden_paths:
            other = Path(forbidden)
            if path.resolve() == other.resolve() or (
                other.exists() and os.path.samefile(path, other)
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
        return token
    except (OSError, ValueError, OverflowError, RuntimeError, TypeError):
        raise BearerFileUnavailable("Bearer file unavailable") from None


def require_bearer(authorization, token: bytes) -> None:
    if (
        type(authorization) is not str
        or not re.fullmatch(r"Bearer [A-Za-z0-9_-]{32,128}", authorization)
        or not hmac.compare_digest(authorization[7:].encode("ascii"), token)
    ):
        raise BearerHeaderUnauthorized("Bearer authentication required")
