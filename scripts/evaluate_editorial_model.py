"""Opt-in model diagnostics; reports never qualify a model or authorize execution.

The call deadline stops new invocations; a bounded in-flight transport may finish
up to 30 seconds later. Credentials are process-local and are never printed.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from newsflow.providers.editorial_classifier import (
    FreeOpenRouterEditorialClassifier,
    OpenAIEditorialClassifier,
)
from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid
from newsflow.services.editorial_classification import _parse_evidence
from newsflow.services.editorial_model_evaluation import (
    _identity,
    _validated_dataset,
    evaluate_editorial_model,
)


class _ArgumentInvalid(ValueError):
    pass


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error echoes supplied values, which may be private.
        raise _ArgumentInvalid


def _emit_error(code, attempted=0):
    print(
        json.dumps(
            {
                "evaluation_kind": "MODEL_DIAGNOSTIC",
                "error_code": code,
                "attempted_count": attempted,
                "real_model_qualified": False,
                "qualification_granted": False,
                "execution_authorized": False,
                "rewrite_allowed": False,
                "rewrite_calls": 0,
                "transport_attestation": "UNATTESTED",
            },
            sort_keys=True,
        )
    )


def _main(argv=None) -> int:
    parser = _SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--provider", choices=("OPENAI", "OPENROUTER"))
    parser.add_argument("--model", help="Explicit pinned model identifier.")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--budget-seconds", type=int)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "backend/tests/fixtures/editorial-model-v1.json",
        help="Read-only synthetic JSON dataset, at most 262144 bytes.",
    )
    try:
        args = parser.parse_args(argv)
    except _ArgumentInvalid:
        _emit_error("ARGUMENT_INVALID")
        return 2
    if not args.allow_provider_calls:
        _emit_error("PROVIDER_CALLS_DISABLED")
        return 2
    if (
        args.provider is None
        or type(args.model) is not str
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", args.model)
        or (args.provider == "OPENROUTER" and not args.model.endswith(":free"))
        or type(args.max_calls) is not int
        or not 1 <= args.max_calls <= 24
        or type(args.budget_seconds) is not int
        or not 1 <= args.budget_seconds <= 300
    ):
        _emit_error("CONFIGURATION_INVALID")
        return 2
    try:
        with args.dataset.open("rb") as stream:
            raw = stream.read(262145)
        if len(raw) > 262144:
            raise ValueError
        dataset = _parse_evidence(raw.decode("utf-8"))
        _validated_dataset(dataset)
    except (OSError, TypeError, ValueError, UnicodeError, RecursionError):
        _emit_error("DATASET_INVALID")
        return 2
    credential = os.environ.get("NEWSFLOW_EDITORIAL_EVAL_API_KEY")
    if type(credential) is not str or not re.fullmatch(r"[!-~]{1,4096}", credential):
        _emit_error("CREDENTIAL_INVALID")
        return 2
    try:
        adapter = (
            OpenAIEditorialClassifier
            if args.provider == "OPENAI"
            else FreeOpenRouterEditorialClassifier
        )
        classifier = adapter(api_key=credential, model=args.model)
        _identity(classifier)
    except ProviderConfigurationInvalid:
        _emit_error("CONFIGURATION_INVALID")
        return 2
    result = evaluate_editorial_model(
        dataset,
        classifier=classifier,
        max_calls=args.max_calls,
        budget_seconds=args.budget_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return (
        0
        if result["completion_status"] == "COMPLETE" and not result["mismatched_count"]
        else 1
    )


def main(argv=None) -> int:
    try:
        return _main(argv)
    except Exception:  # noqa: BLE001 - CLI privacy boundary must sanitize every failure.
        # A partial execution has unknown call count; never fabricate zero.
        _emit_error("EVALUATION_INTERRUPTED", attempted=None)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
