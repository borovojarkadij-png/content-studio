import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutboxEventModel,
    RewriteJobModel,
)
from newsflow.services.telegram_configuration import TelegramConfigurationService


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'configuration.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_configuration_survives_new_sessions_and_retries(engine):
    with Session(engine) as session:
        service = TelegramConfigurationService(session)
        account = service.create_account("Primary", 6000000001)
        donor = service.create_donor(account["id"], -1001234567890, "Source")
        output = service.create_output(account["id"], -1009876543210, "Destination")
        mapping = service.create_mapping(donor["id"], output["id"], 25, 75)
    with Session(engine) as session:
        service = TelegramConfigurationService(session)
        assert service.list_accounts() == [account]
        assert service.list_donors() == [donor]
        assert service.list_outputs() == [output]
        assert service.list_mappings() == [mapping]
        assert service.create_account("Primary", 6000000001) == account
        assert service.create_donor(account["id"], -1001234567890, "Source") == donor
        assert service.create_mapping(donor["id"], output["id"], 25, 75) == mapping
        assert account["health_status"] == "DISCONNECTED"
        assert "encrypted_session" not in account


def test_duplicate_identity_cannot_silently_replace_configuration(engine):
    with Session(engine) as session:
        service = TelegramConfigurationService(session)
        account = service.create_account("Primary", 1001)
        with pytest.raises(ValueError, match="already exists"):
            service.create_account("Other", 1001)
        assert service.list_accounts() == [account]


def test_mutations_validate_references_and_percentages_before_writes(engine):
    with Session(engine) as session:
        service = TelegramConfigurationService(session)
        with pytest.raises(LookupError):
            service.create_donor(999, -1001234567890, "Source")
        account = service.create_account("Primary", 1001)
        donor = service.create_donor(account["id"], -1001234567890, "Source")
        output = service.create_output(account["id"], -1009876543210, "Destination")
        with pytest.raises(ValueError):
            service.create_mapping(donor["id"], output["id"], 101, 50)
        assert service.list_mappings() == []
        mapping = service.create_mapping(donor["id"], output["id"], 10, 80)
        changed = service.update_mapping(mapping["id"], 30, 70)
        assert (changed["intake_percent"], changed["target_mix_percent"]) == (30, 70)


def test_bulk_import_is_durable_case_insensitive_and_does_not_fake_resolution(engine):
    with Session(engine) as session:
        service = TelegramConfigurationService(session)
        account = service.create_account("Primary", 1001)
        result = service.bulk_import_donors(
            account["id"], "@Source_one\nhttps://t.me/source_ONE\ninvalid source"
        )
        assert result == {
            "accepted": ["@source_one"],
            "duplicates": ["@source_one"],
            "rejected": ["invalid source"],
            "status": "PENDING_RESOLUTION",
        }
        assert service.list_donors() == []
    with Session(engine) as session:
        service = TelegramConfigurationService(session)
        assert service.bulk_import_donors(account["id"], "@SOURCE_ONE")["accepted"] == []
        assert service.list_donor_imports()[0]["identifier"] == "@source_one"


def test_bulk_import_rejects_out_of_range_numeric_identity_without_rolling_back_valid_rows(engine):
    too_large = "-100" + "1" * 101
    with Session(engine) as session:
        service = TelegramConfigurationService(session)
        account = service.create_account("Primary", 1001)
        result = service.bulk_import_donors(account["id"], f"@valid_source\n{too_large}")
        assert result["accepted"] == ["@valid_source"]
        assert result["rejected"] == [too_large]
    with Session(engine) as session:
        assert TelegramConfigurationService(session).list_donor_imports() == [{
            "id": 1, "telegram_account_id": account["id"], "identifier": "@valid_source",
            "status": "PENDING_RESOLUTION",
        }]


def test_configuration_mutations_leave_editorial_reject_and_jobs_untouched(engine):
    with Session(engine) as session:
        session.add(
            EditorialDecisionModel(
                content_key="source:revision:1",
                status="REJECT",
                rewrite_allowed=False,
                sentiment="negative",
                framing="hostile",
            )
        )
        session.commit()
        service = TelegramConfigurationService(session)
        account = service.create_account("Primary", 1001)
        donor = service.create_donor(account["id"], -1001234567890, "Source")
        output = service.create_output(account["id"], -1009876543210, "Destination")
        mapping = service.create_mapping(donor["id"], output["id"], 100, 100)
        service.update_mapping(mapping["id"], 0, 0)
        service.update_account(account["id"], "Renamed")
        assert session.scalar(select(EditorialDecisionModel)).rewrite_allowed is False
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0
