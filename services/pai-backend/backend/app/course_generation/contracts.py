from app.content_generation.prompts import (
    COURSE_GENERATION_PROMPT_ID,
    COURSE_GENERATION_PROMPT_VERSION,
    CURRICULUM_PLANNING_PROMPT_ID,
    CURRICULUM_PLANNING_PROMPT_VERSION,
    LESSON_GENERATION_PROMPT_ID,
    LESSON_GENERATION_PROMPT_VERSION,
    LESSON_REPAIR_PROMPT_ID,
    LESSON_REPAIR_PROMPT_VERSION,
    MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION,
    course_generation_prompt_template,
    curriculum_planning_prompt_template,
    lesson_content_generation_prompt_template,
    lesson_content_repair_prompt_template,
)
from app.content_generation.schemas import GeneratedCourseDraft, GeneratedLessonDraft
from app.curriculum_planning.schemas import CurriculumPlanningOutput
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def register_course_generation_contracts(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    schemas.register(
        COURSE_GENERATION_PROMPT_ID,
        COURSE_GENERATION_PROMPT_VERSION,
        GeneratedCourseDraft,
    )
    schemas.register(
        LESSON_GENERATION_PROMPT_ID,
        LESSON_GENERATION_PROMPT_VERSION,
        GeneratedLessonDraft,
    )
    schemas.register(
        LESSON_REPAIR_PROMPT_ID,
        LESSON_REPAIR_PROMPT_VERSION,
        GeneratedLessonDraft,
    )
    schemas.register(
        CURRICULUM_PLANNING_PROMPT_ID,
        CURRICULUM_PLANNING_PROMPT_VERSION,
        CurriculumPlanningOutput,
    )
    schemas.register(
        CURRICULUM_PLANNING_PROMPT_ID,
        MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION,
        CurriculumPlanningOutput,
    )
    prompts.register(course_generation_prompt_template())
    prompts.register(lesson_content_generation_prompt_template())
    prompts.register(lesson_content_repair_prompt_template())
    prompts.register(curriculum_planning_prompt_template())
    prompts.register(
        curriculum_planning_prompt_template(MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION)
    )
