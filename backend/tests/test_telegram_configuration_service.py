import pytest

from newsflow.services.telegram_configuration import TelegramConfigurationService


def test_create_account_rejects_duplicate_telegram_user_identity() -> None:
    service = TelegramConfigurationService()
    service.create_account("Primary", 1001, "ciphertext")

    with pytest.raises(ValueError, match="already exists"):
        service.create_account("Other", 1001, "another-ciphertext")


def test_bulk_import_keeps_only_unique_donor_identifiers() -> None:
    service = TelegramConfigurationService()

    result = service.bulk_import_donors("@source_one\n@source_one\ninvalid source")

    assert result.accepted == ("@source_one",)
    assert result.rejected == ("invalid source",)
