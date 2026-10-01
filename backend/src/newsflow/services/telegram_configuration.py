"""Configuration use cases for accounts and donor imports."""

from dataclasses import dataclass

from newsflow.domain.telegram import parse_donor_import


@dataclass(frozen=True, slots=True)
class ConfiguredTelegramAccount:
    name: str
    telegram_user_id: int
    encrypted_session: str


@dataclass(frozen=True, slots=True)
class BulkDonorImportResult:
    accepted: tuple[str, ...]
    rejected: tuple[str, ...]


class TelegramConfigurationService:
    """In-memory application service until the SQLAlchemy repository is wired."""

    def __init__(self) -> None:
        self._accounts: list[ConfiguredTelegramAccount] = []
        self._donors: set[str] = set()

    def create_account(self, name: str, telegram_user_id: int, encrypted_session: str) -> ConfiguredTelegramAccount:
        if any(account.telegram_user_id == telegram_user_id for account in self._accounts):
            raise ValueError("Telegram user identity already exists")
        account = ConfiguredTelegramAccount(name, telegram_user_id, encrypted_session)
        self._accounts.append(account)
        return account

    def bulk_import_donors(self, raw_text: str) -> BulkDonorImportResult:
        parsed = parse_donor_import(raw_text)
        accepted: list[str] = []
        for entry in parsed.accepted:
            if entry.canonical_identifier not in self._donors:
                self._donors.add(entry.canonical_identifier)
                accepted.append(entry.canonical_identifier)
        return BulkDonorImportResult(tuple(accepted), parsed.rejected)
