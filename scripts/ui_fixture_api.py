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
        OutputChannel,
        PublicationCandidateModel,
        RewriteJobModel,
        TelegramAccount,
    )
    from newsflow.services.publication_planning import PublicationPlanningService
    from newsflow.services.rewrite_outputs import RewriteOutputService

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
            account = TelegramAccount(
                name="Synthetic UI account", telegram_user_id=1001, encrypted_session=""
            )
            session.add(account)
            session.flush()
            output = OutputChannel(
                telegram_account_id=account.id,
                telegram_channel_id=-1001234567890,
                title="Изолированный канал API",
            )
            session.add(output)
            session.flush()
            output_id = output.id
            for number in (1, 2):
                key = f"ui-planner:revision:{number}"
                decision = EditorialDecisionModel(
                    content_key=key,
                    status="PASS",
                    rewrite_allowed=True,
                    sentiment="neutral",
                    framing="neutral",
                )
                job = RewriteJobModel(
                    content_key=key,
                    output_channel_id=output_id,
                    idempotency_key=f"ui-rewrite-{number}",
                    state="SUCCEEDED",
                )
                session.add_all(
                    [
                        decision,
                        job,
                        PublicationCandidateModel(
                            output_channel_id=output_id,
                            content_key=key,
                            priority=10,
                            state="AWAITING_REWRITE",
                        ),
                    ]
                )
                session.commit()
                RewriteOutputService(session).record_succeeded_output(
                    job.id, f"Изолированный вариант API {number}"
                )
                if number == 2:
                    # Simulate editorial policy changing after a previous successful rewrite.
                    decision.status, decision.rewrite_allowed = "REJECT", False
                    session.commit()
            PublicationPlanningService(session).configure_plan(
                output_id, "MANUAL", 1, (540,), "UTC"
            )
        engine.dispose()
        try:
            uvicorn.run(app, host="127.0.0.1", port=5181, log_level="warning")
        finally:
            reset_database_session_factory()


if __name__ == "__main__":
    main()
