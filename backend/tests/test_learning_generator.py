from datetime import date

import pytest

from app.learning.generator import ContentGenerationRequest, FakeContentBlueprintGenerator
from app.learning.schemas import LearningObjective


@pytest.mark.asyncio
async def test_fake_generator_is_deterministic_and_metadata_only() -> None:
    generator = FakeContentBlueprintGenerator()
    request = ContentGenerationRequest(
        target_profile_id="role-1",
        target_profile_version="1.0",
        preliminary_match_id="match-1",
        objectives=[
            LearningObjective(
                id="objective-python",
                competency_id="python",
                current_level=1,
                target_level=2,
                measurable_outcome="Write functions",
                gap_id="python",
                sequence=1,
            )
        ],
        target_completion_date=date(2026, 12, 1),
        policy_version="learning-policy-1",
    )

    first = await generator.generate(request)
    second = await generator.generate(request)

    assert first == second
    assert first.learning_objects[0].approved_source_reference == "catalog:python"
    assert "prompt" not in first.model_dump()
    assert "content" not in first.model_dump()
