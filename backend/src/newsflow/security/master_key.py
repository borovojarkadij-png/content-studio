"""Stable master-key loading.

The caller owns key creation and backup.  Runtime never silently replaces an
unreadable key because doing so would make persisted sessions unrecoverable.
"""

from os import getenv
from pathlib import Path


class MasterKeyUnavailable(RuntimeError):
    """Raised when an explicitly provisioned master key cannot be read."""


def load_master_key(path: Path) -> str:
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise MasterKeyUnavailable("NEWSFLOW_MASTER_KEY is not provisioned") from exc
    if not key:
        raise MasterKeyUnavailable("NEWSFLOW_MASTER_KEY is empty")
    return key


def load_runtime_master_key() -> str:
    """Load only an explicitly mounted, stable secret file at runtime."""
    configured_path = getenv("NEWSFLOW_MASTER_KEY_FILE", "").strip()
    if not configured_path:
        raise MasterKeyUnavailable("NEWSFLOW_MASTER_KEY_FILE is not provisioned")
    return load_master_key(Path(configured_path))
