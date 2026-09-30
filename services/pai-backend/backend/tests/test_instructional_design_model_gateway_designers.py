from datetime import UTC, datetime
from typing import cast

import pytest

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
from app.instructional_design.experiment import (
    ExperimentCondition,
    ExperimentConfig,
    ExperimentRun,
    GenerationConfig,
    PromptSchemaVersion,
)
from app.instructional_design.experiment_runners import (
    execute_one_shot_run,
    execute_structured_run,
)
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.schemas import PrerequisiteBasis, PrerequisiteSpec, PrerequisiteStatus
from app.model_gateway.contracts import (
    DataClassification,
    InferenceAuditMetadata,
    InferenceRequest,
    ModelGateway,
    ModelUsage,
    StructuredInferenceResponse,
)


class GatewayFixture:
    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []
        self.bundle = next(iter(research_fixture_bundles().values()))

    async def infer_structured(self, request: InferenceRequest, output_schema: type[object]) -> object:
        self.requests.append(request)
        audit = InferenceAuditMetadata(
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
            latency_ms=4,
            usage=ModelUsage(input_tokens=10, output_tokens=20),
            outcome="succeeded",
            protocol="openai_compatible",
            deployment_type="external",
            endpoint_origin="https://api.vilao.ai",
            data_boundary="external_provider",
        )
        outputs: dict[type[object], object] = {
            LearningObjectiveDesignOutput: LearningObjectiveDesignOutput(
                brief_id=self.bundle.brief.id,
                objectives=list(self.bundle.objectives),
            ),
            AssessmentDesignOutput: AssessmentDesignOutput(
                objective_ids=[item.id for item in self.bundle.objectives],
                assessments=list(self.bundle.assessments),
            ),
            PrerequisiteProposalOutput: PrerequisiteProposalOutput(
                brief_id=self.bundle.brief.id,
                prerequisites=[
                    PrerequisiteSpec(
                        id="prerequisite-model-proposed",
                        capability="bounded prior knowledge",
                        status=PrerequisiteStatus.CANDIDATE,
                        basis=PrerequisiteBasis.MODEL_PROPOSED,
                    )
                ],
            ),
            CoursePlanningOutput: CoursePlanningOutput(
                brief_id=self.bundle.brief.id,
                course_outline=self.bundle.course_outline,
            ),
            LessonPlanningOutput: LessonPlanningOutput(
                course_id=self.bundle.course_outline.id,
                lessons=list(self.bundle.lessons),
            ),
            OneShotInstructionalDesignOutput: OneShotInstructionalDesignOutput(
                brief_id=self.bundle.brief.id,
                objectives=list(self.bundle.objectives),
                assessments=list(self.bundle.assessments),
                prerequisites=[],
                course_outline=self.bundle.course_outline,
                lessons=list(self.bundle.lessons),
            ),
        }
        return StructuredInferenceResponse(parsed=outputs[output_schema], audit=audit)


def config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="smoke-2",
        experiment_version="0.1",
        fixture_ids=["fixture-model-monitoring-limited-application"],
        runs_per_fixture_per_condition=1,
        model_provider="vilao",
        model_name="claude-sonnet-5",
        model_revision=None,
        generation_config=GenerationConfig(temperature=0.0, max_output_tokens=4096),
        policy_id="pai_instructional_design",
        policy_version="0.1",
        dependency_normalizer_version="id02d.2@0.1",
        prompt_schema_versions=[
            PromptSchemaVersion(
                prompt_id=prompt_id,
                prompt_version="0.2",
                schema_id=prompt_id,
                schema_version="0.2",
            )
            for prompt_id in (
                OBJECTIVE_DESIGN_SCHEMA_ID,
                ASSESSMENT_DESIGN_SCHEMA_ID,
                PREREQUISITE_PROPOSAL_SCHEMA_ID,
                COURSE_PLANNING_SCHEMA_ID,
                LESSON_PLANNING_SCHEMA_ID,
            )
        ]
        + [
            PromptSchemaVersion(
                prompt_id=ONE_SHOT_BASELINE_SCHEMA_ID,
                prompt_version="0.1",
                schema_id=ONE_SHOT_BASELINE_SCHEMA_ID,
                schema_version="0.1",
            )
        ],
    )


def run(condition: ExperimentCondition) -> ExperimentRun:
    return ExperimentRun.from_config(
        run_id=f"run-{condition.value}",
        config=config(),
        fixture_id="fixture-model-monitoring-limited-application",
        condition=condition,
        run_number=1,
        started_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_gateway_backed_conditions_use_isolated_prompts_shared_brief_and_audit_provenance() -> (
    None
):
    from app.instructional_design.model_gateway_designers import (
        ModelGatewayOneShotInstructionalDesignGenerator,
        ModelGatewayStructuredDesigners,
    )

    gateway = GatewayFixture()
    bundle = gateway.bundle
    baseline = await execute_one_shot_run(
        run=run(ExperimentCondition.ONE_SHOT),
        brief=bundle.brief,
        generator=ModelGatewayOneShotInstructionalDesignGenerator(
            gateway=cast(ModelGateway, gateway),
            requested_provider="vilao",
            correlation_id="smoke-2:baseline",
            output_token_budget=4096,
            temperature=0.0,
        ),
    )
    structured = await execute_structured_run(
        run=run(ExperimentCondition.STRUCTURED),
        brief=bundle.brief,
        designers=ModelGatewayStructuredDesigners(
            gateway=cast(ModelGateway, gateway),
            requested_provider="vilao",
            correlation_id="smoke-2:structured",
            output_token_budget=4096,
            temperature=0.0,
        ),
    )

    assert baseline.snapshot is not None and structured.snapshot is not None
    assert [request.prompt_template_id for request in gateway.requests] == [
        ONE_SHOT_BASELINE_SCHEMA_ID,
        OBJECTIVE_DESIGN_SCHEMA_ID,
        ASSESSMENT_DESIGN_SCHEMA_ID,
        PREREQUISITE_PROPOSAL_SCHEMA_ID,
        COURSE_PLANNING_SCHEMA_ID,
        LESSON_PLANNING_SCHEMA_ID,
    ]
    assert all(request.data_classification is DataClassification.PUBLIC for request in gateway.requests)
    assert all(request.requested_provider == "vilao" for request in gateway.requests)
    assert all(request.temperature == 0.0 for request in gateway.requests)
    assert all(
        cast(dict[str, object], request.payload["brief"])["id"] == bundle.brief.id
        for request in gateway.requests
    )
    course_payload = gateway.requests[-2].payload
    lesson_payload = gateway.requests[-1].payload
    assessment_payload = gateway.requests[2].payload
    assessment_allowed = cast(dict[str, object], assessment_payload["allowed_references"])
    assert assessment_allowed["objective_ids"] == [item.id for item in bundle.objectives]
    course_allowed = cast(dict[str, object], course_payload["allowed_references"])
    lesson_allowed = cast(dict[str, object], lesson_payload["allowed_references"])
    assert course_allowed["lesson_ids"] == []
    assert set(cast(list[str], lesson_allowed["module_ids"])) == {
        module.id for module in bundle.course_outline.modules
    }
    assert lesson_allowed["objective_ids_by_module"] == {
        module.id: module.objective_ids for module in bundle.course_outline.modules
    }
    assert baseline.model_audits[0].model_revision == "smoke-2-revision"
    assert len(structured.model_audits) == 5
    assert all(
        prerequisite.status is PrerequisiteStatus.CANDIDATE
        for prerequisite in structured.snapshot.prerequisites
    )
