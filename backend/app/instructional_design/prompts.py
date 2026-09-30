"""Prompt contracts for independent instructional-design proposal stages."""

import json

from pydantic import BaseModel

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_SCHEMA_VERSION,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V032,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V033,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_VERSION,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    AssessmentDesignOutput,
    CoursePlanningOutput,
    LearningObjectiveDesignOutput,
    LessonPlanningOutput,
    OneShotInstructionalDesignOutput,
    PrerequisiteProposalOutput,
)
from app.model_gateway.prompts import PromptTemplate

_SYSTEM_RULES = """You are proposing a research-only instructional-design artifact.
Return JSON only that conforms to the registered output schema.
Do not generate factual lesson content, citations, question banks, or a production learning path.
Do not invent approved role levels, source-backed facts, learner deficiencies, or competency verification.
Keep model-proposed assumptions explicit and provisional; a model-proposed prerequisite is candidate only.
Preserve supplied IDs and traceability. The deterministic policy, not this proposal, decides quality gates."""


_STAGE_INSTRUCTIONS = {
    OBJECTIVE_DESIGN_SCHEMA_ID: "Propose observable and assessable learning objectives from the supplied research brief.",
    ASSESSMENT_DESIGN_SCHEMA_ID: "Design claim-to-evidence-to-task assessment specifications for supplied objectives.",
    PREREQUISITE_PROPOSAL_SCHEMA_ID: "Propose unresolved candidate prerequisites without promoting them to confirmed.",
    COURSE_PLANNING_SCHEMA_ID: "Plan objective-linked modules and sequencing rationale without writing lesson content.",
    LESSON_PLANNING_SCHEMA_ID: "Plan lesson specifications and learner activities without generating factual teaching content.",
}


def instructional_design_prompt_templates() -> list[PromptTemplate]:
    return [
        PromptTemplate(
            template_id=template_id,
            version=INSTRUCTIONAL_DESIGN_SCHEMA_VERSION,
            system_instruction=_SYSTEM_RULES,
            user_instruction=instruction,
            payload_boundary="input_data",
        )
        for template_id, instruction in _STAGE_INSTRUCTIONS.items()
    ]


_EXPERIMENT_STAGE_INSTRUCTIONS = {
    OBJECTIVE_DESIGN_SCHEMA_ID: """Propose only observable, assessable learning objectives from the supplied research brief.
Preserve the brief ID and make any model assumption explicit and provisional. Do not produce lessons, modules, assessments, factual teaching content, approved role level, or competency verification.""",
    ASSESSMENT_DESIGN_SCHEMA_ID: """Propose only assessment specifications for supplied objectives using claim → evidence → task.
Preserve objective IDs and cognitive demand. Do not redesign objectives, generate a large question bank, treat completion as competency, or produce lesson content.""",
    PREREQUISITE_PROPOSAL_SCHEMA_ID: """Propose only possible prerequisite specifications from the supplied brief, objectives, and assessments.
Every model-proposed prerequisite must use basis=model_proposed and status=candidate. Do not mark a model-only prerequisite confirmed or infer learner deficiency.""",
    COURSE_PLANNING_SCHEMA_ID: """Propose only an objective-linked course outline from supplied artifacts.
Preserve objective and prerequisite references, include a conservative sequencing rationale, and avoid orphan modules. Do not generate factual lesson content or claim universal pedagogical optimality.""",
    LESSON_PLANNING_SCHEMA_ID: """Propose only lesson specifications from supplied brief, objectives, assessments, prerequisites, and course outline.
Preserve module/objective/assessment relationships and respect explicit prerequisite ordering. Do not generate factual lesson prose, citations, media, or question banks.""",
}


_ONE_SHOT_BASELINE_INSTRUCTION = """Design a complete canonical instructional-design aggregate for the supplied research brief.
Return objectives, assessments, prerequisites, course outline, lessons, and explicit assumptions in the registered JSON schema.
This is research-only: do not generate factual lesson content, citations, media, question banks, competency verification, learner deficiency claims, or production approval."""


_EXPERIMENT_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    OBJECTIVE_DESIGN_SCHEMA_ID: LearningObjectiveDesignOutput,
    ASSESSMENT_DESIGN_SCHEMA_ID: AssessmentDesignOutput,
    PREREQUISITE_PROPOSAL_SCHEMA_ID: PrerequisiteProposalOutput,
    COURSE_PLANNING_SCHEMA_ID: CoursePlanningOutput,
    LESSON_PLANNING_SCHEMA_ID: LessonPlanningOutput,
    ONE_SHOT_BASELINE_SCHEMA_ID: OneShotInstructionalDesignOutput,
}


def _structured_output_instruction(template_id: str) -> str:
    schema = _EXPERIMENT_OUTPUT_SCHEMAS[template_id].model_json_schema()
    return (
        "Return exactly one JSON object that validates against this registered schema. "
        "Do not include markdown, comments, explanations, or extra keys.\n\nSchema:\n"
        + json.dumps(schema, ensure_ascii=False)
    )


_V03_STAGE_INSTRUCTIONS = {
    OBJECTIVE_DESIGN_SCHEMA_ID: """Create only the smallest set of observable objectives needed for the brief's desired performances. Do not invent capabilities, role levels, learner deficiencies, or redundant micro-objectives. Every success criterion must be assessable.""",
    ASSESSMENT_DESIGN_SCHEMA_ID: """Assess only the supplied objective IDs and their stated performance. Preserve objective references exactly. Use `role` and `required_capabilities`: every required capability is a semantic capability/dependency, never an assessment, objective, lesson, module, or prerequisite ID. For legacy compatibility, `required_capability_refs` must contain capability names, never assessment IDs, objective IDs, or other artifact IDs. A formative assessment must have role=formative; a summative assessment must have role=summative. Do not introduce professional behaviors: do not silently add negotiation, leadership, or conflict resolution. If a task genuinely needs an additional capability, put it in dependency_candidates with a reason and the supplied objective/assessment refs; never make it required evidence silently. Distinguish required evidence from optional extensions.""",
    PREREQUISITE_PROPOSAL_SCHEMA_ID: """Propose only minimal required prerequisites: something the learner must already know or do before instruction can reasonably begin. Classify every proposal as required_prerequisite, helpful_background, or not_required; only required_prerequisite belongs in prerequisites. Model-proposed required candidates must remain candidate/model_proposed, include required_for_refs pointing to supplied objective or assessment IDs, and explain what would fail without them. Do not use vague rationales such as helpful or foundational.""",
    COURSE_PLANNING_SCHEMA_ID: """Create only objective-linked modules from supplied objective IDs. Every module must reference an existing objective and fit the stated time budget; reduce optional scope and state a planning assumption when scope does not fit. Copy IDs exactly from the supplied allow-list: objective_ids may contain only supplied objective IDs, prerequisite_refs may contain only supplied prerequisite IDs, and never put an objective ID in prerequisite_refs. Do not invent objective IDs or lesson IDs. Leave module.lesson_ids empty for orchestration to derive after lesson generation.""",
    LESSON_PLANNING_SCHEMA_ID: """Create lessons only for supplied module, objective, prerequisite, and formative-assessment IDs. Copy IDs exactly from the supplied allow-lists: module_id must be a supplied module ID, objective_ids must be both supplied and owned by that module, prerequisite_refs must be supplied prerequisite IDs, and formative_assessment_ids may contain only supplied assessments whose role is formative. Unknown references are invalid and must not be repaired. Every lesson needs a module and objective reference. Provide practice before summative evidence for apply/analyze/evaluate/create objectives when instruction is required. If a final assessment combines objectives, include integrated practice when appropriate. Do not alter upstream objectives, assessments, or prerequisites.""",
}


_V031_STAGE_INSTRUCTIONS = dict(_V03_STAGE_INSTRUCTIONS)
_V031_STAGE_INSTRUCTIONS[ASSESSMENT_DESIGN_SCHEMA_ID] = (
    _V03_STAGE_INSTRUCTIONS[ASSESSMENT_DESIGN_SCHEMA_ID]
    + """

ID-03B.2 AssessmentDesigner boundaries:
- Use only the supplied objective IDs from the input allow-list. Never invent objective IDs or reference objectives from another module or stage. If an objective is missing, return the existing unresolved state; do not create, rename, or infer an objective relationship.
- `required_capabilities` are capabilities directly demonstrated by the assessment and grounded in the objective performance.
- `dependency_candidates` are supporting knowledge or skills needed before that performance; they must remain candidate/model-proposed and must never be promoted automatically to required evidence.
- The assessment must not introduce capabilities beyond the objective. Keep the boundary domain-neutral and do not add IT-specific assumptions.
"""
)

_V032_STAGE_INSTRUCTIONS = dict(_V031_STAGE_INSTRUCTIONS)
_V032_STAGE_INSTRUCTIONS[COURSE_PLANNING_SCHEMA_ID] = _V031_STAGE_INSTRUCTIONS[COURSE_PLANNING_SCHEMA_ID] + """

Workload semantics (ID-04A): treat the brief's declared total minutes as a hard planning budget. It includes instruction, guided practice, independent practice, formative assessment, summative assessment, and feedback/revision unless the brief explicitly excludes a category. Keep whole-minute estimates auditable, do not redefine the declared budget, and reduce optional scope when the plan would exceed it. Course/module totals are planning estimates, not measured learner completion time.
"""
_V032_STAGE_INSTRUCTIONS[LESSON_PLANNING_SCHEMA_ID] = _V031_STAGE_INSTRUCTIONS[LESSON_PLANNING_SCHEMA_ID] + """

Workload semantics (ID-04A): provide conservative whole-minute lesson estimates within the supplied declared budget. Do not assume assessment time is outside the budget. Do not use fractional-minute precision or silently treat missing allocation as zero; unresolved time must remain explicit for deterministic validation.
"""

_V033_STAGE_INSTRUCTIONS = dict(_V032_STAGE_INSTRUCTIONS)
_V033_STAGE_INSTRUCTIONS[PREREQUISITE_PROPOSAL_SCHEMA_ID] = _V032_STAGE_INSTRUCTIONS[PREREQUISITE_PROPOSAL_SCHEMA_ID] + """

ID-04B prerequisite minimality: classify each proposed dependency explicitly as ENTRY_PREREQUISITE, IN_COURSE_SUPPORT, or NOT_REQUIRED. Minimize entry prerequisites; a dependency needed by an assessment is not automatically an entry prerequisite. Prefer IN_COURSE_SUPPORT when it can reasonably be introduced, refreshed, scaffolded, or practiced inside the course. An ENTRY_PREREQUISITE requires an explicit rationale explaining why it must exist before entry. Preserve source dependency references. All model-proposed dispositions remain status=candidate and basis=model_proposed; never auto-confirm them.
"""

_V034_STAGE_INSTRUCTIONS = dict(_V033_STAGE_INSTRUCTIONS)
_V034_STAGE_INSTRUCTIONS[COURSE_PLANNING_SCHEMA_ID] = _V033_STAGE_INSTRUCTIONS[COURSE_PLANNING_SCHEMA_ID] + """

ID-04C practice coverage: every summative required capability should have prior explicit instruction and, where feasible, guided/independent practice or valid formative evidence. Do not count the summative assessment as its own practice, do not label summative work formative, and preserve objective/module ownership. Practice consumes the declared workload budget; do not add unlimited practice or suppress workload findings.
"""
_V034_STAGE_INSTRUCTIONS[LESSON_PLANNING_SCHEMA_ID] = _V033_STAGE_INSTRUCTIONS[LESSON_PLANNING_SCHEMA_ID] + """

ID-04C practice coverage: use explicit objective and assessment references to place instruction and practice before summative assessment. Use instructional patterns to distinguish explanation from guided/independent practice. Never use the summative assessment as a formative or practice reference, and preserve prerequisite dispositions and workload context.
"""


def instructional_design_experiment_prompt_templates(
    *, version: str = "0.2"
) -> list[PromptTemplate]:
    if version == INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034:
        stage_instructions = _V034_STAGE_INSTRUCTIONS
    elif version == INSTRUCTIONAL_DESIGN_STAGE_VERSION_V033:
        stage_instructions = _V033_STAGE_INSTRUCTIONS
    elif version == INSTRUCTIONAL_DESIGN_STAGE_VERSION_V032:
        stage_instructions = _V032_STAGE_INSTRUCTIONS
    elif version == INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031:
        stage_instructions = _V031_STAGE_INSTRUCTIONS
    elif version.startswith("0.3"):
        stage_instructions = _V03_STAGE_INSTRUCTIONS
    else:
        stage_instructions = _EXPERIMENT_STAGE_INSTRUCTIONS
    structured = [
        PromptTemplate(
            template_id=template_id,
            version=version,
            system_instruction=(_SYSTEM_RULES + "\n\n" + instruction),
            user_instruction=(
                "Use only the supplied typed research artifacts.\n\n"
                + _structured_output_instruction(template_id)
            ),
            payload_boundary="input_data",
        )
        for template_id, instruction in stage_instructions.items()
    ]
    return structured + [
        PromptTemplate(
            template_id=ONE_SHOT_BASELINE_SCHEMA_ID,
            version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
            system_instruction=(_SYSTEM_RULES + "\n\n" + _ONE_SHOT_BASELINE_INSTRUCTION),
            user_instruction=(
                "Use only the supplied research brief.\n\n"
                + _structured_output_instruction(ONE_SHOT_BASELINE_SCHEMA_ID)
            ),
            payload_boundary="input_data",
        )
    ]
