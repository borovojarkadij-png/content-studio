"""Create-only synthetic reviewer browser API; never use operational credentials/providers."""

import os
import sys
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from alembic.config import Config
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main():
    from newsflow.app import app
    from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
    from newsflow.persistence import models
    from newsflow.persistence.database import reset_database_session_factory
    from newsflow.providers.commons_images import ImageSearchResult
    from newsflow.providers.telegram import TelegramMessage
    from newsflow.services.durable_media_runner import DurableMediaRunner
    from newsflow.services.publication_planning import PublicationPlanningService
    from newsflow.services.rewrite_outputs import RewriteOutputService
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    with TemporaryDirectory(prefix="content-studio-review-browser-") as directory:
        root = Path(directory)
        url = f"sqlite:///{(root / 'fixture.db').as_posix()}"
        os.environ["DATABASE_URL"] = url
        media = root / "media"
        media.mkdir()
        os.environ["NEWSFLOW_MEDIA_ROOT"] = str(media)
        # Public synthetic fixture bearer only; never generate or mount a real key.
        secret = root / "synthetic-reviewer"
        with secret.open("x", encoding="ascii") as stream:
            stream.write("synthetic-browser-only-review-token-0001")
        os.environ["NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE"] = str(secret)
        os.environ["NEWSFLOW_ILLUSTRATION_REVIEWER_ID"] = "17"
        os.environ.pop("NEWSFLOW_MASTER_KEY_FILE", None)
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        engine = create_engine(url)
        factory = sessionmaker(engine)
        now = datetime.now(UTC)
        with Session(engine) as session:
            session.add(
                models.TelegramAccount(
                    name="Synthetic browser", telegram_user_id=1001, encrypted_session=""
                )
            )
            session.commit()
            service = TelegramConfigurationService(session)
            donor = service.create_donor(1, -1001234567890, "Изолированный источник проверки")
            output = service.create_output(1, -1001234567891, "Изолированный канал проверки")
            mapping = service.create_mapping(donor["id"], output["id"], 100, 50)
            session.get(models.ChannelMappingModel, mapping["id"]).media_policy = "LICENSED_LIBRARY"
            session.commit()
            result = DurableIngestionWorkflow(session, configured_mapping_id=mapping["id"]).ingest(
                TelegramMessage(
                    "1",
                    "-1001234567890",
                    20,
                    "Завод открыл 3 линии.",
                    media_type="photo",
                    media_id="123",
                    media_protected=False,
                    source_updated_at=now,
                ),
                observed_at=now,
                sentiment="neutral",
                framing="neutral",
            )
            assert result.status == "REWRITE_QUEUED"
            session.get(models.RewriteJobModel, 1).state = "SUCCEEDED"
            session.commit()
            drafts = RewriteOutputService(session)
            drafts.record_succeeded_output(1, "Открыты 3 линии на заводе.")
            drafts.approve(1, activate_candidate=True)
            plan = PublicationPlanningService(session).configure_plan(
                output["id"], "AUTOMATIC", 1, (540,), "UTC"
            )
            assert (
                len(PublicationPlanningService(session).plan_day(plan["id"], date(2030, 1, 3))) == 1
            )
        buffer = BytesIO()
        Image.new("RGB", (64, 32), "navy").save(buffer, format="PNG")
        photo = buffer.getvalue()

        class Images:
            def __init__(self):
                self.calls = []

            def search(self, text, *, limit=5):
                self.calls.append("search")
                return [
                    ImageSearchResult(
                        1,
                        "Synthetic",
                        "https://upload.wikimedia.org/wikipedia/commons/test.png",
                        "https://commons.wikimedia.org/wiki/File:test.png",
                        "CC-BY",
                        "Synthetic illustration credit",
                        "image/png",
                        len(photo),
                        64,
                        32,
                        ("factory",),
                    )
                ]

            def download(self, result):
                self.calls.append("download")
                return photo

        images = Images()
        runner = DurableMediaRunner(factory, media, provider=images)
        runner.enqueue_candidate(1, now=now)
        assert runner.run_next(now=now) == "SUCCEEDED"

        @app.get("/api/ui-test/illustration-evidence")
        def evidence():
            with factory() as session:
                return {
                    "publication_jobs": session.scalar(
                        select(func.count()).select_from(models.PublicationJobModel)
                    ),
                    "review_records": session.scalar(
                        select(func.count()).select_from(models.IllustrationReviewRecordModel)
                    ),
                    "provider_calls": images.calls,
                }

        @app.post("/api/ui-test/reject-illustration-source")
        def reject_source():
            with factory.begin() as session:
                row = session.scalar(select(models.EditorialDecisionModel))
                row.status, row.rewrite_allowed = "REJECT", False
            return {"rejected": True}

        try:
            uvicorn.run(app, host="127.0.0.1", port=5183, log_level="warning")
        finally:
            reset_database_session_factory()
            engine.dispose()


if __name__ == "__main__":
    main()
