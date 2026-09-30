import pytest

from app.instructional_design.blinded_review_id03c2_merge import merge_completion


def _draft() -> dict:
    return {
        "review_id": "review-001",
        "rubric_scores": {
            "objective_measurability": 4, "objective_assessment_alignment": 4,
            "evidence_validity": 4, "cognitive_alignment": 4, "prerequisite_quality": 3,
            "course_sequence_coherence": 4, "instruction_assessment_alignment": 3,
        },
        "rationales": {
            "objective_measurability": "existing", "objective_assessment_alignment": "existing",
            "evidence_validity": "existing", "cognitive_alignment": "existing",
            "prerequisite_quality": "existing", "course_sequence_coherence": "existing",
            "instruction_assessment_alignment": "existing",
        },
        "machine_validity_observations": [], "prerequisites_acceptable": None,
        "edit_effort": "minor", "special_question": None, "top_strengths": [], "top_issues": [],
    }


def _request() -> dict:
    return {
        "review_id": "review-001", "reviewer_id": "reviewer-01",
        "fixture_id": "python_data_processing",
        "required_completion": {
            "rubric_scores.scope_balance": {}, "rubric_scores.workload_time_realism": {},
            "rubric_scores.domain_appropriateness": {}, "prerequisites_acceptable": {},
            "special_question": {},
        },
    }


def _completion() -> dict:
    return {
        "review_id": "review-001", "reviewer_id": "reviewer-01",
        "completion": {
            "rubric_scores": {"scope_balance": 4, "workload_time_realism": 3, "domain_appropriateness": 5},
            "rationales": {"scope_balance": "scope", "workload_time_realism": "time", "domain_appropriateness": "domain"},
            "prerequisites_acceptable": True,
            "special_question": {"answer": "YES", "rationale": "reasonable"},
        },
    }


def test_valid_missing_fields_are_merged() -> None:
    result = merge_completion(_draft(), _request(), _completion(), expected_reviewer_id="reviewer-01")
    assert result.state == "CANONICAL_VALID"
    assert result.merged["rubric_scores"]["scope_balance"] == 4
    assert result.merged["special_question"]["answer"] == "YES"


def test_existing_judgement_overwrite_is_conflict() -> None:
    completion = _completion()
    completion["completion"]["rubric_scores"]["evidence_validity"] = 2
    result = merge_completion(_draft(), _request(), completion, expected_reviewer_id="reviewer-01")
    assert result.state == "CONFLICT"
    assert result.merged["rubric_scores"]["evidence_validity"] == 4


@pytest.mark.parametrize("mutator", [
    lambda value: value["completion"]["rubric_scores"].update(scope_balance=6),
    lambda value: value["completion"]["special_question"].update(answer="YES because..."),
    lambda value: value["completion"].update(prerequisites_acceptable="yes"),
    lambda value: value.update(review_id="review-999"),
    lambda value: value.update(reviewer_id="reviewer-99"),
])
def test_invalid_completion_is_rejected(mutator) -> None:
    completion = _completion()
    mutator(completion)
    result = merge_completion(_draft(), _request(), completion, expected_reviewer_id="reviewer-01")
    assert result.state == "INVALID_COMPLETION"


def test_missing_requested_value_is_incomplete() -> None:
    completion = _completion()
    del completion["completion"]["rationales"]["scope_balance"]
    result = merge_completion(_draft(), _request(), completion, expected_reviewer_id="reviewer-01")
    assert result.state == "INCOMPLETE"
