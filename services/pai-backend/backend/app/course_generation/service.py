import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.authorization.schemas import ActorContext
from app.content_generation.prompts import COURSE_GENERATION_PROMPT_VERSION
from app.content_generation.repository import ContentGenerationRepository
from app.content_generation.schemas import (
    ContentGenerationResult,
    ContentGenerationStatus,
    GenerationMetadata,
    GenerationRun,
    GenerationRunStatus,
)
from app.course_authoring.schemas import CourseAuthoringRequest
from app.model_gateway.errors import (
    ProviderTimeoutError,
    StructuredOutputFailedError,
)

from .context import CourseGenerationContextBuilder
from .errors import (
    CourseGenerationAlreadyInProgressError,
    CourseGenerationArtifactNotFoundError,
    CourseGenerationOutputInvalidError,
    CourseGenerationProviderError,
)
from .generator import CourseContentGenerator
from .schemas import CourseGenerationAccepted
from .validation import validate_generated_course

logger = logging.getLogger(__name__)


class CourseAuthoringRequestReader(Protocol):
    async def get(self, request_id: str, actor: ActorContext) -> CourseAuthoringRequest: ...


class CourseGenerationService:
    def __init__(
        self,
        *,
        authoring: CourseAuthoringRequestReader,
        context_builder: CourseGenerationContextBuilder,
        generator: CourseContentGenerator,
        repository: ContentGenerationRepository,
        provider: str,
        model: str,
        stale_run_after_seconds: float = 360.0,
        generation_timeout_seconds: float = 660.0,
    ) -> None:
        self._authoring = authoring
        self._context_builder = context_builder
        self._generator = generator
        self._repository = repository
        self._provider = provider
        self._model = model
        self._stale_run_after_seconds = stale_run_after_seconds
        self._generation_timeout_seconds = generation_timeout_seconds

    async def generate(self, request_id: str, actor: ActorContext) -> CourseGenerationAccepted:
        request = await self._authoring.get(request_id, actor)
        context = await self._context_builder.build(request, actor)
        if request.mode.value == "GAP_DRIVEN" and not context.learning_objectives:
            raise CourseGenerationArtifactNotFoundError(
                "course_generation_objective_context_required"
            )

        await self._recover_stale_run(request.id)
        run = GenerationRun(
            run_id=f"generation-run-{uuid4().hex}",
            request_ref=request.id,
            provider=self._provider,
            model=self._model,
            prompt_version=COURSE_GENERATION_PROMPT_VERSION,
            started_at=datetime.now(UTC),
            status=GenerationRunStatus.RUNNING,
        )
        try:
            await self._repository.create_run(run)
        except ValueError as exc:
            if str(exc) == "generation_already_in_progress":
                raise CourseGenerationAlreadyInProgressError(str(exc)) from exc
            raise

        try:
            draft = await asyncio.wait_for(
                self._generator.generate(request, context),
                timeout=self._generation_timeout_seconds,
            )
            validate_generated_course(draft, context)
            finished_at = datetime.now(UTC)
            audit = self._latest_audit()
            completed_run = run.model_copy(
                update={
                    "provider": getattr(audit, "provider", run.provider),
                    "model": getattr(audit, "model", run.model),
                    "finished_at": finished_at,
                    "status": GenerationRunStatus.SUCCEEDED,
                }
            )
            await self._repository.update_run(completed_run)
            latest = await self._repository.get_latest_result(request.id)
            version = latest.version + 1 if latest is not None else 1
            result = ContentGenerationResult(
                id=f"content-generation-result-{uuid4().hex}",
                request_ref=request.id,
                objective_refs=[objective.id for objective in context.learning_objectives]
                + [objective.id for objective in context.generated_objectives],
                generated_objectives=list(context.generated_objectives),
                learning_need_refs=list(context.learning_need_refs),
                version=version,
                supersedes_result_ref=latest.id if latest is not None else None,
                status=ContentGenerationStatus.DRAFT,
                sections=[],
                generation_metadata=GenerationMetadata(
                    prompt_version=completed_run.prompt_version,
                    model=completed_run.model,
                    provider=completed_run.provider,
                    created_at=finished_at,
                    generation_run_id=completed_run.run_id,
                ),
                generation_run=completed_run,
                source_blueprint_ref=(
                    context.instructional_blueprint.id
                    if context.instructional_blueprint is not None
                    else None
                ),
                course_authoring_request_ref=request.id,
                generated_course=draft,
                created_at=finished_at,
            )
            await self._repository.create_result(result)
            return CourseGenerationAccepted(
                request_ref=request.id,
                generation_run_ref=completed_run.run_id,
                result_ref=result.id,
                status=result.status,
                version=result.version,
            )
        except asyncio.CancelledError:
            await self._fail_run(run, "generation_cancelled")
            raise
        except CourseGenerationOutputInvalidError as exc:
            logger.warning(
                "course_generation_output_invalid request_ref=%s run_ref=%s error=%s",
                request.id,
                run.run_id,
                exc,
            )
            await self._fail_run(run, "generation_output_invalid")
            raise
        except StructuredOutputFailedError as exc:
            await self._fail_run(run, "malformed_structured_output")
            raise CourseGenerationOutputInvalidError(exc.category) from exc
        except ProviderTimeoutError as exc:
            await self._fail_run(run, "provider_timeout")
            raise CourseGenerationProviderError("provider_timeout") from exc
        except TimeoutError as exc:
            await self._fail_run(run, "generation_timeout")
            raise CourseGenerationProviderError("generation_timeout") from exc
        except CourseGenerationArtifactNotFoundError:
            await self._fail_run(run, "course_generation_artifact_not_found")
            raise
        except Exception as exc:
            await self._fail_run(run, "gateway_failure")
            raise CourseGenerationProviderError("gateway_failure") from exc

    def _latest_audit(self) -> object | None:
        audits = getattr(self._generator, "model_audits", ())
        return audits[-1] if audits else None

    async def _fail_run(self, run: GenerationRun, error_code: str) -> None:
        failed = run.model_copy(
            update={
                "finished_at": datetime.now(UTC),
                "status": GenerationRunStatus.FAILED,
                "error_code": error_code,
            }
        )
        await self._repository.update_run(failed)

    async def _recover_stale_run(self, request_ref: str) -> None:
        active = await self._repository.get_active_run(request_ref)
        if active is None or active.started_at is None:
            return
        age = datetime.now(UTC) - active.started_at
        if age <= timedelta(seconds=self._stale_run_after_seconds):
            return
        await self._repository.update_run(
            active.model_copy(
                update={
                    "finished_at": datetime.now(UTC),
                    "status": GenerationRunStatus.FAILED,
                    "error_code": "stale_run_recovered",
                }
            )
        )
