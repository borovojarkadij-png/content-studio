import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command


def test_media_migration_preserves_rights_and_refuses_populated_downgrade(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'media-migration.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO media_assets (storage_key, sha256, mime_type, origin, license_code, attribution, tags) VALUES ('licensed.png', :digest, 'image/png', 'LICENSED_LIBRARY', 'CC-BY', 'Synthetic author', '[\"марс\"]')"
            ),
            {"digest": "a" * 64},
        )
    with pytest.raises(RuntimeError, match="preserve rights metadata"):
        command.downgrade(config, "d7a1e4c2b805")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT attribution FROM media_assets")) == "Synthetic author"
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "e82a9c7b3061"
    command.upgrade(config, "head")
    engine.dispose()
