"""Synthetic qualifications exercise guards, never qualify operational models."""

from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
    SemanticEvidenceModel,
    SemanticVerifierReleaseModel,
    TelegramAccount,
)
from newsflow.services.automatic_approval import AutomaticApprovalPolicyService
from newsflow.services.rewrite_outputs import RewriteOutputService

SOURCE = "Завод открыл 3 линии."
DRAFT = "Открыты 3 линии на заводе."
KEY = "synthetic:@semantic:1:revision:1"


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


@pytest.fixture
def semantic_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'semantic.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as session:
        account = TelegramAccount(name="synthetic", telegram_user_id=1001, encrypted_session="")
        session.add(account)
        session.flush()
        channels = [
            OutputChannel(
                telegram_account_id=account.id,
                telegram_channel_id=-1000000000000 - n,
                title=f"synthetic-{n}",
            )
            for n in (1, 2)
        ]
        post = IncomingPostModel(
            telegram_account_id="synthetic",
            donor_channel_id="@semantic",
            telegram_message_id=1,
            state="RECEIVED",
        )
        release = SemanticVerifierReleaseModel(
            provider="OPENAI",
            model="synthetic-model",
            prompt_version="semantic-facts-v1",
            benchmark_version="semantic-facts-v1",
            report_sha256="f" * 64,
            active=True,
        )
        session.add_all(
            [
                *channels,
                post,
                release,
                EditorialDecisionModel(
                    content_key=KEY,
                    status="PASS",
                    rewrite_allowed=True,
                    sentiment="neutral",
                    framing="neutral",
                ),
            ]
        )
        session.flush()
        session.add(
            ContentRevisionModel(incoming_post_id=post.id, revision_number=1, source_text=SOURCE)
        )
        for channel in channels:
            job = RewriteJobModel(
                content_key=KEY,
                output_channel_id=channel.id,
                idempotency_key=f"synthetic-{channel.id}",
                state="SUCCEEDED",
            )
            session.add(job)
            session.flush()
            session.add_all(
                [
                    RewriteOutputModel(
                        rewrite_job_id=job.id,
                        output_channel_id=channel.id,
                        content_key=KEY,
                        rewritten_text=DRAFT,
                        approval_state="PENDING",
                    ),
                    PublicationCandidateModel(
                        output_channel_id=channel.id,
                        content_key=KEY,
                        priority=10,
                        state="AWAITING_REWRITE",
                    ),
                ]
            )
        session.commit()
        for channel in channels:
            AutomaticApprovalPolicyService(session).configure(channel.id, "VERIFIED", release.id)
    yield factory
    engine.dispose()


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
