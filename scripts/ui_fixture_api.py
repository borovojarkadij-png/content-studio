"""Isolated UI-test API: actual migrations/reader, synthetic data, no providers/secrets."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main() -> None:
    from newsflow.app import app
    from newsflow.persistence.database import reset_database_session_factory
    from newsflow.persistence.models import (
        ContentRevisionModel,
        EditorialDecisionModel,
        IncomingPostModel,
    )

    with TemporaryDirectory(prefix="content-studio-ui-test-") as directory:
        database_url = f"sqlite:///{Path(directory, 'fixture.db').as_posix()}"
        os.environ["DATABASE_URL"] = database_url
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
        config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(config, "head")
        engine = create_engine(database_url)
        with Session(engine) as session:
            post = IncomingPostModel(
                telegram_account_id="ui-test",
                donor_channel_id="@synthetic_donor",
                telegram_message_id=42,
                state="REJECTED_EDITORIAL",
            )
            session.add(post)
            session.flush()
            session.add(
                ContentRevisionModel(
                    incoming_post_id=post.id,
                    revision_number=1,
                    source_text="Изолированный API fixture: материал отклонён",
                )
            )
            session.add(
                EditorialDecisionModel(
                    content_key="ui-test:@synthetic_donor:42:revision:1",
                    status="REJECT",
                    rewrite_allowed=False,
                    reason_codes="PROTECTED_ENTITY_NEGATIVE",
                    protected_entities="synthetic",
                    sentiment="negative",
                    framing="hostile",
                )
            )
            session.commit()
        engine.dispose()
        try:
            uvicorn.run(app, host="127.0.0.1", port=5181, log_level="warning")
        finally:
            reset_database_session_factory()


if __name__ == "__main__":
    main()
