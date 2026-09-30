#!/usr/bin/env python3
"""Build a privacy-safe failure corpus from an extraction manifest.

This is intentionally observational: it does not retry jobs or classify the
root cause. Raw excerpts and chunk text are never copied to the corpus.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _load_index(directory: Path, suffix: str) -> dict[str, dict[str, object]]:
    result = {}
    for path in directory.glob(f"*{suffix}"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            result[_key(path.stem.removesuffix(suffix.removesuffix(".json")))] = value
    return result


def _stage(entry: dict[str, object]) -> str:
    detail = str(entry.get("failure_detail", ""))
    if entry.get("failure_stage") == "upload":
        return "ingestion"
    if "locator_resolution_failed" in detail:
        return "locator_resolution"
    return str(entry.get("failure_stage") or "unknown")


def build_corpus(
    manifest: list[dict[str, object]],
    jobs_dir: Path,
    forensics_dir: Path | None = None,
) -> dict[str, object]:
    jobs = _load_index(jobs_dir, ".job.json")
    records = []
    for entry in manifest:
        if entry.get("status") != "failed":
            continue
        source = str(entry.get("source_file", ""))
        stem_key = _key(Path(source).stem)
        job = jobs.get(stem_key, {})
        detail = str(entry.get("failure_detail", ""))
        chunk_id = None
        if "chunk_" in detail:
            chunk_id = detail.split("chunk_", 1)[1].split(":", 1)[0]
        records.append(
            {
                "source_file": source,
                "domain": entry.get("domain"),
                "stage": _stage(entry),
                "failure_detail": detail,
                "document_id": job.get("document_id"),
                "job_id": job.get("id"),
                "chunk_id": chunk_id,
                "chunk_start_offset": None,
                "model_source_excerpt": None,
                "raw_exact_match": None,
                "normalized_exact_match": None,
                "match_count": None,
                "failure_class": None,
                "debug_artifact_available": False,
            }
        )
    forensic_records: list[dict[str, object]] = []
    if forensics_dir is not None and forensics_dir.exists():
        for path in sorted(forensics_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("records"), list):
                forensic_records.extend(
                    record for record in payload["records"] if isinstance(record, dict)
                )
    class_map = {
        "WHITESPACE": "A_WHITESPACE",
        "UNICODE": "B_UNICODE",
        "PUNCTUATION": "C_PUNCTUATION",
        "AMBIGUOUS": "D_AMBIGUOUS",
        "WRONG_TEXT_REPRESENTATION": "E_WRONG_TEXT_REPRESENTATION",
        "OFFSET_MAPPING": "F_OFFSET_MAPPING",
    }
    unresolved = [
        record for record in forensic_records if record.get("locator_status") == "unresolved"
    ]
    class_counts = Counter(
        class_map.get(str(record.get("failure_class")), "MANUAL_REVIEW_G_OR_H")
        for record in unresolved
    )
    return {
        "schema_version": "locator_failure_corpus@1",
        "privacy": {
            "raw_excerpt_included": False,
            "chunk_text_included": False,
            "classification_is_unresolved": True,
        },
        "records": records,
        "instrumented_claims": forensic_records,
        "forensics_summary": {
            "instrumented_claim_count": len(forensic_records),
            "resolved_claim_count": sum(
                record.get("locator_status") == "resolved" for record in forensic_records
            ),
            "unresolved_claim_count": len(unresolved),
            "class_counts": dict(sorted(class_counts.items())),
            "representation_mismatch_count": sum(
                record.get("provider_input_text_hash")
                != record.get("locator_source_text_hash")
                for record in forensic_records
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--forensics-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, list):
        raise SystemExit("manifest must be a JSON array")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            build_corpus(manifest, args.jobs_dir, args.forensics_dir),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
