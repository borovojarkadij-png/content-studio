"""Diagnostic admission from migrated canonical SQL, without provider IO."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
from importlib import import_module
from os import getenv
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.telegram_configuration import TelegramConfigurationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)
CHANNEL = -1001234567890
KEY = f"1:{CHANNEL}:7:revision:1"
MESSAGE = TelegramMessage("1", str(CHANNEL), 7, "Synthetic civic report")


@pytest.fixture
def store(tmp_path, monkeypatch):
    supplied = getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL")
    url = (
        create_postgres_namespace(supplied)
        if supplied is not None
        else f"sqlite:///{tmp_path / 'admission.db'}"
    )
    monkeypatch.setenv("DATABASE_URL", url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    with Session(engine) as session:
        session.add(
            models.TelegramAccount(name="Synthetic", telegram_user_id=1001, encrypted_session="")
        )
        session.commit()
        service = TelegramConfigurationService(session)
        donor = service.create_donor(1, CHANNEL, "Synthetic donor")
        output = service.create_output(1, CHANNEL - 1, "Synthetic output")
        mapping = service.create_mapping(donor["id"], output["id"], 100, 100)
        if hasattr(models, "EditorialClassifierPolicyModel"):
            session.add(
                models.EditorialClassifierPolicyModel(
                    id=1,
                    enabled=True,
                    provider="OPENAI",
                    model="synthetic-explicit-model",
                    policy_version="synthetic-v1",
                    protected_entities=[
                        {"entity_id": "synthetic-council", "aliases": ["Civic Council"]}
                    ],
                )
            )
        session.commit()
    yield engine, mapping["id"]
    engine.dispose()


def api():
    return import_module("newsflow.services.editorial_admission")


def ingest(store, message=MESSAGE, **kwargs):
    engine, mapping = store
    with Session(engine) as session:
        return DurableIngestionWorkflow(session, configured_mapping_id=mapping).ingest(
            message, observed_at=NOW, **kwargs
        )


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def diagnostic_events(session):
    return session.scalars(
        select(models.OutboxEventModel).where(
            models.OutboxEventModel.event_type == "editorial.classification.requested"
        )
    ).all()


def test_mapped_unknown_queues_one_durable_diagnostic_and_reopens_terminal_history(store):
    assert "editorial_classification_jobs" in inspect(store[0]).get_table_names(), (
        "Migrated storage must retain diagnostic classification requests"
    )
    assert ingest(store).status == "MANUAL_REVIEW"
    assert ingest(store).status == "MANUAL_REVIEW"
    engine, mapping = store
    with Session(engine) as session:
        job = session.scalar(select(models.EditorialClassificationJobModel))
        assert job is not None
        assert (job.content_key, job.state, job.attempts) == (KEY, "QUEUED", 0)
        assert job.claim_token is job.lease_expires_at is None
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert (decision.status, decision.rewrite_allowed) == ("MANUAL_REVIEW", False)
        assert count(session, models.RewriteJobModel) == 0
        assert count(session, models.PublicationCandidateModel) == 0
        fingerprint = session.scalar(select(models.MappingContentFingerprintModel))
        assert fingerprint.content_key == KEY
        (outbox,) = diagnostic_events(session)
        assert outbox.event_type == "editorial.classification.requested"
        assert outbox.aggregate_key == KEY
        assert outbox.idempotency_key == "editorial.classification.requested:" + job.idempotency_key
        identity = job.id
        job.state = "REJECT"
        session.commit()
    reopened = create_engine(engine.url)
    with Session(reopened) as session:
        job = api().enqueue_editorial_classification(
            session, content_key=KEY, mapping_id=mapping, now=NOW
        )
        assert (job.id, job.state) == (identity, "REJECT")
        session.commit()
    reopened.dispose()
    with Session(engine) as session:
        assert count(session, models.EditorialClassificationJobModel) == 1
        assert len(diagnostic_events(session)) == 1


@pytest.mark.parametrize("mode", ["missing", "disabled"])
def test_absent_or_disabled_policy_keeps_manual_behavior(store, mode):
    with Session(store[0]) as session:
        policy = session.get(models.EditorialClassifierPolicyModel, 1)
        if mode == "missing":
            session.delete(policy)
        else:
            policy.enabled = False
        session.commit()
    assert ingest(store).status == "MANUAL_REVIEW"
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 0
        assert diagnostic_events(session) == []


@pytest.mark.parametrize(
    "change",
    [
        {"media_type": "video"},
        {"album_id": "42"},
        {"text": "Watch youtu.be/synthetic"},
        {"link_destinations": ("https://youtube.com/watch?v=synthetic",)},
        {"text": "Synthetic #ad"},
        {"media_type": "unknown"},
    ],
)
def test_cheap_holds_never_enqueue(store, change):
    ingest(store, replace(MESSAGE, **change))
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 0
        assert count(session, models.RewriteJobModel) == 0


def test_protected_reject_and_actual_duplicate_do_not_enqueue(store):
    ingest(store, protected_entities=["synthetic"], sentiment="negative", framing="hostile")
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 0
        assert count(session, models.RewriteJobModel) == 0
    assert ingest(store, replace(MESSAGE, message_id=8)).status == "REJECTED_DUPLICATE"


def test_same_text_different_message_reserves_only_first_request(store):
    ingest(store)
    assert ingest(store, replace(MESSAGE, message_id=8)).status == "REJECTED_DUPLICATE"
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "reject",
        "pass",
        "permission",
        "unknown",
        "absent_decision",
        "rewrite",
        "owner_null",
        "owner_other",
        "fingerprint_missing",
        "foreign_channel",
        "foreign_account",
        "missing_output",
        "missing_output_owner",
        "missing_donor",
        "missing_donor_owner",
        "video",
        "album",
        "unknown_media",
        "invalid_media",
        "hidden_youtube",
        "unknown_links",
        "corrupt_links",
        "advertisement",
        "filter",
        "sample",
        "stale",
        "deleted",
        "sync",
    ],
)
def test_canonical_guard_blocks_without_mutating_history(store, mutation, monkeypatch):
    ingest(store)
    engine, mapping = store
    with Session(engine) as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        revision = session.scalar(select(models.ContentRevisionModel))
        post = session.scalar(select(models.IncomingPostModel))
        fingerprint = session.scalar(select(models.MappingContentFingerprintModel))
        mapping_row = session.get(models.ChannelMappingModel, mapping)
        if mutation in {"reject", "pass", "unknown"}:
            decision.status = {"reject": "REJECT", "pass": "PASS", "unknown": "CORRUPT"}[mutation]
        elif mutation == "permission":
            decision.rewrite_allowed = True
        elif mutation == "absent_decision":
            # RESTRICT requires a separate unknown source, not deleting retained job history.
            decision.content_key = "unrelated"
        elif mutation == "rewrite":
            session.add(
                models.RewriteJobModel(content_key=KEY, idempotency_key="synthetic", state="QUEUED")
            )
        elif mutation.startswith("owner_"):
            fingerprint.content_key = None if mutation == "owner_null" else "another-source"
        elif mutation == "fingerprint_missing":
            session.delete(fingerprint)
        elif mutation == "foreign_channel":
            session.get(models.DonorChannel, mapping_row.donor_channel_id).telegram_channel_id -= 5
        elif mutation == "foreign_account":
            post.telegram_account_id = "foreign"
        elif mutation in {
            "missing_output",
            "missing_donor",
            "missing_output_owner",
            "missing_donor_owner",
        }:
            # Inject a missing storage read: PostgreSQL FKs prevent manufacturing
            # committed orphan rows. All other SQL resolution remains real.
            missing_model = models.TelegramAccount
            missing_id = 1
            if mutation == "missing_output":
                missing_model, missing_id = models.OutputChannel, mapping_row.output_channel_id
            elif mutation == "missing_donor":
                missing_model, missing_id = models.DonorChannel, mapping_row.donor_channel_id
            else:
                if mutation == "missing_output_owner":
                    session.add(
                        models.TelegramAccount(
                            name="Second synthetic", telegram_user_id=2, encrypted_session=""
                        )
                    )
                    session.flush()
                    session.get(
                        models.OutputChannel, mapping_row.output_channel_id
                    ).telegram_account_id = 2
                    session.commit()
                    missing_id = 2
            original_get = session.get

            def missing_get(model, identity, **kwargs):
                return (
                    None
                    if model is missing_model and identity == missing_id
                    else original_get(model, identity, **kwargs)
                )

            monkeypatch.setattr(session, "get", missing_get)
            assert (
                api().enqueue_editorial_classification(
                    session, content_key=KEY, mapping_id=mapping, now=NOW
                )
                is None
            )
            return
        elif mutation in {"video", "unknown_media", "invalid_media"}:
            revision.media_type = (
                "video"
                if mutation == "video"
                else "unknown"
                if mutation == "unknown_media"
                else "text"
            )
            if mutation == "invalid_media":
                revision.media_id = "123"
        elif mutation == "album":
            revision.album_id = "42"
        elif mutation in {"hidden_youtube", "unknown_links", "corrupt_links"}:
            revision.link_destinations = {
                "hidden_youtube": ["https://youtu.be/synthetic"],
                "unknown_links": None,
                "corrupt_links": {"bad": "shape"},
            }[mutation]
        elif mutation == "advertisement":
            revision.source_text += " #ad"
        elif mutation == "filter":
            session.add(
                models.MappingFilterPolicyModel(
                    mapping_id=mapping, allowed_media_types=[], blocked_domains=[], ad_markers=[]
                )
            )
        elif mutation == "sample":
            mapping_row.intake_percent = 0
        elif mutation == "stale":
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post.id,
                    revision_number=2,
                    source_text="new",
                    link_destinations=[],
                )
            )
        elif mutation == "deleted":
            session.add(
                models.SourceDeletionModel(
                    telegram_account_id="1",
                    donor_channel_id=str(CHANNEL),
                    telegram_message_id=7,
                    latest_pts=1,
                    observed_at=NOW,
                )
            )
        elif mutation == "sync":
            session.add(
                models.ChannelDifferenceCursorModel(
                    donor_channel_id=mapping_row.donor_channel_id,
                    telegram_account_id=1,
                    telegram_user_id=1001,
                    telegram_channel_id=CHANNEL,
                    pts=1,
                    available_at=NOW,
                    last_error_code="GAP_UNRESOLVED",
                )
            )
        session.commit()
    with Session(engine) as session:
        assert (
            api().enqueue_editorial_classification(
                session, content_key=KEY, mapping_id=mapping, now=NOW
            )
            is None
        )
        assert count(session, models.EditorialClassificationJobModel) == 1
        assert len(diagnostic_events(session)) == 1


@pytest.mark.parametrize(
    "policy",
    [
        None,
        {},
        "bad",
        ["bad"],
        [{"entity_id": "x", "aliases": ["x"], "extra": 1}],
        [{"entity_id": "x", "aliases": "x"}],
        [{"entity_id": "x", "aliases": ["x"]}, {"entity_id": "x", "aliases": ["y"]}],
        [{"entity_id": "x", "aliases": ["same"]}, {"entity_id": "y", "aliases": ["SAME"]}],
        [{"entity_id": "x", "aliases": ["x" * 262145]}],
    ],
)
def test_invalid_explicit_policy_never_repairs_to_neutral(store, policy):
    with Session(store[0]) as session:
        session.get(models.EditorialClassifierPolicyModel, 1).protected_entities = policy
        session.commit()
    ingest(store)
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 0


@pytest.mark.parametrize(
    "provider,model,allowed",
    [
        ("OPENAI", "synthetic", True),
        ("OPENROUTER", "synthetic/model:free", True),
        ("OPENROUTER", "openrouter/free", False),
        ("OPENROUTER", "synthetic/paid", False),
        ("OPENROUTER", "a:free,b:free", False),
        ("OPENAI", "  ", False),
        ("OPENAI", "x" * 256, False),
    ],
)
def test_explicit_provider_model_contract(store, provider, model, allowed):
    ingest(store)
    with Session(store[0]) as session:
        policy = session.get(models.EditorialClassifierPolicyModel, 1)
        policy.provider, policy.model = provider, model
        if not model.strip() or len(model) > 255:
            expected = (
                DataError
                if session.get_bind().dialect.name == "postgresql" and len(model) > 255
                else IntegrityError
            )
            with pytest.raises(expected):
                session.commit()
        else:
            session.commit()
            if allowed:
                assert (
                    api()
                    .resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
                    .model
                    == model
                )
            else:
                assert (
                    api().enqueue_editorial_classification(
                        session, content_key=KEY, mapping_id=store[1], now=NOW
                    )
                    is None
                )


@pytest.mark.parametrize(
    "key,mapping,now",
    [
        ("", 1, NOW),
        ("x" * 256, 1, NOW),
        (None, 1, NOW),
        (KEY, True, NOW),
        (KEY, 0, NOW),
        (KEY, "1", NOW),
        (KEY, 1, datetime(2030, 1, 1)),
        (KEY, 1, None),
        (KEY, 1, datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1)))),
    ],
)
def test_invalid_caller_inputs_never_write(store, key, mapping, now):
    with Session(store[0]) as session:
        assert (
            api().enqueue_editorial_classification(
                session, content_key=key, mapping_id=mapping, now=now
            )
            is None
        )
        assert count(session, models.EditorialClassificationJobModel) == 0


def test_explicit_cross_account_output_binds_both_owners(store):
    ingest(store)
    with Session(store[0]) as session:
        first = api().resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        session.add(
            models.TelegramAccount(
                name="Synthetic second", telegram_user_id=2002, encrypted_session=""
            )
        )
        session.flush()
        session.get(models.OutputChannel, 1).telegram_account_id = 2
        session.commit()
        second = api().resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        assert second.mapping_sha256 != first.mapping_sha256
        assert second.request.source_sha256 == sha256(MESSAGE.text.encode()).hexdigest()


@pytest.mark.parametrize("change", ["policy", "filter", "source", "deletion"])
def test_retained_session_uses_fresh_canonical_authority(store, change):
    ingest(store)
    engine, mapping = store
    with Session(engine, expire_on_commit=False) as retained:
        original = api().resolve_editorial_admission(retained, content_key=KEY, mapping_id=mapping)
        retained.commit()
        with Session(engine) as independent:
            if change == "policy":
                independent.get(
                    models.EditorialClassifierPolicyModel, 1
                ).policy_version = "synthetic-v2"
            elif change == "filter":
                independent.add(
                    models.MappingFilterPolicyModel(
                        mapping_id=mapping,
                        allowed_media_types=[],
                        blocked_domains=[],
                        ad_markers=[],
                    )
                )
            elif change == "source":
                independent.scalar(select(models.ContentRevisionModel)).source_text = "changed"
            else:
                independent.add(
                    models.SourceDeletionModel(
                        telegram_account_id="1",
                        donor_channel_id=str(CHANNEL),
                        telegram_message_id=7,
                        latest_pts=1,
                        observed_at=NOW,
                    )
                )
            independent.commit()
        if change == "policy":
            current = api().resolve_editorial_admission(
                retained, content_key=KEY, mapping_id=mapping
            )
            assert current.request.policy_sha256 != original.request.policy_sha256
        else:
            assert (
                api().enqueue_editorial_classification(
                    retained, content_key=KEY, mapping_id=mapping, now=NOW
                )
                is None
            )


@pytest.mark.parametrize("table", ["editorial_classification_jobs", "outbox_events"])
def test_insert_failure_rolls_back_entire_ingress_and_fresh_retry(store, table):
    engine, _ = store

    def fail(connection, cursor, statement, parameters, context, many):
        bound = parameters.values() if isinstance(parameters, dict) else parameters
        if statement.lstrip().upper().startswith("INSERT INTO " + table.upper()) and (
            table != "outbox_events" or "editorial.classification.requested" in bound
        ):
            raise IntegrityError("synthetic storage failure", None, Exception("synthetic"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(IntegrityError):
            ingest(store)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with Session(engine) as session:
        for model in (
            models.IncomingPostModel,
            models.ContentRevisionModel,
            models.MappingContentFingerprintModel,
            models.EditorialDecisionModel,
            models.EditorialClassificationJobModel,
            models.OutboxEventModel,
        ):
            assert count(session, model) == 0
    ingest(store)
    with Session(engine) as session:
        assert count(session, models.EditorialClassificationJobModel) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"source_text": "x" * 32001},
        {"source_text": ""},
        {"link_destinations": ["https://forbidden.example/article"]},
        {"media_protected": True},
    ],
)
def test_stored_source_bounds_and_forbidden_links_fail_closed(store, change):
    ingest(store)
    with Session(store[0]) as session:
        revision = session.scalar(select(models.ContentRevisionModel))
        for name, value in change.items():
            setattr(revision, name, value)
        session.add(
            models.MappingFilterPolicyModel(
                mapping_id=store[1],
                allowed_media_types=["text", "photo"],
                blocked_domains=["forbidden.example"],
                ad_markers=[],
            )
        )
        session.commit()
        assert (
            api().enqueue_editorial_classification(
                session, content_key=KEY, mapping_id=store[1], now=NOW
            )
            is None
        )


def test_canonical_source_identity_is_not_delimiter_parsing_or_ambiguous(store):
    ingest(store)
    with Session(store[0]) as session:
        for account, channel in (("synthetic:a", "b"), ("synthetic", "a:b")):
            post = models.IncomingPostModel(
                telegram_account_id=account,
                donor_channel_id=channel,
                telegram_message_id=7,
                state="MANUAL_REVIEW",
            )
            session.add(post)
            session.flush()
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post.id,
                    revision_number=1,
                    source_text="synthetic collision",
                    media_type="text",
                    link_destinations=[],
                )
            )
        session.commit()
        # Two persisted identities produce the same SQL key; neither wins.
        with pytest.raises(api().EditorialAdmissionBlocked) as ambiguous:
            api().resolve_editorial_admission(
                session, content_key="synthetic:a:b:7:revision:1", mapping_id=store[1]
            )
        assert ambiguous.value.reason_code == "ADMISSION_SOURCE_INVALID"
        assert (
            api().enqueue_editorial_classification(
                session,
                content_key="1:-1001234567890:7:revision:1:revision:1",
                mapping_id=store[1],
                now=NOW,
            )
            is None
        )
        with pytest.raises(api().EditorialAdmissionBlocked) as blocked:
            api().resolve_editorial_admission(session, content_key=KEY, mapping_id=99999)
        assert str(blocked.value) == "ADMISSION_MAPPING_INVALID"
        assert MESSAGE.text not in str(blocked.value)


def test_latest_edit_queues_new_binding_and_stale_replay_adds_nothing(store):
    first = replace(MESSAGE, source_updated_at=NOW)
    ingest(store, first)
    changed = replace(
        first,
        text="Synthetic revised civic report",
        is_edit=True,
        source_updated_at=NOW + timedelta(seconds=1),
    )
    assert ingest(store, changed).status == "MANUAL_REVIEW"
    assert ingest(store, first).status == "REJECTED_STALE_SOURCE"
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 2
        assert len(diagnostic_events(session)) == 2
        assert (
            api().enqueue_editorial_classification(
                session, content_key=KEY, mapping_id=store[1], now=NOW
            )
            is None
        )


def test_prototype_ingestion_and_existing_decision_branch_do_not_activate_policy(store):
    with Session(store[0]) as session:
        result = DurableIngestionWorkflow(session).ingest(MESSAGE, observed_at=NOW)
        assert result.status == "MANUAL_REVIEW"
    assert ingest(store).status == "MANUAL_REVIEW"
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 0


def test_diagnostic_path_never_calls_classifier_or_rewrite_transports(store, monkeypatch):
    from newsflow.providers.editorial_classifier import (
        FreeOpenRouterEditorialClassifier,
        OpenAIEditorialClassifier,
    )
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider

    def forbidden(*args, **kwargs):
        pytest.fail("Diagnostic admission must never construct a provider or call IO")

    for cls in (
        FreeOpenRouterEditorialClassifier,
        OpenAIEditorialClassifier,
        OpenAIRewriteProvider,
        StructuredFreeOpenRouterProvider,
    ):
        monkeypatch.setattr(cls, "__init__", forbidden)
    ingest(store)
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 1
        assert count(session, models.RewriteJobModel) == 0


@pytest.mark.parametrize("change", [{"account_id": "2"}, {"donor_identifier": str(CHANNEL - 8)}])
def test_incoming_source_must_match_actual_mapped_donor(store, change):
    assert ingest(store, replace(MESSAGE, **change)).status == "MANUAL_REVIEW"
    with Session(store[0]) as session:
        assert count(session, models.EditorialClassificationJobModel) == 0
        assert diagnostic_events(session) == []


@pytest.mark.parametrize(
    "change",
    [
        {"target_mix_percent": 25},
        {"eligibility_mode": "DELAYED", "delay_minutes": 5},
        {"priority": 3},
        {"media_policy": "LICENSED_LIBRARY"},
        {"intake_percent": 99},
    ],
)
def test_mapping_policy_changes_derive_new_binding_internally(store, change):
    ingest(store)
    with Session(store[0]) as session:
        original = api().resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        row = session.get(models.ChannelMappingModel, store[1])
        for name, value in change.items():
            setattr(row, name, value)
        session.commit()
        current = api().resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        assert current.mapping_sha256 != original.mapping_sha256
        assert current.request.source_sha256 == original.request.source_sha256


def test_effective_filter_sets_have_deterministic_digest_including_actual_ad_markers(store):
    ingest(store)
    with Session(store[0]) as session:
        baseline = api().resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        row = models.MappingFilterPolicyModel(
            mapping_id=store[1],
            allowed_media_types=["text", "photo"],
            blocked_domains=["b.example", "a.example"],
            ad_markers=["Synthetic Sponsor", "Synthetic Promotion"],
        )
        session.add(row)
        session.commit()
        original = api().resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        assert original.mapping_sha256 != baseline.mapping_sha256
        row.allowed_media_types = ["photo", "text"]
        row.blocked_domains = ["a.example", "b.example"]
        row.ad_markers = ["synthetic promotion", "synthetic sponsor"]
        session.commit()
        reordered = api().resolve_editorial_admission(session, content_key=KEY, mapping_id=store[1])
        assert reordered.mapping_sha256 == original.mapping_sha256


def test_invalid_unicode_in_stored_filter_blocks_with_sanitized_reason(store):
    ingest(store)
    with Session(store[0]) as session:
        session.add(
            models.MappingFilterPolicyModel(
                mapping_id=store[1],
                allowed_media_types=["text"],
                blocked_domains=[],
                ad_markers=["\ud800"],
            )
        )
        session.commit()
        assert (
            api().enqueue_editorial_classification(
                session, content_key=KEY, mapping_id=store[1], now=NOW
            )
            is None
        )
        assert count(session, models.EditorialClassificationJobModel) == 1
        assert len(diagnostic_events(session)) == 1
