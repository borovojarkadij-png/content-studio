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
from test_semantic_approval import SyntheticVerifier
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    MediaAcquisitionJobModel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
)
from newsflow.services.durable_media_runner import DurableMediaRunner
from newsflow.services.publication_planning import PublicationPlanningService
from newsflow.services.rewrite_outputs import RewriteOutputService
from newsflow.services.semantic_verification import SemanticVerificationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)


class NoMatchImages:
    def __init__(self):
        self.calls = 0

    def search(self, query, *, limit):
        self.calls += 1
        return []


class LegacyPlanner(PublicationPlanningService):
    """Frozen offending order, only to prove the interleaving detects 40P01."""

    def _lock_planning_batch(self, plan, day, zone):
        # The historical control intentionally predates transaction-wide locks.
        return {}

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


def automatic_pair(factory):
    """Two independent source-bound synthetic approvals share only channel policy."""
    key = "synthetic:@semantic:2:revision:1"
    with factory.begin() as session:
        post = IncomingPostModel(
            telegram_account_id="synthetic",
            donor_channel_id="@semantic",
            telegram_message_id=2,
            state="RECEIVED",
        )
        session.add(post)
        session.flush()
        session.add(
            ContentRevisionModel(
                incoming_post_id=post.id, revision_number=1, source_text="Фабрика открыла 4 линии."
            )
        )
        session.add(
            EditorialDecisionModel(
                content_key=key,
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
        )
        job = RewriteJobModel(
            content_key=key,
            output_channel_id=1,
            idempotency_key="synthetic-pair-2",
            state="SUCCEEDED",
        )
        session.add(job)
        session.flush()
        output = RewriteOutputModel(
            rewrite_job_id=job.id,
            output_channel_id=1,
            content_key=key,
            rewritten_text="Открыты 4 линии на фабрике.",
            approval_state="PENDING",
        )
        candidate = PublicationCandidateModel(
            output_channel_id=1,
            content_key=key,
            priority=5,
            state="AWAITING_REWRITE",
            media_policy="LICENSED_LIBRARY",
        )
        session.add_all([output, candidate])
        session.flush()
        second_output, second_candidate, second_job = output.id, candidate.id, job.id
        session.get(PublicationCandidateModel, 1).media_policy = "LICENSED_LIBRARY"
    for output_id in (1, second_output):
        result = SemanticVerificationService(
            factory, verifier_for_release=lambda _: SyntheticVerifier()
        ).verify(output_id)
        assert result["verdict"] == "PRESERVED"
        with factory() as session:
            RewriteOutputService(session).auto_approve(output_id, activate_candidate=True)
            assert session.get(RewriteOutputModel, output_id).approval_method == "AUTOMATIC"
    return second_candidate, second_job


@pytest.mark.parametrize("loop", ["reconciliation", "ready", "mixed"])
def test_automatic_pair_shared_policy_has_no_transaction_wide_cycle(
    semantic_store, tmp_path, monkeypatch, loop
):
    raw = getenv("NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL")
    if raw is None:
        pytest.skip("Explicit isolated PostgreSQL concurrency opt-in not supplied")
    url = create_postgres_namespace(raw)
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def bounded_connections(dbapi_connection, _record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '15s'")
            cursor.execute("SET statement_timeout = '20s'")
        dbapi_connection.commit()

    factory = sessionmaker(engine)
    candidate_b, job_b = automatic_pair(semantic_store)
    with semantic_store.kw["bind"].connect() as source, engine.begin() as destination:
        for table in Base.metadata.sorted_tables:
            rows = source.execute(select(table)).mappings().all()
            if rows:
                destination.execute(table.insert(), [dict(row) for row in rows])
    with factory() as session:
        service = PublicationPlanningService(session)
        plan = service.configure_plan(1, "AUTOMATIC", 2, (540, 600))
        if loop == "reconciliation":
            assert len(service.plan_day(plan["id"], NOW.date())) == 2
        elif loop == "mixed":
            session.add(
                PlannedPublicationModel(
                    candidate_id=1,
                    output_channel_id=1,
                    scheduled_for=NOW.replace(hour=9),
                    state="PLANNED",
                )
            )
            session.get(PublicationCandidateModel, 1).state = "SCHEDULED"
            session.commit()
    images = NoMatchImages()
    runner = DurableMediaRunner(factory, tmp_path, provider=images, clock=lambda: NOW)
    media_id = runner.enqueue_candidate(candidate_b, now=NOW)
    claim = runner.claim_next(now=NOW)
    media_upstream, planner_boundary = Event(), Event()
    pids = {}
    armed = True

    def before(connection, cursor, statement, parameters, context, executemany):
        nonlocal armed
        if not armed or "FOR UPDATE" not in statement:
            return
        role = current_thread().name
        if role == "media-pair" and "FROM automatic_approval_policies" in statement:
            # The actual connection already owns B's job/editorial/draft rows.
            pids[role] = connection.connection.driver_connection.info.backend_pid
            media_upstream.set()
            assert planner_boundary.wait(15), "Planner did not reach batch boundary"
            armed = False
        elif role == "planner-pair" and "FROM rewrite_jobs" in statement:
            values = parameters.values() if isinstance(parameters, dict) else parameters
            if job_b in values:
                # Correct batch strategy reaches B before acquiring shared P.
                planner_boundary.set()

    def after(connection, cursor, statement, parameters, context, executemany):
        if not armed or "FOR UPDATE" not in statement or current_thread().name != "planner-pair":
            return
        pids["planner-pair"] = connection.connection.driver_connection.info.backend_pid
        if "FROM automatic_approval_policies" in statement:
            # f8 locks shared P for A, then later asks for B while still owning P.
            planner_boundary.set()

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)

    def media():
        current_thread().name = "media-pair"
        return runner.execute(claim)

    def planner():
        current_thread().name = "planner-pair"
        assert media_upstream.wait(15), "Media did not acquire B's upstream rows"
        with factory() as session:
            return PublicationPlanningService(session).plan_day(plan["id"], NOW.date())

    outcomes, errors = [], []
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(media), executor.submit(planner)]
            for future in futures:
                try:
                    outcomes.append(future.result(timeout=30))
                except DBAPIError as error:
                    errors.append(error.orig.sqlstate)
        assert set(pids) == {"media-pair", "planner-pair"}
        assert len(set(pids.values())) == 2
        assert media_upstream.is_set() and planner_boundary.is_set()
        assert errors == [], errors
        assert "NO_MATCH" in outcomes
        planned = next(value for value in outcomes if isinstance(value, list))
        assert len(planned) == 2
        assert {value["candidate_id"] for value in planned} == {1, candidate_b}
        with factory() as session:
            job = session.get(MediaAcquisitionJobModel, media_id)
            assert (job.state, job.attempts, job.claim_token) == ("NO_MATCH", 1, None)
            assert session.get(PublicationCandidateModel, candidate_b).state == "SCHEDULED"
            assert list(session.scalars(select(PlannedPublicationModel.state))) == [
                "PLANNED",
                "PLANNED",
            ]
        assert images.calls == 1
    finally:
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)
        engine.dispose()
