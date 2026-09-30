from app.authorization.fixtures import LEARNER_ID
from app.extraction.fixtures import FixtureDocument
from app.extraction.prompts import (
    CHUNK_EXTRACTION_SCHEMA_VERSION,
    CV_CHUNK_SCHEMA_ID,
    CV_FULL_SCHEMA_ID,
    FULL_EXTRACTION_SCHEMA_V2_1_VERSION,
    FULL_EXTRACTION_SCHEMA_V2_2_VERSION,
    FULL_EXTRACTION_SCHEMA_VERSION,
    JD_FULL_SCHEMA_ID,
)
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import ExtractionMode
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    ChunkExtractedClaim,
    CVChunkExtractionOutput,
    CVFullExtractionOutput,
    CVFullExtractionOutputV2,
    DocumentKind,
    EvidenceClaim,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    ExtractionJob,
    JDFullExtractionOutput,
    JobStatus,
    ReviewState,
    SourceLocator,
)
from app.extraction.worker import ExtractionWorker
from app.model_gateway.contracts import (
    InferenceAuditMetadata,
    InferenceRequest,
    ModelUsage,
    StructuredInferenceResponse,
)
from app.model_gateway.diagnostics import diagnostic_for_json_parse
from app.model_gateway.errors import StructuredOutputFailedError


class LongCVDocumentSource:
    async def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        assert document_id == "fixture-cv-long"
        assert kind is DocumentKind.CV
        return FixtureDocument(
            document_id=document_id,
            kind=kind,
            content=(
                "Profile\n"
                "Skills: Python\n"
                + ("x" * 1980)
                + "\nExperience: Built internal APIs with FastAPI.\n"
            ),
        )


class RecordingChunkGateway:
    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []

    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[CVChunkExtractionOutput]
    ) -> StructuredInferenceResponse[CVChunkExtractionOutput]:
        self.requests.append(request)
        assert request.output_token_budget == 2048
        assert request.prompt_template_id == CV_CHUNK_SCHEMA_ID
        assert request.output_contract is not None
        assert request.output_contract.schema_id == CV_CHUNK_SCHEMA_ID
        assert request.output_contract.schema_version == CHUNK_EXTRACTION_SCHEMA_VERSION
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

        return StructuredInferenceResponse(
            parsed=parsed,
            audit=InferenceAuditMetadata(
                provider="mock",
                model="mock-v1",
                prompt_template_id=CV_CHUNK_SCHEMA_ID,
                prompt_template_version=CHUNK_EXTRACTION_SCHEMA_VERSION,
                output_schema_id=CV_CHUNK_SCHEMA_ID,
                output_schema_version=CHUNK_EXTRACTION_SCHEMA_VERSION,
                policy_version="privacy-v1",
                correlation_id=request.correlation_id,
                routing_decision="restricted_local_only",
                attempt_count=1,
                latency_ms=0,
                usage=ModelUsage(input_tokens=10, output_tokens=20),
                outcome="succeeded",
            ),
        )


class FailingChunkGateway(RecordingChunkGateway):
    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[CVChunkExtractionOutput]
    ) -> StructuredInferenceResponse[CVChunkExtractionOutput]:
        if len(self.requests) == 0:
            return await RecordingChunkGateway.infer_structured(self, request, output_schema)
        self.requests.append(request)
        raise StructuredOutputFailedError(
            "invalid_model_json",
            diagnostic=diagnostic_for_json_parse(
                content_length=17, provider_finish_reason="stop"
            ),
        )


class UnresolvedLocatorGateway(RecordingChunkGateway):
    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[CVChunkExtractionOutput]
    ) -> StructuredInferenceResponse[CVChunkExtractionOutput]:
        response = await super().infer_structured(request, output_schema)
        if len(self.requests) == 1:
            response = response.model_copy(
                update={
                    "parsed": response.parsed.model_copy(
                        update={
                            "skills": [
                                ChunkExtractedClaim(
                                    value="Production Python deployment",
                                    confidence=0.9,
                                    evidence_status=EvidenceStatus.SUPPORTED,
                                    source_excerpt="Production Python deployment",
                                )
                            ]
                        }
                    )
                }
            )
        return response


class CandidateAssociationSpy:
    def __init__(self) -> None:
        self.profile_ids: list[str] = []

    async def associate_extraction_profile(self, profile_id: str) -> tuple[object, ...]:
        self.profile_ids.append(profile_id)
        return ()


def test_worker_creates_pending_review_profile_from_chunked_cv_fixture() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="job-1",
                document_id="fixture-cv-long",
                document_kind=DocumentKind.CV,
                owner_actor_id=LEARNER_ID,
                correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                status=JobStatus.QUEUED,
            )
        )
        gateway = RecordingChunkGateway()
        worker = ExtractionWorker(
            repository, LongCVDocumentSource(), gateway, extraction_mode=ExtractionMode.SECTION_BASED
        )

        processed = await worker.run_once()
        job = await repository.get_job("job-1")

        assert processed is True
        assert len(gateway.requests) == 2
        assert job is not None
        assert job.status is JobStatus.SUCCEEDED
        assert job.profile_id is not None
        profile = await repository.get_profile(job.profile_id)
        assert profile is not None
        assert profile.review_state is ReviewState.PENDING_REVIEW
        assert profile.audit["provider"] == "mock"
        assert profile.audit["chunk_count"] == 2
        assert profile.output.skills[0].value == "Python"
        assert profile.output.experience[0].value == "Built internal APIs with FastAPI"
        assert profile.candidate_profile is not None
        assert profile.candidate_profile.skills[0].entity == "Python"

    import asyncio

    asyncio.run(scenario())


def test_worker_associates_successful_profile_with_candidate_runtime() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="job-association",
                document_id="fixture-cv-long",
                document_kind=DocumentKind.CV,
                owner_actor_id=LEARNER_ID,
                correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                status=JobStatus.QUEUED,
            )
        )
        association = CandidateAssociationSpy()
        worker = ExtractionWorker(
            repository,
            LongCVDocumentSource(),
            RecordingChunkGateway(),
            candidate_service=association,  # type: ignore[arg-type]
            extraction_mode=ExtractionMode.SECTION_BASED,
        )

        assert await worker.run_once() is True
        job = await repository.get_job("job-association")
        assert job is not None and job.profile_id is not None
        assert association.profile_ids == [job.profile_id]

    import asyncio

    asyncio.run(scenario())


def test_worker_fails_closed_on_second_chunk_without_profile() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="job-1",
                document_id="fixture-cv-long",
                document_kind=DocumentKind.CV,
                owner_actor_id=LEARNER_ID,
                correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                status=JobStatus.QUEUED,
            )
        )
        gateway = FailingChunkGateway()
        worker = ExtractionWorker(
            repository, LongCVDocumentSource(), gateway, extraction_mode=ExtractionMode.SECTION_BASED
        )

        processed = await worker.run_once()
        job = await repository.get_job("job-1")

        assert processed is True
        assert len(gateway.requests) == 2
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.error_category == "chunk_2:invalid_structured_output:invalid_model_json"
        assert job.error_details is not None
        assert job.error_details["failure_code"] == "JSON_PARSE_FAILED"
        assert "raw_content" not in job.error_details
        assert job.profile_id is None
        assert await repository.get_profile("job-1") is None

    import asyncio

    asyncio.run(scenario())


def test_worker_keeps_unresolved_locator_claim_and_succeeds_profile() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="job-1",
                document_id="fixture-cv-long",
                document_kind=DocumentKind.CV,
                owner_actor_id=LEARNER_ID,
                correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                status=JobStatus.QUEUED,
            )
        )
        worker = ExtractionWorker(
            repository,
            LongCVDocumentSource(),
            UnresolvedLocatorGateway(),
            extraction_mode=ExtractionMode.SECTION_BASED,
        )

        assert await worker.run_once() is True
        job = await repository.get_job("job-1")

        assert job is not None
        assert job.status is JobStatus.SUCCEEDED
        assert job.profile_id is not None
        profile = await repository.get_profile(job.profile_id)
        assert profile is not None
        assert profile.review_state is ReviewState.PENDING_REVIEW
        assert profile.output.skills[0].evidence_status is EvidenceStatus.INSUFFICIENT
        assert profile.output.skills[0].unresolved_reason == "locator_unresolved"

    import asyncio

    asyncio.run(scenario())


def test_worker_can_select_v2_1_for_bounded_calibration_without_changing_default() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-full",
        kind=DocumentKind.CV,
        content="Profile\nExperience: Built APIs.",
        content_type="application/pdf",
        raw_bytes=b"%PDF-1.4",
    )
    calibrated = ExtractionWorker(
        InMemoryExtractionRepository(),
        FullCVDocumentSource(),
        RecordingFullGateway(),
        extraction_mode=ExtractionMode.FULL_DOCUMENT,
        full_prompt_version=FULL_EXTRACTION_SCHEMA_V2_1_VERSION,
    )
    request = calibrated._full_request("corr", CV_FULL_SCHEMA_ID, document)

    assert request.prompt_template_version == FULL_EXTRACTION_SCHEMA_V2_1_VERSION
    assert request.output_contract is not None
    assert request.output_contract.schema_version == FULL_EXTRACTION_SCHEMA_V2_1_VERSION
    assert request.output_token_budget == 2048


def test_worker_uses_v2_1_budget_for_v2_2_calibration() -> None:
    document = FixtureDocument(
        document_id="fixture-cv-full",
        kind=DocumentKind.CV,
        content="Profile\nExperience: Built APIs.",
        content_type="application/pdf",
        raw_bytes=b"%PDF-1.4",
    )
    worker = ExtractionWorker(
        InMemoryExtractionRepository(),
        FullCVDocumentSource(),
        RecordingFullGateway(),
        extraction_mode=ExtractionMode.FULL_DOCUMENT,
        full_prompt_version=FULL_EXTRACTION_SCHEMA_V2_2_VERSION,
    )
    request = worker._full_request("corr", CV_FULL_SCHEMA_ID, document)

    assert request.prompt_template_version == FULL_EXTRACTION_SCHEMA_V2_2_VERSION
    assert request.output_contract is not None
    assert request.output_contract.schema_version == FULL_EXTRACTION_SCHEMA_V2_2_VERSION
    assert request.output_token_budget == 2048


class FullCVDocumentSource:
    def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        return FixtureDocument(
            document_id=document_id,
            kind=kind,
            content="Profile\nSkills: Python and FastAPI.\nExperience: Built APIs.",
        )


class RecordingFullGateway:
    def __init__(self, *, excerpt: str = "Python and FastAPI") -> None:
        self.requests: list[InferenceRequest] = []
        self.excerpt = excerpt

    async def infer_structured(self, request, output_schema):
        self.requests.append(request)
        assert request.output_token_budget == 2048
        assert request.prompt_template_id == CV_FULL_SCHEMA_ID
        assert request.prompt_template_version == "2.0"
        assert request.output_contract is not None
        assert request.output_contract.schema_id == CV_FULL_SCHEMA_ID
        assert request.output_contract.strict is True
        assert output_schema is CVFullExtractionOutputV2
        source_text = str(request.payload.get("document", "Profile\nExperience: Built APIs."))
        start = source_text.index(self.excerpt)
        parsed = CVFullExtractionOutputV2(
            capabilities=[
                CapabilityItem(
                    raw_name="Python and FastAPI",
                    canonical_name="Python and FastAPI",
                    evidence=[CapabilityEvidence(
                        source_excerpt=self.excerpt,
                        source_locator=SourceLocator(
                            document_id="fixture-cv-full", section="skills",
                            start_offset=start, end_offset=start + len(self.excerpt),
                        ),
                        evidence_strength=EvidenceStrength.EXPLICIT_MENTION,
                        confidence=0.9,
                    )],
                )
            ],
            experience=[],
            education=[],
        )
        return StructuredInferenceResponse(
            parsed=parsed,
            audit=InferenceAuditMetadata(
                provider="mock",
                model="mock-full-v1",
                prompt_template_id=CV_FULL_SCHEMA_ID,
                prompt_template_version=FULL_EXTRACTION_SCHEMA_VERSION,
                output_schema_id=CV_FULL_SCHEMA_ID,
                output_schema_version=FULL_EXTRACTION_SCHEMA_VERSION,
                policy_version="privacy-v1",
                correlation_id=request.correlation_id,
                routing_decision="restricted_local_only",
                attempt_count=1,
                latency_ms=0,
                usage=ModelUsage(input_tokens=10, output_tokens=20),
                outcome="succeeded",
            ),
        )


class FailingFullGateway(RecordingFullGateway):
    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[CVFullExtractionOutput]
    ) -> StructuredInferenceResponse[CVFullExtractionOutput]:
        self.requests.append(request)
        raise StructuredOutputFailedError(
            "invalid_model_json",
            diagnostic=diagnostic_for_json_parse(
                content_length=len(str(request.payload["document"])),
                provider_finish_reason="stop",
            ),
        )


class FullJDDocumentSource:
    def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        return FixtureDocument(
            document_id=document_id,
            kind=kind,
            content="Role: Backend Engineer\nRequirements: Python experience.",
        )


class RecordingFullJDGateway:
    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []

    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[JDFullExtractionOutput]
    ) -> StructuredInferenceResponse[JDFullExtractionOutput]:
        self.requests.append(request)
        assert request.prompt_template_id == JD_FULL_SCHEMA_ID
        assert request.prompt_template_version == FULL_EXTRACTION_SCHEMA_VERSION
        assert output_schema is JDFullExtractionOutput
        return StructuredInferenceResponse(
            parsed=JDFullExtractionOutput(
                required_skills=[
                    EvidenceClaim(
                        value="Python",
                        evidence_type=EvidenceType.EXPLICIT_SKILL,
                        confidence=0.9,
                        evidence_status="supported",
                        source_excerpt="Python experience",
                    )
                ],
                responsibilities=[],
                qualifications=[],
            ),
            audit=InferenceAuditMetadata(
                provider="mock",
                model="mock-full-v1",
                prompt_template_id=JD_FULL_SCHEMA_ID,
                prompt_template_version=FULL_EXTRACTION_SCHEMA_VERSION,
                output_schema_id=JD_FULL_SCHEMA_ID,
                output_schema_version=FULL_EXTRACTION_SCHEMA_VERSION,
                policy_version="privacy-v1",
                correlation_id=request.correlation_id,
                routing_decision="restricted_local_only",
                attempt_count=1,
                latency_ms=0,
                usage=ModelUsage(input_tokens=10, output_tokens=20),
                outcome="succeeded",
            ),
        )


def _full_job(job_id: str) -> ExtractionJob:
    return ExtractionJob(
        id=job_id,
        document_id="fixture-cv-full",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        status=JobStatus.QUEUED,
    )


def test_full_document_success_does_not_split_or_merge(monkeypatch) -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_full_job("job-full"))
        gateway = RecordingFullGateway()

        def unexpected_split(*args, **kwargs):
            raise AssertionError("full-document extraction must not split")

        def unexpected_merge(*args, **kwargs):
            raise AssertionError("full-document extraction must not merge chunks")

        monkeypatch.setattr("app.extraction.worker.split_document", unexpected_split)
        monkeypatch.setattr("app.extraction.worker.merge_chunk_outputs", unexpected_merge)

        worker = ExtractionWorker(repository, FullCVDocumentSource(), gateway)
        assert await worker.run_once() is True

        job = await repository.get_job("job-full")
        assert job is not None
        assert job.status is JobStatus.SUCCEEDED
        profile = await repository.get_profile(job.profile_id or "")
        assert profile is not None
        assert profile.audit["strategy"] == ExtractionMode.FULL_DOCUMENT.value
        assert profile.audit["chunk_count"] == 0
        assert len(gateway.requests) == 1
        assert profile.output.capabilities[0].evidence[0].source_locator is not None

    import asyncio

    asyncio.run(scenario())


def test_pdf_cv_uses_native_document_input_when_bytes_are_available() -> None:
    async def scenario() -> None:
        class PdfSource:
            async def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
                return FixtureDocument(
                    document_id=document_id,
                    kind=kind,
                    content="Profile\nExperience: Built APIs.",
                    content_type="application/pdf",
                    raw_bytes=b"%PDF-1.4",
                    page_count=1,
                )

        repository = InMemoryExtractionRepository()
        await repository.enqueue(_full_job("job-native-pdf"))
        gateway = RecordingFullGateway(excerpt="Built APIs.")
        worker = ExtractionWorker(repository, PdfSource(), gateway)

        assert await worker.run_once() is True
        assert gateway.requests[0].document is not None
        assert gateway.requests[0].document.media_type == "application/pdf"
        assert gateway.requests[0].payload["input_mode"] == "native_pdf"
        job = await repository.get_job("job-native-pdf")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        profile = await repository.get_profile(job.profile_id or "")
        assert profile is not None
        assert profile.audit["input_mode"] == "native_pdf"

    import asyncio

    asyncio.run(scenario())


def test_full_document_failure_does_not_fallback_to_chunks(monkeypatch) -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_full_job("job-full-failed"))
        gateway = FailingFullGateway()

        def unexpected_split(*args, **kwargs):
            raise AssertionError("provider/schema failure must not trigger chunk fallback")

        monkeypatch.setattr("app.extraction.worker.split_document", unexpected_split)
        worker = ExtractionWorker(repository, FullCVDocumentSource(), gateway)

        assert await worker.run_once() is True
        job = await repository.get_job("job-full-failed")
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.error_category == "invalid_structured_output:invalid_model_json"
        assert len(gateway.requests) == 1

    import asyncio

    asyncio.run(scenario())


def test_full_document_unresolved_excerpt_fails_closed_without_fabricating_locator() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_full_job("job-full-unresolved"))
        worker = ExtractionWorker(
            repository,
            FullCVDocumentSource(),
            RecordingFullGateway(excerpt="not present in document"),
        )

        assert await worker.run_once() is True
        job = await repository.get_job("job-full-unresolved")
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.profile_id is None

    import asyncio

    asyncio.run(scenario())


def test_full_document_jd_uses_one_call_and_maps_evidence() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="job-full-jd",
                document_id="fixture-jd-full",
                document_kind=DocumentKind.JD,
                owner_actor_id=LEARNER_ID,
                correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                status=JobStatus.QUEUED,
            )
        )
        gateway = RecordingFullJDGateway()
        worker = ExtractionWorker(repository, FullJDDocumentSource(), gateway)

        assert await worker.run_once() is True
        job = await repository.get_job("job-full-jd")
        assert job is not None and job.profile_id is not None
        profile = await repository.get_profile(job.profile_id)
        assert profile is not None
        assert len(gateway.requests) == 1
        assert profile.output.required_skills[0].source_locator is not None
        assert profile.audit["strategy"] == ExtractionMode.FULL_DOCUMENT.value

    import asyncio

    asyncio.run(scenario())
