from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleRequirement,
)
from app.role_profile_authoring.quality_gate import (
    evaluate_role_profile_draft,
    validate_role_profile_requirements,
)


def requirement(requirement_id: str, terms: list[str]) -> RoleRequirement:
    return RoleRequirement(
        id=requirement_id,
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.PREFERRED,
        evidence_terms=terms,
        confidence_threshold=0.7,
        assessment_recommendation="practical_task",
        rubric_version="rubric-v1",
    )


def test_gate_rejects_duplicate_ids_and_empty_terms() -> None:
    invalid = RoleRequirement.model_construct(
        id="same",
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.PREFERRED,
        evidence_terms=[],
        conflicting_terms=[],
        confidence_threshold=0.7,
        assessment_recommendation="practical_task",
        rubric_version="rubric-v1",
    )
    result = validate_role_profile_requirements([invalid, requirement("same", ["python"])])

    assert result.passed is False
    assert {item.code for item in result.findings} == {
        "duplicate_requirement_id",
        "empty_evidence_terms",
    }


def test_gate_accepts_complete_structured_requirements() -> None:
    result = validate_role_profile_requirements([requirement("python", ["python"])])

    assert result.passed is True
    assert result.findings == []


def test_gate_accepts_null_dimension_only_for_responsibilities() -> None:
    responsibility = RoleRequirement(
        id="monthly-reports",
        criterion_dimension=None,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["prepare monthly financial reports"],
        modality="responsibility",
        confidence_threshold=0.7,
        assessment_recommendation="review",
        rubric_version="rubric-v1",
    )

    assert validate_role_profile_requirements([responsibility]).passed is True


def test_gate_rejects_null_dimension_for_non_responsibility() -> None:
    criterion = RoleRequirement(
        id="strong-sql",
        criterion_dimension=None,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["strong sql"],
        modality="must",
        confidence_threshold=0.7,
        assessment_recommendation="review",
        rubric_version="rubric-v1",
    )

    result = validate_role_profile_requirements([criterion])

    assert result.passed is False
    assert [item.code for item in result.findings] == ["missing_criterion_dimension"]


def test_gate_accepts_null_dimension_for_unspecified_scope_context() -> None:
    exclusion = RoleRequirement(
        id="warehouse-not-required",
        criterion_dimension=None,
        classification=RequirementClassification.UNCLASSIFIED,
        evidence_terms=["warehouse knowledge is not required"],
        modality="unspecified",
        confidence_threshold=0.7,
        assessment_recommendation="context_only",
        rubric_version="rubric-v1",
    )

    assert validate_role_profile_requirements([exclusion]).passed is True


def test_gate_rejects_dimension_on_responsibility() -> None:
    responsibility = requirement("monthly-reports", ["prepare monthly financial reports"]).model_copy(
        update={"modality": "responsibility"}
    )

    result = validate_role_profile_requirements([responsibility])

    assert result.passed is False
    assert [item.code for item in result.findings] == [
        "responsibility_dimension_must_be_null"
    ]


def test_gate_blocks_only_missing_source_chain_for_legacy_provenance() -> None:
    complete = requirement("python", ["python"]).model_copy(
        update={
            "source_requirement_ref": "legacy.skill.1",
            "source_locator": {
                "document_id": "jd-1",
                "section": "required_skills",
                "start_offset": 0,
                "end_offset": 6,
            },
        }
    )

    _, _, valid_eligibility = evaluate_role_profile_draft(
        [complete],
        source_jd_profile_id="jd-accepted",
        source_jd_profile_version=1,
        source_schema="legacy_v1",
        source_version="1.1",
    )
    _, missing_locator_findings, missing_locator_eligibility = evaluate_role_profile_draft(
        [complete.model_copy(update={"source_locator": None})],
        source_jd_profile_id="jd-accepted",
        source_jd_profile_version=1,
        source_schema="legacy_v1",
        source_version="1.1",
    )

    assert valid_eligibility.can_approve_provisional is True
    assert missing_locator_eligibility.can_approve_provisional is False
    assert {item.code for item in missing_locator_findings} == {
        "legacy_missing_provenance",
        "legacy_missing_modality",
        "legacy_missing_logical_group",
        "legacy_missing_target_level",
        "legacy_missing_observable_behavior",
        "legacy_missing_evidence_constraints",
    }
