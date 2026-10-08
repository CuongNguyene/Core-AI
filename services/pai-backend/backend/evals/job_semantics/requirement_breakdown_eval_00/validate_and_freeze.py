"""Eval-local validation and freeze tooling for requirement-breakdown v1."""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Final

DATASET_ID: Final = "jd-requirement-breakdown-synthetic"
DATASET_VERSION: Final = "jd-requirement-breakdown-synthetic-v1"
SCHEMA_VERSION: Final = "jd-requirement-breakdown-case@1"

SOURCE_KEYS: Final = frozenset(
    {
        "source_application_ref",
        "job_description_html",
        "job_requirements_html",
        "job_posting_url",
    }
)
PROVIDER_HTML_KEYS: Final = ("job_description_html", "job_requirements_html")
SOURCE_FIELD_RANK: Final = {"JOB_DESCRIPTION": 0, "JOB_REQUIREMENTS": 1}
STATEMENT_TYPES: Final = frozenset(
    {
        "RESPONSIBILITY",
        "EXPERIENCE_REQUIREMENT",
        "EDUCATION_REQUIREMENT",
        "QUALIFICATION_REQUIREMENT",
        "BEHAVIORAL_REQUIREMENT",
        "OTHER",
    }
)
CAPABILITY_RELEVANCE: Final = frozenset({"CAPABILITY_BEARING", "NON_CAPABILITY", "UNCLEAR"})
LANGUAGE_PROFILES: Final = frozenset({"VIETNAMESE", "ENGLISH", "MIXED"})
DOMAINS: Final = frozenset(
    {
        "FINANCE_ACCOUNTING",
        "SOFTWARE_ENGINEERING",
        "DATA_ANALYTICS",
        "RECRUITMENT_HR",
        "PROJECT_MANAGEMENT",
        "BUSINESS_COMMUNICATION",
    }
)
DIFFICULTIES: Final = frozenset({"EASY", "MEDIUM", "HARD"})
CASE_KEYS: Final = frozenset(
    {
        "case_id",
        "source_application_ref",
        "target_job_source",
        "expected_statements",
        "language_profile",
        "domain",
        "difficulty",
        "boundary_tags",
        "label_source",
    }
)
STATEMENT_REQUIRED_KEYS: Final = frozenset(
    {
        "statement_id",
        "source_field",
        "source_text",
        "normalized_statement",
        "statement_type",
        "capability_relevance",
        "source_order",
        "label_source",
        "review_status",
    }
)
STATEMENT_OPTIONAL_KEYS: Final = frozenset({"capability_signal_text", "decomposition_group_id"})
FORBIDDEN_GOLD_KEYS: Final = frozenset(
    {
        "canonical_capability_ref",
        "capability_id",
        "capability_namespace",
        "capability_semantic_key",
        "capability_level",
        "proficiency",
        "RoleCompetencyProfile",
        "RoleCapabilityRequirement",
        "CapabilityGapProfile",
    }
)
BLOCK_TAGS: Final = frozenset({"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"})
EXPECTED_DOMAIN_COUNTS: Final = {
    "FINANCE_ACCOUNTING": 8,
    "SOFTWARE_ENGINEERING": 8,
    "DATA_ANALYTICS": 6,
    "RECRUITMENT_HR": 6,
    "PROJECT_MANAGEMENT": 6,
    "BUSINESS_COMMUNICATION": 6,
}
EXPECTED_LANGUAGE_COUNTS: Final = {"VIETNAMESE": 24, "ENGLISH": 10, "MIXED": 6}
MINIMUM_TYPE_COUNTS: Final = {
    "RESPONSIBILITY": 80,
    "EXPERIENCE_REQUIREMENT": 30,
    "EDUCATION_REQUIREMENT": 20,
    "QUALIFICATION_REQUIREMENT": 20,
    "BEHAVIORAL_REQUIREMENT": 30,
    "OTHER": 20,
}
REQUIRED_BOUNDARY_TAGS: Final = frozenset(
    {
        "responsibility_vs_experience",
        "responsibility_vs_behavioral",
        "experience_with_capability_signal",
        "education_not_capability",
        "qualification_not_capability",
        "behavioral_capability_candidate",
        "generic_behavior_not_capability",
        "age_or_personal_condition_other",
        "salary_benefit_other",
        "location_or_schedule_other",
        "mixed_requirement_clause",
        "coordinated_clause_split",
        "coordinated_clause_keep",
        "html_list_boundary",
        "html_inline_formatting",
        "duplicate_semantics_across_source_fields",
        "weak_preference_language",
        "mandatory_vs_preferred",
        "years_experience_not_level",
        "degree_subject_not_capability",
        "certificate_not_capability",
        "tool_mention_in_responsibility",
        "tool_mention_without_capability",
        "generic_keyword_overlap",
        "mixed_language",
    }
)


def load_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """Load strict JSONL records; blank lines and non-object rows are errors."""
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank line at {line_number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at line {line_number}: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"JSONL row at line {line_number} must be an object")
        records.append(record)
    return tuple(records)


def validate_dataset(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Validate the frozen corpus contract and return reproducible coverage counts."""
    if len(cases) != 40:
        raise ValueError(f"expected 40 postings, got {len(cases)}")
    case_ids = [str(case.get("case_id")) for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("duplicate case_id")
    expected_ids = [f"jd-syn-v1-{index:03d}" for index in range(1, 41)]
    if sorted(case_ids) != expected_ids:
        raise ValueError("case IDs must cover jd-syn-v1-001 through jd-syn-v1-040")

    type_counts: Counter[str] = Counter()
    relevance_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    source_type_counts: dict[str, Counter[str]] = {field: Counter() for field in SOURCE_FIELD_RANK}
    type_relevance_counts: dict[str, Counter[str]] = {
        statement_type: Counter() for statement_type in STATEMENT_TYPES
    }
    domain_type_counts: dict[str, Counter[str]] = {domain: Counter() for domain in DOMAINS}
    domain_relevance_counts: dict[str, Counter[str]] = {domain: Counter() for domain in DOMAINS}
    statement_ids: set[str] = set()

    for case in cases:
        validate_case(case)
        language_counts[str(case["language_profile"])] += 1
        domain_counts[str(case["domain"])] += 1
        difficulty_counts[str(case["difficulty"])] += 1
        tags = case.get("boundary_tags")
        if not isinstance(tags, list):
            raise ValueError("boundary_tags must be a list")
        tag_counts.update(tag for tag in tags if isinstance(tag, str))
        statements = case.get("expected_statements")
        if not isinstance(statements, list):
            raise ValueError("expected_statements must be a list")
        for statement in statements:
            if not isinstance(statement, Mapping):
                raise ValueError("each expected statement must be an object")
            statement_id = str(statement["statement_id"])
            if statement_id in statement_ids:
                raise ValueError(f"duplicate statement_id: {statement_id}")
            statement_ids.add(statement_id)
            statement_type = str(statement["statement_type"])
            source_field = str(statement["source_field"])
            type_counts[statement_type] += 1
            relevance = str(statement["capability_relevance"])
            relevance_counts[relevance] += 1
            type_relevance_counts[statement_type][relevance] += 1
            source_counts[source_field] += 1
            source_type_counts[source_field][statement_type] += 1
            domain = str(case["domain"])
            domain_type_counts[domain][statement_type] += 1
            domain_relevance_counts[domain][relevance] += 1

    total = len(statement_ids)
    if not 240 <= total <= 320:
        raise ValueError(f"expected 240–320 atomic statements, got {total}")
    if dict(domain_counts) != EXPECTED_DOMAIN_COUNTS:
        raise ValueError(f"domain distribution mismatch: {dict(domain_counts)}")
    if dict(language_counts) != EXPECTED_LANGUAGE_COUNTS:
        raise ValueError(f"language distribution mismatch: {dict(language_counts)}")
    for statement_type, minimum in MINIMUM_TYPE_COUNTS.items():
        if type_counts[statement_type] < minimum:
            raise ValueError(f"too few {statement_type} statements: {type_counts[statement_type]}")
    if relevance_counts["NON_CAPABILITY"] < 50:
        raise ValueError("at least 50 NON_CAPABILITY statements are required")
    if relevance_counts["UNCLEAR"] < 12:
        raise ValueError("at least 12 UNCLEAR statements are required")
    capability_ratio = relevance_counts["CAPABILITY_BEARING"] / total
    if not 0.55 <= capability_ratio <= 0.80:
        raise ValueError("CAPABILITY_BEARING must be a substantial, non-overwhelming majority")
    missing_tags = REQUIRED_BOUNDARY_TAGS - set(tag_counts)
    if missing_tags:
        raise ValueError(f"missing required boundary tags: {', '.join(sorted(missing_tags))}")

    return {
        "posting_count": len(cases),
        "atomic_statement_count": total,
        "statement_type_distribution": dict(sorted(type_counts.items())),
        "capability_relevance_distribution": dict(sorted(relevance_counts.items())),
        "source_field_distribution": dict(sorted(source_counts.items())),
        "language_distribution": dict(sorted(language_counts.items())),
        "domain_distribution": dict(sorted(domain_counts.items())),
        "difficulty_distribution": dict(sorted(difficulty_counts.items())),
        "boundary_tag_distribution": dict(sorted(tag_counts.items())),
        "source_field_by_statement_type": {
            source: {
                statement_type: counts[statement_type] for statement_type in sorted(STATEMENT_TYPES)
            }
            for source, counts in source_type_counts.items()
        },
        "statement_type_by_capability_relevance": {
            statement_type: {
                relevance: counts[relevance] for relevance in sorted(CAPABILITY_RELEVANCE)
            }
            for statement_type, counts in sorted(type_relevance_counts.items())
        },
        "domain_by_statement_type": {
            domain: {
                statement_type: counts[statement_type] for statement_type in sorted(STATEMENT_TYPES)
            }
            for domain, counts in sorted(domain_type_counts.items())
        },
        "domain_by_capability_relevance": {
            domain: {relevance: counts[relevance] for relevance in sorted(CAPABILITY_RELEVANCE)}
            for domain, counts in sorted(domain_relevance_counts.items())
        },
    }


class _TextViewParser(HTMLParser):
    """Apply the eval taxonomy's deterministic, non-browser HTML text view."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str | None] = []

    def _boundary(self) -> None:
        self.parts.append(None)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized_tag = tag.lower()
        if normalized_tag in BLOCK_TAGS or normalized_tag == "br":
            self._boundary()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in BLOCK_TAGS:
            self._boundary()

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.parts.append(html.unescape(f"&#{name};"))


def html_text_view(value: str) -> str:
    """Render authored HTML to the exact text view used for source-span checks."""
    parser = _TextViewParser()
    parser.feed(value)
    parser.close()
    blocks = []
    current: list[str] = []
    for part in [*parser.parts, None]:
        if part is None:
            block = "".join(current)
            normalized = re.sub(r"\s+", " ", block.replace("\u00a0", " ")).strip()
            current.clear()
            if normalized:
                blocks.append(normalized)
        else:
            current.append(part)
    return "\n".join(blocks)


def validate_source_boundary(source: object) -> None:
    """Validate an optional source object without normalizing its values."""
    if source is None:
        return
    if not isinstance(source, Mapping):
        raise ValueError("target_job_source must be an object or null")
    unknown = set(source) - SOURCE_KEYS
    if unknown:
        raise ValueError(f"unknown source key(s): {', '.join(sorted(map(str, unknown)))}")
    for key, value in source.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"source field {key} must be a string or null")
    url = source.get("job_posting_url")
    if isinstance(url, str) and url.strip() and not url.startswith("https://example.invalid/"):
        raise ValueError("synthetic job_posting_url must use https://example.invalid/")


def validate_case(case: Mapping[str, object]) -> None:
    """Validate one synthetic posting and its gold statement provenance."""
    unknown_case = set(case) - CASE_KEYS
    missing_case = CASE_KEYS - set(case)
    if unknown_case:
        raise ValueError(f"unknown case key(s): {', '.join(sorted(unknown_case))}")
    if missing_case:
        raise ValueError(f"missing case key(s): {', '.join(sorted(missing_case))}")

    case_id = case["case_id"]
    if not isinstance(case_id, str) or not re.fullmatch(r"jd-syn-v1-\d{3}", case_id):
        raise ValueError("case_id must match jd-syn-v1-NNN")
    app_ref = case["source_application_ref"]
    if not isinstance(app_ref, str) or not app_ref.strip():
        raise ValueError("case source_application_ref must be nonempty synthetic metadata")
    if not app_ref.startswith("synthetic-application-"):
        raise ValueError("case source_application_ref must be synthetic")

    source = case["target_job_source"]
    validate_source_boundary(source)
    if isinstance(source, Mapping):
        nested_ref = source.get("source_application_ref")
        if nested_ref is not None and nested_ref != app_ref:
            raise ValueError("case and target source_application_ref must match")

    if case["language_profile"] not in LANGUAGE_PROFILES:
        raise ValueError("invalid language_profile")
    if case["domain"] not in DOMAINS:
        raise ValueError("invalid domain")
    if case["difficulty"] not in DIFFICULTIES:
        raise ValueError("invalid difficulty")
    if case["label_source"] != "synthetic_spec":
        raise ValueError("case label_source must be synthetic_spec")

    tags = case["boundary_tags"]
    if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
        raise ValueError("boundary_tags must be a list of nonempty strings")
    if len(tags) != len(set(tags)):
        raise ValueError("boundary_tags must be unique")

    statements = case["expected_statements"]
    if not isinstance(statements, list):
        raise ValueError("expected_statements must be a list")
    seen_ids: set[str] = set()
    seen_order: set[tuple[str, int]] = set()
    for statement in statements:
        if not isinstance(statement, Mapping):
            raise ValueError("each expected statement must be an object")
        unknown_statement = set(statement) - STATEMENT_REQUIRED_KEYS - STATEMENT_OPTIONAL_KEYS
        missing_statement = STATEMENT_REQUIRED_KEYS - set(statement)
        if unknown_statement:
            raise ValueError(f"unknown statement key(s): {', '.join(sorted(unknown_statement))}")
        if missing_statement:
            raise ValueError(f"missing statement key(s): {', '.join(sorted(missing_statement))}")

        statement_id = statement["statement_id"]
        if not isinstance(statement_id, str) or not re.fullmatch(
            rf"{re.escape(case_id)}-s\d{{2}}", statement_id
        ):
            raise ValueError(f"invalid statement_id for {case_id}")
        if statement_id in seen_ids:
            raise ValueError(f"duplicate statement_id: {statement_id}")
        seen_ids.add(statement_id)

        source_field = statement["source_field"]
        if source_field not in SOURCE_FIELD_RANK:
            raise ValueError(f"invalid source_field for {statement_id}")
        source_order = statement["source_order"]
        if isinstance(source_order, bool) or not isinstance(source_order, int) or source_order < 1:
            raise ValueError(f"source_order must be a positive integer for {statement_id}")
        order_key = (str(source_field), source_order)
        if order_key in seen_order:
            raise ValueError(f"duplicate source_order within {source_field}")
        seen_order.add(order_key)

        source_text = statement["source_text"]
        normalized = statement["normalized_statement"]
        if not isinstance(source_text, str) or not source_text.strip():
            raise ValueError(f"source_text must be nonempty for {statement_id}")
        if not isinstance(normalized, str) or not normalized.strip():
            raise ValueError(f"normalized_statement must be nonempty for {statement_id}")
        if statement["statement_type"] not in STATEMENT_TYPES:
            raise ValueError(f"invalid statement_type for {statement_id}")
        if statement["capability_relevance"] not in CAPABILITY_RELEVANCE:
            raise ValueError(f"invalid capability_relevance for {statement_id}")
        if statement["label_source"] != "synthetic_spec":
            raise ValueError(f"invalid label_source for {statement_id}")
        if statement["review_status"] != "REVIEWED":
            raise ValueError(f"statement is not reviewed: {statement_id}")

        if isinstance(source, Mapping):
            html_key = (
                "job_description_html"
                if source_field == "JOB_DESCRIPTION"
                else "job_requirements_html"
            )
            html_value = source.get(html_key)
            if not isinstance(html_value, str) or source_text not in html_text_view(html_value):
                raise ValueError(f"source_text is not a contiguous source span: {statement_id}")
        else:
            raise ValueError(f"statement has no corresponding HTML source: {statement_id}")

        signal = statement.get("capability_signal_text")
        if signal is not None and (
            not isinstance(signal, str) or not signal or signal not in source_text
        ):
            raise ValueError(f"capability_signal_text must be an exact source span: {statement_id}")
        group = statement.get("decomposition_group_id")
        if group is not None and (not isinstance(group, str) or not group):
            raise ValueError(f"invalid decomposition_group_id for {statement_id}")
        forbidden = FORBIDDEN_GOLD_KEYS & set(statement)
        if forbidden:
            raise ValueError(f"forbidden capability output key(s): {', '.join(sorted(forbidden))}")


def build_provider_input(case: Mapping[str, object]) -> dict[str, object]:
    """Project only present semantic HTML fields; never include correlation/gold data."""
    if "target_job_source" not in case:
        return {}
    source = case["target_job_source"]
    validate_source_boundary(source)
    if source is None:
        return {"target_job_source": None}
    if not isinstance(source, Mapping):
        raise ValueError("target_job_source must be an object or null")
    return {"target_job_source": {key: source[key] for key in PROVIDER_HTML_KEYS if key in source}}


def canonicalize_case(case: Mapping[str, object]) -> dict[str, object]:
    """Copy a case into semantic order while preserving omission and scalar values."""
    result = dict(case)
    tags = case.get("boundary_tags")
    if isinstance(tags, list):
        result["boundary_tags"] = sorted(tags)
    statements = case.get("expected_statements")
    if isinstance(statements, list):
        result["expected_statements"] = sorted(
            statements,
            key=lambda statement: (
                SOURCE_FIELD_RANK.get(str(statement.get("source_field")), 99),
                statement.get("source_order", 0),
                str(statement.get("statement_id", "")),
            ),
        )
    return result


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def semantic_fingerprint(cases: Sequence[Mapping[str, object]], taxonomy_sha256: str) -> str:
    """Hash semantic content independently of JSONL physical line/array order."""
    if not re.fullmatch(r"[0-9a-f]{64}", taxonomy_sha256):
        raise ValueError("taxonomy_sha256 must be a lowercase 64-character SHA-256")
    canonical_cases = sorted(
        (canonicalize_case(case) for case in cases), key=lambda case: str(case.get("case_id", ""))
    )
    bound_content = {
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "taxonomy_sha256": taxonomy_sha256,
        "cases": canonical_cases,
    }
    return hashlib.sha256(_canonical_json_bytes(bound_content)).hexdigest()


def artifact_sha256(raw: bytes) -> str:
    """Hash exact artifact bytes, including JSONL line order and whitespace."""
    return hashlib.sha256(raw).hexdigest()


FROZEN_ARTIFACTS: Final = {
    "taxonomy_sha256": "requirement-breakdown-taxonomy.v1.md",
    "protocol_sha256": "authoring.protocol.v1.md",
    "review_pass1_sha256": "review.pass1.md",
    "review_pass2_sha256": "review.pass2.md",
    "conformance_review_sha256": "conformance.review.v1.md",
    "conformance_jsonl_sha256": "conformance.v1.jsonl",
    "dataset_jsonl_sha256": "dataset.synthetic.v1.jsonl",
}


def build_freeze_manifest(
    eval_dir: Path,
    *,
    code_head: str,
    frozen_at_utc: str | None = None,
    provider_calls_before_freeze: int = 0,
) -> dict[str, object]:
    """Build a manifest from validated local artifacts without provider access."""
    if provider_calls_before_freeze != 0:
        raise ValueError("provider_calls_before_freeze must be 0")
    if not re.fullmatch(r"[0-9a-f]{40,64}", code_head):
        raise ValueError("code_head must be a lowercase Git object ID")
    timestamp = frozen_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("frozen_at_utc must include a UTC offset")

    raw_dataset = (eval_dir / FROZEN_ARTIFACTS["dataset_jsonl_sha256"]).read_bytes()
    cases = load_jsonl(eval_dir / FROZEN_ARTIFACTS["dataset_jsonl_sha256"])
    counts = validate_dataset(cases)
    taxonomy_hash = artifact_sha256((eval_dir / FROZEN_ARTIFACTS["taxonomy_sha256"]).read_bytes())
    hashes = {
        name: artifact_sha256((eval_dir / filename).read_bytes())
        for name, filename in FROZEN_ARTIFACTS.items()
    }
    hashes["semantic_fingerprint_sha256"] = semantic_fingerprint(cases, taxonomy_hash)
    if hashes["dataset_jsonl_sha256"] != artifact_sha256(raw_dataset):
        raise ValueError("dataset JSONL hash mismatch")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=eval_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        "manifest_id": "jd-requirement-breakdown-synthetic-v1",
        "manifest_version": 1,
        "code_head": code_head,
        "code_worktree_clean": not bool(status.strip()),
        "frozen_at_utc": timestamp,
        "provider_calls_before_freeze": 0,
        "counts": counts,
        "hashes": hashes,
    }


def verify_freeze_manifest(eval_dir: Path, manifest: Mapping[str, object]) -> dict[str, object]:
    """Recompute all frozen hashes/counts and fail closed on any mismatch."""
    if manifest.get("provider_calls_before_freeze") != 0:
        raise ValueError("provider_calls_before_freeze must be 0")
    code_head = manifest.get("code_head")
    if not isinstance(code_head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", code_head):
        raise ValueError("invalid code_head")
    try:
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=eval_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("cannot resolve current Git HEAD") from exc
    timestamp = manifest.get("frozen_at_utc")
    if not isinstance(timestamp, str):
        raise ValueError("frozen_at_utc is required")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid frozen_at_utc") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("frozen_at_utc must include a UTC offset")

    expected = build_freeze_manifest(
        eval_dir,
        code_head=code_head,
        frozen_at_utc=timestamp,
        provider_calls_before_freeze=0,
    )
    for key in (
        "manifest_id",
        "manifest_version",
        "code_head",
        "frozen_at_utc",
        "provider_calls_before_freeze",
        "counts",
        "hashes",
    ):
        if manifest.get(key) != expected[key]:
            raise ValueError(f"freeze manifest mismatch: {key}")
    return {
        "valid": True,
        "code_head": code_head,
        "current_code_head": current_head,
        "artifact_count": len(FROZEN_ARTIFACTS),
    }
