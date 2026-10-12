"""Run the checked-in synthetic editorial contract benchmark without external calls."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from newsflow.services.editorial_classification import (
    PROMPT_VERSION,
    _parse_evidence,
    evaluate_editorial_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "backend" / "tests" / "fixtures" / "editorial-classification-v1.json",
        help="Explicit alternative synthetic JSON dataset (default: checked-in fixture).",
    )
    args = parser.parse_args()
    try:
        # Read only a bounded local file; no providers, services, or operational data.
        with args.dataset.open("rb") as stream:
            data = stream.read(262145)
        value = _parse_evidence(data.decode("utf-8"))
        if (
            type(value) is not dict
            or set(value) != {"benchmark_version", "cases"}
            or value["benchmark_version"] != PROMPT_VERSION
        ):
            raise ValueError("DATASET_INVALID")
        result = evaluate_editorial_contract(value["cases"])
    except (OSError, ValueError, UnicodeError):
        print(
            json.dumps(
                {
                    "evaluation_kind": "SYNTHETIC_CONTRACT",
                    "real_model_qualified": False,
                    "provider_calls": 0,
                    "rewrite_calls": 0,
                    "error": "DATASET_INVALID",
                }
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["mismatched_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
