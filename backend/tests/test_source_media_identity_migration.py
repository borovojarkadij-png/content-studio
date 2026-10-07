import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command


def test_media_identity_upgrade_keeps_unknown_legacy_data_and_guards_populated_downgrade(tmp_path):
    url = f"sqlite:///{tmp_path / 'media-id.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "d3a085f4c7e6")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incoming_posts (id,telegram_account_id,donor_channel_id,telegram_message_id,state) VALUES (1,'synthetic','-100123',1,'RECEIVED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO incoming_post_revisions (incoming_post_id,revision_number,source_text) VALUES (1,1,'Legacy source')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        assert connection.execute(
            text("SELECT media_id,media_protected FROM incoming_post_revisions")
        ).one() == (None, None)
        connection.execute(
            text(
                "INSERT INTO incoming_post_revisions (incoming_post_id,revision_number,source_text,media_type,media_id,media_protected) VALUES (1,2,'Caption','photo','-9223372036854775808',0)"
            )
        )
    with pytest.raises(RuntimeError, match="media identity"):
        command.downgrade(config, "d3a085f4c7e6")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM incoming_post_revisions")) == 2
        assert (
            connection.scalar(
                text("SELECT media_id FROM incoming_post_revisions WHERE revision_number=2")
            )
            == "-9223372036854775808"
        )
    engine.dispose()
