from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_VERSION,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    OneShotInstructionalDesignOutput,
    register_instructional_design_experiment_contracts,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def test_v02_structured_prompts_are_registered_as_separate_responsibilities() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()

    register_instructional_design_experiment_contracts(prompts, schemas)

    for prompt_id in (
        OBJECTIVE_DESIGN_SCHEMA_ID,
        ASSESSMENT_DESIGN_SCHEMA_ID,
        PREREQUISITE_PROPOSAL_SCHEMA_ID,
        COURSE_PLANNING_SCHEMA_ID,
        LESSON_PLANNING_SCHEMA_ID,
    ):
        template = prompts.resolve(prompt_id, INSTRUCTIONAL_DESIGN_STAGE_VERSION)
        assert template.version == "0.2"
        assert schemas.resolve(prompt_id, INSTRUCTIONAL_DESIGN_STAGE_VERSION)
        assert "research-only" in template.system_instruction.casefold()


def test_structured_prompt_boundaries_do_not_cross_design_responsibilities() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_instructional_design_experiment_contracts(prompts, schemas)

    objective = prompts.resolve(OBJECTIVE_DESIGN_SCHEMA_ID, "0.2").system_instruction.casefold()
    assessment = prompts.resolve(ASSESSMENT_DESIGN_SCHEMA_ID, "0.2").system_instruction.casefold()
    prerequisite = prompts.resolve(
        PREREQUISITE_PROPOSAL_SCHEMA_ID, "0.2"
    ).system_instruction.casefold()
    course = prompts.resolve(COURSE_PLANNING_SCHEMA_ID, "0.2").system_instruction.casefold()
    lesson = prompts.resolve(LESSON_PLANNING_SCHEMA_ID, "0.2").system_instruction.casefold()

    assert "do not produce lessons" in objective
    assert "do not redesign objectives" in assessment
    assert "candidate" in prerequisite and "confirmed" in prerequisite
    assert "do not generate factual lesson content" in course
    assert "do not generate factual lesson prose" in lesson


def test_one_shot_baseline_maps_to_canonical_output_without_structured_coaching() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_instructional_design_experiment_contracts(prompts, schemas)

    template = prompts.resolve(ONE_SHOT_BASELINE_SCHEMA_ID, ONE_SHOT_BASELINE_SCHEMA_VERSION)
    rendered = "\n".join(
        message.content for message in template.render({"brief_id": "brief-1"})
    ).casefold()

    assert (
        schemas.resolve(ONE_SHOT_BASELINE_SCHEMA_ID, ONE_SHOT_BASELINE_SCHEMA_VERSION)
        is OneShotInstructionalDesignOutput
    )
    assert "canonical instructional-design aggregate" in rendered
    assert "schema:" in rendered
    assert '"brief_id"' in rendered
    assert "first create objectives" not in rendered
    assert "then design assessment" not in rendered
