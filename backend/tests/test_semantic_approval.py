"""Synthetic qualifications exercise guards, never qualify operational models."""

from datetime import date

import pytest
from sqlalchemy import func, select

from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
    SemanticEvidenceModel,
    SemanticVerifierReleaseModel,
)
from newsflow.services.automatic_approval import AutomaticApprovalPolicyService
from newsflow.services.rewrite_outputs import RewriteOutputService

SOURCE = "Завод открыл 3 линии."
DRAFT = "Открыты 3 линии на заводе."
KEY = "synthetic:@semantic:1:revision:1"


def test_approval_policy_read_refreshes_revoked_cached_release_and_policy(semantic_store):
    from newsflow.persistence.models import AutomaticApprovalPolicyModel

    with semantic_store() as cached:
        old_policy = cached.get(AutomaticApprovalPolicyModel, 1)
        old_release = cached.get(SemanticVerifierReleaseModel, 1)
        service = AutomaticApprovalPolicyService(cached)
        assert service.get_policy(1)["mode"] == "VERIFIED"
        with semantic_store.begin() as writer:
            writer.get(SemanticVerifierReleaseModel, 1).active = False
            policy = writer.get(AutomaticApprovalPolicyModel, 1)
            policy.mode, policy.release_id = "MANUAL", None
        report = service.get_policy(1)
        assert (report["mode"], report["release_id"]) == ("MANUAL", None)
        assert report["qualified_releases"] == []
        assert old_policy.mode == "MANUAL" and old_release.active is False
        assert not cached.new and not cached.dirty


@pytest.mark.parametrize("channel_id", [True, 0, -1, "1"])
def test_approval_policy_invalid_identity_refused_before_sql(channel_id):
    with pytest.raises(ValueError):
        AutomaticApprovalPolicyService(None).get_policy(channel_id)


def test_approval_policy_http_configures_only_existing_release_without_jobs(
    semantic_store, monkeypatch
):
    from fastapi.testclient import TestClient

    from newsflow.app import app
    from newsflow.persistence.models import SemanticVerificationJobModel

    monkeypatch.setenv("DATABASE_URL", str(semantic_store.kw["bind"].url))
    path = "/api/telegram/output-channels/1/approval-policy"
    with TestClient(app) as client:
        initial = client.get(path)
        assert initial.headers["Cache-Control"] == "no-store"
        assert initial.json()["qualified_releases"][0]["model"] == "synthetic-model"
        assert (
            client.put(path, json={"mode": "MANUAL", "release_id": None}).json()["mode"] == "MANUAL"
        )
        assert (
            client.put(path, json={"mode": "VERIFIED", "release_id": 1}).json()["mode"]
            == "VERIFIED"
        )
        with semantic_store.begin() as session:
            session.get(SemanticVerifierReleaseModel, 1).active = False
        refused = client.put(path, json={"mode": "VERIFIED", "release_id": 1})
        assert refused.status_code == 409
        assert client.get(path).json()["qualified_releases"] == []
        assert (
            client.put(path, json={"mode": "MANUAL", "release_id": None}).json()["mode"] == "MANUAL"
        )
    with semantic_store() as session:
        assert session.scalar(select(SemanticVerificationJobModel)) is None
        assert session.scalar(select(SemanticEvidenceModel)) is None


class SyntheticVerifier:
    provider = "OPENAI"
    model = "synthetic-model"
    prompt_version = "semantic-facts-v1"

    def __init__(self, *, relation="SUPPORTED", verdict="PRESERVED", change=None, fail=False):
        self.calls = []
        self.relation, self.verdict = relation, verdict
        self.change, self.fail = change, fail

    def verify(self, source, draft):
        self.calls.append((source, draft))
        if self.change:
            self.change()
        if self.fail:
            raise RuntimeError("synthetic-secret-must-not-leak")
        return {
            "verdict": self.verdict,
            "source_complete": True,
            "draft_complete": True,
            "claims": [{"source_quote": source, "draft_quote": draft, "relation": self.relation}],
        }


def verify(factory, verifier, output_id=1):
    from newsflow.services.semantic_verification import SemanticVerificationService

    return SemanticVerificationService(factory, verifier_for_release=lambda _: verifier).verify(
        output_id
    )


def test_supported_evidence_is_durable_idempotent_and_scoped_to_one_channel(semantic_store):
    provider = SyntheticVerifier()
    assert verify(semantic_store, provider)["verdict"] == "PRESERVED"
    assert verify(semantic_store, provider)["verdict"] == "PRESERVED"
    assert provider.calls == [(SOURCE, DRAFT)]
    with semantic_store() as session:
        service = RewriteOutputService(session)
        assert service.auto_approve(1, activate_candidate=True)["approval_state"] == "APPROVED"
        assert service.auto_approve(1, activate_candidate=True)["approval_state"] == "APPROVED"
        assert list(
            session.scalars(
                select(PublicationCandidateModel.state).order_by(PublicationCandidateModel.id)
            )
        ) == ["READY", "AWAITING_REWRITE"]
        with pytest.raises(PermissionError, match="SEMANTIC"):
            service.auto_approve(2, activate_candidate=True)
        assert session.scalar(select(func.count()).select_from(SemanticEvidenceModel)) == 1


@pytest.mark.parametrize(
    "relation,verdict,fail,want",
    [
        ("CONTRADICTED", "CHANGED", False, "CHANGED"),
        ("UNSUPPORTED", "CHANGED", False, "CHANGED"),
        ("UNCERTAIN", "UNCERTAIN", False, "UNCERTAIN"),
        ("SUPPORTED", "PRESERVED", True, "ERROR"),
    ],
)
def test_changed_uncertain_and_provider_error_never_autoapprove(
    semantic_store, relation, verdict, fail, want
):
    provider = SyntheticVerifier(relation=relation, verdict=verdict, fail=fail)
    result = verify(semantic_store, provider)
    assert result["verdict"] == want
    assert "synthetic-secret" not in str(result)
    with semantic_store() as session:
        with pytest.raises(PermissionError, match="SEMANTIC"):
            RewriteOutputService(session).auto_approve(1, activate_candidate=True)
        assert session.get(RewriteOutputModel, 1).approval_state == "PENDING"
        assert session.get(PublicationCandidateModel, 1).state == "AWAITING_REWRITE"


@pytest.mark.parametrize(
    "change",
    ["editorial", "hard-constraints", "source", "numeric", "manual", "release", "provider"],
)
def test_cheap_current_guards_prevent_every_verifier_call(semantic_store, change):
    provider = SyntheticVerifier()
    with semantic_store() as session:
        if change in {"editorial", "hard-constraints"}:
            decision = session.scalar(select(EditorialDecisionModel))
            if change == "editorial":
                decision.status, decision.rewrite_allowed = "REJECT", False
            else:
                decision.protected_entities, decision.sentiment = "Protected", "negative"
        elif change == "source":
            session.add(
                ContentRevisionModel(
                    incoming_post_id=1, revision_number=2, source_text="Edited source"
                )
            )
        elif change == "numeric":
            session.get(RewriteOutputModel, 1).rewritten_text = "Открыты 20 линий."
        elif change == "manual":
            AutomaticApprovalPolicyService(session).configure(1, "MANUAL")
        elif change == "release":
            session.get(SemanticVerifierReleaseModel, 1).active = False
        elif change == "provider":
            provider.model = "unqualified-model"
        session.commit()
    with pytest.raises(PermissionError):
        verify(semantic_store, provider)
    assert provider.calls == []
    with semantic_store() as session:
        assert session.scalar(select(func.count()).select_from(SemanticEvidenceModel)) == 0


@pytest.mark.parametrize("change", ["editorial", "draft", "source", "release", "manual"])
def test_changes_during_verification_invalidate_the_result(semantic_store, change):
    def mutate():
        with semantic_store() as session:
            if change == "editorial":
                decision = session.scalar(select(EditorialDecisionModel))
                decision.status, decision.rewrite_allowed = "REJECT", False
            elif change == "draft":
                session.get(RewriteOutputModel, 1).rewritten_text += " Дополнение."
            elif change == "source":
                session.add(
                    ContentRevisionModel(
                        incoming_post_id=1, revision_number=2, source_text="Edited source"
                    )
                )
            elif change == "release":
                session.get(SemanticVerifierReleaseModel, 1).active = False
            else:
                AutomaticApprovalPolicyService(session).configure(1, "MANUAL")
            session.commit()

    with pytest.raises(PermissionError):
        verify(semantic_store, SyntheticVerifier(change=mutate))
    with semantic_store() as session:
        assert session.get(RewriteOutputModel, 1).approval_state == "PENDING"
        assert session.scalar(select(func.count()).select_from(SemanticEvidenceModel)) == 0


@pytest.mark.parametrize(
    "change", ["draft", "editorial", "evidence", "release", "source", "manual", "reject"]
)
def test_stale_or_corrupted_pass_cannot_authorize_automatic_transition(semantic_store, change):
    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        if change == "draft":
            session.get(RewriteOutputModel, 1).rewritten_text += " Дополнение."
        elif change == "editorial":
            decision = session.scalar(select(EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
        elif change == "evidence":
            session.scalar(select(SemanticEvidenceModel)).evidence_json = '{"verdict":"PRESERVED"}'
        elif change == "release":
            session.get(SemanticVerifierReleaseModel, 1).active = False
        elif change == "source":
            session.add(
                ContentRevisionModel(incoming_post_id=1, revision_number=2, source_text="Edited")
            )
        elif change == "manual":
            AutomaticApprovalPolicyService(session).configure(1, "MANUAL")
        else:
            RewriteOutputService(session).reject(1)
        session.commit()
        with pytest.raises(PermissionError):
            RewriteOutputService(session).auto_approve(1, activate_candidate=True)
        assert session.get(RewriteOutputModel, 1).approval_state != "APPROVED"
        assert session.get(PublicationCandidateModel, 1).state != "READY"


def test_revoked_semantic_release_blocks_existing_automatic_plan(semantic_store):
    from newsflow.services.publication_planning import PublicationPlanningService

    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        RewriteOutputService(session).auto_approve(1, activate_candidate=True)
        planner = PublicationPlanningService(session)
        plan = planner.configure_plan(1, "AUTOMATIC", 1, (720,))
        assert len(planner.plan_day(plan["id"], date(2030, 1, 1))) == 1
        session.get(SemanticVerifierReleaseModel, 1).active = False
        session.commit()
        assert planner.plan_day(plan["id"], date(2030, 1, 1)) == []
        assert (
            planner.list_publications(plan["id"], date(2030, 1, 1))[0]["state"] == "BLOCKED_REVIEW"
        )


def test_release_identity_cannot_be_replaced_under_existing_evidence(semantic_store):
    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        session.get(SemanticVerifierReleaseModel, 1).model = "another-valid-model"
        session.commit()
        with pytest.raises(PermissionError, match="SEMANTIC"):
            RewriteOutputService(session).auto_approve(1, activate_candidate=True)


def test_cached_orm_release_does_not_hide_external_revocation(semantic_store):
    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        cached = session.get(SemanticVerifierReleaseModel, 1)
        assert cached.active is True
        with semantic_store() as external:
            external.get(SemanticVerifierReleaseModel, 1).active = False
            external.commit()
        with pytest.raises(PermissionError, match="SEMANTIC"):
            RewriteOutputService(session).auto_approve(1, activate_candidate=True)


@pytest.mark.parametrize("change", ["draft", "editorial"])
def test_cached_draft_or_editorial_cannot_hide_external_change(semantic_store, change):
    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        cached_draft = session.get(RewriteOutputModel, 1)
        cached_decision = session.scalar(select(EditorialDecisionModel))
        assert cached_draft.approval_state == "PENDING" and cached_decision.status == "PASS"
        with semantic_store() as external:
            if change == "draft":
                external.get(RewriteOutputModel, 1).rewritten_text += " Invented claim."
            else:
                decision = external.scalar(select(EditorialDecisionModel))
                decision.status, decision.rewrite_allowed = "REJECT", False
            external.commit()
        with pytest.raises(PermissionError):
            RewriteOutputService(session).auto_approve(1, activate_candidate=True)


def test_duplicate_json_keys_cannot_revive_corrupted_evidence(semantic_store):
    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        evidence = session.scalar(select(SemanticEvidenceModel))
        evidence.evidence_json = evidence.evidence_json.replace(
            '"source_complete": true', '"source_complete": false, "source_complete": true'
        )
        session.commit()
        with pytest.raises(PermissionError, match="SEMANTIC"):
            RewriteOutputService(session).auto_approve(1, activate_candidate=True)


@pytest.mark.parametrize("change", ["draft", "source"])
def test_current_approval_reloads_cached_content_at_point_of_use(semantic_store, change):
    from newsflow.services.automatic_approval import approval_is_current

    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        RewriteOutputService(session).auto_approve(1)
        cached = session.get(RewriteOutputModel, 1)
        cached_source = session.get(ContentRevisionModel, 1)
        assert approval_is_current(session, cached) is True
        assert cached_source.source_text == SOURCE
        with semantic_store() as external:
            if change == "draft":
                external.get(RewriteOutputModel, 1).rewritten_text += " Invented claim."
            else:
                external.get(ContentRevisionModel, 1).source_text += " Another fact."
            external.commit()
        assert approval_is_current(session, cached) is False


def test_approved_automatic_output_does_not_hide_a_stale_failed_rewrite_job(semantic_store):
    from newsflow.services.automatic_approval import approval_is_current
    from newsflow.services.publication_planning import PublicationPlanningService

    verify(semantic_store, SyntheticVerifier())
    with semantic_store() as session:
        RewriteOutputService(session).auto_approve(1, activate_candidate=True)
        session.get(RewriteJobModel, 1).state = "FAILED"
        session.commit()
        assert approval_is_current(session, session.get(RewriteOutputModel, 1)) is False
        planner = PublicationPlanningService(session)
        plan = planner.configure_plan(1, "AUTOMATIC", 1, (720,))
        assert planner.plan_day(plan["id"], date(2030, 1, 1)) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("active", False),
        ("model", "openrouter/free"),
        ("prompt_version", "unknown"),
        ("benchmark_version", "unknown"),
        ("report_sha256", "z" * 64),
    ],
)
def test_unqualified_or_unknown_version_release_cannot_enable_automatic_mode(
    semantic_store, field, value
):
    with semantic_store() as session:
        AutomaticApprovalPolicyService(session).configure(1, "MANUAL")
        setattr(session.get(SemanticVerifierReleaseModel, 1), field, value)
        session.commit()
        with pytest.raises(PermissionError, match="QUALIFIED"):
            AutomaticApprovalPolicyService(session).configure(1, "VERIFIED", 1)
        assert AutomaticApprovalPolicyService(session).get_policy(1)["mode"] == "MANUAL"
