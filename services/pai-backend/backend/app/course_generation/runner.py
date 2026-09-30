import logging
from typing import Any, cast

from arq import cron
from arq.connections import RedisSettings

from app.authorization.repository import SubjectRepository
from app.authorization.service import DevelopmentIdentityAdapter
from app.course_generation.dispatch import SqlAlchemyCourseGenerationDispatchRepository
from app.course_generation.hierarchical_service import HierarchicalCourseGenerationService
from app.main import create_app
from app.shared.config import Settings

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    ctx["app"] = create_app()


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["app"].state.course_generation_dispatcher.close()
    await ctx["app"].state.database.dispose()


async def run_course_generation_plan(ctx: dict[str, Any], plan_ref: str) -> None:
    app = ctx["app"]
    dispatches = SqlAlchemyCourseGenerationDispatchRepository(app.state.database.session_factory)
    dispatch = await dispatches.claim(plan_ref)
    if dispatch is None:
        return
    try:
        actor = await DevelopmentIdentityAdapter(
            cast(SubjectRepository, app.state.subject_repository)
        ).resolve(dispatch.actor_id)
        service = cast(HierarchicalCourseGenerationService, app.state.course_generation_service)
        await service.run_dispatched_plan(
            plan_ref,
            actor,
            task_statuses=dispatch.task_statuses,
            assemble_result=dispatch.assemble_result,
        )
    except Exception:
        await dispatches.finish(plan_ref, succeeded=False)
        logger.exception("course_generation_dispatch_failed plan_ref=%s", plan_ref)
        # The durable record is the retry source of truth. Do not let ARQ retry
        # a job whose dispatch has already been recorded as FAILED.
        return
    else:
        await dispatches.finish(plan_ref, succeeded=True)


async def reconcile_course_generation_dispatches(ctx: dict[str, Any]) -> None:
    """Re-enqueue durable jobs after a Redis/worker interruption.

    The database remains authoritative. ARQ receives only a stable opaque plan id,
    and the worker's lease claim continues to prevent duplicate execution.
    """
    app = ctx["app"]
    dispatches = SqlAlchemyCourseGenerationDispatchRepository(app.state.database.session_factory)
    dispatcher = app.state.course_generation_dispatcher
    for dispatch in await dispatches.list_reconcilable():
        await dispatcher.enqueue(dispatch.plan_ref)


class WorkerSettings:
    functions = [run_course_generation_plan]
    cron_jobs = [
        cron(
            reconcile_course_generation_dispatches,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
        )
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(Settings().redis_queue_url)
    max_jobs = 2
    job_timeout = 1800
    max_tries = 1
    keep_result = 0


if __name__ == "__main__":
    from arq import run_worker

    run_worker(WorkerSettings)
