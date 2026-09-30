from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
    register_instructional_design_experiment_contracts,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def _rendered(version: str) -> str:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_instructional_design_experiment_contracts(prompts, schemas)
    return "\n".join(
        message.content
        for message in prompts.resolve(ASSESSMENT_DESIGN_SCHEMA_ID, version).render(
            {"brief_id": "brief-1", "objectives": [{"id": "obj-a"}]}
        )
    )


def test_v031_assessment_prompt_owns_only_supplied_objective_ids() -> None:
    rendered = _rendered(INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031).casefold()

    assert "only the supplied objective ids" in rendered
    assert "never invent objective ids" in rendered
    assert "or reference objectives from another module or stage" in rendered


def test_v031_assessment_prompt_separates_measured_capabilities_from_dependencies() -> None:
    rendered = _rendered(INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031).casefold()

    assert "`required_capabilities` are capabilities directly demonstrated" in rendered
    assert "`dependency_candidates` are supporting knowledge or skills" in rendered
    assert "must remain candidate" in rendered


def test_v031_assessment_prompt_blocks_scope_creep_and_stays_domain_neutral() -> None:
    rendered = _rendered(INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031).casefold()

    assert "must not introduce capabilities beyond the objective" in rendered
    assert "do not add it-specific assumptions" in rendered
    assert "if an objective is missing, return the existing unresolved state" in rendered


def test_v03_assessment_prompt_remains_the_historical_contract() -> None:
    historical = _rendered(INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03)

    assert "never invent objective IDs" not in historical
