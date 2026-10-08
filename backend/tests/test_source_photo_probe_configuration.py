import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import Base, TelegramAccount
from newsflow.services.telegram_configuration import TelegramConfigurationService


def test_source_probe_coexists_with_mapping_fixture_without_replacing_history(tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts" / "docker_source_photo_probe.py"
    spec = importlib.util.spec_from_file_location("source_photo_probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    engine = create_engine(f"sqlite:///{tmp_path / 'probe.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as session:
        original = TelegramConfigurationService(session).create_account(
            "synthetic-mapping-filters", 600600
        )
    account, mapping = probe.seed_configuration(sessions)
    assert account["id"] != original["id"]
    with sessions() as session:
        assert session.get(TelegramAccount, original["id"]).name == "synthetic-mapping-filters"
        assert len(session.scalars(select(TelegramAccount)).all()) == 2
        assert (
            TelegramConfigurationService(session).source_media_rights(mapping["id"])["license_code"]
            == "OWNED"
        )
    with pytest.raises(RuntimeError, match="fresh fixture"):
        probe.seed_configuration(sessions)
    engine.dispose()
