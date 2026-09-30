import json
from pathlib import Path

import pytest

from app.authorization.fixtures import LEARNER_ID
from app.extraction.fixtures import FixtureDocumentSource
from app.extraction.prompts import CHUNK_EXTRACTION_SCHEMA_VERSION, CV_CHUNK_SCHEMA_ID
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import (
    ChunkExtractedClaim,
    CVChunkExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    ExtractionJob,
    JobStatus,
)
from app.extraction.worker import ExtractionWorker
from app.model_gateway.contracts import (
    InferenceAuditMetadata,
    ModelUsage,
    StructuredInferenceResponse,
)


class GoldenCVGateway:
    async def infer_structured(
        self, request: object, output_schema: type[CVChunkExtractionOutput]
    ) -> StructuredInferenceResponse[CVChunkExtractionOutput]:
        assert output_schema is CVChunkExtractionOutput
        return StructuredInferenceResponse(
            parsed=CVChunkExtractionOutput(
                skills=[
                    ChunkExtractedClaim(
                        value="Python",
                        confidence=0.9,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_excerpt="Python, FastAPI",
                    )
                ],
                experience=[],
                education=[],
            ),
            audit=InferenceAuditMetadata(
                provider="mock",
                model="mock-v1",
                prompt_template_id=CV_CHUNK_SCHEMA_ID,
                prompt_template_version=CHUNK_EXTRACTION_SCHEMA_VERSION,
                output_schema_id=CV_CHUNK_SCHEMA_ID,
                output_schema_version=CHUNK_EXTRACTION_SCHEMA_VERSION,
                policy_version="privacy-v1",
                correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                routing_decision="restricted_local_only",
                attempt_count=1,
                latency_ms=0,
                usage=ModelUsage(),
                outcome="succeeded",
            ),
        )


@pytest.mark.asyncio
async def test_cv_fixture_matches_golden_profile() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(
        ExtractionJob(
            id="job-golden-cv",
            document_id="fixture-cv-basic",
            document_kind=DocumentKind.CV,
            owner_actor_id=LEARNER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await ExtractionWorker(
        repository,
        FixtureDocumentSource.default(),
        GoldenCVGateway(),
        extraction_mode=ExtractionMode.SECTION_BASED,
    ).run_once()
    job = await repository.get_job("job-golden-cv")
    assert job is not None and job.profile_id is not None
    profile = await repository.get_profile(job.profile_id)
    assert profile is not None

    golden_path = Path(__file__).parent / "golden" / "cv_basic.json"
    assert profile.output.model_dump(mode="json") == json.loads(golden_path.read_text())
