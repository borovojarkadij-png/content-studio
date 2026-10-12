"""Bounded diagnostics through migrated synthetic storage and the actual worker loop."""

import io
import json
from dataclasses import replace
from datetime import datetime
from functools import partial
from urllib.error import URLError

import pytest
import test_editorial_admission as admission_tests
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_editorial_admission import KEY, MESSAGE, NOW, count, ingest
from test_openai_rewrite_provider import envelope
from test_openrouter_structured import reply

from newsflow import worker
from newsflow.persistence import models
from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider
from newsflow.services.editorial_admission import resolve_editorial_admission

store = admission_tests.store


class Cipher:
    def __init__(self, callback=None):
        self.calls = 0
        self.callback = callback

    def decrypt(self, value):
        self.calls += 1
        assert value == "synthetic-ciphertext"
        if self.callback:
            self.callback()
        return "synthetic-private-key"


def configured(store, provider="OPENAI"):
    engine, mapping = store
    with Session(engine) as session:
        policy = session.get(models.EditorialClassifierPolicyModel, 1)
        policy.provider = provider
        policy.model = "synthetic-explicit-model" if provider == "OPENAI" else "a/model:free"
        session.add(
            models.RewriteProviderSettingModel(
                provider=provider,
                encrypted_api_key="synthetic-ciphertext",
                primary_model="different-rewrite-model",
                fallback_models="different/fallback:free,another/fallback:free",
            )
        )
        session.commit()
    ingest(store)
    with Session(engine) as session:
        binding = resolve_editorial_admission(session, content_key=KEY, mapping_id=mapping)
    return sessionmaker(engine), binding


class Http:
    def __init__(self, binding, *, error=None, assert_closed=lambda: None):
        self.binding, self.error, self.assert_closed = binding, error, assert_closed
        self.requests = []

    def __call__(self, request, *, timeout):
        self.assert_closed()
        self.requests.append(json.loads(request.data))
        assert 0 < timeout <= 15
        if self.error:
            raise self.error
        binding = self.binding
        req = binding.request
        evidence = {
            "content_key": KEY,
            "source_sha256": req.source_sha256,
            "policy_sha256": req.policy_sha256,
            "prompt_version": "editorial-classification-v1",
            "source_complete": True,
            "ambiguous": False,
            "sentiment": "neutral",
            "framing": "neutral",
            "entity_findings": [],
        }
        body = envelope() if binding.provider == "OPENAI" else reply()
        body["model"] = binding.model
        if binding.provider == "OPENAI":
            body["output"][0]["content"][0]["text"] = json.dumps(evidence)
        else:
            body["choices"][0]["message"]["content"] = json.dumps(evidence)
        return io.BytesIO(json.dumps(body).encode())


@pytest.fixture(autouse=True)
def fixed_clock_and_no_rewrite(monkeypatch):
    if hasattr(worker, "DurableEditorialRunner"):
        monkeypatch.setattr(
            worker,
            "DurableEditorialRunner",
            partial(worker.DurableEditorialRunner, clock=lambda: NOW),
        )
    for provider in (OpenAIRewriteProvider, StructuredFreeOpenRouterProvider):
        monkeypatch.setattr(provider, "rewrite", lambda *a, **k: pytest.fail("rewrite called"))


def tick(*args, **kwargs):
    return worker.run_editorial_classification_tick(*args, **kwargs)


def test_bounded_tick_commits_review_history_without_rewrite(store):
    factory, binding = configured(store)
    cipher, http = Cipher(), Http(binding)
    assert tick(factory, enabled=True, cipher=cipher, now=NOW, opener=http) == "REVIEW"
    assert len(http.requests) == cipher.calls == 1
    with factory() as session:
        assert session.scalar(select(models.EditorialClassificationJobModel)).state == "REVIEW"
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert (decision.status, decision.rewrite_allowed) == ("MANUAL_REVIEW", False)
        assert count(session, models.RewriteJobModel) == 0
        assert count(session, models.EditorialClassificationClaimModel) == 1
        attempt = session.scalar(select(models.EditorialClassificationAttemptModel))
        assert (attempt.outcome, attempt.diagnostic_status, attempt.usage_observed) == (
            "REVIEW",
            "PASS",
            True,
        )
        assert (attempt.input_tokens, attempt.output_tokens) == (100, 20)
        assert attempt.reason_codes == ["REAL_MODEL_NOT_QUALIFIED"]
        assert (
            session.scalar(
                select(models.OutboxEventModel.id).where(
                    models.OutboxEventModel.event_type == "editorial.classification.attempted"
                )
            )
            is not None
        )
    assert tick(factory, enabled=True, cipher=cipher, now=NOW, opener=http) == "IDLE"
    assert len(http.requests) == 1


@pytest.mark.parametrize("value, expected", [("0", False), ("1", True)])
def test_flag_accepts_only_explicit_strings(value, expected):
    assert worker.editorial_classification_enabled(value) is expected


@pytest.mark.parametrize("value", [True, False, 0, 1, None, "true", "", " 1", "1 ", [], {}])
def test_malformed_flag_is_static_value_error(value):
    with pytest.raises(
        ValueError, match="^NEWSFLOW_EDITORIAL_CLASSIFICATION_ENABLED must be exactly 0 or 1$"
    ):
        worker.editorial_classification_enabled(value)


def test_disabled_tick_does_nothing_before_any_dependency(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("disabled dependency invoked")

    monkeypatch.setattr(worker, "ConfiguredEditorialClassifierFactory", forbidden)
    monkeypatch.setattr(worker, "DurableEditorialRunner", forbidden)
    assert (
        tick(forbidden, enabled=False, cipher=forbidden, now=None, opener=forbidden) == "DISABLED"
    )


@pytest.mark.parametrize("enabled", [0, 1, "0", "1", None, [], {}])
def test_tick_requires_exact_bool_before_dependencies(enabled):
    with pytest.raises(ValueError, match="NEWSFLOW_EDITORIAL_CLASSIFICATION_ENABLED"):
        tick(lambda: pytest.fail("SQL"), enabled=enabled, cipher=None, now=NOW)


def test_enabled_missing_cipher_fails_before_sql():
    with pytest.raises(ValueError, match="stable cipher"):
        tick(lambda: pytest.fail("SQL"), enabled=True, cipher=None, now=NOW)


@pytest.mark.parametrize("now", [None, "now", True, datetime(2030, 1, 1)])
def test_enabled_invalid_time_fails_before_sql(now):
    with pytest.raises(ValueError, match="EDITORIAL_TIME_INVALID"):
        tick(lambda: pytest.fail("SQL"), enabled=True, cipher=Cipher(), now=now)


def test_typed_provider_failure_is_one_bounded_persisted_retry(store):
    factory, binding = configured(store)
    http = Http(binding, error=URLError("PRIVATE_SENTINEL"))
    assert tick(factory, enabled=True, cipher=Cipher(), now=NOW, opener=http) == "RETRY"
    assert len(http.requests) == 1
    with factory() as session:
        job = session.scalar(select(models.EditorialClassificationJobModel))
        assert job.attempts == 1
        assert job.last_error_code == "EDITORIAL_PROVIDER_UNAVAILABLE"
        assert count(session, models.EditorialClassificationClaimModel) == 1
        assert count(session, models.EditorialClassificationAttemptModel) == 1
        assert count(session, models.RewriteJobModel) == 0


def test_tick_processes_only_one_of_two_queued_jobs(store):
    factory, binding = configured(store)
    ingest(store, replace(MESSAGE, message_id=8, text="Synthetic second report"))
    http = Http(binding)
    assert tick(factory, enabled=True, cipher=Cipher(), now=NOW, opener=http) == "REVIEW"
    assert len(http.requests) == 1
    with factory() as session:
        assert session.scalars(
            select(models.EditorialClassificationJobModel.state).order_by(
                models.EditorialClassificationJobModel.id
            )
        ).all() == ["REVIEW", "QUEUED"]
        assert count(session, models.EditorialClassificationClaimModel) == 1
        assert count(session, models.RewriteJobModel) == 0


@pytest.mark.parametrize(
    "flag, stop_early, error",
    [
        (None, False, False),
        ("1", False, False),
        ("1", True, False),
        ("1", False, True),
    ],
)
def test_main_default_off_or_one_enabled_tick_and_sanitized_failure(
    monkeypatch, flag, stop_early, error
):
    from types import SimpleNamespace

    calls, logs = [], []
    cipher, factory = object(), object()

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def set(self):
            self.stopped = True

        def wait(self, interval):
            self.set()

    stop = Stop()

    def getenv(name, default=None):
        if name == "NEWSFLOW_EDITORIAL_CLASSIFICATION_ENABLED" and flag is not None:
            return flag
        return default

    def load_key():
        calls.append("load_stable_key")
        return "synthetic-test-key"

    def scheduler(*args, **kwargs):
        calls.append("scheduler")
        if stop_early:
            stop.set()
        return SimpleNamespace(plans_visited=0, active_reservations=0, failed_plan_ids=())

    def diagnostic(*args, **kwargs):
        assert args == (factory,)
        assert kwargs["cipher"] is cipher
        assert kwargs["enabled"] is True
        assert kwargs["now"].tzinfo is not None
        calls.append("diagnostic")
        if error:
            raise RuntimeError("PRIVATE_SENTINEL source credential")
        return "IDLE"

    def log(event, **kwargs):
        logs.append((event, kwargs))

    monkeypatch.setattr(worker, "getenv", getenv)
    monkeypatch.setattr(worker, "Event", lambda: stop)
    monkeypatch.setattr(worker.signal, "signal", lambda *a: None)
    monkeypatch.setattr(worker, "configured_session_factory", lambda: factory)
    monkeypatch.setattr(worker, "load_runtime_master_key", load_key)
    monkeypatch.setattr(worker, "SessionCipher", lambda value: cipher)
    monkeypatch.setattr(worker, "run_scheduler_tick", scheduler)
    monkeypatch.setattr(worker, "run_editorial_classification_tick", diagnostic)
    monkeypatch.setattr(worker, "logger", SimpleNamespace(info=log, warning=log))
    for name in (
        "run_rewrite_tick",
        "run_semantic_tick",
        "run_media_tick",
        "run_source_photo_tick",
        "run_ingestion_tick",
        "run_publication_tick",
        "run_channel_sync_tick",
    ):
        monkeypatch.setattr(worker, name, lambda *a, **k: pytest.fail("other network feature"))
    worker.main()
    assert calls == (["load_stable_key"] if flag == "1" else []) + ["scheduler"] + (
        ["diagnostic"] if flag == "1" and not stop_early else []
    )
    editorial = [entry for entry in logs if entry[0].startswith("editorial.")]
    expected = []
    if flag == "1" and not stop_early:
        expected = (
            [("editorial.execution_interrupted", {"recovery": "persisted_lease"})]
            if error
            else [("editorial.tick", {"outcome": "IDLE"})]
        )
    assert editorial == expected
    assert "PRIVATE_SENTINEL" not in repr(logs)
