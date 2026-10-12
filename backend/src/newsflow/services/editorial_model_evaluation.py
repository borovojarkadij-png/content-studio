"""Bounded diagnostic evaluation; no qualification or execution permission.

The orchestration deadline stops new calls. An in-flight accepted transport may
finish up to 30 seconds beyond it; this is not wall-clock cancellation.
"""

import json
import math
import re
from hashlib import sha256
from time import monotonic

from newsflow.providers.editorial_classifier import (
    FreeOpenRouterEditorialClassifier,
    OpenAIEditorialClassifier,
)
from newsflow.providers.openai_rewrite import (
    OpenAIRewriteProvider,
    ProviderConfigurationInvalid,
    ProviderResponseInvalid,
)
from newsflow.providers.openrouter import ProviderUnavailable
from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider
from newsflow.services.editorial_classification import (
    PROMPT_VERSION,
    EditorialClassificationRequest,
    ProtectedEntity,
    assess_editorial_classification,
)

BENCHMARK_VERSION = "editorial-model-v1"
_CASE_KEYS = {
    "id",
    "content_key",
    "source_text",
    "policy_version",
    "protected_entities",
    "expected_diagnostic_status",
}
_MANUAL_REASONS = {"SOURCE_INCOMPLETE", "CLASSIFICATION_AMBIGUOUS", "CLASSIFICATION_REQUIRED"}


def _validated_dataset(dataset):
    """Snapshot all requests and labels before any provider invocation."""
    try:
        if (
            type(dataset) is not dict
            or set(dataset) != {"benchmark_version", "synthetic", "cases"}
            or dataset["benchmark_version"] != BENCHMARK_VERSION
            or dataset["synthetic"] is not True
            or type(dataset["cases"]) is not list
            or not 1 <= len(dataset["cases"]) <= 24
        ):
            raise ValueError
        cases, ids, keys = [], set(), set()
        for case in dataset["cases"]:
            if type(case) is not dict or set(case) != _CASE_KEYS:
                raise ValueError
            case_id = case["id"]
            if (
                type(case_id) is not str
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", case_id)
                or case_id in ids
                or type(case["expected_diagnostic_status"]) is not str
                or case["expected_diagnostic_status"] not in {"PASS", "REJECT", "MANUAL_REVIEW"}
                or type(case["protected_entities"]) is not list
            ):
                raise ValueError
            entities = []
            for entity in case["protected_entities"]:
                if (
                    type(entity) is not dict
                    or set(entity) != {"entity_id", "aliases"}
                    or type(entity["aliases"]) is not list
                ):
                    raise ValueError
                entities.append(ProtectedEntity(entity["entity_id"], tuple(entity["aliases"])))
            request = EditorialClassificationRequest(
                case["content_key"], case["source_text"], case["policy_version"], tuple(entities)
            )
            payload = json.dumps(request.payload, ensure_ascii=False)
            if (
                request.content_key in keys
                or len(payload) > 131072
                or len(payload.encode("utf-8")) > 262144
            ):
                raise ValueError
            ids.add(case_id)
            keys.add(request.content_key)
            cases.append((case_id, case["expected_diagnostic_status"], request))
        canonical = json.dumps(
            dataset, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return tuple(cases), sha256(canonical).hexdigest()
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError("DATASET_INVALID") from None


def _identity(classifier):
    """Inspect public binding and accepted transport configuration, never keys."""
    kind = type(classifier)
    if kind not in (OpenAIEditorialClassifier, FreeOpenRouterEditorialClassifier):
        raise ProviderConfigurationInvalid("CLASSIFIER_CONFIGURATION_INVALID")
    provider = "OPENAI" if kind is OpenAIEditorialClassifier else "OPENROUTER"
    model, transport = classifier.model, classifier._transport
    if (
        classifier.provider != provider
        or type(model) is not str
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", model)
        or classifier.prompt_version != PROMPT_VERSION
        or (
            provider == "OPENAI"
            and (
                type(transport) is not OpenAIRewriteProvider
                or transport._model != model
                or type(transport._timeout) not in (int, float)
                or not 0 < transport._timeout <= 15
            )
        )
        or (
            provider == "OPENROUTER"
            and (
                not model.endswith(":free")
                or type(transport) is not StructuredFreeOpenRouterProvider
                or type(transport._models) is not tuple
                or transport._models != (model,)
            )
        )
    ):
        raise ProviderConfigurationInvalid("CLASSIFIER_CONFIGURATION_INVALID")
    timeout = transport._timeout if provider == "OPENAI" else None
    return provider, model, classifier.prompt_version, id(transport), id(transport._open), timeout


def _request_identity(request):
    return (
        request.content_key,
        request.source_text,
        request.policy_version,
        tuple((entity.entity_id, entity.aliases) for entity in request.protected_entities),
        request.source_sha256,
        request.policy_sha256,
        request.prompt_version,
    )


def evaluate_editorial_model(
    dataset, *, classifier, max_calls: int, budget_seconds: int, clock=None
) -> dict:
    """Evaluate independently labeled synthetic cases with one call per case."""
    if (
        type(max_calls) is not int
        or not 1 <= max_calls <= 24
        or type(budget_seconds) is not int
        or not 1 <= budget_seconds <= 300
    ):
        raise ValueError("EVALUATION_LIMIT_INVALID")
    cases, digest = _validated_dataset(dataset)
    pinned = _identity(classifier)
    requests = tuple(_request_identity(case[2]) for case in cases)
    timer = monotonic if clock is None else clock
    result = {
        "evaluation_kind": "MODEL_DIAGNOSTIC",
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_sha256": digest,
        "prompt_version": pinned[2],
        "provider": pinned[0],
        "model": pinned[1],
        "max_calls": max_calls,
        "budget_seconds": budget_seconds,
        "case_count": len(cases),
        "attempted_count": 0,
        "completed_count": 0,
        "matched_count": 0,
        "mismatched_count": 0,
        "completion_status": "COMPLETE",
        "cases": [],
        "real_model_qualified": False,
        "qualification_granted": False,
        "execution_authorized": False,
        "rewrite_allowed": False,
        "rewrite_calls": 0,
        "transport_attestation": "UNATTESTED",
    }
    previous = None

    def reading():
        nonlocal previous
        try:
            value = timer()
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value < 0
                or (previous is not None and value < previous)
            ):
                return None
        except Exception:  # noqa: BLE001 - A failed injected clock is invalid, never private text.
            return None
        previous = value
        return value

    def binding_valid():
        try:
            return pinned == _identity(classifier) and requests == tuple(
                _request_identity(case[2]) for case in cases
            )
        except (AttributeError, TypeError, ValueError):
            return False

    start = reading()
    if start is None:
        result["completion_status"] = "CLOCK_INVALID"
        return result
    for case_id, expected, request in cases:
        if result["attempted_count"] >= max_calls:
            result["completion_status"] = "CALL_BUDGET_EXHAUSTED"
            break
        now = reading()
        if now is None:
            result["completion_status"] = "CLOCK_INVALID"
            break
        if now - start >= budget_seconds:
            result["completion_status"] = "TIME_BUDGET_EXHAUSTED"
            break
        if not binding_valid():
            result["completion_status"] = "CONFIGURATION_FAILED"
            break
        actual, error = None, None
        # Clear prior receipts even when an injected classify method fails to do so.
        classifier._last_evidence_json = None
        result["attempted_count"] += 1
        try:
            classifier.classify(request)
        except ProviderConfigurationInvalid:
            error = "PROVIDER_CONFIGURATION_INVALID"
            result["completion_status"] = "CONFIGURATION_FAILED"
        except ProviderResponseInvalid:
            error = "PROVIDER_RESPONSE_INVALID"
        except ProviderUnavailable:
            error = "PROVIDER_UNAVAILABLE"
        if not binding_valid():
            error = "CLASSIFIER_IDENTITY_CHANGED"
            result["completion_status"] = "CONFIGURATION_FAILED"
        after = reading()
        if after is None:
            error = "CLOCK_INVALID"
            result["completion_status"] = "CLOCK_INVALID"
        if error is None:
            assessed = assess_editorial_classification(request, classifier.last_evidence_json)
            if assessed.diagnostic_status == "MANUAL_REVIEW" and not set(
                assessed.reason_codes
            ).issubset(_MANUAL_REASONS):
                error = "EVIDENCE_INVALID"
            else:
                actual = assessed.diagnostic_status
                result["completed_count"] += 1
        matched = error is None and actual == expected
        result["cases"].append(
            {
                "id": case_id,
                "expected_diagnostic_status": expected,
                "actual_diagnostic_status": actual,
                "matched": matched,
                "error_code": error,
            }
        )
        result["matched_count"] += int(matched)
        result["mismatched_count"] += int(not matched)
        if result["completion_status"] != "COMPLETE":
            break
    return result
