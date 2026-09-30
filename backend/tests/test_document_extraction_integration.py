import json
from uuid import uuid4

import pytest

from app.extraction.fixtures import FixtureDocument
from app.extraction.prompts import (
    CHUNK_EXTRACTION_SCHEMA_VERSION,
    CV_CHUNK_SCHEMA_ID,
    JD_CHUNK_SCHEMA_ID,
)
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import (
    ChunkExtractedClaim,
    CVChunkExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    ExtractionJob,
    JDChunkExtractionOutput,
    JobStatus,
    ReviewState,
)
from app.extraction.worker import ExtractionWorker
from app.model_gateway.contracts import (
    InferenceAuditMetadata,
    InferenceRequest,
    ModelUsage,
    StructuredInferenceResponse,
)
from app.model_gateway.errors import StructuredOutputFailedError

ACTOR_ID = uuid4()


class StaticChunkDocumentSource:
    def __init__(self, documents: dict[str, FixtureDocument]) -> None:
        self._documents = documents

    async def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        document = self._documents.get(document_id)
        if document is None or document.kind is not kind:
            raise KeyError(document_id)
        return document


class ChunkGateway:
    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []

    async def infer_structured(
        self,
        request: InferenceRequest,
        output_schema: type[CVChunkExtractionOutput] | type[JDChunkExtractionOutput],
    ) -> (
        StructuredInferenceResponse[CVChunkExtractionOutput]
        | StructuredInferenceResponse[JDChunkExtractionOutput]
    ):
        self.requests.append(request)
        assert request.output_token_budget == 2048
        assert request.output_contract is not None
        assert request.output_contract.schema_version == CHUNK_EXTRACTION_SCHEMA_VERSION

        if request.prompt_template_id == CV_CHUNK_SCHEMA_ID:
            assert output_schema is CVChunkExtractionOutput
            if "Skills: Python" in request.payload["document"]:
                parsed = CVChunkExtractionOutput(
                    skills=[
                        ChunkExtractedClaim(
                            value="Python",
                            confidence=0.9,
                            evidence_status=EvidenceStatus.SUPPORTED,
                            source_excerpt="Python",
                        )
                    ],
                    experience=[],
                    education=[],
                )
            else:
                parsed = CVChunkExtractionOutput(
                    skills=[],
                    experience=[
                        ChunkExtractedClaim(
                            value="Built internal APIs with FastAPI",
                            confidence=0.8,
                            evidence_status=EvidenceStatus.SUPPORTED,
                            source_excerpt="Built internal APIs with FastAPI.",
                        )
                    ],
                    education=[],
                )
        else:
            assert request.prompt_template_id == JD_CHUNK_SCHEMA_ID
            assert output_schema is JDChunkExtractionOutput
            if "Requirements:" in request.payload["document"]:
                parsed = JDChunkExtractionOutput(
                    required_skills=[
                        ChunkExtractedClaim(
                            value="Python and FastAPI experience",
                            confidence=0.9,
                            evidence_status=EvidenceStatus.SUPPORTED,
                            source_excerpt="Python and FastAPI experience.",
                        )
                    ],
                    responsibilities=[],
                    qualifications=[],
                )
            else:
                parsed = JDChunkExtractionOutput(
                    required_skills=[],
                    responsibilities=[
                        ChunkExtractedClaim(
                            value="Build reliable internal APIs",
                            confidence=0.8,
                            evidence_status=EvidenceStatus.SUPPORTED,
                            source_excerpt="Build reliable internal APIs.",
                        )
                    ],
                    qualifications=[
                        ChunkExtractedClaim(
                            value="Engineering degree",
                            confidence=0.7,
                            evidence_status=EvidenceStatus.SUPPORTED,
                            source_excerpt="Engineering degree.",
                        )
                    ],
                )

        return StructuredInferenceResponse(
            parsed=parsed,
            audit=InferenceAuditMetadata(
                provider="mock",
                model="mock-v1",
                prompt_template_id=request.prompt_template_id,
                prompt_template_version=CHUNK_EXTRACTION_SCHEMA_VERSION,
                output_schema_id=request.output_contract.schema_id,
                output_schema_version=request.output_contract.schema_version,
                policy_version="privacy-v1",
                correlation_id=request.correlation_id,
                routing_decision="restricted_local_only",
                attempt_count=1,
                latency_ms=0,
                usage=ModelUsage(input_tokens=10, output_tokens=20),
                outcome="succeeded",
            ),
        )


def _long_cv_document() -> FixtureDocument:
    return FixtureDocument(
        document_id="fixture-cv-long",
        kind=DocumentKind.CV,
        content=(
            "Profile\n"
            "Skills: Python\n" + ("x" * 1980) + "\nExperience: Built internal APIs with FastAPI.\n"
        ),
    )


def _long_jd_document() -> FixtureDocument:
    return FixtureDocument(
        document_id="fixture-jd-long",
        kind=DocumentKind.JD,
        content=(
            "Role: Backend Engineer\n"
            "Requirements: Python and FastAPI experience.\n"
            + ("y" * 1980)
            + "\nResponsibilities: Build reliable internal APIs.\n"
            "Qualifications: Engineering degree.\n"
        ),
    )


@pytest.mark.asyncio
async def test_chunked_cv_and_jd_extraction_persists_normalized_profiles() -> None:
    repository = InMemoryExtractionRepository()
    source = StaticChunkDocumentSource(
        {
            "fixture-cv-long": _long_cv_document(),
            "fixture-jd-long": _long_jd_document(),
        }
    )
    gateway = ChunkGateway()

    await repository.enqueue(
        ExtractionJob(
            id="cv-job",
            document_id="fixture-cv-long",
            document_kind=DocumentKind.CV,
            owner_actor_id=ACTOR_ID,
            correlation_id=str(uuid4()),
            status=JobStatus.QUEUED,
        )
    )
    await repository.enqueue(
        ExtractionJob(
            id="jd-job",
            document_id="fixture-jd-long",
            document_kind=DocumentKind.JD,
            owner_actor_id=ACTOR_ID,
            correlation_id=str(uuid4()),
            status=JobStatus.QUEUED,
        )
    )

    worker = ExtractionWorker(repository, source, gateway, extraction_mode=ExtractionMode.SECTION_BASED)
    await worker.run_once()
    await worker.run_once()

    cv_job = await repository.get_job("cv-job")
    jd_job = await repository.get_job("jd-job")
    assert cv_job is not None and cv_job.status is JobStatus.SUCCEEDED
    assert jd_job is not None and jd_job.status is JobStatus.SUCCEEDED
    assert len(gateway.requests) == 4

    cv_profile = await repository.get_profile(cv_job.profile_id or "")
    jd_profile = await repository.get_profile(jd_job.profile_id or "")
    assert cv_profile is not None and cv_profile.review_state is ReviewState.PENDING_REVIEW
    assert jd_profile is not None and jd_profile.review_state is ReviewState.PENDING_REVIEW
    assert cv_profile.audit["chunk_count"] == 2
    assert jd_profile.audit["chunk_count"] == 2
    assert cv_profile.output.skills[0].value == "Python"
    assert jd_profile.output.required_skills[0].value == "Python and FastAPI experience"
    assert "Skills: Python" not in json.dumps(cv_profile.audit)
    assert "Requirements: Python and FastAPI experience" not in json.dumps(jd_profile.audit)


@pytest.mark.asyncio
async def test_invalid_gateway_json_fails_job_without_profile() -> None:
    class InvalidGateway(ChunkGateway):
        async def infer_structured(self, request, output_schema):
            if len(self.requests) == 0:
                return await super().infer_structured(request, output_schema)
            self.requests.append(request)
            raise StructuredOutputFailedError("invalid_model_json")

    repository = InMemoryExtractionRepository()
    source = StaticChunkDocumentSource({"fixture-cv-long": _long_cv_document()})
    gateway = InvalidGateway()
    await repository.enqueue(
        ExtractionJob(
            id="invalid-job",
            document_id="fixture-cv-long",
            document_kind=DocumentKind.CV,
            owner_actor_id=ACTOR_ID,
            correlation_id=str(uuid4()),
            status=JobStatus.QUEUED,
        )
    )

    await ExtractionWorker(
        repository, source, gateway, extraction_mode=ExtractionMode.SECTION_BASED
    ).run_once()
    job = await repository.get_job("invalid-job")
    assert job is not None and job.status is JobStatus.FAILED
    assert job.error_category == "chunk_2:invalid_structured_output:invalid_model_json"
    assert job.profile_id is None
    assert await repository.get_profile("invalid-job") is None
