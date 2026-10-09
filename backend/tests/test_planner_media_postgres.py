"""Controlled two-connection regression; explicit create-only synthetic PG only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from os import getenv
from threading import Event, current_thread

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from test_internet_media import setup
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.persistence.models import (
    Base,
    MediaAcquisitionJobModel,
    PlannedPublicationModel,
    PublicationCandidateModel,
)
from newsflow.services.durable_media_runner import DurableMediaRunner
from newsflow.services.publication_planning import PublicationPlanningService

NOW = datetime(2030, 1, 1, tzinfo=UTC)


class NoMatchImages:
    def __init__(self):
        self.calls = 0

    def search(self, query, *, limit):
        self.calls += 1
        return []


class LegacyPlanner(PublicationPlanningService):
    """Frozen offending order, only to prove the interleaving detects 40P01."""

    def _reconcile_stale_reservations(self, plan, day, zone):
        rows = self._session.execute(
            select(PlannedPublicationModel, PublicationCandidateModel)
            .join(
                PublicationCandidateModel,
                PlannedPublicationModel.candidate_id == PublicationCandidateModel.id,
            )
            .where(
                PlannedPublicationModel.output_channel_id == plan.output_channel_id,
                PlannedPublicationModel.state == "PLANNED",
            )
            .with_for_update()
        )
        for _, candidate in rows:
            self._is_currently_editorial_pass(candidate.content_key)


@pytest.mark.parametrize(
    "legacy", [True, False], ids=["old-order-detects-deadlock", "current-order-completes"]
)
def test_planner_media_two_connection_lock_order(semantic_store, tmp_path, monkeypatch, legacy):
    raw = getenv("NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL")
    if raw is None:
        pytest.skip("Explicit isolated PostgreSQL concurrency opt-in not supplied")
    # Validator permits only the known local synthetic fixture; never relax it.
    url = create_postgres_namespace(raw)
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def bounded_connections(dbapi_connection, _record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '15s'")
            cursor.execute("SET statement_timeout = '20s'")
        dbapi_connection.commit()

    factory = sessionmaker(engine)
    setup(semantic_store)
    with semantic_store() as session:
        plan = PublicationPlanningService(session).configure_plan(1, "AUTOMATIC", 1, (540,))
        PublicationPlanningService(session).plan_day(plan["id"], NOW.date())
    # Copy only test-created SQLite synthetic rows into this fresh UUID schema.
    with semantic_store.kw["bind"].connect() as source, engine.begin() as destination:
        for table in Base.metadata.sorted_tables:
            rows = source.execute(select(table)).mappings().all()
            if rows:
                destination.execute(table.insert(), [dict(row) for row in rows])
    images = NoMatchImages()
    runner = DurableMediaRunner(factory, tmp_path, provider=images, clock=lambda: NOW)
    job_id = runner.enqueue_candidate(1, now=NOW)
    claim = runner.claim_next(now=NOW)
    editorial_held, planner_reached = Event(), Event()
    pids = {}
    armed = True

    def before(connection, cursor, statement, parameters, context, executemany):
        role = current_thread().name
        if (
            armed
            and role == "planner"
            and "FOR UPDATE" in statement
            and "FROM rewrite_jobs" in statement
        ):
            # Correct order: planner tries job before candidate, which media owns.
            planner_reached.set()

    def after(connection, cursor, statement, parameters, context, executemany):
        nonlocal armed
        role = current_thread().name
        if not armed or "FOR UPDATE" not in statement:
            return
        if role in {"media", "planner"}:
            # This is the exact connection that just acquired a row lock.
            pids.setdefault(role, connection.connection.driver_connection.info.backend_pid)
        if role == "media" and "FROM editorial_decisions" in statement:
            editorial_held.set()
            assert planner_reached.wait(15), "Planner failed to reach controlled lock boundary"
            armed = False
        elif role == "planner" and "JOIN publication_candidates" in statement:
            # Legacy order: joined FOR UPDATE has already locked candidate C.
            planner_reached.set()

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)

    def run_media():
        current_thread().name = "media"
        return runner.execute(claim)

    def run_planner():
        current_thread().name = "planner"
        assert editorial_held.wait(15), "Media did not acquire editorial lock"
        with factory() as session:
            service = (LegacyPlanner if legacy else PublicationPlanningService)(session)
            return service.plan_day(plan["id"], NOW.date())

    outcomes, errors = [], []
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_media), executor.submit(run_planner)]
            for future in futures:
                try:
                    outcomes.append(future.result(timeout=30))
                except DBAPIError as error:
                    errors.append(error.orig.sqlstate)
        assert set(pids) == {"media", "planner"} and len(set(pids.values())) == 2
        assert editorial_held.is_set() and planner_reached.is_set()
        if legacy:
            assert errors == ["40P01"], errors
        else:
            assert errors == [], errors
            assert "NO_MATCH" in outcomes
            with factory() as session:
                job = session.get(MediaAcquisitionJobModel, job_id)
                assert (job.state, job.attempts, job.claim_token) == ("NO_MATCH", 1, None)
                assert session.get(PublicationCandidateModel, 1).state == "SCHEDULED"
                assert session.scalar(select(PlannedPublicationModel.state)) == "PLANNED"
            assert images.calls == 1
    finally:
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)
        engine.dispose()  # Namespace/history intentionally retained; no DROP/reset.
