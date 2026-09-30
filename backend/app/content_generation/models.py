from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy import Uuid as SqlUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class GenerationRunRecord(Base):
    __tablename__ = "generation_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_run_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    unit_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    generation_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="INITIAL")
    repair_source_diagnostic_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)


class LessonValidationDiagnosticRecord(Base):
    __tablename__ = "lesson_validation_diagnostics"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authoring_request_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    plan_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lesson_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_run_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    sanitized_parsed_draft: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    validation_issues: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    section_metrics: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    assessment_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class CourseGenerationPlanRecord(Base):
    __tablename__ = "course_generation_plans"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authoring_request_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_run_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    course_title: Mapped[str] = mapped_column(String(512), nullable=False)
    course_description_context: Mapped[str] = mapped_column(String(4096), nullable=False)
    module_plans: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    lesson_descriptors: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_constraint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    curriculum_plan_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CourseGenerationDispatchRecord(Base):
    __tablename__ = "course_generation_dispatches"

    plan_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(SqlUuid, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    task_statuses: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    assemble_result: Mapped[bool] = mapped_column(nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CurriculumPlanRecord(Base):
    __tablename__ = "curriculum_plans"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authoring_request_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_plan_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    course_title: Mapped[str] = mapped_column(String(512), nullable=False)
    course_description: Mapped[str] = mapped_column(String(4096), nullable=False)
    normalized_duration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    learning_objectives: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    modules: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    estimated_total_learning_hours: Mapped[float] = mapped_column(nullable=False)
    planning_metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CurriculumPlanningAttemptRecord(Base):
    __tablename__ = "curriculum_planning_attempts"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authoring_request_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    original_duration_constraint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    normalized_duration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    weekly_effort_hours: Mapped[float | None] = mapped_column(nullable=True)
    weekly_effort_source: Mapped[str] = mapped_column(String(16), nullable=False)
    estimated_total_learning_hours: Mapped[float | None] = mapped_column(nullable=True)
    min_modules: Mapped[int] = mapped_column(Integer, nullable=False)
    max_modules: Mapped[int] = mapped_column(Integer, nullable=False)
    min_lessons: Mapped[int] = mapped_column(Integer, nullable=False)
    max_lessons: Mapped[int] = mapped_column(Integer, nullable=False)
    objective_count: Mapped[int] = mapped_column(Integer, nullable=False)
    module_count: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_count: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_candidate_hours: Mapped[float | None] = mapped_column(nullable=True)
    covered_objective_count: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_issues: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    uncovered_objective_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    unknown_objective_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sanitized_parsed_candidate: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class LessonGenerationTaskRecord(Base):
    __tablename__ = "lesson_generation_tasks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    plan_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lesson_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    module_order: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_order: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_title: Mapped[str] = mapped_column(String(512), nullable=False)
    objective_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_run_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_lesson: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContentGenerationResultRecord(Base):
    __tablename__ = "content_generation_results"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_result_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    lesson_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    objective_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    generated_objectives: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    learning_need_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sections: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    generation_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    generation_run: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    source_blueprint_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    course_authoring_request_ref: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    generated_course: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    revision_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
