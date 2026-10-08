"""Render isolated deterministic source/taxonomy conformance fixtures."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE_KEYS = (
    "source_application_ref",
    "job_description_html",
    "job_requirements_html",
    "job_posting_url",
)
STATE_VALUES: dict[str, object] = {
    "OMITTED": "__OMIT__",
    "NULL": None,
    "EMPTY": "",
    "WHITESPACE": " \t ",
}
SEMANTIC_CASES = [
    (
        "split_types",
        "At least 3 years building Python services and a degree in computing.",
        "split into EXPERIENCE_REQUIREMENT and EDUCATION_REQUIREMENT",
    ),
    (
        "coherent_keep",
        "Design and implement REST APIs for the order service.",
        "keep as one RESPONSIBILITY",
    ),
    (
        "source_field_crossover",
        "Manage the monthly close checklist.",
        "RESPONSIBILITY regardless of source field",
    ),
    (
        "html_entity_and_inline",
        "Prepare R&D reports.",
        "decode entity and treat inline tags as transparent",
    ),
    (
        "html_list_and_br",
        "Review exceptions\nthen record the decision.",
        "preserve br boundary and list order",
    ),
    (
        "provider_exclusion",
        "Only present HTML fields are projected.",
        "exclude source ref, URL, IDs, and gold metadata",
    ),
    (
        "capability_non_inference",
        "Bachelor's degree in data science.",
        "EDUCATION_REQUIREMENT + NON_CAPABILITY",
    ),
    (
        "split_types",
        "Prepare forecasts and interview vendors.",
        "split independent responsibilities",
    ),
    (
        "coherent_keep",
        "Reconcile and explain the same account variance.",
        "keep coherent outcome as one responsibility",
    ),
    (
        "source_field_crossover",
        "Bachelor's degree in communication.",
        "EDUCATION_REQUIREMENT even in description",
    ),
    (
        "html_entity_and_inline",
        "Use SQL & Excel responsibly.",
        "decode named entities exactly once",
    ),
    ("html_list_and_br", "First item\nSecond item", "preserve DOM and boundary order"),
    (
        "capability_non_inference",
        "CPA certification preferred.",
        "QUALIFICATION_REQUIREMENT + NON_CAPABILITY",
    ),
]


def render() -> list[dict[str, object]]:
    fixtures: list[dict[str, object]] = []
    for state in ("OMITTED", "NULL", "EMPTY"):
        source: object = {} if state == "EMPTY" else STATE_VALUES[state]
        fixture: dict[str, object] = {
            "fixture_id": f"jdb-cf-v1-{len(fixtures) + 1:02d}",
            "group": "source_object_state",
            "input": {},
            "expected_provider_input": {},
            "source_states": {"target_job_source": state},
        }
        if state != "OMITTED":
            fixture["input"] = {"target_job_source": source}
            fixture["expected_provider_input"] = {"target_job_source": source}
        fixtures.append(fixture)

    for key in SOURCE_KEYS:
        for state, value in STATE_VALUES.items():
            source_map: dict[str, object] = {}
            source_states = {"target_job_source": "PRESENT"}
            if state != "OMITTED":
                source_map[key] = value
            source_states[key] = state
            if key == "target_job_source":
                raise AssertionError("target source is not a source field")
            projected = {
                k: v
                for k, v in source_map.items()
                if k in {"job_description_html", "job_requirements_html"}
            }
            fixtures.append(
                {
                    "fixture_id": f"jdb-cf-v1-{len(fixtures) + 1:02d}",
                    "group": "nullable_source_field",
                    "input": {"target_job_source": source_map},
                    "expected_provider_input": {"target_job_source": projected},
                    "source_states": source_states,
                }
            )

    for semantic_index, (title, source_text, expected) in enumerate(SEMANTIC_CASES, start=1):
        case_id = f"jd-syn-v1-{900 + semantic_index:03d}"
        display_text = source_text
        escaped_lines = [html.escape(line) for line in display_text.split("\n")]
        if title == "html_entity_and_inline":
            first_word = escaped_lines[0].split(" ", 1)[0]
            escaped_lines[0] = escaped_lines[0].replace(
                first_word, f"<strong>{first_word}</strong>", 1
            )
        html_body = "<p>" + "<br>".join(escaped_lines) + "</p>"
        source_field = (
            "JOB_REQUIREMENTS"
            if title == "source_field_crossover" and semantic_index == 3
            else "JOB_DESCRIPTION"
        )
        source_key = (
            "job_requirements_html"
            if source_field == "JOB_REQUIREMENTS"
            else "job_description_html"
        )
        source = {
            "source_application_ref": f"synthetic-application-{900 + semantic_index:03d}",
            source_key: html_body,
            "job_posting_url": f"https://example.invalid/posting/{900 + semantic_index:03d}",
        }
        lines = [line for line in display_text.split("\n") if line.strip()]
        if not lines:
            lines = [display_text]
        statement_specs = [(line, "RESPONSIBILITY", "CAPABILITY_BEARING") for line in lines]
        if title == "split_types" and semantic_index == 1:
            statement_specs = [
                (
                    "At least 3 years building Python services",
                    "EXPERIENCE_REQUIREMENT",
                    "CAPABILITY_BEARING",
                ),
                ("a degree in computing.", "EDUCATION_REQUIREMENT", "NON_CAPABILITY"),
            ]
        elif title == "split_types" and semantic_index == 8:
            statement_specs = [
                ("Prepare forecasts", "RESPONSIBILITY", "CAPABILITY_BEARING"),
                ("interview vendors.", "RESPONSIBILITY", "CAPABILITY_BEARING"),
            ]
        if title == "source_field_crossover" and semantic_index == 10:
            statement_specs = [(display_text, "EDUCATION_REQUIREMENT", "NON_CAPABILITY")]
        if title == "capability_non_inference":
            statement_specs = [
                (
                    display_text,
                    "QUALIFICATION_REQUIREMENT"
                    if "certification" in display_text.lower()
                    else "EDUCATION_REQUIREMENT",
                    "NON_CAPABILITY",
                )
            ]
        statements = []
        for order, (line, statement_type, relevance) in enumerate(statement_specs, start=1):
            statements.append(
                {
                    "statement_id": f"{case_id}-s{order:02d}",
                    "source_field": source_field,
                    "source_text": line,
                    "normalized_statement": line,
                    "statement_type": statement_type,
                    "capability_relevance": relevance,
                    "source_order": order,
                    "label_source": "synthetic_spec",
                    "review_status": "REVIEWED",
                }
            )
        case_value = {
            "case_id": case_id,
            "source_application_ref": source["source_application_ref"],
            "target_job_source": source,
            "expected_statements": statements,
            "language_profile": "ENGLISH",
            "domain": "SOFTWARE_ENGINEERING",
            "difficulty": "MEDIUM",
            "boundary_tags": [],
            "label_source": "synthetic_spec",
        }
        fixtures.append(
            {
                "fixture_id": f"jdb-cf-v1-{len(fixtures) + 1:02d}",
                "group": title,
                "case": case_value,
                "expected_text_view": display_text,
                "expected": expected,
                "source_states": {},
            }
        )
    return fixtures


if __name__ == "__main__":
    output = ROOT / "conformance.v1.jsonl"
    output.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in render()
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(render())} conformance fixtures to {output}")
