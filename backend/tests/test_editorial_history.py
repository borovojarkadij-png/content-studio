"""Read-only retained diagnostic history from migrated, canonical runner fixtures."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value
from test_durable_editorial_runner import Classifier, make_runner
from test_editorial_admission import KEY, MESSAGE, NOW, count, ingest
from test_editorial_admission import store as admission_store

from newsflow.app import app
from newsflow.persistence import models
from newsflow.providers.openai_rewrite import OpenAIRewriteProvider, RewriteUsage
from newsflow.providers.openrouter import ProviderUnavailable
from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider
from newsflow.services.editorial_admission import enqueue_editorial_classification
from newsflow.services.editorial_history import EditorialHistoryReader

PATH = "/api/studio/editorial-classification-history"
store = admission_store


@pytest.fixture(autouse=True)
def no_rewrite(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("history invoked rewrite")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(StructuredFreeOpenRouterProvider, "rewrite", forbidden)
    from newsflow.security.session_cipher import SessionCipher

    monkeypatch.setattr(SessionCipher, "decrypt", forbidden)


def read(store, **kwargs):
    with Session(store[0]) as session:
        result = EditorialHistoryReader(session).read(KEY, store[1], **kwargs)
        assert not session.new and not session.dirty and not session.deleted
        return result


def headers(response):
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("reject", [False, True], ids=["review", "reject"])
def test_http_projects_real_receipt_without_writes_or_rewrite(store, reject, monkeypatch):
    ingest(store, replace(MESSAGE, text="Civic Council opened a civic center"))
    client = Classifier()
    original = client.classify

    def classify(request):
        original(request)
        value = json.loads(client.last_evidence_json)
        value["entity_findings"] = [
            {"entity_id": "synthetic-council", "source_quote": "Civic Council"}
        ]
        if reject:
            value.update(sentiment="negative", framing="hostile")
        client.last_evidence_json = json.dumps(value)

    client.classify = classify
    outcome = "REJECT" if reject else "REVIEW"
    assert make_runner(store[0], client).run_next(now=NOW) == outcome
    from newsflow import worker
    from newsflow.api import studio
    from newsflow.services.editorial_classifier_factory import ConfiguredEditorialClassifierFactory

    def forbidden(*args, **kwargs):
        pytest.fail("history invoked provider, worker, or commit")

    monkeypatch.setattr(ConfiguredEditorialClassifierFactory, "__call__", forbidden)
    monkeypatch.setattr(worker, "run_editorial_classification_tick", forbidden)
    monkeypatch.setattr(Classifier, "classify", forbidden)

    def sessions():
        with Session(store[0]) as session:
            yield session

    monkeypatch.setattr(studio, "database_session", sessions)
    with Session(store[0]) as session:
        before = count(session, models.OutboxEventModel)
    statements = []

    def record(connection, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(store[0], "before_cursor_execute", record)
    event.listen(Session, "before_commit", forbidden)
    try:
        response = TestClient(app).get(PATH, params={"content_key": KEY, "mapping_id": store[1]})
        assert response.status_code == 200
        headers(response)
        payload = response.json()
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert item["state"] == outcome
        assert item["receipts"][0]["outcome"] == outcome
        assert item["receipts"][0]["diagnostic_status"] == ("REJECT" if reject else "PASS")
        assert payload == {
            "content_key": KEY,
            "mapping_id": store[1],
            "diagnostic_only": True,
            "execution_authorized": False,
            "rewrite_allowed": False,
            "network_checked": False,
            "worker_enabled": None,
            "real_model_qualified": False,
            "items": [
                {
                    "job_id": 1,
                    "state": outcome,
                    "attempts": 1,
                    "max_attempts": 2,
                    "provider": "OPENAI",
                    "model": "synthetic-explicit-model",
                    "created_at": "2030-01-01T00:00:00+00:00",
                    "available_at": "2030-01-01T00:00:00+00:00",
                    "lease_expires_at": None,
                    "reason_code": "PROTECTED_ENTITY_NEGATIVE"
                    if reject
                    else "REAL_MODEL_NOT_QUALIFIED",
                    "receipts": [
                        {
                            "attempt": 1,
                            "outcome": outcome,
                            "diagnostic_status": "REJECT" if reject else "PASS",
                            "reason_codes": [
                                "PROTECTED_ENTITY_NEGATIVE"
                                if reject
                                else "REAL_MODEL_NOT_QUALIFIED"
                            ],
                            "usage_observed": False,
                            "input_tokens": None,
                            "cached_tokens": None,
                            "output_tokens": None,
                            "estimated_cost_usd": None,
                            "created_at": "2030-01-01T00:00:00+00:00",
                        }
                    ],
                }
            ],
            "next_before_job_id": None,
        }
    finally:
        event.remove(store[0], "before_cursor_execute", record)
        event.remove(Session, "before_commit", forbidden)
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert statements
    with Session(store[0]) as session:
        assert count(session, models.RewriteJobModel) == 0
        assert session.scalar(select(models.EditorialDecisionModel)).rewrite_allowed is False
        assert count(session, models.OutboxEventModel) == before
    assert client.calls == 1


@pytest.mark.parametrize("cost", [Decimal("0.0001234567"), Decimal(0)], ids=["precise", "zero"])
def test_two_runner_attempts_preserve_observed_decimal_and_unknown_usage(store, cost):
    ingest(store)
    client = Classifier()
    original = client.classify
    now = [NOW]

    def classify(request):
        original(request)
        if client.calls == 1:
            client.last_usage = RewriteUsage(client.model, 100, 10, 20, cost)
            raise ProviderUnavailable("PRIVATE_PROVIDER_MARKER")
        client.last_usage = None

    client.classify = classify
    runner = make_runner(store[0], client, clock=lambda: now[0])
    assert runner.run_next(now=now[0]) == "RETRY"
    retry = read(store)
    assert retry["items"][0]["state"] == "QUEUED"
    assert retry["items"][0]["receipts"][0]["outcome"] == "RETRY"
    now[0] += timedelta(seconds=60)
    assert runner.run_next(now=now[0]) == "REVIEW"
    payload = read(store)
    first, second = payload["items"][0]["receipts"]
    assert first["usage_observed"] is True
    assert (first["input_tokens"], first["cached_tokens"], first["output_tokens"]) == (100, 10, 20)
    assert first["estimated_cost_usd"] == ("0.0001234567" if cost else "0.0000000000")
    assert second["usage_observed"] is False
    assert second["estimated_cost_usd"] is None
    assert payload["rewrite_allowed"] is payload["execution_authorized"] is False
    assert "PRIVATE_PROVIDER_MARKER" not in json.dumps(payload)
    assert "evidence_json" not in json.dumps(payload)
    assert "response_model" not in json.dumps(payload)


def test_empty_history_and_bounded_cursor_pages(store):
    with Session(store[0]) as session:
        session.get(models.EditorialClassifierPolicyModel, 1).enabled = False
        session.commit()
    ingest(store)
    assert read(store)["items"] == []
    with Session(store[0]) as session:
        policy = session.get(models.EditorialClassifierPolicyModel, 1)
        policy.enabled = True
        for index in range(4):
            policy.policy_version = f"version-{index}"
            session.flush()
            enqueue_editorial_classification(session, content_key=KEY, mapping_id=store[1], now=NOW)
        session.commit()
    statements = []

    def observe(connection, cursor, statement, params, context, many):
        if "FROM editorial_classification_jobs" in statement:
            statements.append((statement, params))

    event.listen(store[0], "before_cursor_execute", observe)
    try:
        first = read(store, limit=2)
        assert [item["job_id"] for item in first["items"]] == [4, 3]
        assert first["next_before_job_id"] == 3
        last = read(store, limit=2, before_job_id=3)
        assert [item["job_id"] for item in last["items"]] == [2, 1]
        assert last["next_before_job_id"] is None
        assert read(store, before_job_id=1)["items"] == []
    finally:
        event.remove(store[0], "before_cursor_execute", observe)
    assert len(statements) == 3
    assert all(
        "LIMIT" in sql and "source_revision_id =" in sql and "mapping_id =" in sql
        for sql, _ in statements
    )
    if store[0].dialect.name == "sqlite":
        assert statements[0][1][-2:] == (3, 0)
    else:
        assert 3 in statements[0][1].values()


@pytest.mark.parametrize(
    "field,value",
    [
        ("content_key", True),
        ("content_key", ""),
        ("content_key", " "),
        ("content_key", "a" * 256),
        ("content_key", "\ud800"),
        ("mapping_id", True),
        ("mapping_id", 0),
        ("mapping_id", "1"),
        ("limit", True),
        ("limit", 0),
        ("limit", 26),
        ("limit", 1.0),
        ("before_job_id", True),
        ("before_job_id", 0),
        ("before_job_id", "1"),
    ],
    ids=[
        "key-bool",
        "key-empty",
        "key-space",
        "key-long",
        "key-unicode",
        "map-bool",
        "map-zero",
        "map-str",
        "limit-bool",
        "limit-zero",
        "limit-large",
        "limit-float",
        "cursor-bool",
        "cursor-zero",
        "cursor-str",
    ],
)
def test_invalid_inputs_fail_before_sql(store, field, value):
    args = {"content_key": KEY, "mapping_id": store[1], field: value}
    with Session(store[0]) as session:

        def forbidden(*args):
            pytest.fail("invalid input performed SQL")

        event.listen(session, "do_orm_execute", forbidden)
        with pytest.raises(ValueError, match="^EDITORIAL_HISTORY_INPUT_INVALID$"):
            EditorialHistoryReader(session).read(**args)


@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_pending_session_state_fails_before_sql(store, pending):
    with Session(store[0]) as session:
        account = session.get(models.TelegramAccount, 1)
        if pending == "new":
            session.add(
                models.TelegramAccount(name="pending", telegram_user_id=5555, encrypted_session="")
            )
        elif pending == "dirty":
            account.name = "pending"
        else:
            session.delete(account)

        def forbidden(*args):
            pytest.fail("pending state performed SQL")

        event.listen(session, "do_orm_execute", forbidden)
        with pytest.raises(ValueError, match="^EDITORIAL_HISTORY_INVALID$"):
            EditorialHistoryReader(session).read(KEY, store[1])


def test_retained_rejected_old_deleted_disabled_records_stay_readable_cross_account(store):
    ingest(store)
    assert make_runner(store[0], Classifier()).run_next(now=NOW) == "REVIEW"
    with Session(store[0]) as session:
        session.add(
            models.TelegramAccount(name="Other", telegram_user_id=2002, encrypted_session="")
        )
        session.flush()
        session.get(models.OutputChannel, 1).telegram_account_id = 2
        session.get(models.ChannelMappingModel, store[1]).intake_percent = 0
        session.get(models.TelegramAccount, 1).health_status = "DISCONNECTED"
        session.get(models.TelegramAccount, 2).health_status = "DISCONNECTED"
        session.get(models.EditorialClassifierPolicyModel, 1).enabled = False
        session.scalar(select(models.EditorialDecisionModel)).status = "REJECT"
        session.add(
            models.ContentRevisionModel(incoming_post_id=1, revision_number=2, source_text="new")
        )
        session.add(
            models.SourceDeletionModel(
                telegram_account_id="1",
                donor_channel_id=str(-1001234567890),
                telegram_message_id=7,
                latest_pts=1,
                observed_at=NOW,
            )
        )
        session.commit()
    result = read(store)
    assert len(result["items"]) == 1
    assert result["rewrite_allowed"] is False


@pytest.mark.parametrize("foreign", ["account", "channel", "output", "mapping", "source"])
def test_missing_or_foreign_ownership_returns_fixed_lookup_error(store, foreign):
    ingest(store)
    with Session(store[0]) as session:
        if foreign == "account":
            session.scalar(select(models.IncomingPostModel)).telegram_account_id = "01"
        elif foreign == "channel":
            session.get(models.DonorChannel, 1).telegram_channel_id -= 10
        session.commit()

    def missing_owner(target, context):
        set_committed_value(target, "telegram_account_id", 99999)

    if foreign == "output":
        event.listen(models.OutputChannel, "load", missing_owner)
    try:
        with (
            Session(store[0]) as session,
            pytest.raises(LookupError, match="^EDITORIAL_HISTORY_NOT_FOUND$"),
        ):
            EditorialHistoryReader(session).read(
                KEY if foreign != "source" else "foreign",
                99999 if foreign == "mapping" else store[1],
            )
    finally:
        if foreign == "output":
            event.remove(models.OutputChannel, "load", missing_owner)


def test_fresh_committed_ownership_is_checked_despite_stale_identity_map(store):
    ingest(store)
    with Session(store[0], expire_on_commit=False) as stale:
        donor = stale.get(models.DonorChannel, 1)
        assert read(store)["items"]
        stale.commit()
        with Session(store[0]) as writer:
            writer.get(models.DonorChannel, 1).telegram_channel_id -= 1
            writer.commit()
        assert donor.telegram_channel_id == -1001234567890
        with pytest.raises(LookupError):
            EditorialHistoryReader(stale).read(KEY, store[1])


@pytest.mark.parametrize(
    "model,attribute,value",
    [
        (models.EditorialClassificationJobModel, "state", "PRIVATE_MARKER"),
        (models.EditorialClassificationJobModel, "attempts", True),
        (models.EditorialClassificationJobModel, "editorial_decision_id", True),
        (models.EditorialClassificationJobModel, "state", "QUEUED"),
        (models.EditorialClassificationJobModel, "provider", "PRIVATE_MARKER"),
        (models.EditorialClassificationJobModel, "model", "bad model"),
        (models.EditorialClassificationJobModel, "last_error_code", "PRIVATE_MARKER"),
        (models.EditorialClassificationJobModel, "lease_expires_at", NOW),
        (models.EditorialClassificationClaimModel, "attempt", 2),
        (models.EditorialClassificationClaimModel, "claim_token", "bad"),
        (models.EditorialClassificationAttemptModel, "outcome", "PRIVATE_MARKER"),
        (models.EditorialClassificationAttemptModel, "diagnostic_status", "PRIVATE_MARKER"),
        (models.EditorialClassificationAttemptModel, "reason_codes", ["PRIVATE_MARKER"]),
        (models.EditorialClassificationAttemptModel, "reason_codes", []),
        (models.EditorialClassificationAttemptModel, "input_tokens", 1),
        (models.EditorialClassificationAttemptModel, "usage_observed", 1),
        (models.EditorialClassificationAttemptModel, "estimated_cost_usd", Decimal("NaN")),
        (models.EditorialClassificationAttemptModel, "created_at", "PRIVATE_MARKER"),
    ],
    ids=[
        "state",
        "attempt-count",
        "decision-bool",
        "state-receipt",
        "provider",
        "model",
        "job-reason",
        "lease",
        "claim-attempt",
        "claim-token",
        "outcome",
        "diagnostic",
        "receipt-reason",
        "empty-reasons",
        "unknown-count",
        "observed-type",
        "cost",
        "time",
    ],
)
def test_malformed_decoded_history_fails_closed_without_echo(store, model, attribute, value):
    ingest(store)
    assert make_runner(store[0], Classifier()).run_next(now=NOW) == "REVIEW"

    def corrupt(target, context):
        set_committed_value(target, attribute, value)

    # Migrated immutable rows are the source; corrupt only their decoded read boundary.
    event.listen(model, "load", corrupt)
    try:
        with pytest.raises(ValueError, match="^EDITORIAL_HISTORY_INVALID$"):
            read(store)
    finally:
        event.remove(model, "load", corrupt)


@pytest.mark.parametrize("outcome", ["FAILED", "BLOCKED"])
@pytest.mark.parametrize("position", ["queued", "earlier-attempt"])
def test_terminal_receipt_rejects_wrong_job_state_or_later_attempt(store, outcome, position):
    ingest(store)
    client = Classifier()
    now = [NOW]
    original = client.classify

    def classify(request):
        original(request)
        if client.calls == 1:
            raise ProviderUnavailable("PRIVATE_PROVIDER_MARKER")

    client.classify = classify
    runner = make_runner(store[0], client, clock=lambda: now[0])
    assert runner.run_next(now=NOW) == "RETRY"
    if position == "earlier-attempt":
        now[0] += timedelta(seconds=60)
        assert runner.run_next(now=now[0]) == "REVIEW"

    def corrupt(target, context):
        if target.outcome == "RETRY":
            set_committed_value(target, "outcome", outcome)

    # Only the decoded immutable receipt changes: null diagnostic is already valid.
    event.listen(models.EditorialClassificationAttemptModel, "load", corrupt)
    try:
        with pytest.raises(ValueError, match="^EDITORIAL_HISTORY_INVALID$"):
            read(store)
    finally:
        event.remove(models.EditorialClassificationAttemptModel, "load", corrupt)


@pytest.mark.parametrize(
    "case,state,attempts,outcomes",
    [
        ("failed", "FAILED", 1, ["FAILED"]),
        ("blocked", "BLOCKED", 1, ["BLOCKED"]),
        ("preclaim-blocked", "BLOCKED", 0, []),
        ("preclaim-blocked-after-claim", "BLOCKED", 1, []),
        ("exhausted", "FAILED", 2, []),
        ("late-after-terminal", "REVIEW", 2, ["LOST_LEASE", "REVIEW"]),
    ],
    ids=["failed", "blocked", "preclaim", "preclaim-after-claim", "exhausted", "late"],
)
def test_terminal_receipt_controls_preserve_real_runner_history(
    store, case, state, attempts, outcomes
):
    ingest(store)
    client = Classifier()
    now = [NOW]
    runner = make_runner(store[0], client, clock=lambda: now[0])

    def disable_policy():
        with Session(store[0]) as session:
            session.get(models.EditorialClassifierPolicyModel, 1).enabled = False
            session.commit()

    if case == "failed":

        def failed(request):
            raise RuntimeError("PRIVATE_PROVIDER_MARKER")

        client.classify = failed
        assert runner.run_next(now=NOW) == "FAILED"
    elif case == "preclaim-blocked":
        disable_policy()
        assert runner.run_next(now=NOW) == "BLOCKED"
    else:
        first = runner.claim_next(now=NOW)
        assert first.attempt == 1
        if case in {"blocked", "preclaim-blocked-after-claim"}:
            disable_policy()
            if case == "blocked":
                assert runner.execute(first) == "BLOCKED"
            else:
                now[0] += timedelta(seconds=60)
                assert runner.run_next(now=now[0]) == "BLOCKED"
        else:
            now[0] += timedelta(seconds=60)
            second = runner.claim_next(now=now[0])
            assert second.attempt == 2
            if case == "exhausted":
                now[0] += timedelta(seconds=60)
                assert runner.run_next(now=now[0]) == "FAILED"
            else:
                assert runner.execute(second) == "REVIEW"
                assert runner.execute(first) == "LOST_LEASE"

    payload = read(store)
    item = payload["items"][0]
    assert (item["state"], item["attempts"]) == (state, attempts)
    assert [receipt["outcome"] for receipt in item["receipts"]] == outcomes
    assert payload["execution_authorized"] is payload["rewrite_allowed"] is False


@pytest.mark.parametrize("mode", ["missing-db", "unmigrated", "foreign", "invalid", "sql"])
def test_http_errors_are_static_private_and_never_fake_success(store, monkeypatch, tmp_path, mode):
    from sqlalchemy.exc import OperationalError

    from newsflow.api import studio

    ingest(store)
    params = {"content_key": KEY, "mapping_id": store[1]}
    if mode == "missing-db":
        monkeypatch.delenv("DATABASE_URL")
    elif mode == "unmigrated":
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty.db'}")
    elif mode == "foreign":
        params["mapping_id"] = 9999
    elif mode == "invalid":
        params["limit"] = "true"
    elif mode == "sql":

        def unavailable(*args, **kwargs):
            raise OperationalError("PRIVATE_SQL_MARKER", {}, Exception("PRIVATE_SOURCE"))

        monkeypatch.setattr(studio.EditorialHistoryReader, "read", unavailable)
    response = TestClient(app).get(PATH, params=params)
    assert response.status_code == {"foreign": 404, "invalid": 422}.get(mode, 503)
    headers(response)
    assert KEY not in response.text and "PRIVATE" not in response.text


@pytest.mark.parametrize("outcome", ["FAILED", "LOST_LEASE"], ids=["failed", "late"])
def test_failed_and_late_runner_receipts_remain_diagnostic_only(store, outcome):
    ingest(store)
    now = [NOW]
    client = Classifier()
    original = client.classify

    def classify(request):
        original(request)
        if outcome == "FAILED":
            raise RuntimeError("PRIVATE_MARKER")
        now[0] += timedelta(seconds=60)

    client.classify = classify
    runner = make_runner(store[0], client, clock=lambda: now[0])
    assert runner.run_next(now=NOW) == outcome
    result = read(store)
    assert result["items"][0]["receipts"][0]["outcome"] == outcome
    assert result["items"][0]["state"] == ("RUNNING" if outcome == "LOST_LEASE" else "FAILED")
    assert result["execution_authorized"] is result["rewrite_allowed"] is False


def test_ambiguous_delimiter_identity_does_not_resolve_or_leak_history(store):
    with Session(store[0]) as session:
        posts = [
            models.IncomingPostModel(
                telegram_account_id="1",
                donor_channel_id="foo:bar",
                telegram_message_id=7,
                state="RECEIVED",
            ),
            models.IncomingPostModel(
                telegram_account_id="1:foo",
                donor_channel_id="bar",
                telegram_message_id=7,
                state="RECEIVED",
            ),
        ]
        session.add_all(posts)
        session.flush()
        for post in posts:
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post.id, revision_number=1, source_text="PRIVATE_SOURCE"
                )
            )
        session.commit()
    with (
        Session(store[0]) as session,
        pytest.raises(LookupError, match="^EDITORIAL_HISTORY_NOT_FOUND$"),
    ):
        EditorialHistoryReader(session).read("1:foo:bar:7:revision:1", store[1])


def test_each_job_resolves_exact_decision_binding(store):
    ingest(store)
    with Session(store[0]) as session:
        session.scalar(select(models.EditorialDecisionModel)).content_key = "PRIVATE_OTHER_BINDING"
        session.commit()
    response = TestClient(app).get(PATH, params={"content_key": KEY, "mapping_id": store[1]})
    assert response.status_code == 503
    headers(response)
    assert "PRIVATE_OTHER_BINDING" not in response.text


@pytest.mark.parametrize("field", ["state", "provider", "last_error_code"])
def test_unhashable_decoded_enums_fail_with_static_error(store, field):
    ingest(store)

    def corrupt(target, context):
        set_committed_value(target, field, [])

    event.listen(models.EditorialClassificationJobModel, "load", corrupt)
    try:
        with pytest.raises(ValueError, match="^EDITORIAL_HISTORY_INVALID$"):
            read(store)
    finally:
        event.remove(models.EditorialClassificationJobModel, "load", corrupt)


def test_large_positive_ids_do_not_overflow_sql_parameters(store):
    ingest(store)
    with (
        Session(store[0]) as session,
        pytest.raises(LookupError, match="^EDITORIAL_HISTORY_NOT_FOUND$"),
    ):
        EditorialHistoryReader(session).read(KEY, 10**30)
    assert len(read(store, before_job_id=10**30)["items"]) == 1


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("input_tokens", True),
        ("input_tokens", -1),
        ("input_tokens", 2147483648),
        ("cached_tokens", 101),
        ("output_tokens", None),
        ("estimated_cost_usd", Decimal(-1)),
        ("estimated_cost_usd", Decimal("Infinity")),
        ("estimated_cost_usd", 0.5),
    ],
    ids=[
        "bool",
        "negative",
        "oversize",
        "cache",
        "missing",
        "negative-cost",
        "infinite-cost",
        "float-cost",
    ],
)
def test_observed_usage_requires_exact_counts_and_finite_decimal(store, attribute, value):
    ingest(store)
    client = Classifier()
    client.last_usage = RewriteUsage(client.model, 100, 10, 20, Decimal("0.1"))
    assert make_runner(store[0], client).run_next(now=NOW) == "REVIEW"

    def corrupt(target, context):
        set_committed_value(target, attribute, value)

    event.listen(models.EditorialClassificationAttemptModel, "load", corrupt)
    try:
        with pytest.raises(ValueError, match="^EDITORIAL_HISTORY_INVALID$"):
            read(store)
    finally:
        event.remove(models.EditorialClassificationAttemptModel, "load", corrupt)


@pytest.mark.parametrize("kind", ["claims", "receipts"])
def test_inconsistent_extra_claims_or_receipts_fail_without_truncation(store, monkeypatch, kind):
    ingest(store)
    assert make_runner(store[0], Classifier()).run_next(now=NOW) == "REVIEW"
    with Session(store[0]) as session:
        original = session.scalars

        class Rows:
            def __init__(self, rows):
                self.rows = rows

            def all(self):
                return self.rows

        def scalars(statement, *args, **kwargs):
            rows = original(statement, *args, **kwargs)
            entity = statement.column_descriptions[0]["entity"]
            if entity is (
                models.EditorialClassificationClaimModel
                if kind == "claims"
                else models.EditorialClassificationAttemptModel
            ):
                assert statement._limit_clause.value == (3 if kind == "claims" else 2)
                values = rows.all()
                return Rows(values * (3 if kind == "claims" else 2))
            return rows

        monkeypatch.setattr(session, "scalars", scalars)
        with pytest.raises(ValueError, match="^EDITORIAL_HISTORY_INVALID$"):
            EditorialHistoryReader(session).read(KEY, store[1])


@pytest.mark.parametrize(
    "extra",
    [
        {"limit": "26"},
        {"mapping_id": "true"},
        {"before_job_id": "0"},
        {"limit": "1.0"},
        {"mapping_id": "-1"},
        {"content_key": " "},
        {"content_key": "я" * 256},
    ],
    ids=["cap", "bool", "cursor", "float", "negative", "blank", "unicode"],
)
def test_http_invalid_queries_have_private_sanitized_422(store, extra):
    response = TestClient(app).get(
        PATH, params={"content_key": KEY, "mapping_id": store[1], **extra}
    )
    assert response.status_code == 422
    headers(response)
    assert response.json() == {"detail": "Invalid diagnostic history request"}
