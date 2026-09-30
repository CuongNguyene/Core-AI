import asyncio
import logging

from app.extraction.worker import ExtractionWorker
from app.main import create_app

logger = logging.getLogger(__name__)


async def run() -> None:
    app = create_app()
    worker = ExtractionWorker(
        app.state.extraction_repository,
        app.state.document_source,
        app.state.model_gateway,
        app.state.settings.cv_jd_extraction_max_tokens,
        app.state.settings.evidence_graph_runtime_enabled,
        app.state.settings.extraction_forensics_enabled,
        app.state.settings.extraction_forensics_dir,
        app.state.candidate_service,
        pipeline_mode=app.state.settings.cv_extraction_pipeline,
        capability_mode=app.state.settings.cv_two_stage_capability_mode,
        jd_extraction_mode=app.state.settings.jd_extraction_mode,
        heartbeat_seconds=app.state.settings.extraction_job_heartbeat_seconds,
    )
    try:
        while True:
            recovered = await app.state.extraction_repository.recover_stale_jobs(
                app.state.settings.extraction_job_stale_seconds
            )
            if recovered:
                logger.warning("recovered_stale_extraction_jobs count=%s", recovered)
            processed = await worker.run_once()
            if not processed:
                await asyncio.sleep(1)
    finally:
        await app.state.database.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
