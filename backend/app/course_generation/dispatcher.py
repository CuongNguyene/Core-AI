from typing import Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings


class CourseGenerationDispatcher(Protocol):
    async def enqueue(self, plan_ref: str) -> None: ...


class ArqCourseGenerationDispatcher:
    """Enqueue only opaque plan IDs; lifecycle state remains in PostgreSQL."""

    def __init__(self, redis_url: str) -> None:
        self._settings = RedisSettings.from_dsn(redis_url)
        self._pool: ArqRedis | None = None

    async def enqueue(self, plan_ref: str) -> None:
        if self._pool is None:
            self._pool = await create_pool(self._settings)
        await self._pool.enqueue_job(
            "run_course_generation_plan", plan_ref, _job_id=f"course-generation:{plan_ref}"
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
