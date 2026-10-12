"""Migrated diagnostic execution: every synthetic result retains manual permission."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from importlib import import_module
from uuid import uuid4

import pytest
import test_editorial_admission as admission_tests
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from test_editorial_admission import CHANNEL, KEY, MESSAGE, NOW, count, ingest

from newsflow.persistence import models
from newsflow.providers.openai_rewrite import (
    OpenAIRewriteProvider,
    ProviderConfigurationInvalid,
    ProviderResponseInvalid,
    RewriteUsage,
)
from newsflow.providers.openrouter import ProviderUnavailable
from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider

store = admission_tests.store


@pytest.fixture(autouse=True)
def forbid_rewrite(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("diagnostic execution invoked rewrite")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", fail)
    monkeypatch.setattr(StructuredFreeOpenRouterProvider, "rewrite", fail)


class Classifier:
    provider = "OPENAI"
    model = "synthetic-explicit-model"
    prompt_version = "editorial-classification-v1"
    last_usage = None
    last_response_model = model
    last_evidence_json = None

    def __init__(self):
        self.calls = 0

    def classify(self, request):
        self.calls += 1
        self.last_evidence_json = json.dumps(
            {
                "content_key": request.content_key,
                "source_sha256": request.source_sha256,
                "policy_sha256": request.policy_sha256,
                "prompt_version": "editorial-classification-v1",
                "source_complete": True,
                "ambiguous": False,
                "sentiment": "neutral",
                "framing": "neutral",
                "entity_findings": [],
            }
        )
        return object()  # The return is never authorization or durable evidence.


def test_ingress_claim_and_neutral_receipt_reopen_as_review_without_rewrite(store):
    assert ingest(store).status == "MANUAL_REVIEW"
    engine, _ = store
    client = Classifier()
    runner = make_runner(engine, client)
    claim = runner.claim_next(now=NOW)
    with Session(engine) as session:
        job = session.get(models.EditorialClassificationJobModel, claim.job_id)
        assert (job.state, job.attempts) == ("RUNNING", 1)
        assert job.claim_token == claim.token
        assert job.lease_expires_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(seconds=60)
        history = session.scalar(select(models.EditorialClassificationClaimModel))
        assert (history.classification_job_id, history.claim_token, history.attempt) == (
            claim.job_id,
            claim.token,
            1,
        )
    assert runner.execute(claim) == "REVIEW"
    with Session(engine) as session:
        job = session.scalar(select(models.EditorialClassificationJobModel))
        assert (job.state, job.attempts) == ("REVIEW", 1)
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert (decision.status, decision.rewrite_allowed) == ("MANUAL_REVIEW", False)
        assert count(session, models.RewriteJobModel) == 0
        assert job.content_key == KEY
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        assert (receipt.outcome, receipt.diagnostic_status, receipt.usage_observed) == (
            "REVIEW",
            "PASS",
            False,
        )
        assert receipt.reason_codes == ["REAL_MODEL_NOT_QUALIFIED"]
        assert json.loads(receipt.evidence_json)["content_key"] == KEY
        assert receipt.input_tokens is receipt.estimated_cost_usd is None
        assert job.claim_token is job.lease_expires_at is None
    assert runner.execute(claim) == "REVIEW"
    assert client.calls == 1
    with Session(engine) as session:
        attempted = session.scalars(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.event_type == "editorial.classification.attempted"
            )
        ).all()
        assert len(attempted) == 1
        assert (attempted[0].aggregate_key, attempted[0].idempotency_key) == (
            KEY,
            f"editorial.classification.attempted:{claim.job_id}:1",
        )
        assert count(session, models.EditorialClassificationAttemptModel) == 1


def test_due_order_and_bounded_scan_do_not_reactivate_terminal_or_live_leases(store):
    ingest(store)
    ingest(store, replace(MESSAGE, message_id=8, text="Synthetic second civic report"))
    engine, _ = store
    with Session(engine) as session:
        first, second = session.scalars(
            select(models.EditorialClassificationJobModel).order_by(
                models.EditorialClassificationJobModel.id
            )
        ).all()
        first_id, second_id = first.id, second.id
        first.available_at = NOW + timedelta(seconds=60)
        session.commit()
    runner = make_runner(engine, Classifier())
    claim = runner.claim_next(now=NOW, limit=1)
    assert claim.job_id == second_id
    assert runner.claim_next(now=NOW, limit=100) is None
    assert runner.execute(claim) == "REVIEW"
    with Session(engine) as session:
        session.get(models.EditorialClassifierPolicyModel, 1).enabled = False
        session.get(models.EditorialClassificationJobModel, first_id).available_at = NOW
        session.commit()
    assert runner.run_next(now=NOW) == "BLOCKED"
    with Session(engine) as session:
        session.get(models.EditorialClassifierPolicyModel, 1).enabled = True
        session.commit()
    assert runner.run_next(now=NOW + timedelta(hours=1)) == "IDLE"
    with Session(engine) as session:
        assert (
            session.get(models.EditorialClassificationJobModel, first_id).state,
            session.get(models.EditorialClassificationJobModel, first_id).attempts,
        ) == ("BLOCKED", 0)
        assert (
            session.get(models.EditorialClassificationJobModel, second_id).state,
            session.get(models.EditorialClassificationJobModel, second_id).attempts,
        ) == ("REVIEW", 1)


def test_scan_limit_is_not_spent_on_non_due_jobs_and_bounds_due_blocked_rows(store):
    ingest(store)
    ingest(store, replace(MESSAGE, message_id=8, text="Synthetic second civic report"))
    engine, _ = store
    with Session(engine) as session:
        first, second = session.scalars(
            select(models.EditorialClassificationJobModel).order_by(
                models.EditorialClassificationJobModel.id
            )
        ).all()
        first_id, second_id = first.id, second.id
        session.get(models.EditorialClassifierPolicyModel, 1).enabled = False
        session.commit()
    runner = make_runner(engine, factory=lambda binding: pytest.fail("bounded scan factory"))
    assert runner.claim_next(now=NOW, limit=1) is None
    with Session(engine) as session:
        assert session.get(models.EditorialClassificationJobModel, first_id).state == "BLOCKED"
        assert session.get(models.EditorialClassificationJobModel, second_id).state == "QUEUED"


@pytest.mark.parametrize(
    "table", ["editorial_classification_claims", "editorial_classification_attempts"]
)
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_completed_runner_history_refuses_sql_mutation_on_migrated_storage(store, table, operation):
    from sqlalchemy import text

    ingest(store)
    assert make_runner(store[0], Classifier()).run_next(now=NOW) == "REVIEW"
    with pytest.raises(DatabaseError, match="append-only"), store[0].begin() as connection:
        connection.execute(
            text(f"UPDATE {table} SET id=id" if operation == "UPDATE" else f"DELETE FROM {table}")
        )
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationClaimModel) == 1
        assert count(session, models.EditorialClassificationAttemptModel) == 1


def api():
    return import_module("newsflow.services.durable_editorial_runner")


def make_runner(engine, client=None, *, factory=None, clock=lambda: NOW):
    return api().DurableEditorialRunner(
        sessionmaker(engine),
        classifier_for_binding=factory or (lambda binding: client),
        clock=clock,
    )


@pytest.mark.parametrize(
    "change",
    [
        "disabled",
        "policy",
        "mapping",
        "source",
        "reject",
        "pass",
        "permission",
        "owner",
        "missing_policy",
        "decision",
        "rewrite",
        "fingerprint_missing",
        "fingerprint_foreign",
        "fingerprint_null",
        "foreign_account",
        "foreign_channel",
        "video",
        "album",
        "youtube",
        "ads",
        "filter",
        "stale",
        "deleted",
        "sync",
    ],
)
def test_fresh_binding_blocks_before_factory_and_keeps_budget(store, change):
    ingest(store)
    engine, mapping_id = store
    mutate(engine, mapping_id, change)
    runner = make_runner(engine, factory=lambda binding: pytest.fail("blocked provider factory"))
    assert runner.run_next(now=NOW) == "BLOCKED"
    with Session(engine) as session:
        job = session.scalar(select(models.EditorialClassificationJobModel))
        assert (job.state, job.attempts) == ("BLOCKED", 0)
        assert count(session, models.EditorialClassificationClaimModel) == 0
        assert count(session, models.RewriteJobModel) == (change == "rewrite")


def mutate(engine, mapping_id, change):
    with Session(engine) as session:
        policy = session.get(models.EditorialClassifierPolicyModel, 1)
        if change == "disabled":
            policy.enabled = False
        elif change == "policy":
            policy.policy_version = "synthetic-v2"
        elif change == "mapping":
            session.get(models.ChannelMappingModel, mapping_id).priority = 10
        elif change == "source":
            session.scalar(select(models.ContentRevisionModel)).source_text = "Changed report"
        elif change in {"reject", "pass"}:
            session.scalar(select(models.EditorialDecisionModel)).status = change.upper()
        elif change == "permission":
            session.scalar(select(models.EditorialDecisionModel)).rewrite_allowed = True
        elif change == "owner":
            session.get(models.TelegramAccount, 1).telegram_user_id = 9999
        elif change == "missing_policy":
            session.delete(policy)
        elif change == "decision":
            session.scalar(select(models.EditorialDecisionModel)).content_key = "unrelated"
        elif change == "rewrite":
            session.add(
                models.RewriteJobModel(content_key=KEY, idempotency_key="held", state="BLOCKED")
            )
        elif change.startswith("fingerprint_"):
            owner = session.scalar(select(models.MappingContentFingerprintModel))
            if change == "fingerprint_missing":
                session.delete(owner)
            else:
                owner.content_key = None if change == "fingerprint_null" else "foreign-owner"
        elif change == "foreign_account":
            session.scalar(select(models.IncomingPostModel)).telegram_account_id = "foreign"
        elif change == "foreign_channel":
            session.get(models.DonorChannel, 1).telegram_channel_id = CHANNEL - 10
        elif change in {"video", "album", "youtube", "ads"}:
            revision = session.scalar(select(models.ContentRevisionModel))
            if change == "video":
                revision.media_type = "video"
            elif change == "album":
                revision.album_id = "42"
            elif change == "youtube":
                revision.link_destinations = ["https://youtu.be/synthetic"]
            else:
                revision.source_text += " #ad"
        elif change == "filter":
            session.add(
                models.MappingFilterPolicyModel(
                    mapping_id=mapping_id, allowed_media_types=[], blocked_domains=[], ad_markers=[]
                )
            )
        elif change == "stale":
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=1, revision_number=2, source_text="new", link_destinations=[]
                )
            )
        elif change == "deleted":
            session.add(
                models.SourceDeletionModel(
                    telegram_account_id="1",
                    donor_channel_id=str(CHANNEL),
                    telegram_message_id=7,
                    latest_pts=1,
                    observed_at=NOW,
                )
            )
        elif change == "sync":
            session.add(
                models.ChannelDifferenceCursorModel(
                    donor_channel_id=mapping_id,
                    telegram_account_id=1,
                    telegram_user_id=1001,
                    telegram_channel_id=CHANNEL,
                    pts=1,
                    available_at=NOW,
                    last_error_code="GAP_UNRESOLVED",
                )
            )
        else:
            raise AssertionError(change)
        session.commit()


@pytest.mark.parametrize("stage", ["after_claim", "factory", "classify"])
@pytest.mark.parametrize("change", ["policy", "source", "filter", "owner", "reject", "deleted"])
def test_independent_committed_change_is_checked_at_each_external_boundary(store, stage, change):
    ingest(store)
    engine, mapping_id = store
    client = Classifier()
    original = client.classify

    def classify(request):
        original(request)
        mutate(engine, mapping_id, change)

    if stage == "classify":
        client.classify = classify

    def factory(binding):
        if stage == "factory":
            mutate(engine, mapping_id, change)
        return client

    runner = make_runner(engine, factory=factory)
    claim = runner.claim_next(now=NOW)
    if stage == "after_claim":
        mutate(engine, mapping_id, change)
    assert runner.execute(claim) == "BLOCKED"
    assert client.calls == (1 if stage == "classify" else 0)
    with Session(engine) as session:
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        assert receipt.outcome == "BLOCKED"
        assert (receipt.evidence_json is not None) == (stage == "classify")
        assert count(session, models.RewriteJobModel) == 0


def test_forged_claim_cannot_call_or_append_history(store):
    ingest(store)
    engine, _ = store
    runner = make_runner(engine, factory=lambda binding: pytest.fail("forged factory"))
    claim = runner.claim_next(now=NOW)
    assert (
        runner.execute(api().EditorialClaim(claim.job_id, str(uuid4()), claim.attempt))
        == "LOST_LEASE"
    )
    with Session(engine) as session:
        assert count(session, models.EditorialClassificationAttemptModel) == 0
        assert (
            session.get(models.EditorialClassificationJobModel, claim.job_id).claim_token
            == claim.token
        )


@pytest.mark.parametrize(
    "raw,want,diagnostic,reason",
    [
        (None, "FAILED", None, "EDITORIAL_EVIDENCE_MISSING"),
        ({}, "FAILED", None, "EDITORIAL_EVIDENCE_INVALID"),
        ("界" * 87382, "FAILED", None, "EDITORIAL_EVIDENCE_TOO_LARGE"),
        ("\ud800", "FAILED", None, "EDITORIAL_EVIDENCE_INVALID"),
        ('{"approve":true}', "REVIEW", "MANUAL_REVIEW", "EVIDENCE_SCHEMA_INVALID"),
        ("not-json", "REVIEW", "MANUAL_REVIEW", "EVIDENCE_JSON_INVALID"),
    ],
    ids=["missing", "wrong-type", "byte-limit", "encoding", "schema", "json"],
)
def test_only_bounded_evidence_is_assessed_never_the_forged_return(
    store, raw, want, diagnostic, reason
):
    ingest(store)
    client = Classifier()

    def forged(request):
        client.calls += 1
        client.last_evidence_json = raw
        return {"status": "PASS", "rewrite_allowed": True}

    client.classify = forged
    runner = make_runner(store[0], client)
    assert runner.run_next(now=NOW) == want
    with Session(store[0]) as session:
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        assert (receipt.outcome, receipt.diagnostic_status, receipt.reason_codes) == (
            want,
            diagnostic,
            [reason],
        )
        assert (receipt.evidence_json is not None) == (want == "REVIEW")
        assert count(session, models.RewriteJobModel) == 0
        assert session.scalar(select(models.EditorialDecisionModel)).rewrite_allowed is False
    assert client.calls == 1


@pytest.mark.parametrize(
    "change,want,diagnostic,reason",
    [
        ({"content_key": "foreign"}, "REVIEW", "MANUAL_REVIEW", "CONTENT_BINDING_MISMATCH"),
        ({"source_sha256": "a" * 64}, "REVIEW", "MANUAL_REVIEW", "SOURCE_BINDING_MISMATCH"),
        ({"policy_sha256": "a" * 64}, "REVIEW", "MANUAL_REVIEW", "POLICY_BINDING_MISMATCH"),
        ({"prompt_version": "old"}, "REVIEW", "MANUAL_REVIEW", "PROMPT_BINDING_MISMATCH"),
        ({"ambiguous": True}, "REVIEW", "MANUAL_REVIEW", "CLASSIFICATION_AMBIGUOUS"),
        ({"source_complete": False}, "REVIEW", "MANUAL_REVIEW", "SOURCE_INCOMPLETE"),
        (
            {
                "sentiment": "negative",
                "framing": "hostile",
                "entity_findings": [
                    {"entity_id": "synthetic-council", "source_quote": "Civic Council"}
                ],
            },
            "REJECT",
            "REJECT",
            "PROTECTED_ENTITY_NEGATIVE",
        ),
    ],
)
def test_effective_diagnostic_is_derived_from_actual_bound_json(
    store, change, want, diagnostic, reason
):
    ingest(store, replace(MESSAGE, text="Civic Council opened a civic center"))
    client = Classifier()
    original = client.classify

    def classify(request):
        original(request)
        value = json.loads(client.last_evidence_json)
        value["entity_findings"] = [
            {"entity_id": "synthetic-council", "source_quote": "Civic Council"}
        ]
        client.last_evidence_json = json.dumps(value | change)

    client.classify = classify
    assert make_runner(store[0], client).run_next(now=NOW) == want
    with Session(store[0]) as session:
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        assert (receipt.outcome, receipt.diagnostic_status) == (want, diagnostic)
        assert reason in receipt.reason_codes
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert (decision.status, decision.rewrite_allowed) == ("MANUAL_REVIEW", False)
        assert count(session, models.RewriteJobModel) == 0


@pytest.mark.parametrize(
    "attribute,value", [("provider", "OTHER"), ("model", "paid-model"), ("prompt_version", "old")]
)
def test_factory_identity_mismatch_is_terminal_without_classify(store, attribute, value):
    ingest(store)
    client = Classifier()
    setattr(client, attribute, value)
    assert make_runner(store[0], client).run_next(now=NOW) == "FAILED"
    assert client.calls == 0
    with Session(store[0]) as session:
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        assert receipt.reason_codes == ["EDITORIAL_PROVIDER_CONFIGURATION_INVALID"]
        assert receipt.evidence_json is receipt.response_model is None


@pytest.mark.parametrize("stage", ["factory", "classify"])
@pytest.mark.parametrize(
    "error,code,state",
    [
        (ProviderUnavailable, "EDITORIAL_PROVIDER_UNAVAILABLE", "RETRY"),
        (ProviderConfigurationInvalid, "EDITORIAL_PROVIDER_CONFIGURATION_INVALID", "FAILED"),
        (ProviderResponseInvalid, "EDITORIAL_PROVIDER_RESPONSE_INVALID", "FAILED"),
        (RuntimeError, "EDITORIAL_PROVIDER_FAILED", "FAILED"),
    ],
)
def test_raw_provider_exception_is_sanitized_and_only_unavailable_retries(
    store, stage, error, code, state
):
    ingest(store)
    client = Classifier()

    def fail(*args):
        raise error("sk-raw-secret SOURCE_PRIVATE_SENTINEL")

    if stage == "classify":
        client.classify = fail
    runner = make_runner(store[0], client, factory=fail if stage == "factory" else None)
    assert runner.run_next(now=NOW) == state
    with Session(store[0]) as session:
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        job = session.scalar(select(models.EditorialClassificationJobModel))
        assert receipt.reason_codes == [code]
        assert job.last_error_code == code
        assert (job.state, job.attempts) == ("QUEUED" if state == "RETRY" else state, 1)
        if state == "RETRY":
            assert job.available_at.replace(tzinfo=UTC) == NOW + timedelta(seconds=60)
        assert count(session, models.RewriteJobModel) == 0


def test_retry_consumes_two_attempts_then_stops_permanently(store):
    ingest(store)
    now = [NOW]
    client = Classifier()

    def fail(request):
        client.calls += 1
        raise ProviderUnavailable("synthetic")

    client.classify = fail
    runner = make_runner(store[0], client, clock=lambda: now[0])
    assert runner.run_next(now=now[0]) == "RETRY"
    assert runner.run_next(now=now[0]) == "IDLE"
    now[0] += timedelta(seconds=60)
    assert runner.run_next(now=now[0]) == "FAILED"
    assert runner.run_next(now=now[0] + timedelta(hours=1)) == "IDLE"
    assert client.calls == 2
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationClaimModel) == 2
        assert count(session, models.EditorialClassificationAttemptModel) == 2
        assert session.scalar(select(models.EditorialClassificationJobModel)).attempts == 2


@pytest.mark.parametrize(
    "change,observed",
    [
        ({}, True),
        ({"estimated_cost_usd": None}, True),
        ({"input_tokens": True}, False),
        ({"input_tokens": -1}, False),
        ({"input_tokens": 1.5}, False),
        ({"cached_tokens": 101}, False),
        ({"output_tokens": None}, False),
        ({"provider": "OTHER"}, False),
        ({"provider": []}, False),
        ({"model": "x" * 256}, False),
        ({"estimated_cost_usd": Decimal("NaN")}, False),
        ({"estimated_cost_usd": Decimal("Infinity")}, False),
        ({"estimated_cost_usd": Decimal(-1)}, False),
        ({"estimated_cost_usd": 0.5}, False),
        ({"estimated_cost_usd": Decimal(10000000000)}, False),
    ],
)
def test_observed_usage_is_validated_without_coercing_unknown_or_invalid_counts(
    store, change, observed
):
    ingest(store)
    client = Classifier()
    client.last_usage = replace(
        RewriteUsage(client.model, 100, 10, 20, Decimal("0.00042")), **change
    )
    assert make_runner(store[0], client).run_next(now=NOW) == "REVIEW"
    with Session(store[0]) as session:
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        assert receipt.usage_observed is observed
        assert receipt.input_tokens == (100 if observed else None)
        assert receipt.cached_tokens == (10 if observed else None)
        assert receipt.output_tokens == (20 if observed else None)
        assert receipt.estimated_cost_usd == (
            client.last_usage.estimated_cost_usd if observed else None
        )
        assert ("EDITORIAL_USAGE_INVALID" in receipt.reason_codes) is (not observed)


@pytest.mark.parametrize("reclaim", [False, True])
def test_old_result_keeps_exact_usage_and_never_overwrites_new_owner(store, reclaim):
    ingest(store)
    now = [NOW]
    client = Classifier()
    client.last_usage = RewriteUsage(client.model, 100, 10, 20, None)
    runner = make_runner(store[0], client, clock=lambda: now[0])
    old = runner.claim_next(now=NOW)
    original = client.classify
    newer = []

    def classify(request):
        original(request)
        now[0] += timedelta(seconds=60)
        if reclaim:
            newer.append(runner.claim_next(now=now[0]))

    client.classify = classify
    assert runner.execute(old) == "LOST_LEASE"
    with Session(store[0]) as session:
        job = session.get(models.EditorialClassificationJobModel, old.job_id)
        assert (job.state, job.attempts, job.claim_token) == (
            "RUNNING",
            2 if reclaim else 1,
            newer[0].token if reclaim else old.token,
        )
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        history = session.get(models.EditorialClassificationClaimModel, receipt.claim_id)
        assert (history.claim_token, history.attempt, receipt.outcome, receipt.input_tokens) == (
            old.token,
            1,
            "LOST_LEASE",
            100,
        )
    assert runner.execute(old) == "LOST_LEASE"
    assert client.calls == 1


def test_legacy_running_without_immutable_history_never_invokes_factory(store):
    ingest(store)
    token = str(uuid4())
    with Session(store[0]) as session:
        job = session.scalar(select(models.EditorialClassificationJobModel))
        job.state, job.attempts, job.claim_token, job.lease_expires_at = (
            "RUNNING",
            1,
            token,
            NOW + timedelta(seconds=60),
        )
        identity = job.id
        session.commit()
    runner = make_runner(store[0], factory=lambda binding: pytest.fail("legacy factory"))
    assert runner.execute(api().EditorialClaim(identity, token, 1)) == "LOST_LEASE"
    assert runner.run_next(now=NOW + timedelta(seconds=60)) == "FAILED"
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationClaimModel) == 0
        assert count(session, models.EditorialClassificationAttemptModel) == 0


def test_second_crashed_claim_is_exhausted_without_refund_or_io(store):
    ingest(store)
    runner = make_runner(store[0], factory=lambda binding: pytest.fail("exhausted factory"))
    assert runner.claim_next(now=NOW).attempt == 1
    assert runner.claim_next(now=NOW + timedelta(seconds=60)).attempt == 2
    assert runner.run_next(now=NOW + timedelta(seconds=120)) == "FAILED"
    with Session(store[0]) as session:
        job = session.scalar(select(models.EditorialClassificationJobModel))
        assert (job.attempts, job.last_error_code) == (2, "EDITORIAL_ATTEMPTS_EXHAUSTED")


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        NOW.replace(tzinfo=None),
        "now",
        datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
        datetime.max.replace(tzinfo=UTC),
    ],
)
def test_malformed_clock_is_rejected_before_sessions(invalid):
    runner = api().DurableEditorialRunner(
        lambda: pytest.fail("invalid clock SQL"),
        classifier_for_binding=lambda binding: pytest.fail("invalid clock factory"),
        clock=lambda: invalid,
    )
    with pytest.raises(ValueError, match="EDITORIAL_TIME_INVALID"):
        runner.claim_next(now=invalid)
    with pytest.raises(ValueError, match="EDITORIAL_TIME_INVALID"):
        runner.execute(api().EditorialClaim(1, str(uuid4()), 1))


@pytest.mark.parametrize("limit", [None, True, 0, 101, 1.5, "16"])
def test_malformed_limit_is_rejected_before_sessions(limit):
    runner = api().DurableEditorialRunner(
        lambda: pytest.fail("invalid limit SQL"), classifier_for_binding=None
    )
    with pytest.raises(ValueError, match="EDITORIAL_LIMIT_INVALID"):
        runner.claim_next(now=NOW, limit=limit)


@pytest.mark.parametrize(
    "identity,token,attempt",
    [
        (True, str(uuid4()), 1),
        (0, str(uuid4()), 1),
        ("1", str(uuid4()), 1),
        (1, "x" * 36, 1),
        (1, str(uuid4()).upper(), 1),
        (1, str(uuid4()), True),
        (1, str(uuid4()), 0),
        (1, str(uuid4()), 3),
    ],
)
def test_malformed_claim_is_rejected_before_sessions(identity, token, attempt):
    runner = api().DurableEditorialRunner(
        lambda: pytest.fail("invalid claim SQL"), classifier_for_binding=None
    )
    with pytest.raises(ValueError, match="EDITORIAL_CLAIM_INVALID"):
        runner.execute(api().EditorialClaim(identity, token, attempt))


def test_sessions_close_for_both_factory_and_classify_and_committed_result_reopens(store):
    ingest(store)
    active = set()

    class Tracked(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            active.add(self)

        def close(self):
            super().close()
            active.remove(self)

    client = Classifier()
    original = client.classify

    def classify(request):
        assert active == set()
        original(request)

    def factory(binding):
        assert active == set()
        return client

    client.classify = classify
    runner = api().DurableEditorialRunner(
        sessionmaker(store[0], class_=Tracked), classifier_for_binding=factory, clock=lambda: NOW
    )
    assert runner.run_next(now=NOW) == "REVIEW"
    assert active == set()
    reopened = create_engine(store[0].url)
    try:
        with Session(reopened) as session:
            assert (
                session.scalar(select(models.EditorialClassificationAttemptModel)).outcome
                == "REVIEW"
            )
            assert session.scalar(select(models.EditorialClassificationJobModel)).state == "REVIEW"
    finally:
        reopened.dispose()


@pytest.mark.parametrize(
    "table,operation,phase",
    [
        ("editorial_classification_claims", "INSERT", "claim"),
        ("editorial_classification_jobs", "UPDATE", "claim"),
        ("editorial_classification_attempts", "INSERT", "finish"),
        ("editorial_classification_jobs", "UPDATE", "finish"),
        ("outbox_events", "INSERT", "finish"),
    ],
)
def test_storage_faults_propagate_and_roll_back_entire_atomic_boundary(
    store, table, operation, phase
):
    ingest(store)
    engine, _ = store
    client = Classifier()
    runner = make_runner(engine, client)
    claim = runner.claim_next(now=NOW) if phase == "finish" else None

    def fail(connection, cursor, statement, parameters, context, many):
        if (
            statement.lstrip()
            .upper()
            .startswith(operation + (" INTO " if operation == "INSERT" else " ") + table.upper())
        ):
            raise IntegrityError("synthetic storage insertion", {}, RuntimeError("fault"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(IntegrityError):
            runner.execute(claim) if phase == "finish" else runner.claim_next(now=NOW)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with Session(engine) as session:
        job = session.scalar(select(models.EditorialClassificationJobModel))
        assert (job.state, job.attempts) == (("RUNNING", 1) if phase == "finish" else ("QUEUED", 0))
        assert count(session, models.EditorialClassificationClaimModel) == (phase == "finish")
        assert count(session, models.EditorialClassificationAttemptModel) == 0
        assert (
            session.scalars(
                select(models.OutboxEventModel).where(
                    models.OutboxEventModel.event_type == "editorial.classification.attempted"
                )
            ).all()
            == []
        )
    if phase == "claim":
        claim = runner.claim_next(now=NOW)
    assert runner.execute(claim) == "REVIEW"


def test_two_postgres_claimants_cannot_own_the_same_attempt(store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    engine, _ = store
    if engine.dialect.name != "postgresql":
        pytest.skip("Actual strict migrated PostgreSQL lock proof is root-owned")
    ingest(store)
    locked, release = Event(), Event()
    first_connection = []

    def hold(connection, cursor, statement, parameters, context, many):
        if "FOR UPDATE SKIP LOCKED" in statement and not first_connection:
            first_connection.append(connection)
            locked.set()
            assert release.wait(20), "second claimant never completed"

    runner = make_runner(engine, factory=lambda binding: pytest.fail("claim should not invoke IO"))
    event.listen(engine, "after_cursor_execute", hold)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(runner.claim_next, now=NOW)
            try:
                assert locked.wait(20), "first claimant never acquired lock"
                assert runner.claim_next(now=NOW) is None
            finally:
                release.set()
            owned = pending.result(timeout=20)
    finally:
        event.remove(engine, "after_cursor_execute", hold)
    assert owned.attempt == 1
    with Session(engine) as session:
        assert count(session, models.EditorialClassificationClaimModel) == 1
        assert session.get(models.EditorialClassificationJobModel, owned.job_id).attempts == 1


@pytest.mark.parametrize("stage", ["factory", "classify", "finish"])
def test_expiry_during_canonical_sql_check_fences_io_and_finalization(store, stage):
    ingest(store)
    engine, _ = store
    now = [NOW]
    client = Classifier()
    factory_calls = []

    def factory(binding):
        factory_calls.append(binding)
        return client

    runner = make_runner(engine, factory=factory, clock=lambda: now[0])
    claimed = runner.claim_next(now=NOW)
    target = {"factory": 1, "classify": 2, "finish": 3}[stage]
    checks = []

    def expire(connection, cursor, statement, parameters, context, many):
        if (
            statement.lstrip().upper().startswith("SELECT")
            and "FROM editorial_classifier_policy" in statement
        ):
            checks.append(statement)
            if len(checks) == target:
                now[0] = NOW + timedelta(seconds=60)

    event.listen(engine, "before_cursor_execute", expire)
    try:
        assert runner.execute(claimed) == "LOST_LEASE"
    finally:
        event.remove(engine, "before_cursor_execute", expire)
    assert len(factory_calls) == (stage != "factory")
    assert client.calls == (stage == "finish")
    assert_lost_receipt_keeps_owner(engine, claimed)


@pytest.mark.parametrize("stage", ["factory", "classify"])
def test_expiry_at_closed_session_boundary_prevents_external_io(store, stage):
    ingest(store)
    engine, _ = store
    now = [NOW]
    enabled = [False]
    closed = []
    client = Classifier()
    factory_calls = []
    target = 1 if stage == "factory" else 2

    class Closing(Session):
        def close(self):
            super().close()
            if enabled[0]:
                closed.append(self)
                if len(closed) == target:
                    now[0] = NOW + timedelta(seconds=60)

    def factory(binding):
        factory_calls.append(binding)
        return client

    runner = api().DurableEditorialRunner(
        sessionmaker(engine, class_=Closing), classifier_for_binding=factory, clock=lambda: now[0]
    )
    claimed = runner.claim_next(now=NOW)
    enabled[0] = True
    assert runner.execute(claimed) == "LOST_LEASE"
    assert len(factory_calls) == (stage != "factory")
    assert client.calls == 0
    assert_lost_receipt_keeps_owner(engine, claimed)


def assert_lost_receipt_keeps_owner(engine, claimed, *, observed=False):
    with Session(engine) as session:
        job = session.get(models.EditorialClassificationJobModel, claimed.job_id)
        assert (job.state, job.attempts, job.claim_token, job.last_error_code) == (
            "RUNNING",
            claimed.attempt,
            claimed.token,
            None,
        )
        assert job.lease_expires_at.replace(tzinfo=UTC) == NOW + timedelta(seconds=60)
        receipt = session.scalar(select(models.EditorialClassificationAttemptModel))
        history = session.get(models.EditorialClassificationClaimModel, receipt.claim_id)
        assert (history.classification_job_id, history.claim_token, history.attempt) == (
            claimed.job_id,
            claimed.token,
            claimed.attempt,
        )
        assert (receipt.outcome, receipt.diagnostic_status, receipt.reason_codes) == (
            "LOST_LEASE",
            None,
            ["EDITORIAL_LEASE_LOST"],
        )
        assert receipt.usage_observed is observed
        assert receipt.input_tokens == (100 if observed else None)
        assert count(session, models.RewriteJobModel) == 0


@pytest.mark.parametrize("completion", ["review", "reject", "retry", "blocked"])
def test_postgres_finalizer_waiting_on_row_lock_refreshes_lease_clock(store, completion):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic

    from sqlalchemy import text

    engine, mapping_id = store
    if engine.dialect.name != "postgresql":
        pytest.skip("Actual strict migrated PostgreSQL finalizer row-lock proof is root-owned")
    ingest(store, replace(MESSAGE, text="Civic Council opened a civic center"))
    now = [NOW]
    client = Classifier()
    client.last_usage = RewriteUsage(client.model, 100, 10, 20, None)
    original = client.classify

    def classify(request):
        original(request)
        if completion == "retry":
            raise ProviderUnavailable("synthetic unavailable")
        if completion == "blocked":
            mutate(engine, mapping_id, "disabled")
        value = json.loads(client.last_evidence_json)
        value["entity_findings"] = [
            {"entity_id": "synthetic-council", "source_quote": "Civic Council"}
        ]
        if completion == "reject":
            value.update(sentiment="negative", framing="hostile")
        client.last_evidence_json = json.dumps(value)

    client.classify = classify
    runner = make_runner(engine, client, clock=lambda: now[0])
    claimed = runner.claim_next(now=NOW)
    requesting = Event()
    waiter_pid = []

    def requested(connection, cursor, statement, parameters, context, many):
        if "FOR UPDATE" in statement and "SKIP LOCKED" not in statement:
            waiter_pid.append(connection.connection.driver_connection.info.backend_pid)
            requesting.set()

    with Session(engine) as holder:
        holder_pid = holder.scalar(text("SELECT pg_backend_pid()"))
        holder.scalar(
            select(models.EditorialClassificationJobModel)
            .where(models.EditorialClassificationJobModel.id == claimed.job_id)
            .with_for_update()
        )
        event.listen(engine, "before_cursor_execute", requested)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(runner.execute, claimed)
                try:
                    assert requesting.wait(20), "finalizer never requested its row lock"
                    # Observe the actual backend wait, not thread scheduling or elapsed sleep.
                    deadline = monotonic() + 20
                    with engine.connect() as observer:
                        while monotonic() < deadline:
                            blockers = observer.scalar(
                                text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter_pid[0]}
                            )
                            if holder_pid in blockers:
                                break
                        else:
                            pytest.fail("finalizer never waited on the independent held row lock")
                    now[0] = NOW + timedelta(seconds=60)
                finally:
                    holder.commit()  # Release without changing the job row.
                assert pending.result(timeout=20) == "LOST_LEASE"
        finally:
            event.remove(engine, "before_cursor_execute", requested)
    assert client.calls == 1
    assert_lost_receipt_keeps_owner(engine, claimed, observed=True)
    assert runner.execute(claimed) == "LOST_LEASE"
    assert client.calls == 1


def test_completed_receipt_replays_unchanged_after_lease_expiry(store):
    ingest(store)
    now = [NOW]
    client = Classifier()
    factory_calls = []

    def factory(binding):
        factory_calls.append(binding)
        return client

    runner = make_runner(store[0], factory=factory, clock=lambda: now[0])
    claimed = runner.claim_next(now=NOW)
    assert runner.execute(claimed) == "REVIEW"
    now[0] = NOW + timedelta(seconds=60)
    assert runner.execute(claimed) == "REVIEW"
    assert client.calls == len(factory_calls) == 1
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationAttemptModel) == 1
