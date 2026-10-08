"""Isolated UI-test API: actual migrations/reader, synthetic data, no providers/secrets."""

import os
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from alembic.config import Config
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main() -> None:
    from newsflow.app import app
    from newsflow.persistence.database import reset_database_session_factory
    from newsflow.persistence.models import (
        ChannelDifferenceCursorModel,
        ContentRevisionModel,
        EditorialDecisionModel,
        IncomingPostModel,
        OutputChannel,
        PlannedPublicationModel,
        PublicationCandidateModel,
        PublicationJobModel,
        RewriteJobModel,
        RewriteUsageModel,
        TelegramAccount,
    )
    from newsflow.providers.commons_images import ImageSearchResult
    from newsflow.providers.telegram import TelegramChannelDifference
    from newsflow.services.durable_media_runner import DurableMediaRunner
    from newsflow.services.publication_planning import PublicationPlanningService
    from newsflow.services.rewrite_outputs import RewriteOutputService
    from newsflow.services.source_deletions import SourceDeletionService
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    with TemporaryDirectory(prefix="content-studio-ui-test-") as directory:
        database_url = f"sqlite:///{Path(directory, 'fixture.db').as_posix()}"
        os.environ["DATABASE_URL"] = database_url
        media_root = Path(directory, "media")
        media_root.mkdir()
        os.environ["NEWSFLOW_MEDIA_ROOT"] = str(media_root)
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
            session.commit()
            configuration = TelegramConfigurationService(session)
            donor = configuration.create_donor(
                account.id, -1002222222222, "Изолированный донор API"
            )
            configuration.create_donor(account.id, -1003333333333, "Другой изолированный донор API")
            configuration.create_mapping(donor["id"], output_id, 100, 50)
            photo_output = configuration.create_output(
                account.id, -1005555555555, "Изолированный канал фото API"
            )
            for number in (1, 2, 3):
                target_output_id = photo_output["id"] if number == 3 else output_id
                key = f"ui-planner:@planner_donor:{number}:revision:1"
                source = IncomingPostModel(
                    telegram_account_id="ui-planner",
                    donor_channel_id="@planner_donor",
                    telegram_message_id=number,
                    state="RECEIVED",
                )
                session.add(source)
                session.flush()
                session.add(
                    ContentRevisionModel(
                        incoming_post_id=source.id,
                        revision_number=1,
                        source_text=f"Isolated planner source {number}",
                    )
                )
                decision = EditorialDecisionModel(
                    content_key=key,
                    status="PASS",
                    rewrite_allowed=True,
                    sentiment="neutral",
                    framing="neutral",
                )
                job = RewriteJobModel(
                    content_key=key,
                    output_channel_id=target_output_id,
                    idempotency_key=f"ui-rewrite-{number}",
                    state="SUCCEEDED",
                )
                session.add_all(
                    [
                        decision,
                        job,
                        PublicationCandidateModel(
                            output_channel_id=target_output_id,
                            content_key=key,
                            priority=10,
                            state="AWAITING_REWRITE",
                            media_policy="LICENSED_LIBRARY",
                        ),
                    ]
                )
                session.commit()
                review = RewriteOutputService(session)
                draft = review.record_succeeded_output(
                    job.id, f"Изолированный вариант API {number}"
                )
                if number == 1:
                    # Synthetic observed usage + unobserved reserved attempt, not live spend.
                    job.attempts = 2
                    session.add(
                        RewriteUsageModel(
                            rewrite_job_id=job.id,
                            attempt=1,
                            provider="OPENAI",
                            model="synthetic-ui-usage",
                            style="NEUTRAL",
                            input_tokens=100,
                            cached_tokens=40,
                            output_tokens=20,
                            estimated_cost_usd=None,
                        )
                    )
                    session.commit()
                if number == 3:
                    review.approve(draft["id"], activate_candidate=True)
                if number == 2:
                    # Simulate editorial policy changing after a previous successful rewrite.
                    decision.status, decision.rewrite_allowed = "REJECT", False
                    session.commit()
            PublicationPlanningService(session).configure_plan(
                output_id, "MANUAL", 1, (540,), "UTC"
            )
            PublicationPlanningService(session).configure_plan(
                photo_output["id"], "MANUAL", 1, (540,), "UTC"
            )
        buffer = BytesIO()
        Image.new("RGB", (64, 32), "navy").save(buffer, format="PNG")
        photo_bytes = buffer.getvalue()

        class FixtureImages:
            """Synthetic byte source only; no real Commons search/download."""

            def search(self, text, *, limit=5):
                return [
                    ImageSearchResult(
                        1,
                        "Synthetic UI photo",
                        "https://upload.wikimedia.org/wikipedia/commons/test.png",
                        "https://commons.wikimedia.org/wiki/File:test.png",
                        "CC0",
                        "Synthetic isolated UI illustration; not a real event photo",
                        "image/png",
                        len(photo_bytes),
                        64,
                        32,
                        ("isolated",),
                    )
                ]

            def download(self, result):
                return photo_bytes

        execution = DurableMediaRunner(sessionmaker(engine), media_root, provider=FixtureImages())
        execution.enqueue_candidate(3, now=datetime.now(UTC))
        assert execution.run_next(now=datetime.now(UTC)) == "SUCCEEDED"
        # Synthetic committed history for READ-ONLY browser tests. No sender is
        # instantiated and these rows are not proof of live Telegram delivery.
        with Session(engine) as session:
            history_output = TelegramConfigurationService(session).create_output(
                1, -1006666666666, "Изолированная история доставки API"
            )
            PublicationPlanningService(session).configure_plan(
                history_output["id"], "MANUAL", 2, (0, 5), "UTC"
            )
            for number, state in ((4, "NEEDS_RECONCILIATION"), (5, "SUCCEEDED")):
                key = f"ui-history:@history_donor:{number}:revision:1"
                source = IncomingPostModel(
                    telegram_account_id="ui-history",
                    donor_channel_id="@history_donor",
                    telegram_message_id=number,
                    state="RECEIVED",
                )
                session.add(source)
                session.flush()
                session.add(
                    ContentRevisionModel(
                        incoming_post_id=source.id,
                        revision_number=1,
                        source_text=f"Synthetic history {number}",
                    )
                )
                session.add(
                    EditorialDecisionModel(
                        content_key=key,
                        status="REJECT" if number == 4 else "PASS",
                        rewrite_allowed=number != 4,
                        sentiment="neutral",
                        framing="neutral",
                    )
                )
                candidate = PublicationCandidateModel(
                    output_channel_id=history_output["id"],
                    content_key=key,
                    priority=10,
                    state="SCHEDULED" if number == 4 else "PUBLISHED",
                    media_policy="REUSE_SOURCE",
                )
                session.add(candidate)
                session.flush()
                item = PlannedPublicationModel(
                    candidate_id=candidate.id,
                    output_channel_id=history_output["id"],
                    scheduled_for=datetime(2026, 10, 8, 0, 0 if number == 4 else 5, tzinfo=UTC),
                    state="PLANNED" if number == 4 else "PUBLISHED",
                )
                session.add(item)
                session.flush()
                session.add(
                    PublicationJobModel(
                        planned_id=item.id,
                        telegram_account_id=1,
                        telegram_channel_id=-1006666666666,
                        request_nonce=1000 + number,
                        binding_sha256="a" * 64,
                        state=state,
                        attempts=1,
                        available_at=item.scheduled_for,
                        sent_message_id=502 if number == 5 else None,
                        completed_at=datetime(2026, 10, 8, 0, 6, tzinfo=UTC)
                        if number == 5
                        else None,
                        last_error_code="PUBLICATION_SEND_OUTCOME_UNKNOWN" if number == 4 else None,
                    )
                )
            session.commit()
        # Retained synthetic original + historical PASS, no rewrite job/provider.
        # Use the actual deletion service against this create-only isolated DB.
        with Session(engine) as session:
            deleted_source = IncomingPostModel(
                telegram_account_id="1",
                donor_channel_id="-1002222222222",
                telegram_message_id=90,
                state="RECEIVED",
            )
            session.add(deleted_source)
            session.flush()
            session.add(
                ContentRevisionModel(
                    incoming_post_id=deleted_source.id,
                    revision_number=1,
                    source_text="Изолированный удалённый источник API",
                )
            )
            session.add(
                EditorialDecisionModel(
                    content_key="1:-1002222222222:90:revision:1",
                    status="PASS",
                    rewrite_allowed=True,
                    sentiment="neutral",
                    framing="neutral",
                )
            )
            session.commit()
        SourceDeletionService(sessionmaker(engine)).record(
            TelegramChannelDifference("1", "-1002222222222", 10, 11, True, 0, (), (90,)),
            observed_at=datetime.now(UTC),
        )
        # Explicit synthetic unresolved-gap ledger, never operational configuration.
        with Session(engine) as session:
            source = IncomingPostModel(
                telegram_account_id="1",
                donor_channel_id="-1002222222222",
                telegram_message_id=91,
                state="RECEIVED",
            )
            session.add(source)
            session.flush()
            session.add(
                ContentRevisionModel(
                    incoming_post_id=source.id,
                    revision_number=1,
                    source_text="Изолированный источник с gap API",
                )
            )
            session.add(
                EditorialDecisionModel(
                    content_key="1:-1002222222222:91:revision:1",
                    status="PASS",
                    rewrite_allowed=True,
                    sentiment="neutral",
                    framing="neutral",
                )
            )
            session.add(
                ChannelDifferenceCursorModel(
                    donor_channel_id=donor["id"],
                    telegram_account_id=1,
                    telegram_user_id=1001,
                    telegram_channel_id=-1002222222222,
                    pts=10,
                    available_at=datetime.now(UTC),
                    last_error_code="GAP_UNRESOLVED",
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
