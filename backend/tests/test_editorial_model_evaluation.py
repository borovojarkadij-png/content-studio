"""Injected HTTP evidence proves harness conformance, never real model quality."""

import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from test_editorial_classifier_adapters import HttpBoundary, body, classifier, evidence, request

from newsflow.services.editorial_model_evaluation import evaluate_editorial_model

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "backend/tests/fixtures/editorial-model-v1.json"
SCRIPT = ROOT / "scripts/evaluate_editorial_model.py"
SECRET = "synthetic-eval-secret-marker"


def fixture_dataset():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def two_cases():
    value = single_dataset()
    second = copy.deepcopy(value["cases"][0])
    second.update(id="synthetic-2", content_key="synthetic:second")
    value["cases"].append(second)
    return value


def run(dataset=None, client=None, **kwargs):
    return evaluate_editorial_model(
        single_dataset() if dataset is None else dataset,
        classifier=client
        or classifier("OPENAI", HttpBoundary(body("OPENAI", evidence(request())))),
        max_calls=kwargs.get("max_calls", 24),
        budget_seconds=kwargs.get("budget_seconds", 90),
        clock=kwargs.get("clock", lambda: 0),
    )


def assert_denied(result):
    for name in (
        "real_model_qualified",
        "qualification_granted",
        "execution_authorized",
        "rewrite_allowed",
    ):
        assert result[name] is False
    assert result["rewrite_calls"] == 0
    assert result["transport_attestation"] == "UNATTESTED"


class FixtureHTTP:
    """Independent synthetic evidence choices, transported through real adapters."""

    def __init__(self, provider):
        self.provider = provider
        self.requests = []

    def __call__(self, req, *, timeout):
        sent = json.loads(req.data)
        self.requests.append(sent)
        messages = sent["input"] if self.provider == "OPENAI" else sent["messages"]
        payload = json.loads(messages[1]["content"])
        case_id = payload["content_key"].split(":")[-1]
        # These labels and evidence choices are hand specified, never model outputs.
        modes = {
            "neutral": (True, False, "neutral", "neutral"),
            "positive": (True, False, "positive", "positive"),
            "negative": (True, False, "negative", "neutral"),
            "hostile": (True, False, "neutral", "hostile"),
            "unprotected": (True, False, "negative", "neutral"),
            "mixed": (True, False, "mixed", "neutral"),
            "unknown": (True, False, "unknown", "unknown"),
            "ambiguous": (True, True, "neutral", "neutral"),
            "incomplete": (False, False, "unknown", "unknown"),
            "injection": (True, False, "neutral", "neutral"),
        }
        complete, ambiguous, sentiment, framing = modes[case_id.split("-", 1)[1]]
        entity = payload["protected_entities"][0]
        findings = (
            []
            if case_id.endswith("unprotected")
            else [{"entity_id": entity["entity_id"], "source_quote": entity["aliases"][0]}]
        )
        value = {
            "content_key": payload["content_key"],
            "source_sha256": payload["source_sha256"],
            "policy_sha256": payload["policy_sha256"],
            "prompt_version": payload["prompt_version"],
            "source_complete": complete,
            "ambiguous": ambiguous,
            "sentiment": sentiment,
            "framing": framing,
            "entity_findings": findings,
        }
        return io.BytesIO(json.dumps(body(self.provider, value)).encode())


@pytest.mark.parametrize("provider", ["OPENAI", "OPENROUTER"])
def test_all_24_independent_fixture_labels_through_accepted_http_adapters(provider, monkeypatch):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider

    def forbidden(*args, **kwargs):
        pytest.fail("rewrite must never execute")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(StructuredFreeOpenRouterProvider, "rewrite", forbidden)
    dataset = fixture_dataset()
    http = FixtureHTTP(provider)
    result = run(dataset, classifier(provider, http))
    assert result["completion_status"] == "COMPLETE"
    assert result["attempted_count"] == result["completed_count"] == result["matched_count"] == 24
    assert result["mismatched_count"] == 0
    assert result["case_count"] == len(result["cases"]) == len(http.requests) == 24
    assert_denied(result)
    for sent in http.requests:
        assert sent["model"] == (
            "synthetic-model" if provider == "OPENAI" else "synthetic/model:free"
        )
        if provider == "OPENROUTER":
            assert sent["provider"] == {
                "require_parameters": True,
                "allow_fallbacks": False,
                "max_price": {"prompt": 0, "completion": 0, "request": 0},
            }
    public = json.dumps(result)
    for case in dataset["cases"]:
        assert case["source_text"] not in public
    assert SECRET not in public
    reordered = {name: dataset[name] for name in reversed(dataset)}
    assert (
        run(reordered, classifier(provider, FixtureHTTP(provider)))["dataset_sha256"]
        == result["dataset_sha256"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "extra-root",
        "wrong-version",
        "synthetic-bool",
        "empty",
        "25",
        "extra-case",
        "duplicate-id",
        "duplicate-key",
        "unicode-id",
        "newline-id",
        "bool-id",
        "wrong-label",
        "evidence",
        "bad-entity",
        "bool-source",
        "aliases-tuple",
        "extra-entity",
        "ambiguous-alias",
        "oversized-source",
    ],
)
def test_entire_dataset_invalid_final_case_prevents_earlier_calls(mutation):
    dataset = two_cases()
    case = dataset["cases"][-1]
    if mutation == "extra-root":
        dataset["execution_authorized"] = True
    elif mutation == "wrong-version":
        dataset["benchmark_version"] = "wrong"
    elif mutation == "synthetic-bool":
        dataset["synthetic"] = 1
    elif mutation == "empty":
        dataset["cases"] = []
    elif mutation == "25":
        dataset["cases"] *= 13
    elif mutation == "extra-case":
        case["rewrite_allowed"] = True
    elif mutation == "duplicate-id":
        case["id"] = dataset["cases"][0]["id"]
    elif mutation == "duplicate-key":
        case["content_key"] = dataset["cases"][0]["content_key"]
    elif mutation == "unicode-id":
        case["id"] = "кириллица"
    elif mutation == "newline-id":
        case["id"] = "synthetic\n"
    elif mutation == "bool-id":
        case["id"] = True
    elif mutation == "wrong-label":
        case["expected_diagnostic_status"] = True
    elif mutation == "evidence":
        case["evidence"] = {}
    elif mutation == "bad-entity":
        case["protected_entities"] = [True]
    elif mutation == "bool-source":
        case["source_text"] = True
    elif mutation == "aliases-tuple":
        case["protected_entities"][0]["aliases"] = ("Protected Company",)
    elif mutation == "extra-entity":
        case["protected_entities"][0]["approve"] = True
    elif mutation == "ambiguous-alias":
        case["protected_entities"].append({"entity_id": "other", "aliases": ["protected company"]})
    elif mutation == "oversized-source":
        case["source_text"] = "x" * 32001
    http = HttpBoundary(None)
    with pytest.raises(ValueError, match="^DATASET_INVALID$"):
        run(dataset, classifier("OPENAI", http))
    assert http.requests == []


@pytest.mark.parametrize(
    "name, value",
    [
        ("max_calls", True),
        ("max_calls", 0),
        ("max_calls", 25),
        ("max_calls", 1.0),
        ("budget_seconds", True),
        ("budget_seconds", 0),
        ("budget_seconds", 301),
        ("budget_seconds", "3"),
    ],
)
def test_invalid_limits_prevent_calls(name, value):
    http = HttpBoundary(None)
    with pytest.raises(ValueError, match="^EVALUATION_LIMIT_INVALID$"):
        run(client=classifier("OPENAI", http), **{name: value})
    assert http.requests == []


@pytest.mark.parametrize(
    "mutation", ["class", "model", "prompt", "provider", "transport", "fallback"]
)
def test_invalid_classifier_binding_prevents_calls(mutation):
    from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid

    http = HttpBoundary(None)
    client = classifier("OPENROUTER", http)
    if mutation == "class":
        client = object()
    elif mutation == "model":
        client._model = "paid/model"
    elif mutation == "prompt":
        client.prompt_version = "wrong"
    elif mutation == "provider":
        client.provider = "OPENAI"
    elif mutation == "transport":
        client._transport = object()
    else:
        client._transport._models = (client.model, "other/model:free")
    with pytest.raises(ProviderConfigurationInvalid):
        run(client=client)
    assert http.requests == []


@pytest.mark.parametrize("kind", ["stale", "malformed", "missing", "stale-prior", "unknown-entity"])
def test_invalid_evidence_is_error_never_expected_manual_match(kind, monkeypatch):
    dataset = single_dataset()
    dataset["cases"][0]["expected_diagnostic_status"] = "MANUAL_REVIEW"
    value = evidence(request())
    if kind == "stale":
        value["source_sha256"] = "0" * 64
    elif kind == "malformed":
        value = {"approve": True}
    elif kind == "unknown-entity":
        value["entity_findings"][0]["entity_id"] = "foreign"
    client = classifier("OPENAI", HttpBoundary(body("OPENAI", value)))
    if kind in {"missing", "stale-prior"}:
        if kind == "stale-prior":
            client.classify(request())
        monkeypatch.setattr(client, "classify", lambda request: object())
    result = run(dataset, client)
    assert result["attempted_count"] == 1 and result["completed_count"] == 0
    assert result["cases"][0] == {
        "id": "synthetic-1",
        "expected_diagnostic_status": "MANUAL_REVIEW",
        "actual_diagnostic_status": None,
        "matched": False,
        "error_code": "EVIDENCE_INVALID",
    }


@pytest.mark.parametrize("mutation", ["model", "prompt", "provider", "transport-model", "request"])
def test_identity_change_during_call_stops_run(mutation):
    http = HttpBoundary(body("OPENAI", evidence(request())))
    client = classifier("OPENAI", http)
    original = client.classify

    def changed(req):
        result = original(req)
        if mutation == "request":
            object.__setattr__(req, "source_text", "mutated")
        elif mutation == "transport-model":
            client._transport._model = "foreign"
        else:
            setattr(
                client,
                "_model"
                if mutation == "model"
                else mutation + "_version"
                if mutation == "prompt"
                else "provider",
                "foreign",
            )
        return result

    client.classify = changed
    result = run(two_cases(), client)
    assert result["completion_status"] == "CONFIGURATION_FAILED"
    assert result["attempted_count"] == len(http.requests) == 1
    assert result["completed_count"] == 0
    assert result["cases"][0]["error_code"] == "CLASSIFIER_IDENTITY_CHANGED"


@pytest.mark.parametrize("provider", ["OPENAI", "OPENROUTER"])
@pytest.mark.parametrize("kind", ["auth", "unavailable", "refusal"])
def test_typed_failures_are_static_and_without_retry(provider, kind):
    response = body(provider, evidence(request()))
    if kind == "auth":
        response = HTTPError("https://synthetic.invalid", 401, SECRET, {}, None)
    elif kind == "unavailable":
        response = URLError(SECRET)
    elif provider == "OPENAI":
        response["output"][0]["content"] = [{"type": "refusal", "refusal": SECRET}]
    else:
        response["choices"][0]["message"]["refusal"] = SECRET
    http = HttpBoundary(response)
    result = run(two_cases(), classifier(provider, http), max_calls=24 if kind == "auth" else 1)
    expected = {
        "auth": "PROVIDER_CONFIGURATION_INVALID",
        "unavailable": "PROVIDER_UNAVAILABLE",
        "refusal": "PROVIDER_RESPONSE_INVALID",
    }[kind]
    assert result["cases"][0]["error_code"] == expected
    assert result["attempted_count"] == len(http.requests) == 1
    assert result["completed_count"] == 0
    assert result["completion_status"] == (
        "CONFIGURATION_FAILED" if kind == "auth" else "CALL_BUDGET_EXHAUSTED"
    )
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize(
    "clock, cap, status, attempted, completed",
    [
        ([0, 0, 0], 1, "CALL_BUDGET_EXHAUSTED", 1, 1),
        ([0, 0, 90, 90], 24, "TIME_BUDGET_EXHAUSTED", 1, 1),
        ([0, 90], 24, "TIME_BUDGET_EXHAUSTED", 0, 0),
        ([float("nan")], 24, "CLOCK_INVALID", 0, 0),
        ([float("inf")], 24, "CLOCK_INVALID", 0, 0),
        ([-1], 24, "CLOCK_INVALID", 0, 0),
        ([True], 24, "CLOCK_INVALID", 0, 0),
        ([0, 0, float("nan")], 24, "CLOCK_INVALID", 1, 0),
        ([0, 1, 0], 24, "CLOCK_INVALID", 1, 0),
    ],
)
def test_cap_deadline_and_invalid_clock_preserve_partial_accounting(
    clock, cap, status, attempted, completed
):
    http = HttpBoundary(body("OPENAI", evidence(request())))
    result = run(two_cases(), classifier("OPENAI", http), max_calls=cap, clock=iter(clock).__next__)
    assert result["completion_status"] == status
    assert result["attempted_count"] == len(result["cases"]) == len(http.requests) == attempted
    assert result["completed_count"] == completed
    assert result["case_count"] == 2
    assert_denied(result)


@pytest.mark.parametrize(
    "args",
    [
        [],
        [
            "--allow-provider-calls",
            "--provider",
            "OPENAI",
            "--model",
            "synthetic-model",
            "--max-calls",
            "1",
            "--budget-seconds",
            "10",
        ],
        ["--unknown-private", SECRET],
    ],
)
def test_cli_safe_subprocess_paths_never_echo_secret(args):
    env = {key: os.environ[key] for key in os.environ if key != "NEWSFLOW_EDITORIAL_EVAL_API_KEY"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    value = json.loads(result.stdout)
    assert value["attempted_count"] == 0
    assert_denied(value)
    assert result.stderr == ""
    assert SECRET not in result.stdout


def cli_module():
    spec = importlib.util.spec_from_file_location("editorial_eval_cli_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_explicit_opt_in_injects_only_http_and_fake_credential(monkeypatch, capsys):
    from newsflow.providers.editorial_classifier import OpenAIEditorialClassifier

    http = FixtureHTTP("OPENAI")
    original = OpenAIEditorialClassifier.__init__

    def injected(self, *, api_key, model):
        assert api_key == SECRET
        original(self, api_key=api_key, model=model, opener=http)

    monkeypatch.setattr(OpenAIEditorialClassifier, "__init__", injected)
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_EVAL_API_KEY", SECRET)
    cli = cli_module()
    assert (
        cli.main(
            [
                "--allow-provider-calls",
                "--provider",
                "OPENAI",
                "--model",
                "synthetic-model",
                "--max-calls",
                "24",
                "--budget-seconds",
                "90",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    value = json.loads(output.out)
    assert value["matched_count"] == len(http.requests) == 24
    assert_denied(value)
    assert SECRET not in output.out and output.err == ""


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "newline",
        "space",
        "control",
        "oversize",
        "bad-dataset",
        "large-dataset",
        "duplicate-json",
        "wrong-model",
    ],
)
def test_cli_invalid_preflight_has_zero_calls(kind, monkeypatch, capsys, tmp_path):
    cli = cli_module()
    calls = []
    monkeypatch.setattr(cli, "OpenAIEditorialClassifier", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_EVAL_API_KEY", SECRET)
    args = [
        "--allow-provider-calls",
        "--provider",
        "OPENAI",
        "--model",
        "synthetic-model",
        "--max-calls",
        "1",
        "--budget-seconds",
        "10",
    ]
    if kind == "missing":
        monkeypatch.delenv("NEWSFLOW_EDITORIAL_EVAL_API_KEY")
    elif kind in {"newline", "space", "control", "oversize"}:
        monkeypatch.setenv(
            "NEWSFLOW_EDITORIAL_EVAL_API_KEY",
            {
                "newline": SECRET + "\n",
                "space": " " + SECRET,
                "control": SECRET + "\x01",
                "oversize": "s" * 4097,
            }[kind],
        )
    elif kind == "wrong-model":
        args[args.index("synthetic-model")] = SECRET + "\n"
    else:
        path = tmp_path / "invalid.json"
        path.write_text(
            {
                "bad-dataset": '{"secret":"' + SECRET + '"}',
                "large-dataset": " " * 262145,
                "duplicate-json": '{"cases":[],"cases":[]}',
            }[kind],
            encoding="utf-8",
        )
        args.extend(["--dataset", str(path)])
    assert cli.main(args) == 2
    output = capsys.readouterr()
    value = json.loads(output.out)
    assert value["attempted_count"] == 0 and calls == []
    assert SECRET not in output.out and output.err == ""


def test_cli_unknown_partial_execution_reports_null_count(monkeypatch, capsys):
    cli = cli_module()
    from newsflow.providers.editorial_classifier import OpenAIEditorialClassifier

    monkeypatch.setenv("NEWSFLOW_EDITORIAL_EVAL_API_KEY", SECRET)
    http = FixtureHTTP("OPENAI")
    original = OpenAIEditorialClassifier.__init__
    attempts = []

    def interrupted(req, *, timeout):
        attempts.append(req)
        if len(attempts) == 2:
            raise RuntimeError(SECRET)
        return http(req, timeout=timeout)

    def injected(self, *, api_key, model):
        original(self, api_key=api_key, model=model, opener=interrupted)

    monkeypatch.setattr(OpenAIEditorialClassifier, "__init__", injected)
    assert (
        cli.main(
            [
                "--allow-provider-calls",
                "--provider",
                "OPENAI",
                "--model",
                "synthetic-model",
                "--max-calls",
                "3",
                "--budget-seconds",
                "10",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    value = json.loads(output.out)
    assert value["error_code"] == "EVALUATION_INTERRUPTED"
    assert value["attempted_count"] is None
    assert SECRET not in output.out and output.err == ""
    assert len(attempts) == 2 and len(http.requests) == 1


def test_exact_sanitized_report_schema_and_case_schema():
    result = run()
    assert set(result) == {
        "evaluation_kind",
        "benchmark_version",
        "dataset_sha256",
        "prompt_version",
        "provider",
        "model",
        "max_calls",
        "budget_seconds",
        "case_count",
        "attempted_count",
        "completed_count",
        "matched_count",
        "mismatched_count",
        "completion_status",
        "cases",
        "real_model_qualified",
        "qualification_granted",
        "execution_authorized",
        "rewrite_allowed",
        "rewrite_calls",
        "transport_attestation",
    }
    assert set(result["cases"][0]) == {
        "id",
        "expected_diagnostic_status",
        "actual_diagnostic_status",
        "matched",
        "error_code",
    }
    assert result["evaluation_kind"] == "MODEL_DIAGNOSTIC"
    assert result["benchmark_version"] == "editorial-model-v1"
    assert result["prompt_version"] == "editorial-classification-v1"
    assert len(result["dataset_sha256"]) == 64


@pytest.mark.parametrize("kind", ["empty", "duplicate", "nonfinite", "overlimit"])
def test_cli_malformed_dataset_subprocess_is_zero_call(kind, tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        {
            "empty": "",
            "duplicate": '{"cases":[],"cases":[]}',
            "nonfinite": '{"cases":NaN}',
            "overlimit": " " * 262145,
        }[kind],
        encoding="utf-8",
    )
    env = {key: os.environ[key] for key in os.environ if key != "NEWSFLOW_EDITORIAL_EVAL_API_KEY"}
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--allow-provider-calls",
            "--provider",
            "OPENAI",
            "--model",
            "synthetic-model",
            "--max-calls",
            "1",
            "--budget-seconds",
            "10",
            "--dataset",
            str(path),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2 and result.stderr == ""
    value = json.loads(result.stdout)
    assert value["error_code"] == "DATASET_INVALID" and value["attempted_count"] == 0
    assert_denied(value)


def test_cli_no_flag_never_reads_credential_dataset_or_constructs_classifier(monkeypatch, capsys):
    cli = cli_module()

    def forbidden(*args, **kwargs):
        pytest.fail("safe no-flag CLI performed preflight IO or constructed classifier")

    original_get = cli.os.environ.get

    def credential_guard(key, *args):
        if key == "NEWSFLOW_EDITORIAL_EVAL_API_KEY":
            forbidden()
        return original_get(key, *args)

    monkeypatch.setattr(cli.os.environ, "get", credential_guard)
    monkeypatch.setattr(cli.Path, "open", forbidden)
    monkeypatch.setattr(cli, "OpenAIEditorialClassifier", forbidden)
    assert cli.main([]) == 2
    assert json.loads(capsys.readouterr().out)["error_code"] == "PROVIDER_CALLS_DISABLED"


@pytest.mark.parametrize(
    "provider, cap, failure, expected_exit",
    [
        ("OPENROUTER", 24, False, 0),
        ("OPENAI", 1, False, 1),
        ("OPENAI", 24, True, 1),
        ("OPENROUTER", 24, True, 1),
    ],
)
def test_cli_success_partial_and_failed_runs_have_native_semantics(
    provider, cap, failure, expected_exit, monkeypatch, capsys
):
    from newsflow.providers.editorial_classifier import (
        FreeOpenRouterEditorialClassifier,
        OpenAIEditorialClassifier,
    )

    cli = cli_module()
    kind = OpenAIEditorialClassifier if provider == "OPENAI" else FreeOpenRouterEditorialClassifier
    http = HttpBoundary(URLError(SECRET)) if failure else FixtureHTTP(provider)
    original = kind.__init__

    def injected(self, *, api_key, model):
        original(self, api_key=api_key, model=model, opener=http)

    monkeypatch.setattr(kind, "__init__", injected)
    monkeypatch.setenv("NEWSFLOW_EDITORIAL_EVAL_API_KEY", SECRET)
    assert (
        cli.main(
            [
                "--allow-provider-calls",
                "--provider",
                provider,
                "--model",
                "synthetic-model" if provider == "OPENAI" else "synthetic/model:free",
                "--max-calls",
                str(cap),
                "--budget-seconds",
                "90",
            ]
        )
        == expected_exit
    )
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["attempted_count"] == cap
    assert_denied(result)
    assert SECRET not in output.out and output.err == ""


def test_broken_clock_is_visibly_invalid_before_transport():
    def broken():
        raise RuntimeError(SECRET)

    http = HttpBoundary(None)
    result = run(client=classifier("OPENAI", http), clock=broken)
    assert result["completion_status"] == "CLOCK_INVALID"
    assert result["attempted_count"] == 0 and http.requests == []
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize("value", [0, 16, float("inf"), True, "15"])
def test_unbounded_or_malformed_accepted_transport_timeout_is_configuration_error(value):
    from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid

    http = HttpBoundary(None)
    client = classifier("OPENAI", http)
    client._transport._timeout = value
    with pytest.raises(ProviderConfigurationInvalid):
        run(client=client)
    assert http.requests == []


def single_dataset():
    req = request()
    return {
        "benchmark_version": "editorial-model-v1",
        "synthetic": True,
        "cases": [
            {
                "id": "synthetic-1",
                "content_key": req.content_key,
                "source_text": req.source_text,
                "policy_version": req.policy_version,
                "protected_entities": [{"entity_id": "company", "aliases": ["Protected Company"]}],
                "expected_diagnostic_status": "PASS",
            }
        ],
    }


def test_returned_pass_cannot_replace_rejected_source_bound_evidence(monkeypatch):
    req = request()
    value = evidence(req)
    value["sentiment"] = "negative"
    http = HttpBoundary(body("OPENAI", value))
    client = classifier("OPENAI", http)
    classify = client.classify

    def misleading(request):
        classify(request)
        return type("Fabricated", (), {"diagnostic_status": "PASS"})()

    monkeypatch.setattr(client, "classify", misleading)
    result = evaluate_editorial_model(
        single_dataset(), classifier=client, max_calls=1, budget_seconds=10, clock=lambda: 0
    )
    assert len(http.requests) == 1
    assert result["attempted_count"] == result["completed_count"] == 1
    assert result["cases"][0]["actual_diagnostic_status"] == "REJECT"
    assert result["mismatched_count"] == 1
    assert result["real_model_qualified"] is False
    assert result["rewrite_calls"] == 0
    assert req.source_text not in json.dumps(result)
