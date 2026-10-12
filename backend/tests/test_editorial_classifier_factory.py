"""Fresh admission and encrypted credential boundaries with synthetic transports."""

import json
from contextlib import contextmanager
from dataclasses import replace
from importlib import import_module

import pytest
import test_editorial_admission as admission_tests
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_durable_editorial_runner import mutate
from test_editorial_worker import Cipher, Http, configured

from newsflow.persistence import models
from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid
from newsflow.security.session_cipher import SessionCipher, SessionDecryptionUnavailable
from newsflow.services.durable_editorial_runner import DurableEditorialRunner
from newsflow.services.editorial_admission import EditorialAdmissionBlocked

store = admission_tests.store


def build(factory, cipher, opener):
    return import_module(
        "newsflow.services.editorial_classifier_factory"
    ).ConfiguredEditorialClassifierFactory(factory, cipher=cipher, opener=opener)


@pytest.mark.parametrize("provider", ["OPENAI", "OPENROUTER"])
def test_pinned_diagnostic_model_ignores_rewrite_policy_and_closes_sql_before_transport(
    store, provider, monkeypatch
):
    factory, binding = configured(store, provider)
    active = 0

    @contextmanager
    def tracked():
        nonlocal active
        with factory() as session:
            active += 1
            try:
                yield session
            finally:
                active -= 1

    def assert_closed():
        assert active == 0

    module = import_module("newsflow.services.editorial_classifier_factory")
    name = (
        "OpenAIEditorialClassifier" if provider == "OPENAI" else "FreeOpenRouterEditorialClassifier"
    )
    real = getattr(module, name)
    constructed = []

    def construct(**kwargs):
        assert_closed()
        constructed.append(kwargs["model"])
        return real(**kwargs)

    monkeypatch.setattr(module, name, construct)
    cipher, http = Cipher(), Http(binding, assert_closed=assert_closed)
    client = build(tracked, cipher, http)(binding)
    assert constructed == [binding.model]
    assert http.requests == []
    report = client.classify(binding.request)
    assert report.decision.rewrite_allowed is False
    assert report.real_model_qualified is False
    assert cipher.calls == len(http.requests) == 1
    sent = http.requests[0]
    assert sent["model"] == binding.model
    messages = sent["input"] if provider == "OPENAI" else sent["messages"]
    assert messages[0]["content"] == binding.request.messages[0]["content"]
    assert messages[0]["role"] == ("developer" if provider == "OPENAI" else "system")
    assert messages[1]["role"] == "user"
    assert json.loads(messages[1]["content"]) == binding.request.payload
    schema = (
        sent["text"]["format"] if provider == "OPENAI" else sent["response_format"]["json_schema"]
    )
    assert schema["strict"] is True
    assert schema["name"] == "newsflow_editorial_classification"
    if provider == "OPENROUTER":
        assert sent["provider"] == {
            "require_parameters": True,
            "allow_fallbacks": False,
            "max_price": {"prompt": 0, "completion": 0, "request": 0},
        }
    assert client.last_usage.model == binding.model
    assert (client.last_usage.input_tokens, client.last_usage.output_tokens) == (100, 20)
    runner = DurableEditorialRunner(
        tracked,
        classifier_for_binding=build(tracked, cipher, http),
        clock=lambda: admission_tests.NOW,
    )
    assert runner.run_next(now=admission_tests.NOW) == "REVIEW"
    assert len(http.requests) == cipher.calls == 2


@pytest.mark.parametrize(
    "change",
    [
        "disabled",
        "missing_policy",
        "policy",
        "mapping",
        "source",
        "reject",
        "pass",
        "permission",
        "owner",
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
def test_fresh_holds_never_decrypt_or_construct(store, change, monkeypatch):
    factory, binding = configured(store)
    cipher, http = Cipher(), Http(binding)
    module = import_module("newsflow.services.editorial_classifier_factory")
    monkeypatch.setattr(
        module, "OpenAIEditorialClassifier", lambda **k: pytest.fail("construction")
    )
    mutate(store[0], store[1], change)
    with pytest.raises(EditorialAdmissionBlocked):
        build(factory, cipher, http)(binding)
    assert cipher.calls == 0
    assert http.requests == []


@pytest.mark.parametrize(
    "change",
    [
        {"provider": "OTHER"},
        {"model": "paid/model"},
        {"revision_id": 999},
        {"mapping_id": 999},
        {"decision_id": 999},
        {"mapping_sha256": "0" * 64},
    ],
)
def test_entire_binding_must_match_current_snapshot_before_secret(store, change):
    factory, binding = configured(store)
    cipher, http = Cipher(), Http(binding)
    with pytest.raises(EditorialAdmissionBlocked):
        build(factory, cipher, http)(replace(binding, **change))
    assert cipher.calls == 0
    assert http.requests == []


@pytest.mark.parametrize(
    "provider, model",
    [
        ("OPENAI", "bad model"),
        ("OPENROUTER", "paid/model"),
        ("OPENROUTER", "openrouter/free"),
        ("OPENROUTER", "openrouter/random:free"),
        ("OPENROUTER", "a/model:free:free"),
    ],
)
def test_invalid_current_model_policy_blocks_before_secret(store, provider, model, monkeypatch):
    factory, binding = configured(store)
    with factory() as session:
        policy = session.get(models.EditorialClassifierPolicyModel, 1)
        policy.provider, policy.model = provider, model
        session.commit()
    module = import_module("newsflow.services.editorial_classifier_factory")
    for name in ("OpenAIEditorialClassifier", "FreeOpenRouterEditorialClassifier"):
        monkeypatch.setattr(module, name, lambda **k: pytest.fail("construction"))
    cipher, http = Cipher(), Http(binding)
    with pytest.raises(EditorialAdmissionBlocked, match="ADMISSION_POLICY_OR_SOURCE_INVALID"):
        build(factory, cipher, http)(replace(binding, provider=provider, model=model))
    assert cipher.calls == 0
    assert http.requests == []


@pytest.mark.parametrize("value", [None, {}, object(), True])
def test_wrong_binding_type_is_rejected_without_sql(value):
    def forbidden():
        pytest.fail("SQL called")

    with pytest.raises(ProviderConfigurationInvalid, match="EDITORIAL_BINDING_INVALID"):
        build(forbidden, object(), forbidden)(value)


@pytest.mark.parametrize("value", [None, "", "broken-token", "non-ascii-\u2603"])
def test_missing_or_unreadable_credential_has_sanitized_code(store, value):
    factory, binding = configured(store)
    with factory() as session:
        setting = session.get(models.RewriteProviderSettingModel, "OPENAI")
        if value is None:
            session.delete(setting)
        else:
            setting.encrypted_api_key = value
        session.commit()
    http = Http(binding)
    # Fixed synthetic test key, never generated or rotated.
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    expected = "EDITORIAL_SECRET_MISSING" if value in (None, "") else "EDITORIAL_SECRET_UNAVAILABLE"
    with pytest.raises(ProviderConfigurationInvalid, match=f"^{expected}$"):
        build(factory, cipher, http)(binding)
    assert http.requests == []


@pytest.mark.parametrize("error", [SessionDecryptionUnavailable, ValueError, TypeError])
def test_malformed_decryption_errors_do_not_expose_private_exception(store, error):
    factory, binding = configured(store)

    class BrokenCipher:
        def decrypt(self, value):
            raise error("PRIVATE_SENTINEL")

    with pytest.raises(ProviderConfigurationInvalid, match="^EDITORIAL_SECRET_UNAVAILABLE$"):
        build(factory, BrokenCipher(), Http(binding))(binding)


@pytest.mark.parametrize("value", [None, 3, "", " ", "bad\nkey"])
def test_invalid_decrypted_value_is_sanitized_before_adapter(store, value):
    factory, binding = configured(store)

    class InvalidCipher:
        def decrypt(self, encrypted):
            return value

    with pytest.raises(ProviderConfigurationInvalid, match="^EDITORIAL_SECRET_UNAVAILABLE$"):
        build(factory, InvalidCipher(), Http(binding))(binding)


def test_unexpected_storage_failure_propagates(store):
    _, binding = configured(store)

    def failed_storage():
        raise OperationalError("PRIVATE_SQL", {}, RuntimeError("private"))

    with pytest.raises(OperationalError):
        build(failed_storage, Cipher(), Http(binding))(binding)


@pytest.mark.parametrize("stage", ["decrypt", "construct"])
@pytest.mark.parametrize("change", ["policy", "source", "reject", "sync", "fingerprint_foreign"])
def test_runner_rechecks_independent_commit_after_factory_before_io(
    store, stage, change, monkeypatch
):
    factory, binding = configured(store)
    callback = lambda: mutate(store[0], store[1], change)
    cipher = Cipher(callback if stage == "decrypt" else None)
    module = import_module("newsflow.services.editorial_classifier_factory")
    if stage == "construct":
        real = module.OpenAIEditorialClassifier

        def construct(**kwargs):
            callback()
            return real(**kwargs)

        monkeypatch.setattr(module, "OpenAIEditorialClassifier", construct)
    http = Http(binding)
    runner = DurableEditorialRunner(
        factory,
        classifier_for_binding=build(factory, cipher, http),
        clock=lambda: admission_tests.NOW,
    )
    assert runner.run_next(now=admission_tests.NOW) == "BLOCKED"
    assert cipher.calls == 1
    assert http.requests == []
    with Session(store[0]) as session:
        assert admission_tests.count(session, models.RewriteJobModel) == 0
