from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LessonType(StrEnum):
    SKILL_PRACTICE = "skill_practice"


class InstructionalPattern(StrEnum):
    CONCEPT_INTRODUCTION = "concept_introduction"
    WORKED_EXAMPLE = "worked_example"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    REFLECTION = "reflection"
    ASSESSMENT = "assessment"


class LessonBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective_refs: list[str] = Field(min_length=1)
    lesson_type: LessonType
    estimated_minutes: int = Field(gt=0)
    instructional_pattern: list[InstructionalPattern] = Field(min_length=1)
    assessment_refs: list[str] = Field(default_factory=list)
    sequence: int = Field(ge=1)


class ModuleBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective_refs: list[str] = Field(min_length=1)
    lesson_refs: list[str] = Field(min_length=1)
    sequence: int = Field(ge=1)


class CourseBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective_refs: list[str] = Field(min_length=1)
    module_refs: list[str] = Field(min_length=1)


class InstructionalBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    version: str = Field(default="instructional-blueprint-v1", min_length=1)
    learning_need_ref: str = Field(min_length=1)
    objective_refs: list[str] = Field(min_length=1)
    course: CourseBlueprint
    modules: list[ModuleBlueprint] = Field(min_length=1)
    lessons: list[LessonBlueprint] = Field(min_length=1)
