from datetime import timedelta

import pytest
from sqlalchemy import select
from test_configured_text_publication import CIPHER
from test_publication_preflight import seed_plan
from test_publication_runner import Publisher
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store

from newsflow import worker
from newsflow.persistence import models
from newsflow.services.durable_publication_runner import DurablePublicationRunner

source_store = _source_store


def tick(factory, **kwargs):
    assert hasattr(worker, "run_publication_tick"), "Guarded publication tick is missing"
    return worker.run_publication_tick(factory, **kwargs)


def test_disabled_tick_never_opens_database_or_constructs_provider():
    def forbidden():
        raise AssertionError("Disabled publication must not access storage")

    result = tick(forbidden, enabled=False, cipher=None, media_root=None, now=NOW)
    assert result.outcome == "DISABLED" and result.queued_ids == ()


@pytest.mark.parametrize("cipher", [None, CIPHER])
def test_enabled_tick_requires_explicit_stable_key_and_credentials_before_database(cipher):
    def forbidden():
        raise AssertionError("Missing publication credentials must not access storage")

    with pytest.raises(ValueError):
        tick(forbidden, enabled=True, cipher=cipher, media_root=None, now=NOW)


def test_opt_in_tick_enqueues_and_commits_one_due_publication_once(source_store):
    seed_plan(source_store)
    sender = Publisher()
    kwargs = {
        "enabled": True,
        "cipher": CIPHER,
        "media_root": source_store[1],
        "now": NOW,
        "publisher": sender,
        "clock": lambda: NOW,
    }
    result = tick(source_store[0], **kwargs)
    assert result.outcome == "SUCCEEDED" and result.queued_ids == (1,)
    assert tick(source_store[0], **kwargs).outcome == "IDLE" and len(sender.calls) == 1
    with source_store[0]() as session:
        assert session.scalar(select(models.PublicationJobModel)).sent_message_id == 101


def test_future_or_expired_plans_never_create_send_intents(source_store):
    seed_plan(source_store)
    sender = Publisher()
    with source_store[0].begin() as session:
        session.get(models.PlannedPublicationModel, 1).scheduled_for = NOW + timedelta(minutes=1)
    assert (
        tick(
            source_store[0],
            enabled=True,
            cipher=CIPHER,
            media_root=source_store[1],
            now=NOW,
            publisher=sender,
            clock=lambda: NOW,
        ).outcome
        == "IDLE"
    )
    late = NOW + timedelta(hours=7)
    assert (
        tick(
            source_store[0],
            enabled=True,
            cipher=CIPHER,
            media_root=source_store[1],
            now=late,
            publisher=sender,
            clock=lambda: late,
        ).outcome
        == "IDLE"
    )
    assert not sender.calls
    with source_store[0]() as session:
        assert session.scalar(select(models.PublicationJobModel)) is None


def test_bounded_admission_cursor_prevents_stale_first_plan_starving_next(source_store):
    seed_plan(source_store)
    with source_store[0].begin() as session:
        # Move the good reservation behind an unsupported legacy candidate.
        session.get(models.PlannedPublicationModel, 1).id = 3
        session.add(
            models.PublicationCandidateModel(
                id=2,
                output_channel_id=1,
                content_key="synthetic:missing",
                priority=1,
                state="SCHEDULED",
                eligible_at=NOW,
            )
        )
        session.flush()
        session.add(
            models.PlannedPublicationModel(
                id=1,
                candidate_id=2,
                output_channel_id=1,
                scheduled_for=NOW - timedelta(seconds=1),
                state="PLANNED",
            )
        )
    sender = Publisher()
    kwargs = {
        "enabled": True,
        "cipher": CIPHER,
        "media_root": source_store[1],
        "now": NOW,
        "publisher": sender,
        "clock": lambda: NOW,
        "admission_limit": 1,
    }
    first = tick(source_store[0], **kwargs)
    assert first.outcome == "IDLE" and first.blocked_ids == (1,) and first.cursor == 1
    second = tick(source_store[0], cursor=first.cursor, **kwargs)
    assert second.outcome == "SUCCEEDED" and second.queued_ids == (3,) and len(sender.calls) == 1
    # Cursor is only scanning progress; restart/wrap cannot lose durable intents.
    assert tick(source_store[0], cursor=second.cursor, **kwargs).blocked_ids == (1,)


def test_rejected_due_plan_and_existing_uncertain_intent_do_not_send(source_store):
    seed_plan(source_store)
    sender = Publisher(failure=TimeoutError("synthetic lost response"))
    execution = DurablePublicationRunner(*source_store, publisher=sender, clock=lambda: NOW)
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    result = tick(
        source_store[0],
        enabled=True,
        cipher=CIPHER,
        media_root=source_store[1],
        now=NOW,
        publisher=sender,
        clock=lambda: NOW,
    )
    assert result.outcome == "IDLE" and result.queued_ids == () and len(sender.calls) == 1


@pytest.mark.parametrize("kind", ["text", "photo"])
def test_tick_with_encrypted_dispatcher_selects_correct_real_tl_request(source_store, kind):
    from telethon.tl.functions.messages import SendMediaRequest, SendMessageRequest
    from test_configured_photo_publication import photo_setup
    from test_configured_text_publication import ReceiptClient, setup

    from newsflow.services.telegram_publication_factory import ConfiguredTelegramPublisher

    if kind == "photo":
        client, _ = photo_setup(source_store)
    else:
        client = setup(source_store, ReceiptClient())
        client.factory = source_store[0]
    sender = ConfiguredTelegramPublisher(
        *source_store,
        cipher=CIPHER,
        api_id=123,
        api_hash="a" * 32,
        client_factory=lambda _: client,
    )
    result = tick(
        source_store[0],
        enabled=True,
        cipher=CIPHER,
        media_root=source_store[1],
        now=NOW,
        publisher=sender,
        clock=lambda: NOW,
    )
    assert result.outcome == "SUCCEEDED"
    assert len(client.requests) == 1
    assert isinstance(
        client.requests[0], SendMediaRequest if kind == "photo" else SendMessageRequest
    )


@pytest.mark.parametrize("cursor,limit", [(-1, 16), (True, 16), (0, 0), (0, 65), (0, True)])
def test_invalid_admission_parameters_cannot_mutate_jobs(source_store, cursor, limit):
    seed_plan(source_store)
    sender = Publisher()
    with pytest.raises(ValueError):
        tick(
            source_store[0],
            enabled=True,
            cipher=CIPHER,
            media_root=source_store[1],
            now=NOW,
            publisher=sender,
            clock=lambda: NOW,
            cursor=cursor,
            admission_limit=limit,
        )
    assert not sender.calls
    with source_store[0]() as session:
        assert session.scalar(select(models.PublicationJobModel)) is None
