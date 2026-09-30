import json
from datetime import date
from pathlib import Path

import pytest

from app.learning.generator import ContentGenerationRequest, FakeContentBlueprintGenerator
from app.learning.schemas import LearningObjective


@pytest.mark.asyncio
async def test_learning_blueprint_golden_is_deterministic_and_safe() -> None:
    fixture = json.loads(
        Path(__file__).with_name("golden").joinpath("learning_path_blueprint.json").read_text()
    )
    request = ContentGenerationRequest(
        target_profile_id=fixture["target_profile_id"],
        target_profile_version=fixture["target_profile_version"],
        preliminary_match_id=fixture["preliminary_match_id"],
        objectives=[
            LearningObjective(
                id="objective-python",
                competency_id="python",
                current_level=1,
                target_level=2,
                measurable_outcome="Demonstrate python at the next target level",
                gap_id="python",
                sequence=1,
            )
        ],
        target_completion_date=date.fromisoformat(fixture["target_completion_date"]),
        policy_version="policy-1",
    )
    generator = FakeContentBlueprintGenerator()

    first = await generator.generate(request)
    second = await generator.generate(request)
    output = first.model_dump()

    assert first == second
    assert output["learning_objects"][0]["id"] == fixture["expected"]["learning_object_id"]
    assert (
        output["learning_objects"][0]["approved_source_reference"]
        == fixture["expected"]["approved_source_reference"]
    )
    assert (
        output["learning_objects"][0]["assessment_template_id"]
        == fixture["expected"]["assessment_template_id"]
    )
    assert output["lessons"][0]["id"] == fixture["expected"]["lesson_id"]
    assert output["modules"][0]["id"] == fixture["expected"]["module_id"]
    assert all(key not in output for key in ("prompt", "content", "raw_document", "credential"))
