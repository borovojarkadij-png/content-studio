import pytest
from cryptography.fernet import Fernet

from newsflow.security import session_cipher


def test_session_cipher_round_trips_a_telegram_session_without_exposing_plaintext() -> None:
    cipher = session_cipher.SessionCipher(Fernet.generate_key().decode("ascii"))

    encrypted = cipher.encrypt("telegram-string-session")

    assert encrypted != "telegram-string-session"
    assert cipher.decrypt(encrypted) == "telegram-string-session"


def test_session_cipher_refuses_a_ciphertext_encrypted_with_another_master_key() -> None:
    primary = session_cipher.SessionCipher(Fernet.generate_key().decode("ascii"))
    replacement = session_cipher.SessionCipher(Fernet.generate_key().decode("ascii"))

    with pytest.raises(session_cipher.SessionDecryptionUnavailable):
        replacement.decrypt(primary.encrypt("telegram-string-session"))


def test_session_cipher_rejects_an_invalid_provisioned_master_key() -> None:
    with pytest.raises(session_cipher.MasterKeyFormatInvalid):
        session_cipher.SessionCipher("not-a-fernet-key")
