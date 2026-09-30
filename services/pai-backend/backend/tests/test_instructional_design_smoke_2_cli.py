import asyncio
from datetime import UTC, datetime
from typing import cast

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_ID,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    AssessmentDesignOutput,
    CoursePlanningOutput,
    LearningObjectiveDesignOutput,
    LessonPlanningOutput,
    OneShotInstructionalDesignOutput,
    PrerequisiteProposalOutput,
)
from app.instructional_design.experiment import ExperimentCondition
from app.instructional_design.fixtures import research_fixture_bundles
from app.model_gateway.contracts import (
    InferenceAuditMetadata,
    InferenceRequest,
    ModelGateway,
    ModelUsage,
    StructuredInferenceResponse,
)


class SmokeGateway:
    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []
        self.bundles = research_fixture_bundles()

    async def infer_structured(self, request: InferenceRequest, output_schema: type[object]) -> object:
        self.requests.append(request)
        brief_id = cast(dict[str, object], request.payload["brief"])["id"]
        bundle = next(bundle for bundle in self.bundles.values() if bundle.brief.id == brief_id)
        outputs: dict[type[object], object] = {
            LearningObjectiveDesignOutput: LearningObjectiveDesignOutput(
                brief_id=bundle.brief.id, objectives=list(bundle.objectives)
            ),
            AssessmentDesignOutput: AssessmentDesignOutput(
                objective_ids=[item.id for item in bundle.objectives],
                assessments=list(bundle.assessments),
            ),
            PrerequisiteProposalOutput: PrerequisiteProposalOutput(
                brief_id=bundle.brief.id, prerequisites=[]
            ),
            CoursePlanningOutput: CoursePlanningOutput(
                brief_id=bundle.brief.id, course_outline=bundle.course_outline
            ),
            LessonPlanningOutput: LessonPlanningOutput(
                course_id=bundle.course_outline.id, lessons=list(bundle.lessons)
            ),
            OneShotInstructionalDesignOutput: OneShotInstructionalDesignOutput(
                brief_id=bundle.brief.id,
                objectives=list(bundle.objectives),
                assessments=list(bundle.assessments),
                prerequisites=[],
                course_outline=bundle.course_outline,
                lessons=list(bundle.lessons),
            ),
        }
        return StructuredInferenceResponse(
            parsed=outputs[output_schema],
            audit=InferenceAuditMetadata(
                provider="vilao",
                model="claude-sonnet-5",
                model_revision="smoke-2-revision",
                prompt_template_id=request.prompt_template_id,
                prompt_template_version=request.prompt_template_version,
                output_schema_id=request.output_contract.schema_id if request.output_contract else None,
                output_schema_version=(
                    request.output_contract.schema_version if request.output_contract else None
                ),
                policy_version="privacy-v1",
                correlation_id=request.correlation_id,
                routing_decision="approved_external_sanitized",
                attempt_count=1,
                latency_ms=1,
                usage=ModelUsage(input_tokens=1, output_tokens=1),
                outcome="succeeded",
                protocol="openai_compatible",
                deployment_type="external",
                endpoint_origin="https://api.vilao.ai",
                data_boundary="external_provider",
            ),
        )


def test_smoke_2_uses_three_fixtures_both_conditions_and_eighteen_stage_calls() -> None:
    from app.instructional_design.smoke_2_cli import run_smoke_2

    gateway = SmokeGateway()
    execution = asyncio.run(
        run_smoke_2(
            gateway=cast(ModelGateway, gateway),
            model_provider="vilao",
            model_name="claude-sonnet-5",
            model_revision=None,
            policy_id="pai_instructional_design",
            policy_version="0.1",
            generation_started_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
    )

    assert execution.manifest.fixture_ids == [
        "model_monitoring",
        "python_data_processing",
        "technical_communication",
    ]
    assert execution.manifest.conditions == (
        ExperimentCondition.ONE_SHOT,
        ExperimentCondition.STRUCTURED,
    )
    assert execution.manifest.runs_per_fixture_per_condition == 1
    assert execution.manifest.estimated_model_call_count == 18
    assert len(execution.results) == 6
    assert len(gateway.requests) == 18
    assert len(execution.comparisons) == 3
    assert all(len(item.one_shot_runs) == len(item.structured_runs) == 1 for item in execution.comparisons)
    assert all(result.snapshot is not None for result in execution.results)
    assert all(
        result.snapshot.quality_report.policy_id == "pai_instructional_design"
        and result.snapshot.quality_report.policy_version == "0.1"
        for result in execution.results
        if result.snapshot is not None
    )
    assert all("winner" not in item.model_dump(mode="json") for item in execution.comparisons)
    assert [request.prompt_template_id for request in gateway.requests].count(
        ONE_SHOT_BASELINE_SCHEMA_ID
    ) == 3
    for prompt_id in (
        OBJECTIVE_DESIGN_SCHEMA_ID,
        ASSESSMENT_DESIGN_SCHEMA_ID,
        PREREQUISITE_PROPOSAL_SCHEMA_ID,
        COURSE_PLANNING_SCHEMA_ID,
        LESSON_PLANNING_SCHEMA_ID,
    ):
        assert [request.prompt_template_id for request in gateway.requests].count(prompt_id) == 3
