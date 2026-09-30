from datetime import UTC, datetime

import pytest

from app.instructional_design.contracts import (
    AssessmentDesignOutput,
    CoursePlanningOutput,
    LearningObjectiveDesignOutput,
    LessonPlanningOutput,
    PrerequisiteProposalOutput,
)
from app.instructional_design.experiment import (
    ExperimentCondition,
    ExperimentConfig,
    ExperimentRun,
    GenerationConfig,
    PromptSchemaVersion,
)
from app.instructional_design.experiment_runners import (
    StructuredDesigners,
    execute_structured_run,
)
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    AssessmentDependencyRole,
    AssessmentDependencyStatus,
)


def _run() -> ExperimentRun:
    config = ExperimentConfig(
        experiment_id="id-03b5a",
        experiment_version="0.1",
        fixture_ids=["fixture-1"],
        runs_per_fixture_per_condition=1,
        conditions=(ExperimentCondition.STRUCTURED_V031,),
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
                prompt_version="0.3.1",
                schema_id="instructional_objective_design",
                schema_version="0.3.1",
            )
        ],
    )
    return ExperimentRun.from_config(
        run_id="id-03b5a-run",
        config=config,
        fixture_id="fixture-1",
        condition=ExperimentCondition.STRUCTURED_V031,
        run_number=1,
        started_at=datetime(2026, 8, 14, tzinfo=UTC),
    )


class _DependencyRecordingStages:
    def __init__(self, bundle: object, candidate: AssessmentDependencyCandidate) -> None:
        self.bundle = bundle
        self.candidate = candidate
        self.received: dict[str, list[AssessmentDependencyCandidate]] = {}
        self.prerequisites_received: dict[str, object] = {}

    async def objective(self, brief: object) -> LearningObjectiveDesignOutput:
        return LearningObjectiveDesignOutput(
            brief_id=self.bundle.brief.id, objectives=list(self.bundle.objectives)
        )

    async def assessment(self, brief: object, objectives: object) -> AssessmentDesignOutput:
        return AssessmentDesignOutput(
            objective_ids=[item.id for item in self.bundle.objectives],
            assessments=list(self.bundle.assessments),
            dependency_candidates=[self.candidate],
        )

    async def prerequisite(
        self,
        brief: object,
        objectives: object,
        assessments: object,
        dependency_candidates: list[AssessmentDependencyCandidate],
    ) -> PrerequisiteProposalOutput:
        self.received["prerequisite"] = dependency_candidates
        self.prerequisites_received["prerequisite"] = list(self.bundle.prerequisites)
        return PrerequisiteProposalOutput(
            brief_id=self.bundle.brief.id, prerequisites=list(self.bundle.prerequisites)
        )

    async def course(
        self,
        brief: object,
        objectives: object,
        assessments: object,
        prerequisites: object,
        dependency_candidates: list[AssessmentDependencyCandidate],
    ) -> CoursePlanningOutput:
        self.received["course"] = dependency_candidates
        self.prerequisites_received["course"] = prerequisites
        return CoursePlanningOutput(
            brief_id=self.bundle.brief.id, course_outline=self.bundle.course_outline
        )

    async def lesson(
        self,
        brief: object,
        objectives: object,
        assessments: object,
        prerequisites: object,
        course_outline: object,
        dependency_candidates: list[AssessmentDependencyCandidate],
        module_objective_scope: object,
    ) -> LessonPlanningOutput:
        self.received["lesson"] = dependency_candidates
        self.prerequisites_received["lesson"] = prerequisites
        return LessonPlanningOutput(
            course_id=self.bundle.course_outline.id, lessons=list(self.bundle.lessons)
        )


class _StageAdapter:
    def __init__(self, function: object) -> None:
        self.function = function

    async def propose(self, *args: object) -> object:
        return await self.function(*args)


@pytest.mark.asyncio
async def test_dependency_candidates_reach_each_planning_stage_without_promotion() -> None:
    bundle = next(iter(research_fixture_bundles().values()))
    candidate = AssessmentDependencyCandidate(
        capability="understand data types",
        reason="Needed before the target performance can begin.",
        required_for_refs=[bundle.assessments[0].id],
    )
    stages = _DependencyRecordingStages(bundle, candidate)
    result = await execute_structured_run(
        run=_run(),
        brief=bundle.brief,
        designers=StructuredDesigners(
            objective=_StageAdapter(stages.objective),
            assessment=_StageAdapter(stages.assessment),
            prerequisite=_StageAdapter(stages.prerequisite),
            course=_StageAdapter(stages.course),
            lesson=_StageAdapter(stages.lesson),
        ),
    )

    assert result.snapshot is not None
    assert result.snapshot.dependency_candidates == [candidate]
    assert stages.received == {
        "prerequisite": [candidate],
        "course": [candidate],
        "lesson": [candidate],
    }
    assert all(
        item.source_dependency_refs
        for item in stages.prerequisites_received["course"]
    )
    assert all(
        item.source_dependency_refs
        for item in stages.prerequisites_received["lesson"]
    )
    assert candidate not in result.snapshot.assessments[0].required_capability_refs
    propagated = [
        item
        for item in result.snapshot.canonical_dependencies
        if item.capability_ref == "understand data types"
    ]
    assert len(propagated) == 1
    assert propagated[0].dependency_role is AssessmentDependencyRole.SUPPORTING_DEPENDENCY
    assert propagated[0].status is AssessmentDependencyStatus.CANDIDATE
    assert propagated[0].provenance.sources[0].source_ref == bundle.assessments[0].id
