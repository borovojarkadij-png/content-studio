from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from test_semantic_approval import DRAFT, SOURCE, SyntheticVerifier

from newsflow.persistence.models import EditorialDecisionModel, RewriteOutputModel

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def runner(factory, provider, clock=lambda: NOW):
    from newsflow.services.durable_semantic_runner import DurableSemanticRunner

    return DurableSemanticRunner(factory, verifier_for_release=lambda _: provider, clock=clock)


def test_durable_verification_claim_and_approval_are_independent_per_output(semantic_store):
    from newsflow.persistence.models import SemanticVerificationJobModel

    provider = SyntheticVerifier()
    execution = runner(semantic_store, provider)
    assert execution.enqueue_pending(now=NOW) == 2
    assert execution.enqueue_pending(now=NOW) == 0
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    assert execution.run_next(now=NOW) == "IDLE"
    assert provider.calls == [(SOURCE, DRAFT), (SOURCE, DRAFT)]
    with semantic_store() as session:
        assert list(session.scalars(select(RewriteOutputModel.approval_state))) == [
            "APPROVED",
            "APPROVED",
        ]
        jobs = session.scalars(select(SemanticVerificationJobModel)).all()
        assert [(job.state, job.attempts, job.claim_token) for job in jobs] == [
            ("SUCCEEDED", 1, None),
            ("SUCCEEDED", 1, None),
        ]
        assert all(job.evidence_id is not None for job in jobs)


def test_editorial_reject_of_queued_verification_has_zero_provider_calls(semantic_store):
    provider = SyntheticVerifier()
    execution = runner(semantic_store, provider)
    execution.enqueue_pending(now=NOW)
    with semantic_store() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert provider.calls == []


def test_expired_claim_is_recovered_and_old_owner_is_fenced(semantic_store):
    provider = SyntheticVerifier()
    execution = runner(semantic_store, provider)
    execution.enqueue_pending(now=NOW)
    old = execution.claim_next(now=NOW)
    recovered = runner(semantic_store, provider, clock=lambda: NOW + timedelta(seconds=61))
    new = recovered.claim_next(now=NOW + timedelta(seconds=61))
    assert new.job_id == old.job_id and new.token != old.token and new.attempt == 2
    assert execution.execute(old) == "LOST_LEASE"
    assert recovered.execute(new) == "SUCCEEDED"
    assert provider.calls == [(SOURCE, DRAFT)]


def test_claim_attempt_budget_survives_restarts_before_any_network_call(semantic_store):
    from newsflow.persistence.models import SemanticVerificationJobModel

    provider = SyntheticVerifier()
    execution = runner(semantic_store, provider)
    execution.enqueue_pending(now=NOW)
    first = execution.claim_next(now=NOW)
    second = execution.claim_next(now=NOW + timedelta(seconds=61))
    assert second.job_id == first.job_id
    execution.claim_next(now=NOW + timedelta(seconds=122))
    with semantic_store() as session:
        failed = session.get(SemanticVerificationJobModel, first.job_id)
        assert failed.state == "FAILED" and failed.attempts == 2
    assert provider.calls == []


def test_lease_lost_during_verification_cannot_record_evidence_or_autoapprove(semantic_store):
    from newsflow.persistence.models import SemanticEvidenceModel

    clock = [NOW]
    execution = None

    def lose():
        clock[0] = NOW + timedelta(seconds=61)
        execution.claim_next(now=clock[0])

    provider = SyntheticVerifier(change=lose)
    execution = runner(semantic_store, provider, clock=lambda: clock[0])
    execution.enqueue_pending(now=NOW)
    assert execution.run_next(now=NOW) == "LOST_LEASE"
    with semantic_store() as session:
        assert session.scalar(select(SemanticEvidenceModel)) is None
        assert session.get(RewriteOutputModel, 1).approval_state == "PENDING"


def test_error_or_uncertainty_is_terminal_manual_review_not_repeated_paid_classification(
    semantic_store,
):
    provider = SyntheticVerifier(relation="UNCERTAIN", verdict="UNCERTAIN")
    execution = runner(semantic_store, provider)
    execution.enqueue_pending(now=NOW)
    assert execution.run_next(now=NOW) == "REVIEW"
    assert execution.enqueue_pending(now=NOW) == 0
    assert execution.run_next(now=NOW) == "REVIEW"
    assert execution.run_next(now=NOW) == "IDLE"
    assert len(provider.calls) == 2


def test_known_usage_is_persisted_even_when_semantic_claims_are_changed(semantic_store):
    from newsflow.persistence.models import SemanticVerificationUsageModel
    from newsflow.providers.openai_rewrite import RewriteUsage

    provider = SyntheticVerifier(relation="CONTRADICTED", verdict="CHANGED")
    provider.last_usage = RewriteUsage("synthetic-model", 100, 40, 20, None)
    execution = runner(semantic_store, provider)
    execution.enqueue_pending(now=NOW)
    assert execution.run_next(now=NOW) == "REVIEW"
    with semantic_store() as session:
        usage = session.scalar(select(SemanticVerificationUsageModel))
        assert (usage.attempt, usage.input_tokens, usage.cached_tokens, usage.output_tokens) == (
            1,
            100,
            40,
            20,
        )
        assert usage.estimated_cost_usd is None


def test_disabled_semantic_worker_does_not_access_database_or_keys():
    from newsflow.worker import run_semantic_tick

    def forbidden():
        raise AssertionError("Disabled verification must not access state")

    assert run_semantic_tick(forbidden, enabled=False, cipher=None, now=NOW) == "DISABLED"


def test_enqueue_limit_does_not_starve_later_channels_with_older_manual_drafts(semantic_store):
    from newsflow.services.automatic_approval import AutomaticApprovalPolicyService

    with semantic_store() as session:
        AutomaticApprovalPolicyService(session).configure(1, "MANUAL")
    provider = SyntheticVerifier()
    execution = runner(semantic_store, provider)
    assert execution.enqueue_pending(now=NOW, limit=1) == 1
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    with semantic_store() as session:
        assert session.get(RewriteOutputModel, 1).approval_state == "PENDING"
        assert session.get(RewriteOutputModel, 2).approval_state == "APPROVED"


def test_encrypted_factory_worker_uses_qualified_verifier_not_rewrite_model(semantic_store):
    import json

    from test_openai_rewrite_provider import HttpFixture, envelope

    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.rewrite_provider_settings import RewriteProviderSettingsService
    from newsflow.worker import run_semantic_tick

    body = envelope()
    body["output"][0]["content"][0]["text"] = json.dumps(
        {
            "verdict": "PRESERVED",
            "source_complete": True,
            "draft_complete": True,
            "claims": [{"source_quote": SOURCE, "draft_quote": DRAFT, "relation": "SUPPORTED"}],
        }
    )
    http = HttpFixture(body)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with semantic_store() as session:
        RewriteProviderSettingsService(session, cipher=cipher).configure_openai(
            api_key="synthetic", model="other-rewrite-model"
        )
    assert (
        run_semantic_tick(semantic_store, enabled=True, cipher=cipher, now=NOW, opener=http)
        == "SUCCEEDED"
    )
    assert json.loads(http.requests[0].data)["model"] == "synthetic-model"
    with semantic_store() as session:
        assert session.get(RewriteOutputModel, 1).approval_state == "APPROVED"


def test_unreadable_stable_key_is_terminal_configuration_not_network_retry(semantic_store):
    from newsflow.persistence.models import RewriteProviderSettingModel
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.durable_semantic_runner import DurableSemanticRunner
    from newsflow.services.semantic_verifier_factory import ConfiguredSemanticVerifierFactory

    with semantic_store() as session:
        session.add(
            RewriteProviderSettingModel(
                provider="OPENAI",
                encrypted_api_key="invalid-synthetic-ciphertext",
                primary_model="unused",
            )
        )
        session.commit()
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    execution = DurableSemanticRunner(
        semantic_store,
        verifier_for_release=ConfiguredSemanticVerifierFactory(semantic_store, cipher=cipher),
        clock=lambda: NOW,
    )
    execution.enqueue_pending(now=NOW)
    assert execution.run_next(now=NOW) == "FAILED"
