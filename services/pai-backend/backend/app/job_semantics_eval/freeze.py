"""Verify frozen EVAL-00 and create/verify the extractor's pre-call freeze manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.job_semantics_eval.contracts import JobRequirementExtractionOutputV1, ProviderInputV1

BACKEND = Path(__file__).resolve().parents[2]
EVAL00 = BACKEND / "evals/job_semantics/requirement_breakdown_eval_00"
EVAL01 = BACKEND / "evals/job_semantics/requirement_breakdown_01"
MANIFEST = EVAL01 / "freeze-manifest-v1.json"
FROZEN_FILES = (
    "extractor-spec-v1.json",
    "provider-input-schema-v1.json",
    "output-schema-v1.json",
    "source-adapter-spec-v1.json",
    "matching-spec-v1.json",
    "metrics-spec-v1.json",
    "runner-spec-v1.json",
    "../../../app/job_semantics_eval/source_adapter.py",
    "../../../app/job_semantics_eval/contracts.py",
    "../../../app/job_semantics_eval/validation.py",
    "../../../app/job_semantics_eval/provider.py",
    "../../../app/job_semantics_eval/metrics.py",
    "../../../app/job_semantics_eval/runner.py",
    "../../../app/job_semantics_eval/freeze.py",
)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=BACKEND, check=True, capture_output=True, text=True
    ).stdout.strip()


def verify_eval00() -> dict[str, Any]:
    from evals.job_semantics.requirement_breakdown_eval_00.validate_and_freeze import (
        verify_freeze_manifest,
    )

    frozen = json.loads((EVAL00 / "manifest.synthetic.v1.json").read_text(encoding="utf-8"))
    result = verify_freeze_manifest(EVAL00, frozen)
    expected = {
        "dataset_jsonl_sha256": "sha256:6b9453a1c000f51a95b0ead39a94aca55eb7582489fca2a1b13550128df32cc5",
        "semantic_fingerprint_sha256": "sha256:b479fe2ecce0b7278506c4376e336b0cda916eba9f57c4e73b661e829a867421",
        "taxonomy_sha256": "sha256:bfb17a8f931e11f8c3e455048e9b4669c0cdd444246a66ade95a287e5a2622b4",
    }
    hashes = frozen.get("hashes", {})
    for key, expected_hash in expected.items():
        if "sha256:" + hashes.get(key, "") != expected_hash:
            raise ValueError(f"frozen EVAL-00 identity mismatch: {key}")
    if frozen.get("provider_calls_before_freeze") != 0:
        raise ValueError("frozen EVAL-00 provider_calls_before_freeze must equal 0")
    if (
        frozen.get("counts", {}).get("posting_count") != 40
        or frozen.get("counts", {}).get("atomic_statement_count") != 301
    ):
        raise ValueError("frozen EVAL-00 counts mismatch")
    return {"valid": True, "verifier": result, "manifest": frozen}


def verify_or_freeze(*, create: bool) -> dict[str, Any]:
    verify_eval00()
    schema_files = {
        "provider-input-schema-v1.json": ProviderInputV1.model_json_schema(),
        "output-schema-v1.json": JobRequirementExtractionOutputV1.model_json_schema(),
    }
    for name, schema in schema_files.items():
        path = EVAL01 / name
        if create:
            path.write_bytes(
                json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
            )
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved != schema:
            raise ValueError(f"schema artifact differs from runtime DTO: {name}")

    component_hashes: dict[str, str] = {}
    for relative in FROZEN_FILES:
        path = (EVAL01 / relative).resolve()
        component_hashes[relative] = _sha(path.read_bytes())
    spec_hash = _sha(_canonical(component_hashes))
    if create:
        if MANIFEST.exists():
            raise FileExistsError(
                "freeze manifest already exists; immutable freeze will not be overwritten"
            )
        eval00 = json.loads((EVAL00 / "manifest.synthetic.v1.json").read_text(encoding="utf-8"))
        manifest = {
            "manifest_id": "pai-jd-semantic-requirement-breakdown-01",
            "manifest_version": 1,
            "frozen_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "code_head": _git_head(),
            "eval00_dataset_sha256": "sha256:" + eval00["hashes"]["dataset_jsonl_sha256"],
            "eval00_semantic_fingerprint": "sha256:"
            + eval00["hashes"]["semantic_fingerprint_sha256"],
            "eval00_taxonomy_sha256": "sha256:" + eval00["hashes"]["taxonomy_sha256"],
            "component_sha256": component_hashes,
            "extractor_spec_sha256": spec_hash,
            "provider_calls_before_freeze": 0,
            "first_provider_call_permitted_after_freeze": True,
        }
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
        return manifest
    frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        frozen["component_sha256"] != component_hashes
        or frozen["extractor_spec_sha256"] != spec_hash
    ):
        raise ValueError("frozen extractor component hash mismatch")
    return cast(dict[str, Any], frozen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify_or_freeze(create=args.freeze), sort_keys=True))


if __name__ == "__main__":
    main()
