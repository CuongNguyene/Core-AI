from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.authorization.schemas import ActorContext
from app.content_generation.repository import ContentGenerationRepository
from app.content_generation.schemas import (
    ContentGenerationResult,
    ContentGenerationStatus,
    GeneratedCourseDraft,
    GeneratedCourseLesson,
    GeneratedCourseModule,
    GeneratedCourseSection,
    RevisionMetadata,
)

from .errors import CourseAuthoringAccessDeniedError, CourseAuthoringRequestNotFoundError
from .revision_errors import (
    CourseRevisionAccessDeniedError,
    CourseRevisionConflictError,
    CourseRevisionNotFoundError,
    CourseRevisionValidationError,
)
from .revision_schemas import CourseDraftRevisionRequest


class CourseAuthoringRequestReader(Protocol):
    async def get(self, request_id: str, actor: ActorContext) -> object: ...


class CourseDraftRevisionService:
    def __init__(
        self,
        *,
        repository: ContentGenerationRepository,
        authoring: CourseAuthoringRequestReader,
    ) -> None:
        self._repository = repository
        self._authoring = authoring

    async def create_revision(
        self, request: CourseDraftRevisionRequest, actor: ActorContext
    ) -> ContentGenerationResult:
        source = await self._load_owned_result(request.source_result_ref, actor)
        latest = await self._latest(source, actor)
        if latest.id != source.id:
            raise CourseRevisionConflictError("stale_revision_source")
        if source.generated_course is None:
            raise CourseRevisionValidationError("generated_course_required")

        revised_course = self._apply_changes(source.generated_course, request)
        revised = source.model_copy(
            update={
                "id": f"content-generation-result-{uuid4().hex}",
                "version": source.version + 1,
                "supersedes_result_ref": source.id,
                "status": ContentGenerationStatus.IN_REVIEW,
                "generated_course": revised_course,
                "revision_metadata": RevisionMetadata(
                    revision_id=f"course-revision-{uuid4().hex}",
                    result_ref=f"pending-{uuid4().hex}",
                    editor_actor_ref=str(actor.actor_id),
                    created_at=datetime.now(UTC),
                    change_summary=request.change_summary,
                    source_version=source.version,
                ),
                "created_at": datetime.now(UTC),
            }
        )
        if revised.revision_metadata is not None:
            revised = revised.model_copy(update={
                "revision_metadata": revised.revision_metadata.model_copy(
                    update={"result_ref": revised.id}
                )
            })
        self._validate_revision_integrity(source, revised)
        await self._repository.create_result(revised)
        return revised

    async def list_versions(
        self, request_ref: str, actor: ActorContext
    ) -> list[ContentGenerationResult]:
        await self._ensure_request_access(request_ref, actor)
        return await self._repository.list_results(request_ref)

    async def get_version(
        self, result_id: str, actor: ActorContext
    ) -> ContentGenerationResult:
        return await self._load_owned_result(result_id, actor)

    async def mark_ready(
        self, result_id: str, actor: ActorContext
    ) -> ContentGenerationResult:
        result = await self._load_owned_result(result_id, actor)
        latest = await self._latest(result, actor)
        if latest.id != result.id:
            raise CourseRevisionConflictError("only_latest_result_can_be_marked_ready")
        if result.generated_course is None:
            raise CourseRevisionValidationError("generated_course_required")
        if result.status is ContentGenerationStatus.READY_FOR_MATERIALIZATION:
            return result
        if result.status not in {
            ContentGenerationStatus.DRAFT,
            ContentGenerationStatus.IN_REVIEW,
        }:
            raise CourseRevisionConflictError("result_not_ready_for_materialization")
        return await self._repository.update_result_status(
            result.id, ContentGenerationStatus.READY_FOR_MATERIALIZATION
        )

    async def approve(
        self, result_id: str, actor: ActorContext
    ) -> ContentGenerationResult:
        result = await self._load_owned_result(result_id, actor)
        latest = await self._latest(result, actor)
        if latest.id != result.id:
            raise CourseRevisionConflictError("only_latest_result_can_be_approved")
        if result.status is ContentGenerationStatus.REJECTED:
            raise CourseRevisionConflictError("rejected_result_cannot_be_approved")
        if result.status is ContentGenerationStatus.APPROVED:
            return result
        if result.status not in {
            ContentGenerationStatus.DRAFT,
            ContentGenerationStatus.IN_REVIEW,
            ContentGenerationStatus.REVIEW_REQUIRED,
            ContentGenerationStatus.READY_FOR_MATERIALIZATION,
        }:
            raise CourseRevisionConflictError("result_not_approvable")
        return await self._record_decision(
            result, ContentGenerationStatus.APPROVED, actor, "Content approved"
        )

    async def reject(
        self, result_id: str, actor: ActorContext, *, reason: str | None = None
    ) -> ContentGenerationResult:
        result = await self._load_owned_result(result_id, actor)
        latest = await self._latest(result, actor)
        if latest.id != result.id:
            raise CourseRevisionConflictError("only_latest_result_can_be_rejected")
        if result.status is ContentGenerationStatus.APPROVED:
            raise CourseRevisionConflictError("approved_result_cannot_be_rejected")
        if result.status is ContentGenerationStatus.REJECTED:
            return result
        return await self._record_decision(
            result,
            ContentGenerationStatus.REJECTED,
            actor,
            reason or "Content rejected",
        )

    async def _record_decision(
        self,
        result: ContentGenerationResult,
        status: ContentGenerationStatus,
        actor: ActorContext,
        summary: str,
    ) -> ContentGenerationResult:
        decided = result.model_copy(update={
            "status": status,
            "revision_metadata": RevisionMetadata(
                revision_id=f"content-review-{uuid4().hex}",
                result_ref=result.id,
                editor_actor_ref=str(actor.actor_id),
                created_at=datetime.now(UTC),
                change_summary=summary,
                source_version=result.version,
            ),
        })
        return await self._repository.update_result(decided)

    async def _load_owned_result(
        self, result_id: str, actor: ActorContext
    ) -> ContentGenerationResult:
        result = await self._repository.get_result(result_id)
        if result is None:
            raise CourseRevisionNotFoundError("course_generation_result_not_found")
        await self._ensure_request_access(result.request_ref, actor)
        return result

    async def _ensure_request_access(self, request_ref: str, actor: ActorContext) -> None:
        try:
            await self._authoring.get(request_ref, actor)
        except CourseAuthoringRequestNotFoundError as exc:
            raise CourseRevisionNotFoundError("course_authoring_request_not_found") from exc
        except CourseAuthoringAccessDeniedError as exc:
            raise CourseRevisionAccessDeniedError("course_revision_access_denied") from exc

    async def _latest(
        self, result: ContentGenerationResult, actor: ActorContext
    ) -> ContentGenerationResult:
        latest = await self._repository.get_latest_result(result.request_ref)
        if latest is None:
            raise CourseRevisionNotFoundError("course_generation_result_not_found")
        return latest

    @staticmethod
    def _apply_changes(
        course: GeneratedCourseDraft, request: CourseDraftRevisionRequest
    ) -> GeneratedCourseDraft:
        CourseDraftRevisionService._reject_duplicate_targets(request)
        updated_course = course
        if request.course_changes is not None:
            updated_course = updated_course.model_copy(update={
                "course": updated_course.course.model_copy(update={
                    key: value
                    for key, value in {
                        "title": request.course_changes.title,
                        "description": request.course_changes.description,
                    }.items()
                    if value is not None
                })
            })

        modules = list(updated_course.modules)
        for module_change in request.module_changes:
            module_index = CourseDraftRevisionService._module_index(modules, module_change.module_order)
            modules[module_index] = modules[module_index].model_copy(update={"title": module_change.title})

        for lesson_change in request.lesson_changes:
            module_index = CourseDraftRevisionService._module_index(modules, lesson_change.module_order)
            module = modules[module_index]
            lesson_index = CourseDraftRevisionService._lesson_index(module.lessons, lesson_change.lesson_order)
            lessons = list(module.lessons)
            lessons[lesson_index] = lessons[lesson_index].model_copy(update={"title": lesson_change.title})
            modules[module_index] = module.model_copy(update={"lessons": lessons})

        for section_change in request.section_changes:
            module_index = CourseDraftRevisionService._module_index(modules, section_change.module_order)
            module = modules[module_index]
            lesson_index = CourseDraftRevisionService._lesson_index(module.lessons, section_change.lesson_order)
            lesson = module.lessons[lesson_index]
            section_index = CourseDraftRevisionService._section_index(lesson.sections, section_change.section_order)
            section = lesson.sections[section_index]
            sections = list(lesson.sections)
            sections[section_index] = section.model_copy(update={
                key: value
                for key, value in {"title": section_change.title, "content": section_change.content}.items()
                if value is not None
            })
            lessons = list(module.lessons)
            lessons[lesson_index] = lesson.model_copy(update={"sections": sections})
            modules[module_index] = module.model_copy(update={"lessons": lessons})

        assessment = updated_course.assessment
        if request.assessment_changes:
            if assessment is None:
                raise CourseRevisionValidationError("assessment_target_not_found")
            questions = list(assessment.questions)
            for assessment_change in request.assessment_changes:
                if assessment_change.question_index >= len(questions):
                    raise CourseRevisionValidationError("assessment_target_not_found")
                question = questions[assessment_change.question_index]
                questions[assessment_change.question_index] = question.model_copy(update={
                    key: value
                    for key, value in {
                        "prompt": assessment_change.prompt,
                        "options": assessment_change.options,
                        "expected_answer": assessment_change.expected_answer,
                    }.items()
                    if value is not None
                })
            assessment = assessment.model_copy(update={"questions": questions})

        return updated_course.model_copy(update={"modules": modules, "assessment": assessment})

    @staticmethod
    def _reject_duplicate_targets(request: CourseDraftRevisionRequest) -> None:
        for changes, key in (
            (request.module_changes, lambda item: item.module_order),
            (request.lesson_changes, lambda item: (item.module_order, item.lesson_order)),
            (request.section_changes, lambda item: (item.module_order, item.lesson_order, item.section_order)),
            (request.assessment_changes, lambda item: item.question_index),
        ):
            targets = [key(item) for item in changes]
            if len(targets) != len(set(targets)):
                raise CourseRevisionValidationError("duplicate_revision_target")

    @staticmethod
    def _module_index(modules: Sequence[GeneratedCourseModule], order: int) -> int:
        for index, module in enumerate(modules):
            if module.order == order:
                return index
        raise CourseRevisionValidationError("module_target_not_found")

    @staticmethod
    def _lesson_index(lessons: Sequence[GeneratedCourseLesson], order: int) -> int:
        for index, lesson in enumerate(lessons):
            if lesson.order == order:
                return index
        raise CourseRevisionValidationError("lesson_target_not_found")

    @staticmethod
    def _section_index(sections: Sequence[GeneratedCourseSection], order: int) -> int:
        for index, section in enumerate(sections):
            if section.order == order:
                return index
        raise CourseRevisionValidationError("section_target_not_found")

    @staticmethod
    def _validate_revision_integrity(
        source: ContentGenerationResult, revised: ContentGenerationResult
    ) -> None:
        protected_fields = (
            "request_ref",
            "objective_refs",
            "learning_need_refs",
            "source_blueprint_ref",
            "course_authoring_request_ref",
            "generation_run",
            "generation_metadata",
        )
        for field in protected_fields:
            if getattr(source, field) != getattr(revised, field):
                raise CourseRevisionValidationError(f"protected_field_changed:{field}")
        if source.generated_course is None or revised.generated_course is None:
            raise CourseRevisionValidationError("generated_course_required")
        old_modules = source.generated_course.modules
        new_modules = revised.generated_course.modules
        if len(old_modules) != len(new_modules):
            raise CourseRevisionValidationError("module_structure_changed")
        for old_module, new_module in zip(old_modules, new_modules, strict=True):
            if old_module.order != new_module.order or len(old_module.lessons) != len(new_module.lessons):
                raise CourseRevisionValidationError("lesson_structure_changed")
            for old_lesson, new_lesson in zip(old_module.lessons, new_module.lessons, strict=True):
                if (
                    old_lesson.order != new_lesson.order
                    or old_lesson.objective_refs != new_lesson.objective_refs
                    or len(old_lesson.sections) != len(new_lesson.sections)
                ):
                    raise CourseRevisionValidationError("lesson_reference_changed")
                for old_section, new_section in zip(old_lesson.sections, new_lesson.sections, strict=True):
                    if old_section.order != new_section.order or old_section.type != new_section.type:
                        raise CourseRevisionValidationError("section_reference_changed")
        if source.generated_course.assessment != revised.generated_course.assessment:
            old_questions = source.generated_course.assessment.questions if source.generated_course.assessment else []
            new_questions = revised.generated_course.assessment.questions if revised.generated_course.assessment else []
            if len(old_questions) != len(new_questions):
                raise CourseRevisionValidationError("assessment_structure_changed")
            for old_question, new_question in zip(old_questions, new_questions, strict=True):
                if old_question.question_type != new_question.question_type or old_question.objective_refs != new_question.objective_refs:
                    raise CourseRevisionValidationError("assessment_reference_changed")
