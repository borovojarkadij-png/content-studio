"""Durable configuration only: no authentication, AI, ingestion or publication.

The service owns a dedicated request/session transaction and commits mutations.
It must not share a session with an unrelated unit of work. Natural identities
are immutable; matching create retries return the same row, conflicting creates
require an explicit metadata update. Secrets never enter public projections.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.domain.telegram import parse_donor_import
from newsflow.persistence.models import (
    ChannelMappingModel,
    DonorChannel,
    DonorImportModel,
    OutputChannel,
    TelegramAccount,
)


class ConfigurationConflict(ValueError):
    """An identity is already configured with different metadata."""


def _text(value: str, limit: int) -> str:
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError("Configuration text is empty or too long")
    return value


def _identity(value: int, *, positive: bool = False) -> int:
    if type(value) is not int or not -(2**63) <= value < 2**63 or value == 0:
        raise ValueError("Telegram identity must be a nonzero signed 64-bit integer")
    if positive and value < 1:
        raise ValueError("Account identity must be positive")
    return value


def _percent(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError("Mapping percentages must be between 0 and 100")
    return value


def _mapping_policy(
    eligibility_mode: str,
    delay_minutes: int,
    priority: int,
    media_policy: str,
) -> dict[str, object]:
    if eligibility_mode not in {"IMMEDIATE", "DELAYED"}:
        raise ValueError("Mapping eligibility mode is invalid")
    if type(delay_minutes) is not int or not 0 <= delay_minutes <= 10080:
        raise ValueError("Mapping delay must be between 0 and 10080 minutes")
    if eligibility_mode == "IMMEDIATE" and delay_minutes != 0:
        raise ValueError("Immediate mapping must not have a delay")
    if type(priority) is not int or not -1000 <= priority <= 1000:
        raise ValueError("Mapping priority must be between -1000 and 1000")
    if media_policy not in {"REUSE_SOURCE", "LICENSED_LIBRARY"}:
        raise ValueError("Mapping media policy is invalid")
    return {
        "eligibility_mode": eligibility_mode,
        "delay_minutes": delay_minutes,
        "priority": priority,
        "media_policy": media_policy,
    }


def _persistable_import_identifier(identifier: str) -> str | None:
    """Reject parser candidates that cannot be represented by durable storage."""
    identifier = identifier.lower()
    if len(identifier) > 100:
        return None
    if identifier.startswith("-100"):
        try:
            _identity(int(identifier))
        except ValueError:
            return None
    return identifier


def _project(row) -> dict[str, object]:
    if isinstance(row, TelegramAccount):
        return {
            "id": row.id,
            "name": row.name,
            "telegram_user_id": row.telegram_user_id,
            "health_status": row.health_status,
            "session_provisioned": bool(row.encrypted_session),
        }
    if isinstance(row, (DonorChannel, OutputChannel)):
        return {
            "id": row.id,
            "telegram_account_id": row.telegram_account_id,
            "telegram_channel_id": row.telegram_channel_id,
            "title": row.title,
        }
    if isinstance(row, ChannelMappingModel):
        return {
            "id": row.id,
            "donor_channel_id": row.donor_channel_id,
            "output_channel_id": row.output_channel_id,
            "intake_percent": row.intake_percent,
            "target_mix_percent": row.target_mix_percent,
            "eligibility_mode": row.eligibility_mode,
            "delay_minutes": row.delay_minutes,
            "priority": row.priority,
            "media_policy": row.media_policy,
        }
    return {
        "id": row.id,
        "telegram_account_id": row.telegram_account_id,
        "identifier": row.identifier,
        "status": row.status,
    }


class TelegramConfigurationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _require(self, model, row_id: int):
        row = self._session.get(model, row_id)
        if row is None:
            raise LookupError("Referenced configuration was not found")
        return row

    def _list(self, model) -> list[dict[str, object]]:
        return [_project(row) for row in self._session.scalars(select(model).order_by(model.id))]

    def list_accounts(self) -> list[dict[str, object]]:
        return self._list(TelegramAccount)

    def list_donors(self) -> list[dict[str, object]]:
        return self._list(DonorChannel)

    def list_outputs(self) -> list[dict[str, object]]:
        return self._list(OutputChannel)

    def list_mappings(self) -> list[dict[str, object]]:
        return self._list(ChannelMappingModel)

    def list_donor_imports(self) -> list[dict[str, object]]:
        return self._list(DonorImportModel)

    def _create(self, model, identity: dict, metadata: dict, defaults: dict | None = None):
        query = select(model).filter_by(**identity)
        try:
            existing = self._session.scalar(query)
            if existing is not None:
                if any(getattr(existing, key) != value for key, value in metadata.items()):
                    raise ConfigurationConflict("Configuration identity already exists")
                result = _project(existing)
            else:
                row = model(**identity, **metadata, **(defaults or {}))
                self._session.add(row)
                self._session.flush()
                result = _project(row)
            self._session.commit()
            return result
        except IntegrityError:
            self._session.rollback()
            # Unique constraints arbitrate concurrent delivery; never overwrite.
            existing = self._session.scalar(query)
            if existing is not None and all(
                getattr(existing, key) == value for key, value in metadata.items()
            ):
                return _project(existing)
            raise ConfigurationConflict("Configuration identity already exists") from None
        except Exception:
            self._session.rollback()
            raise

    def _update(self, model, row_id: int, metadata: dict):
        try:
            row = self._require(model, row_id)
            for key, value in metadata.items():
                setattr(row, key, value)
            self._session.flush()
            result = _project(row)
            self._session.commit()
            return result
        except IntegrityError:
            self._session.rollback()
            raise ConfigurationConflict("Configuration identity already exists") from None
        except Exception:
            self._session.rollback()
            raise

    def create_account(self, name: str, telegram_user_id: int) -> dict[str, object]:
        return self._create(
            TelegramAccount,
            {"telegram_user_id": _identity(telegram_user_id, positive=True)},
            {"name": _text(name, 100)},
            {"encrypted_session": "", "health_status": "DISCONNECTED"},
        )

    def update_account(self, account_id: int, name: str) -> dict[str, object]:
        return self._update(TelegramAccount, account_id, {"name": _text(name, 100)})

    def _create_channel(self, model, account_id: int, channel_id: int, title: str):
        title = _text(title, 255)
        channel_id = _identity(channel_id)
        self._require(TelegramAccount, account_id)
        return self._create(
            model,
            {"telegram_account_id": account_id, "telegram_channel_id": channel_id},
            {"title": title},
        )

    def create_donor(self, account_id: int, channel_id: int, title: str) -> dict[str, object]:
        return self._create_channel(DonorChannel, account_id, channel_id, title)

    def create_output(self, account_id: int, channel_id: int, title: str) -> dict[str, object]:
        return self._create_channel(OutputChannel, account_id, channel_id, title)

    def update_donor(self, donor_id: int, title: str) -> dict[str, object]:
        return self._update(DonorChannel, donor_id, {"title": _text(title, 255)})

    def update_output(self, output_id: int, title: str) -> dict[str, object]:
        return self._update(OutputChannel, output_id, {"title": _text(title, 255)})

    def create_mapping(
        self,
        donor_id: int,
        output_id: int,
        intake_percent: int,
        target_mix_percent: int,
        *,
        eligibility_mode: str = "IMMEDIATE",
        delay_minutes: int = 0,
        priority: int = 0,
        media_policy: str = "REUSE_SOURCE",
    ) -> dict[str, object]:
        metadata = {
            "intake_percent": _percent(intake_percent),
            "target_mix_percent": _percent(target_mix_percent),
            **_mapping_policy(eligibility_mode, delay_minutes, priority, media_policy),
        }
        self._require(DonorChannel, donor_id)
        self._require(OutputChannel, output_id)
        return self._create(
            ChannelMappingModel,
            {"donor_channel_id": donor_id, "output_channel_id": output_id},
            metadata,
        )

    def update_mapping(
        self,
        mapping_id: int,
        intake_percent: int,
        target_mix_percent: int,
        *,
        eligibility_mode: str | None = None,
        delay_minutes: int | None = None,
        priority: int | None = None,
        media_policy: str | None = None,
    ) -> dict[str, object]:
        row = self._require(ChannelMappingModel, mapping_id)
        return self._update(
            ChannelMappingModel,
            mapping_id,
            {
                "intake_percent": _percent(intake_percent),
                "target_mix_percent": _percent(target_mix_percent),
                **_mapping_policy(
                    row.eligibility_mode if eligibility_mode is None else eligibility_mode,
                    row.delay_minutes if delay_minutes is None else delay_minutes,
                    row.priority if priority is None else priority,
                    row.media_policy if media_policy is None else media_policy,
                ),
            },
        )

    def bulk_import_donors(self, account_id: int, raw_text: str) -> dict[str, object]:
        if len(raw_text) > 100000:
            raise ValueError("Donor import is too large")
        parsed = parse_donor_import(raw_text)
        try:
            self._require(TelegramAccount, account_id)
            known = set(
                self._session.scalars(
                    select(DonorImportModel.identifier).where(
                        DonorImportModel.telegram_account_id == account_id
                    )
                )
            )
            accepted, duplicates, rejected = [], [], list(parsed.rejected)
            for entry in parsed.accepted:
                identifier = _persistable_import_identifier(entry.canonical_identifier)
                if identifier is None:
                    rejected.append(entry.canonical_identifier)
                    continue
                if identifier in known:
                    duplicates.append(identifier)
                    continue
                # Savepoints keep a concurrent duplicate from rolling back this batch.
                try:
                    with self._session.begin_nested():
                        self._session.add(
                            DonorImportModel(
                                telegram_account_id=account_id,
                                identifier=identifier,
                                status="PENDING_RESOLUTION",
                            )
                        )
                        self._session.flush()
                    accepted.append(identifier)
                except IntegrityError:
                    duplicates.append(identifier)
                known.add(identifier)
            self._session.commit()
            return {
                "accepted": accepted,
                "duplicates": duplicates,
                "rejected": rejected,
                "status": "PENDING_RESOLUTION",
            }
        except Exception:
            self._session.rollback()
            raise
