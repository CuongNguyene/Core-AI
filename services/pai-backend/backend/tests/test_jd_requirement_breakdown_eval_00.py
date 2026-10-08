import importlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

TOOL_PATH = (
    Path(__file__).parents[1]
    / "evals/job_semantics/requirement_breakdown_eval_00/validate_and_freeze.py"
)


@pytest.fixture
def api():
    if not TOOL_PATH.is_file():
        pytest.skip("eval tool is introduced by the implementation step")
    return importlib.import_module(
        "evals.job_semantics.requirement_breakdown_eval_00.validate_and_freeze"
    )


def function(api, name: str):
    candidate = getattr(api, name, None)
    assert callable(candidate), f"{name} is not implemented"
    return candidate


def test_eval_tool_module_exists():
    assert TOOL_PATH.is_file(), f"missing eval tool module: {TOOL_PATH}"


def case(source: object, statements: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "case_id": "jd-syn-v1-001",
        "source_application_ref": "synthetic-application-001",
        "target_job_source": source,
        "expected_statements": statements or [],
        "language_profile": "ENGLISH",
        "domain": "SOFTWARE_ENGINEERING",
        "difficulty": "EASY",
        "boundary_tags": [],
        "label_source": "synthetic_spec",
    }


def statement(
    statement_id: str = "jd-syn-v1-001-s01",
    *,
    source_field: str = "JOB_DESCRIPTION",
    source_order: int = 1,
    source_text: str = "Prepare monthly reports.",
) -> dict[str, object]:
    return {
        "statement_id": statement_id,
        "source_field": source_field,
        "source_text": source_text,
        "normalized_statement": source_text,
        "statement_type": "RESPONSIBILITY",
        "capability_relevance": "CAPABILITY_BEARING",
        "source_order": source_order,
        "label_source": "synthetic_spec",
        "review_status": "REVIEWED",
    }


def test_html_text_view_decodes_entities_and_preserves_inline_and_block_order(api):
    html = (
        "<h2>Reports &amp; controls</h2><ul>"
        "<li>Prepare <strong>monthly</strong> reports.</li>"
        "<li>Review<br>exceptions.</li></ul>"
    )

    assert function(api, "html_text_view")(html) == (
        "Reports & controls\nPrepare monthly reports.\nReview\nexceptions."
    )


def test_html_text_view_discards_comments_and_collapses_block_whitespace(api):
    html = "<p>  Use&nbsp; SQL\n responsibly. <!-- hidden --> </p><p></p>"

    assert function(api, "html_text_view")(html) == "Use SQL responsibly."


def test_provider_projection_excludes_correlation_url_and_gold_metadata(api):
    source = {
        "source_application_ref": "synthetic-application-001",
        "job_description_html": "<p>Develop APIs.</p>",
        "job_requirements_html": None,
        "job_posting_url": "https://example.invalid/posting/001",
    }
    value = case(source, [statement()])
    value["boundary_tags"] = ["html_list_boundary"]

    assert function(api, "build_provider_input")(value) == {
        "target_job_source": {
            "job_description_html": "<p>Develop APIs.</p>",
            "job_requirements_html": None,
        }
    }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("__OMIT__", {}),
        (None, {"target_job_source": None}),
        ({}, {"target_job_source": {}}),
        ({"job_description_html": None}, {"target_job_source": {"job_description_html": None}}),
        ({"job_description_html": ""}, {"target_job_source": {"job_description_html": ""}}),
        (
            {"job_description_html": " \t "},
            {"target_job_source": {"job_description_html": " \t "}},
        ),
    ],
)
def test_provider_projection_preserves_nullable_empty_and_missing_states(
    api, source: object, expected: dict[str, object]
):
    value = case(source)
    if source == "__OMIT__":
        del value["target_job_source"]

    assert function(api, "build_provider_input")(value) == expected


def test_validate_case_rejects_unknown_source_keys(api):
    value = case(
        {
            "source_application_ref": "synthetic-application-001",
            "job_description_html": "<p>Prepare reports.</p>",
            "job_requirements_html": "",
            "job_posting_url": "https://example.invalid/posting/001",
            "salary": "invented source field",
        }
    )

    with pytest.raises(ValueError, match="unknown.*source"):
        function(api, "validate_case")(value)


def test_validate_case_accepts_exact_visible_span_across_inline_markup(api):
    source_text = "Prepare monthly reports."
    value = case(
        {
            "source_application_ref": "synthetic-application-001",
            "job_description_html": "<p>Prepare <strong>monthly</strong> reports.</p>",
            "job_requirements_html": "",
            "job_posting_url": "https://example.invalid/posting/001",
        },
        [statement(source_text=source_text)],
    )

    function(api, "validate_case")(value)


def test_validate_case_rejects_a_noncontiguous_source_text_span(api):
    value = case(
        {"job_description_html": "<p>Prepare monthly reports.</p>"},
        [statement(source_text="Prepare reports monthly.")],
    )

    with pytest.raises(ValueError, match="not a contiguous source span"):
        function(api, "validate_case")(value)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("source_html", "<p>Prepare quarterly reports.</p>"),
        ("source_text", "Prepare quarterly reports."),
        ("statement_type", "EXPERIENCE_REQUIREMENT"),
        ("capability_relevance", "NON_CAPABILITY"),
    ],
)
def test_semantic_fingerprint_binds_all_gold_semantics(api, mutation: str, expected: str):
    value = case(
        {"job_description_html": "<p>Prepare monthly reports.</p>"},
        [statement()],
    )
    changed = deepcopy(value)
    if mutation == "source_html":
        changed["target_job_source"]["job_description_html"] = expected  # type: ignore[index]
    else:
        changed["expected_statements"][0][mutation] = expected  # type: ignore[index]

    fingerprint = function(api, "semantic_fingerprint")
    assert fingerprint([value], "a" * 64) != fingerprint([changed], "a" * 64)


def test_semantic_fingerprint_ignores_physical_case_statement_and_tag_order(api):
    first = case(
        {"job_description_html": "<p>Draft reports.</p>", "job_requirements_html": ""},
        [
            statement("jd-syn-v1-001-s02", source_order=2, source_text="Explain variances."),
            statement(source_order=1),
        ],
    )
    first["boundary_tags"] = ["z_tag", "a_tag"]
    second = case(
        {"job_description_html": "<p>Review risks.</p>", "job_requirements_html": ""},
        [statement(source_text="Review risks.")],
    )
    second["case_id"] = "jd-syn-v1-002"
    second["source_application_ref"] = "synthetic-application-002"
    second["target_job_source"] = {
        "source_application_ref": "synthetic-application-002",
        **second["target_job_source"],  # type: ignore[misc]
    }

    reordered = deepcopy(first)
    reordered["expected_statements"] = list(reversed(first["expected_statements"]))  # type: ignore[arg-type]
    reordered["boundary_tags"] = ["a_tag", "z_tag"]

    fingerprint = function(api, "semantic_fingerprint")
    assert fingerprint([first, second], "a" * 64) == fingerprint([second, reordered], "a" * 64)


def test_semantic_fingerprint_changes_when_semantic_source_order_changes(api):
    value = case({"job_description_html": "<p>A.</p><p>B.</p>"}, [statement()])
    changed = deepcopy(value)
    changed["expected_statements"][0]["source_order"] = 2  # type: ignore[index]

    fingerprint = function(api, "semantic_fingerprint")
    assert fingerprint([value], "a" * 64) != fingerprint([changed], "a" * 64)


def test_semantic_fingerprint_binds_source_field_presence_and_empty_state(api):
    source_states = [
        case({}),
        case({"job_description_html": None}),
        case({"job_description_html": ""}),
        case({"job_description_html": " \t "}),
    ]
    fingerprint = function(api, "semantic_fingerprint")
    fingerprints = {fingerprint([value], "a" * 64) for value in source_states}

    assert len(fingerprints) == len(source_states)


def test_semantic_fingerprint_binds_taxonomy_hash(api):
    value = case({"job_description_html": "<p>Prepare reports.</p>"})

    fingerprint = function(api, "semantic_fingerprint")
    assert fingerprint([value], "a" * 64) != fingerprint([value], "b" * 64)


def test_artifact_hash_binds_exact_jsonl_bytes_and_line_order(api):
    first = b'{"case_id":"001"}\n{"case_id":"002"}\n'
    reordered = b'{"case_id":"002"}\n{"case_id":"001"}\n'

    assert function(api, "artifact_sha256")(first) != function(api, "artifact_sha256")(reordered)


DATASET_PATH = (
    Path(__file__).parents[1]
    / "evals/job_semantics/requirement_breakdown_eval_00/dataset.synthetic.v1.jsonl"
)
REQUIRED_BOUNDARY_TAGS = {
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


@pytest.fixture
def synthetic_cases(api):
    if not DATASET_PATH.is_file():
        pytest.skip("synthetic corpus is authored in Task 3")
    return function(api, "load_jsonl")(DATASET_PATH)


def test_synthetic_dataset_file_exists_before_authoring():
    assert DATASET_PATH.is_file(), f"missing synthetic corpus: {DATASET_PATH}"


def test_load_jsonl_reads_records_and_rejects_blank_lines(api, tmp_path):
    loader = function(api, "load_jsonl")
    valid_path = tmp_path / "valid.jsonl"
    valid_path.write_text('{"case_id":"one"}\n{"case_id":"two"}\n', encoding="utf-8")
    assert loader(valid_path) == ({"case_id": "one"}, {"case_id": "two"})

    blank_path = tmp_path / "blank.jsonl"
    blank_path.write_text('{"case_id":"one"}\n\n', encoding="utf-8")
    with pytest.raises(ValueError, match="blank line"):
        loader(blank_path)


def test_synthetic_dataset_meets_count_distribution_and_boundary_gates(api, synthetic_cases):
    stats = function(api, "validate_dataset")(synthetic_cases)

    assert stats["posting_count"] == 40
    assert 240 <= stats["atomic_statement_count"] <= 320
    assert stats["domain_distribution"] == {
        "FINANCE_ACCOUNTING": 8,
        "SOFTWARE_ENGINEERING": 8,
        "DATA_ANALYTICS": 6,
        "RECRUITMENT_HR": 6,
        "PROJECT_MANAGEMENT": 6,
        "BUSINESS_COMMUNICATION": 6,
    }
    assert stats["language_distribution"] == {
        "VIETNAMESE": 24,
        "ENGLISH": 10,
        "MIXED": 6,
    }
    assert set(stats["boundary_tag_distribution"]) >= REQUIRED_BOUNDARY_TAGS
    assert stats["statement_type_by_capability_relevance"]["RESPONSIBILITY"]["NON_CAPABILITY"] > 0
    relevance = stats["capability_relevance_distribution"]
    ratio = relevance["CAPABILITY_BEARING"] / stats["atomic_statement_count"]
    assert 0.55 <= ratio <= 0.80
    assert stats["domain_by_statement_type"]["FINANCE_ACCOUNTING"]["RESPONSIBILITY"] > 0
    assert stats["domain_by_capability_relevance"]["SOFTWARE_ENGINEERING"]["NON_CAPABILITY"] > 0


def test_synthetic_dataset_has_source_field_type_crossovers(api, synthetic_cases):
    stats = function(api, "validate_dataset")(synthetic_cases)
    source_type = stats["source_field_by_statement_type"]

    assert source_type["JOB_DESCRIPTION"]["RESPONSIBILITY"] > 0
    assert (
        sum(
            source_type["JOB_DESCRIPTION"][statement_type]
            for statement_type in source_type["JOB_DESCRIPTION"]
            if statement_type != "RESPONSIBILITY"
        )
        > 0
    )
    assert source_type["JOB_REQUIREMENTS"]["RESPONSIBILITY"] > 0


def test_synthetic_corpus_covers_nullable_and_one_sided_source_cases(api, synthetic_cases):
    by_id = {case["case_id"]: case for case in synthetic_cases}
    expected = {
        "jd-syn-v1-001": ("job_requirements_html", "OMITTED"),
        "jd-syn-v1-002": ("job_requirements_html", "NULL"),
        "jd-syn-v1-003": ("job_requirements_html", "EMPTY"),
        "jd-syn-v1-004": ("job_requirements_html", "WHITESPACE"),
        "jd-syn-v1-005": ("job_description_html", "OMITTED"),
        "jd-syn-v1-006": ("job_description_html", "NULL"),
    }
    for case_id, (field, state) in expected.items():
        record = by_id[case_id]
        source = record["target_job_source"]
        if state == "OMITTED":
            assert field not in source
        elif state == "NULL":
            assert source[field] is None
        elif state == "EMPTY":
            assert source[field] == ""
        else:
            assert source[field] == " \t "
        available_field = (
            "job_requirements_html" if field == "job_description_html" else "job_description_html"
        )
        statements = record["expected_statements"]
        assert statements
        assert {statement["source_field"] for statement in statements} == {
            "JOB_REQUIREMENTS" if available_field == "job_requirements_html" else "JOB_DESCRIPTION"
        }
        assert isinstance(source[available_field], str) and source[available_field].strip()


def test_required_boundary_tags_point_to_semantic_examples(api, synthetic_cases):
    by_id = {case["case_id"]: case for case in synthetic_cases}
    tagged = {tag: case for case in synthetic_cases for tag in case["boundary_tags"]}
    assert any(
        statement["statement_type"] == "BEHAVIORAL_REQUIREMENT"
        and statement["capability_relevance"] == "CAPABILITY_BEARING"
        for statement in tagged["behavioral_capability_candidate"]["expected_statements"]
    )

    split = tagged["coordinated_clause_split"]
    split_responsibilities = [
        item
        for item in split["expected_statements"]
        if item["statement_type"] == "RESPONSIBILITY"
        and item["source_field"] == "JOB_DESCRIPTION"
        and item["source_order"] in {1, 2}
    ]
    assert len(split_responsibilities) == 2
    split_source = split["target_job_source"]["job_description_html"]
    assert "và kiểm thử luồng thanh toán" in split_source

    mixed = tagged["mixed_requirement_clause"]
    mixed_source = mixed["target_job_source"]["job_requirements_html"]
    assert "và Tốt nghiệp" in mixed_source
    assert {item["statement_type"] for item in mixed["expected_statements"]} >= {
        "EXPERIENCE_REQUIREMENT",
        "EDUCATION_REQUIREMENT",
    }

    duplicate = tagged["duplicate_semantics_across_source_fields"]
    duplicate_texts = [
        item["source_text"]
        for item in duplicate["expected_statements"]
        if item["statement_type"] == "RESPONSIBILITY"
    ]
    assert len(duplicate_texts) != len(set(duplicate_texts))
    assert {
        item["source_field"]
        for item in duplicate["expected_statements"]
        if item["source_text"] == duplicate_texts[0]
    } == {"JOB_DESCRIPTION", "JOB_REQUIREMENTS"}

    age = tagged["age_or_personal_condition_other"]
    age_statement = next(
        item for item in age["expected_statements"] if "25 đến 35" in item["source_text"]
    )
    assert (age_statement["statement_type"], age_statement["capability_relevance"]) == (
        "OTHER",
        "NON_CAPABILITY",
    )
    tool_context = by_id["jd-syn-v1-022"]
    tool_other = next(
        item for item in tool_context["expected_statements"] if "Tableau" in item["source_text"]
    )
    assert (tool_other["statement_type"], tool_other["capability_relevance"]) == (
        "OTHER",
        "NON_CAPABILITY",
    )


CONFORMANCE_PATH = (
    Path(__file__).parents[1]
    / "evals/job_semantics/requirement_breakdown_eval_00/conformance.v1.jsonl"
)
MANIFEST_PATH = CONFORMANCE_PATH.with_name("manifest.synthetic.v1.json")


def test_conformance_suite_has_32_isolated_fixtures_and_nullable_state_coverage(api):
    assert CONFORMANCE_PATH.is_file(), f"missing conformance suite: {CONFORMANCE_PATH}"
    fixtures = function(api, "load_jsonl")(CONFORMANCE_PATH)
    assert len(fixtures) == 32
    ids = [fixture["fixture_id"] for fixture in fixtures]
    assert len(ids) == len(set(ids))
    assert all(str(fixture_id).startswith("jdb-cf-v1-") for fixture_id in ids)

    expected_states = {"OMITTED", "NULL", "EMPTY", "WHITESPACE"}
    matrix: dict[str, set[str]] = {"target_job_source": set()}
    source_keys = (
        "source_application_ref",
        "job_description_html",
        "job_requirements_html",
        "job_posting_url",
    )
    matrix.update({key: set() for key in source_keys})
    for fixture in fixtures:
        states = fixture.get("source_states")
        if isinstance(states, dict):
            for key, state in states.items():
                if key in matrix:
                    matrix[key].add(str(state))
        input_value = fixture.get("input")
        if isinstance(input_value, dict):
            projected = function(api, "build_provider_input")(input_value)
            assert projected == fixture["expected_provider_input"]
    assert {"OMITTED", "NULL", "EMPTY"} <= matrix["target_job_source"]
    assert all(expected_states <= matrix[key] for key in source_keys)

    semantic_groups = {fixture.get("group") for fixture in fixtures}
    assert {
        "split_types",
        "coherent_keep",
        "source_field_crossover",
        "html_entity_and_inline",
        "html_list_and_br",
        "provider_exclusion",
        "capability_non_inference",
    } <= semantic_groups

    corpus_ids = {case["case_id"] for case in function(api, "load_jsonl")(DATASET_PATH)}
    semantic_fixtures = [fixture for fixture in fixtures if fixture.get("group") in semantic_groups]
    semantic_fixtures = [fixture for fixture in semantic_fixtures if "case" in fixture]
    assert len(semantic_fixtures) == 13
    by_group = {}
    for fixture in semantic_fixtures:
        by_group.setdefault(fixture["group"], []).append(fixture)
    for fixture in semantic_fixtures:
        value = fixture["case"]
        assert value["case_id"] not in corpus_ids
        function(api, "validate_case")(value)
        source_html = value["target_job_source"].get(
            "job_description_html", value["target_job_source"].get("job_requirements_html")
        )
        assert function(api, "html_text_view")(source_html) == fixture["expected_text_view"]
        if fixture["group"] == "provider_exclusion":
            assert function(api, "build_provider_input")(value) == {
                "target_job_source": {"job_description_html": source_html}
            }
    split_types = by_group["split_types"][0]["case"]["expected_statements"]
    assert {statement["statement_type"] for statement in split_types} == {
        "EXPERIENCE_REQUIREMENT",
        "EDUCATION_REQUIREMENT",
    }
    assert (
        by_group["coherent_keep"][0]["case"]["expected_statements"][0]["statement_type"]
        == "RESPONSIBILITY"
    )
    assert (
        by_group["source_field_crossover"][0]["case"]["expected_statements"][0]["source_field"]
        == "JOB_REQUIREMENTS"
    )
    assert all(
        statement["capability_relevance"] == "NON_CAPABILITY"
        for fixture in by_group["capability_non_inference"]
        for statement in fixture["case"]["expected_statements"]
    )


def test_freeze_manifest_recomputes_and_matches_all_frozen_artifacts(api):
    assert MANIFEST_PATH.is_file(), f"missing freeze manifest: {MANIFEST_PATH}"
    verifier = function(api, "verify_freeze_manifest")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    result = verifier(MANIFEST_PATH.parent, manifest)

    assert result["valid"] is True
    assert manifest["provider_calls_before_freeze"] == 0
    assert isinstance(manifest["code_worktree_clean"], bool)
    assert manifest["counts"]["posting_count"] == 40
    assert manifest["counts"]["atomic_statement_count"] == 301
    assert manifest["hashes"]["dataset_jsonl_sha256"] == function(api, "artifact_sha256")(
        DATASET_PATH.read_bytes()
    )
    assert len(manifest["hashes"]["semantic_fingerprint_sha256"]) == 64

    tampered = dict(manifest)
    tampered["provider_calls_before_freeze"] = 1
    with pytest.raises(ValueError, match="provider_calls_before_freeze"):
        verifier(MANIFEST_PATH.parent, tampered)
