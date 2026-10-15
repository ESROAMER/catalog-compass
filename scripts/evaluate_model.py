"""Run four real-model sample smoke checks, not an accuracy benchmark.

Run from the project root with the local model already running:
    python scripts/evaluate_model.py
    python scripts/evaluate_model.py --output evidence/another-run.json

The model's suggestions are measured before any human correction. Rule reports
use explicit human-reviewed mappings, so mapping mistakes and rule behavior stay
separately inspectable. No mock, simulated response, or fallback mapping is used.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog_check import model  # noqa: E402
from catalog_check.catalog import CANONICAL_FIELDS, profile_csv, validate_catalog  # noqa: E402
from catalog_check.samples import SAMPLES, get_sample  # noqa: E402


SAMPLE_IDS = ("supplier-demo", "woocommerce-official", "crosspeak-good", "crosspeak-bad")
BEIJING = timezone(timedelta(hours=8), name="Asia/Shanghai")

SUPPLIER_MAPPING = {
    "sku": "Item ref",
    "name": "Display label",
    "regular_price": "List amount",
    "sale_price": "Deal amount",
    "currency": "Money",
    "product_type": "Kind",
    "parent_sku": None,
    "barcode": "GTIN",
    "stock": "Units available",
    "description": None,
}
WOO_MAPPING = {
    "sku": "SKU",
    "name": "Name",
    "regular_price": "Regular price",
    "sale_price": "Sale price",
    "currency": None,
    "product_type": "Type",
    "parent_sku": "Parent",
    "barcode": None,
    "stock": "Stock",
    "description": "Description",
}


def timestamp() -> str:
    return datetime.now(BEIJING).isoformat(timespec="seconds")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_mapping(sample_id: str) -> dict[str, str | None]:
    mapping = dict(SUPPLIER_MAPPING if sample_id == "supplier-demo" else WOO_MAPPING)
    if sample_id.startswith("crosspeak-"):
        mapping["barcode"] = "GTIN, UPC, EAN, or ISBN"
    return mapping


def write_evidence(output: Path, evidence: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement keeps a readable earlier checkpoint if interrupted.
    pending = output.with_name(output.name + ".tmp")
    pending.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(output)


def evaluate(output: Path) -> int:
    try:
        readiness = model.status()
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"Could not inspect the local model: {exc}", file=sys.stderr)
        print("Start scripts/start_model.ps1 and try again. No evidence was overwritten.", file=sys.stderr)
        return 1
    if not readiness.get("ready"):
        print("The local open model is not ready. Start scripts/start_model.ps1 and try again.", file=sys.stderr)
        print("This evaluation requires real inference; no fallback was run and no evidence was overwritten.", file=sys.stderr)
        return 1

    source_paths = ("catalog_check/model.py", "catalog_check/catalog.py", "catalog_check/samples.py", "scripts/evaluate_model.py")
    evidence = {
        "schema_version": 1,
        "evaluation_kind": "sample_smoke_check",
        "status": "running",
        "started_at": timestamp(),
        "timezone": "Asia/Shanghai (UTC+08:00)",
        "limitations": [
            "These four familiar public/synthetic samples are smoke checks, not a held-out benchmark or an estimate of generalization accuracy.",
            "Field-match counts include correctly absent (null) columns; they do not measure catalog issue-detection accuracy.",
            "CrossPeak problem examples contain issue hints in names/SKUs and must not support an AI accuracy claim.",
            "raw_model_mapping is the adapter-validated suggestion before human correction, not the raw HTTP/token response. Invalid/duplicate suggestions may have been replaced with null; see model_response.warnings.",
            "Rule reports use the human expected mapping, independently of the model suggestion. Rules never infer missing prices or modify source records.",
            "One sequential inference is run per sample; latency includes local warmup/load effects and is not a performance benchmark.",
        ],
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "model_endpoint": model.endpoint(),
            "model_status_at_start": readiness,
            "source_sha256": {name: sha256((ROOT / name).read_bytes()) for name in source_paths},
            "runtime_manifest": json.loads((ROOT / ".runtime" / "manifest.json").read_text(encoding="utf-8")) if (ROOT / ".runtime" / "manifest.json").is_file() else None,
        },
        "samples": [],
    }
    sample_metadata = {sample["id"]: sample for sample in SAMPLES}
    current_sample = None
    try:
        for sample_id in SAMPLE_IDS:
            current_sample = sample_id
            print(f"Evaluating {sample_id} with the real local model...", flush=True)
            source = get_sample(sample_id)
            profile = profile_csv(source["csv"])
            expected = expected_mapping(sample_id)
            if set(expected) != set(CANONICAL_FIELDS):
                raise ValueError("The human expected mapping must explicitly cover all canonical fields.")
            if any(header is not None and header not in profile["headers"] for header in expected.values()):
                raise ValueError(f"Sample {sample_id} no longer matches its human-reviewed expected headers.")

            started = time.perf_counter()
            suggestion = model.suggest_mapping(profile)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            proposed = suggestion["mapping"]
            differences = [
                {"field": field, "expected": expected[field], "suggested": proposed.get(field)}
                for field in CANONICAL_FIELDS if proposed.get(field) != expected[field]
            ]
            rules = validate_catalog(source["csv"], expected)
            field_matches = len(CANONICAL_FIELDS) - len(differences)
            evidence["samples"].append({
                "sample_id": sample_id,
                "sample_description": sample_metadata[sample_id]["description"],
                "filename": source["filename"],
                "csv_utf8_sha256": sha256(source["csv"].encode("utf-8")),
                "evaluated_at": timestamp(),
                "row_count": profile["row_count"],
                "column_count": len(profile["headers"]),
                "headers": profile["headers"],
                "human_expected_mapping": expected,
                "raw_model_mapping": proposed,
                "matching_fields": field_matches,
                "total_fields": len(CANONICAL_FIELDS),
                "matching_present_fields": sum(expected[field] is not None and expected[field] == proposed.get(field) for field in CANONICAL_FIELDS),
                "total_present_fields": sum(value is not None for value in expected.values()),
                "differences": differences,
                "elapsed_ms": elapsed_ms,
                "usage": suggestion.get("engine", {}).get("usage", {}),
                "model_response": suggestion,
                "rule_report_with_human_mapping": {
                    "summary": rules["summary"],
                    "issues": rules["issues"],
                    "notes": rules["notes"],
                },
            })
            write_evidence(output, evidence)
            print(f"  {field_matches}/{len(CANONICAL_FIELDS)} expected fields matched; "
                  f"{len(differences)} to review; {elapsed_ms} ms. "
                  f"Human-mapped rules: {rules['summary']['error_count']} errors, "
                  f"{rules['summary']['warning_count']} warnings.", flush=True)
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        evidence["status"] = "failed"
        evidence["finished_at"] = timestamp()
        evidence["failure"] = {"sample_id": current_sample, "type": type(exc).__name__, "message": str(exc)}
        try:
            write_evidence(output, evidence)
        except OSError as write_error:
            print(f"Could not save partial evidence: {write_error}", file=sys.stderr)
        print(f"Evaluation stopped at {current_sample}: {exc}", file=sys.stderr)
        print("No fallback or replacement model answers were generated.", file=sys.stderr)
        return 1

    evidence["status"] = "complete"
    evidence["finished_at"] = timestamp()
    write_evidence(output, evidence)
    print(f"Saved sample smoke-check evidence: {output}")
    print("Report these as observations on four examples, not general model accuracy.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "initial-evaluation.json",
                        help="JSON evidence path (default: project evidence/initial-evaluation.json).")
    args = parser.parse_args()
    return evaluate(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
