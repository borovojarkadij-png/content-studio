"""Create-only synthetic policy browser fixture; no operational secrets or providers."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import Depends
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main():
    # Clear every credential environment consulted by the operator/reviewer/master loaders
    # before importing the application. Never inspect inherited paths or their contents.
    for name in (
        "NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE",
        "NEWSFLOW_EDITORIAL_OPERATOR_ID",
        "NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE",
        "NEWSFLOW_ILLUSTRATION_REVIEWER_ID",
        "NEWSFLOW_MASTER_KEY_FILE",
    ):
        os.environ.pop(name, None)
    with TemporaryDirectory(prefix="content-studio-editorial-browser-") as directory:
        root = Path(directory)
        database = root / "fixture.db"
        database.touch(exist_ok=False)
        url = f"sqlite:///{database.as_posix()}"
        os.environ["DATABASE_URL"] = url
        media = root / "media"
        media.mkdir()
        os.environ["NEWSFLOW_MEDIA_ROOT"] = str(media)
        secret = root / "synthetic-operator"
        with secret.open("x", encoding="ascii") as stream:
            stream.write("synthetic-browser-only-operator-token-0001")
        os.environ["NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE"] = str(secret)
        os.environ["NEWSFLOW_EDITORIAL_OPERATOR_ID"] = "29"

        from newsflow.api.editorial_policy import operator
        from newsflow.api.settings import get_rewrite_provider_settings_service
        from newsflow.app import app
        from newsflow.persistence import models
        from newsflow.persistence.database import (
            configured_session_factory,
            reset_database_session_factory,
        )
        from newsflow.services.editorial_policy_configuration import (
            EditorialPolicyConfigurationService,
        )

        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        reset_database_session_factory()
        factory = configured_session_factory()
        assert factory is not None and str(factory.kw["bind"].url) == url
        with factory.begin() as session:
            session.add(
                models.EditorialDecisionModel(
                    content_key="synthetic-editorial-browser-rejected",
                    status="REJECT",
                    rewrite_allowed=False,
                    reason_codes="PROTECTED_ENTITY_NEGATIVE",
                    protected_entities="synthetic-entity",
                    sentiment="negative",
                    framing="hostile",
                )
            )

        class EmptyProviderSettings:
            def list_settings(self):
                return []

        # The unrelated Settings auto-read needs no key store or model catalog.
        app.dependency_overrides[get_rewrite_provider_settings_service] = EmptyProviderSettings

        @app.get("/api/ui-test/editorial-evidence", dependencies=[Depends(operator)])
        def evidence():
            with factory() as session:
                policy = EditorialPolicyConfigurationService(session).read()
                events = session.scalars(
                    select(models.OutboxEventModel).order_by(models.OutboxEventModel.id)
                ).all()
                counts = {
                    name: session.scalar(select(func.count()).select_from(model))
                    for name, model in (
                        ("rewrite_jobs", models.RewriteJobModel),
                        ("diagnostic_jobs", models.EditorialClassificationJobModel),
                        ("diagnostic_attempts", models.EditorialClassificationAttemptModel),
                        ("publication_jobs", models.PublicationJobModel),
                        ("rewrite_calls", models.RewriteUsageModel),
                        ("semantic_jobs", models.SemanticVerificationJobModel),
                    )
                }
                return {
                    "policy": policy,
                    "outbox_count": len(events),
                    "rejected_decisions": [
                        {"status": row.status, "rewrite_allowed": row.rewrite_allowed}
                        for row in session.scalars(select(models.EditorialDecisionModel))
                    ],
                    "events": [
                        {
                            "event_type": event.event_type,
                            "actor_id": int(event.aggregate_key.split(":")[1]),
                            "before_etag": event.aggregate_key.split(":")[2],
                            "after_etag": event.aggregate_key.split(":")[3],
                            "idempotency_key": event.idempotency_key,
                        }
                        for event in events
                    ],
                    **counts,
                }
        try:
            uvicorn.run(app, host="127.0.0.1", port=5193, log_level="warning")
        finally:
            app.dependency_overrides.clear()
            factory.kw["bind"].dispose()
            reset_database_session_factory()


if __name__ == "__main__":
    main()
