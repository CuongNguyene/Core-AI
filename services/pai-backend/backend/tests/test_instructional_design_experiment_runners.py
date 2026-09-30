from datetime import UTC, datetime
from typing import cast

import pytest

from app.instructional_design.contracts import (
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_VERSION,
    AssessmentDesigner,
    CoursePlanner,
    LearningObjectiveDesignOutput,
    LessonPlanner,
    PrerequisiteProposer,
)
from app.instructional_design.experiment import (
    ExperimentCondition,
    ExperimentConfig,
    ExperimentRun,
    ExperimentRunStatus,
    GenerationConfig,
    PromptSchemaVersion,
)
from app.instructional_design.experiment_runners import (
    FixtureOneShotInstructionalDesignGenerator,
    FixtureStructuredDesigners,
    StructuredDesigners,
    execute_one_shot_run,
    execute_structured_run,
)
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.schemas import ResearchLearningBrief


def config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="id-02",
        experiment_version="0.1",
        fixture_ids=["fixture-1"],
        runs_per_fixture_per_condition=1,
        model_provider="fixture-provider",
        model_name="fixture-model",
        model_revision="fixture-revision",
        generation_config=GenerationConfig(temperature=0.0, max_output_tokens=4096),
        policy_id="pai_instructional_design",
        policy_version="0.1",
        dependency_normalizer_version="id02d.2@0.1",
        prompt_schema_versions=[
            PromptSchemaVersion(
                prompt_id="instructional_objective_design",
                prompt_version="0.2",
                schema_id="instructional_objective_design",
                schema_version="0.2",
            ),
            PromptSchemaVersion(
                prompt_id=ONE_SHOT_BASELINE_SCHEMA_ID,
                prompt_version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
                schema_id=ONE_SHOT_BASELINE_SCHEMA_ID,
                schema_version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
            ),
        ],
    )


def run(condition: ExperimentCondition) -> ExperimentRun:
    return ExperimentRun.from_config(
        run_id=f"run-{condition.value}",
        config=config(),
        fixture_id="fixture-1",
        condition=condition,
        run_number=1,
        started_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_baseline_and_structured_runs_use_same_brief_and_quality_gate() -> None:
    bundle = next(iter(research_fixture_bundles().values()))
    baseline_generator = FixtureOneShotInstructionalDesignGenerator(bundle)
    structured_designers = FixtureStructuredDesigners(bundle)

    baseline = await execute_one_shot_run(
        run=run(ExperimentCondition.ONE_SHOT),
        brief=bundle.brief,
        generator=baseline_generator,
    )
    structured = await execute_structured_run(
        run=run(ExperimentCondition.STRUCTURED),
        brief=bundle.brief,
        designers=structured_designers,
    )

    assert baseline.status is ExperimentRunStatus.COMPLETED
    assert structured.status is ExperimentRunStatus.COMPLETED
    assert baseline.snapshot is not None and structured.snapshot is not None
    assert baseline_generator.received_brief_id == structured_designers.received_brief_ids[0]
    assert baseline.snapshot.quality_report == structured.snapshot.quality_report
    assert set(baseline.snapshot.generation_provenance.prompt_versions) == {
        ONE_SHOT_BASELINE_SCHEMA_ID
    }
    assert OBJECTIVE_DESIGN_SCHEMA_ID in structured.snapshot.generation_provenance.prompt_versions
    assert ONE_SHOT_BASELINE_SCHEMA_ID not in structured.snapshot.generation_provenance.prompt_versions


@pytest.mark.asyncio
async def test_failed_objective_stage_is_explicit_and_does_not_invent_downstream_artifacts() -> (
    None
):
    bundle = next(iter(research_fixture_bundles().values()))

    class FailingObjectiveDesigner:
        async def propose(self, brief: ResearchLearningBrief) -> LearningObjectiveDesignOutput:
            raise ValueError("invalid objective proposal")

    class MustNotRun:
        async def propose(self, *args: object) -> object:
            raise AssertionError("downstream stage must not run")

    designers = StructuredDesigners(
        objective=FailingObjectiveDesigner(),
        assessment=cast(AssessmentDesigner, MustNotRun()),
        prerequisite=cast(PrerequisiteProposer, MustNotRun()),
        course=cast(CoursePlanner, MustNotRun()),
        lesson=cast(LessonPlanner, MustNotRun()),
    )

    result = await execute_structured_run(
        run=run(ExperimentCondition.STRUCTURED), brief=bundle.brief, designers=designers
    )

    assert result.status is ExperimentRunStatus.FAILED
    assert result.stage_failure is not None
    assert result.stage_failure.stage == "ObjectiveDesigner"
    assert result.stage_failure.failure_class == "ValueError"
    assert result.snapshot is None
    assert result.partial_artifacts is not None
    assert result.partial_artifacts.objectives == []
