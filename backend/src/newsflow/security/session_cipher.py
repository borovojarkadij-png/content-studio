"""Encryption boundary for persisted Telegram string sessions.

The key is supplied by :mod:`newsflow.security.master_key`; this module never
creates or rotates it.  A changed or malformed key therefore fails visibly
instead of silently making stored sessions look like a fresh installation.
"""

from cryptography.fernet import Fernet, InvalidToken


class MasterKeyFormatInvalid(ValueError):
    """Raised when the externally provisioned key cannot initialize Fernet."""


class SessionDecryptionUnavailable(RuntimeError):
    """Raised when a persisted session cannot be decrypted by the supplied key."""


class SessionCipher:
    """Small, explicit boundary between an account repository and session secrets."""

    def __init__(self, master_key: str) -> None:
        try:
            self._fernet = Fernet(master_key.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as exc:
            raise MasterKeyFormatInvalid("NEWSFLOW_MASTER_KEY is not a valid Fernet key") from exc

    def encrypt(self, session: str) -> str:
        return self._fernet.encrypt(session.encode("utf-8")).decode("ascii")

    def decrypt(self, encrypted_session: str) -> str:
        try:
            return self._fernet.decrypt(encrypted_session.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
            raise SessionDecryptionUnavailable(
                "Persisted Telegram session cannot be decrypted with NEWSFLOW_MASTER_KEY"
            ) from exc
