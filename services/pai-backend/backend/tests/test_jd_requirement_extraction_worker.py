import asyncio

import pytest

from app.authorization.fixtures import LEARNER_ID
from app.extraction.fixtures import FixtureDocument
from app.extraction.prompts import (
    JD_REQUIREMENT_PDF_SCHEMA_ID,
    JD_REQUIREMENT_SCHEMA_VERSION,
    JD_REQUIREMENT_TEXT_SCHEMA_ID,
)
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import JdExtractionMode
from app.extraction.schemas import (
    DocumentKind,
    EvidenceStatus,
    ExtractionJob,
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionOutputV2Pdf,
    JDRequirementExtractionOutputV2Text,
    JDRequirementExtractionV2,
    JDRequirementModality,
    JobStatus,
    NativePdfLocator,
    ProviderPdfLocator,
    RequirementFieldProvenance,
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


def _audit(request: InferenceRequest) -> InferenceAuditMetadata:
    return InferenceAuditMetadata(
        provider="mock",
        model="mock-jd-v2",
        prompt_template_id=request.prompt_template_id,
        prompt_template_version=request.prompt_template_version,
        output_schema_id=request.output_contract.schema_id if request.output_contract else None,
        output_schema_version=request.output_contract.schema_version if request.output_contract else None,
        policy_version="privacy-v1",
        correlation_id=request.correlation_id,
        routing_decision="restricted_local_only",
        attempt_count=1,
        latency_ms=0,
        usage=ModelUsage(input_tokens=10, output_tokens=20),
        outcome="succeeded",
    )


def _job(job_id: str = "job-jd-v2") -> ExtractionJob:
    return ExtractionJob(
        id=job_id,
        document_id="fixture-jd-v2",
        document_kind=DocumentKind.JD,
        owner_actor_id=LEARNER_ID,
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        status=JobStatus.QUEUED,
    )


def _supported_requirement(
    document_id: str = "fixture-jd-v2",
    source_locator: SourceLocator | NativePdfLocator | ProviderPdfLocator | None = None,
) -> JDRequirementExtractionV2:
    return JDRequirementExtractionV2(
        requirement_id="req-python",
        statement="Build services with Python",
        criterion_dimension="skill",
        modality=JDRequirementModality.MUST,
        evidence_terms=["Python"],
        confidence=0.95,
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=source_locator
        or SourceLocator(
            document_id=document_id,
            section="requirements",
            start_offset=15,
            end_offset=21,
        ),
        source_excerpt="Python",
        provenance={"statement": RequirementFieldProvenance.JD_EXTRACTION},
    )


class RecordingJdV2Gateway:
    def __init__(self, parsed: JDRequirementExtractionOutputV2 | None = None) -> None:
        self.requests: list[InferenceRequest] = []
        self.parsed = parsed or JDRequirementExtractionOutputV2(
            requirements=[_supported_requirement()]
        )

    async def infer_structured(self, request: InferenceRequest, output_schema: type[object]):
        self.requests.append(request)
        assert request.prompt_template_id in {
            JD_REQUIREMENT_PDF_SCHEMA_ID,
            JD_REQUIREMENT_TEXT_SCHEMA_ID,
        }
        assert request.prompt_template_version == JD_REQUIREMENT_SCHEMA_VERSION
        expected_schema = (
            JDRequirementExtractionOutputV2Pdf
            if request.prompt_template_id == JD_REQUIREMENT_PDF_SCHEMA_ID
            else JDRequirementExtractionOutputV2Text
        )
        assert output_schema is expected_schema
        return StructuredInferenceResponse(parsed=self.parsed, audit=_audit(request))


class SingleJdSource:
    def __init__(self, document: FixtureDocument) -> None:
        self.document = document

    def get(self, _document_id: str, _kind: DocumentKind) -> FixtureDocument:
        return self.document


def test_settings_default_jd_mode_is_legacy_full_and_supports_explicit_requirement_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.shared.config import Settings

    monkeypatch.delenv("JD_EXTRACTION_MODE", raising=False)
    monkeypatch.delenv("PAI_JD_EXTRACTION_MODE", raising=False)

    assert Settings(_env_file=None).jd_extraction_mode == "legacy_full"
    assert (
        Settings(_env_file=None, jd_extraction_mode="requirement_v2").jd_extraction_mode
        == "requirement_v2"
    )


def test_requirement_v2_validation_rejects_missing_or_duplicate_supported_ids() -> None:
    from app.extraction.jd_requirement_validation import validate_requirement_v2_output

    duplicate = JDRequirementExtractionOutputV2(
        requirements=[_supported_requirement(), _supported_requirement()]
    )
    with pytest.raises(ValueError, match="duplicate_requirement_id"):
        validate_requirement_v2_output(
            duplicate, "fixture-jd-v2", "Role: Engineer\nPython services are required."
        )

    missing_id = _supported_requirement().model_copy(update={"requirement_id": None})
    output = JDRequirementExtractionOutputV2(requirements=[missing_id])
    with pytest.raises(ValueError, match="missing_requirement_id"):
        validate_requirement_v2_output(
            output, "fixture-jd-v2", "Role: Engineer\nPython services are required."
        )

    missing_locator = _supported_requirement().model_copy(update={"source_locator": None})
    with pytest.raises(ValueError, match="missing_source_locator"):
        validate_requirement_v2_output(
            JDRequirementExtractionOutputV2.model_construct(requirements=[missing_locator]),
            "fixture-jd-v2",
            "Role: Engineer\nPython services are required.",
        )


def test_requirement_v2_binds_provider_locator_to_backend_document_id() -> None:
    from app.extraction.jd_requirement_validation import bind_jd_requirement_source_document

    provider_output = JDRequirementExtractionOutputV2(
        requirements=[_supported_requirement(document_id="provider-placeholder")]
    )

    normalized = bind_jd_requirement_source_document(
        provider_output,
        document_id="fixture-jd-v2",
        parsed_text="Role: Engineer\nPython services are required.",
    )

    assert normalized.requirements[0].source_locator is not None
    assert normalized.requirements[0].source_locator.document_id == "fixture-jd-v2"


def test_exact_source_excerpt_resolver_uses_unique_match_not_model_offsets() -> None:
    from app.extraction.jd_requirement_validation import resolve_exact_source_excerpt

    resolved = resolve_exact_source_excerpt(
        "Role: Engineer\nPython services are required.",
        "Python",
    )

    assert resolved.start_offset == 15
    assert resolved.end_offset == 21


def test_exact_source_excerpt_resolver_rejects_missing_excerpt() -> None:
    from app.extraction.jd_requirement_validation import resolve_exact_source_excerpt

    with pytest.raises(ValueError, match="source_excerpt_not_found"):
        resolve_exact_source_excerpt("Role: Engineer", "Python")


def test_exact_source_excerpt_resolver_rejects_ambiguous_excerpt() -> None:
    from app.extraction.jd_requirement_validation import resolve_exact_source_excerpt

    with pytest.raises(ValueError, match="ambiguous_source_excerpt"):
        resolve_exact_source_excerpt("Python services; Python APIs", "Python")


def test_requirement_v2_worker_ignores_wrong_model_offsets_when_excerpt_is_unique() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-resolved"))
        provider_requirement = _supported_requirement(document_id="provider-placeholder").model_copy(
            update={
                "source_locator": SourceLocator(
                    document_id="provider-placeholder",
                    section="requirements",
                    start_offset=0,
                    end_offset=6,
                )
            }
        )
        gateway = RecordingJdV2Gateway(
            JDRequirementExtractionOutputV2(requirements=[provider_requirement])
        )
        source = FixtureDocument(
            document_id="fixture-jd-v2",
            kind=DocumentKind.JD,
            content="Role: Engineer\nPython services are required.",
        )

        worker = ExtractionWorker(
            repository,
            SingleJdSource(source),
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )
        assert await worker.run_once() is True

        job = await repository.get_job("job-jd-v2-resolved")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        profile = await repository.get_profile(job.profile_id or "")
        assert profile is not None
        assert isinstance(profile.output, JDRequirementExtractionOutputV2)
        locator = profile.output.requirements[0].source_locator
        assert locator is not None
        assert locator.document_id == "fixture-jd-v2"
        assert (locator.start_offset, locator.end_offset) == (15, 21)

    asyncio.run(scenario())


def test_requirement_v2_resolves_wrong_offset_from_exact_excerpt() -> None:
    from app.extraction.jd_requirement_validation import (
        bind_jd_requirement_source_document,
        validate_requirement_v2_output,
    )

    provider_output = JDRequirementExtractionOutputV2(
        requirements=[
            _supported_requirement(document_id="provider-placeholder").model_copy(
                update={
                    "source_locator": SourceLocator(
                        document_id="provider-placeholder",
                        section="requirements",
                        start_offset=100,
                        end_offset=106,
                    )
                }
            )
        ]
    )
    normalized = bind_jd_requirement_source_document(
        provider_output,
        document_id="fixture-jd-v2",
        parsed_text="Role: Engineer\nPython services are required.",
    )

    validate_requirement_v2_output(
        normalized,
        "fixture-jd-v2",
        "Role: Engineer\nPython services are required.",
    )
    locator = normalized.requirements[0].source_locator
    assert locator is not None
    assert (locator.start_offset, locator.end_offset) == (15, 21)


def test_requirement_v2_resolves_whitespace_normalized_excerpt() -> None:
    from app.extraction.jd_requirement_validation import (
        bind_jd_requirement_source_document,
        validate_requirement_v2_output,
    )

    document_text = "Role: Engineer\nPython services are required."
    provider_output = JDRequirementExtractionOutputV2(
        requirements=[
            _supported_requirement(document_id="provider-placeholder").model_copy(
                update={"source_excerpt": "Python services  are required."}
            )
        ]
    )

    normalized = bind_jd_requirement_source_document(
        provider_output,
        document_id="fixture-jd-v2",
        parsed_text=document_text,
    )

    validate_requirement_v2_output(normalized, "fixture-jd-v2", document_text)
    requirement = normalized.requirements[0]
    assert requirement.source_excerpt == "Python services are required."
    locator = requirement.source_locator
    assert locator is not None
    assert (locator.start_offset, locator.end_offset) == (15, 44)


def test_requirement_v2_rejects_wrong_excerpt_after_document_binding() -> None:
    from app.extraction.jd_requirement_validation import bind_jd_requirement_source_document

    provider_output = JDRequirementExtractionOutputV2(
        requirements=[
            _supported_requirement(document_id="provider-placeholder").model_copy(
                update={"source_excerpt": "FastAPI"}
            )
        ]
    )
    with pytest.raises(ValueError, match="source_excerpt_not_found"):
        bind_jd_requirement_source_document(
            provider_output,
            document_id="fixture-jd-v2",
            parsed_text="Role: Engineer\nPython services are required.",
        )


def test_requirement_v2_rejects_pdf_text_span_locator() -> None:
    from app.extraction.jd_requirement_validation import bind_jd_requirement_source_document

    provider_output = JDRequirementExtractionOutputV2(
        requirements=[
            _supported_requirement(
                source_locator=SourceLocator(
                    document_id="provider-placeholder",
                    section="requirements",
                    start_offset=15,
                    end_offset=21,
                )
            )
        ]
    )
    with pytest.raises(ValueError, match="pdf_requires_page_locator"):
        bind_jd_requirement_source_document(
            provider_output,
            document_id="fixture-jd-v2",
            parsed_text="Role: Engineer\nPython services are required.",
            is_pdf=True,
            page_texts=["Role: Engineer\nPython services are required."],
        )


def test_requirement_v2_rejects_text_native_pdf_locator() -> None:
    from app.extraction.jd_requirement_validation import bind_jd_requirement_source_document

    provider_output = JDRequirementExtractionOutputV2(
        requirements=[
            _supported_requirement(
                source_locator=NativePdfLocator(
                    document_id="provider-placeholder",
                    page_number=1,
                )
            )
        ]
    )
    with pytest.raises(ValueError, match="text_requires_span_locator"):
        bind_jd_requirement_source_document(
            provider_output,
            document_id="fixture-jd-v2",
            parsed_text="Role: Engineer\nPython services are required.",
        )


def test_requirement_v2_worker_persists_backend_owned_locator_identity() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-normalized"))
        gateway = RecordingJdV2Gateway(
            JDRequirementExtractionOutputV2(
                requirements=[_supported_requirement(document_id="provider-placeholder")]
            )
        )
        source = FixtureDocument(
            document_id="fixture-jd-v2",
            kind=DocumentKind.JD,
            content="Role: Engineer\nPython services are required.",
        )

        worker = ExtractionWorker(
            repository,
            SingleJdSource(source),
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )
        assert await worker.run_once() is True

        job = await repository.get_job("job-jd-v2-normalized")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        profile = await repository.get_profile(job.profile_id or "")
        assert profile is not None
        assert isinstance(profile.output, JDRequirementExtractionOutputV2)
        assert profile.output.requirements[0].source_locator is not None
        assert profile.output.requirements[0].source_locator.document_id == "fixture-jd-v2"

    asyncio.run(scenario())


def test_requirement_v2_worker_persists_pending_review_without_legacy_fallback() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job())
        gateway = RecordingJdV2Gateway()
        source = FixtureDocument(
            document_id="fixture-jd-v2",
            kind=DocumentKind.JD,
            content="Role: Engineer\nPython services are required.",
        )

        worker = ExtractionWorker(
            repository,
            SingleJdSource(source),
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )
        assert await worker.run_once() is True

        job = await repository.get_job("job-jd-v2")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        profile = await repository.get_profile(job.profile_id or "")
        assert profile is not None
        assert profile.review_state is ReviewState.PENDING_REVIEW
        assert isinstance(profile.output, JDRequirementExtractionOutputV2)
        assert profile.output.requirements[0].requirement_id == "req-python"
        assert profile.audit["pipeline_mode"] == "legacy_v2"
        assert profile.audit["jd_extraction_mode"] == "requirement_v2"
        assert profile.audit["input_mode"] == "whole_parsed_text"
        assert len(gateway.requests) == 1

    asyncio.run(scenario())


def test_requirement_v2_pdf_uses_native_document_input_for_page_locator_contract() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-pdf"))
        gateway = RecordingJdV2Gateway(
            JDRequirementExtractionOutputV2(
                requirements=[
                    _supported_requirement(
                        source_locator=NativePdfLocator(
                            document_id="provider-placeholder",
                            page_number=1,
                        )
                    )
                ]
            )
        )
        source = FixtureDocument(
            document_id="fixture-jd-v2",
            kind=DocumentKind.JD,
            content="Role: Engineer\nPython services are required.",
            content_type="application/pdf",
            raw_bytes=b"%PDF-1.4",
            page_count=1,
            page_texts=["Role: Engineer\nPython services are required."],
        )
        worker = ExtractionWorker(
            repository,
            SingleJdSource(source),
            gateway,
            jd_extraction_mode="requirement_v2",
        )
        assert await worker.run_once() is True
        assert gateway.requests[0].document is not None
        assert gateway.requests[0].payload["input_mode"] == "native_pdf"

    asyncio.run(scenario())


def test_requirement_v2_provider_pdf_locator_does_not_require_document_id() -> None:
    from app.extraction.jd_requirement_validation import bind_jd_requirement_source_document

    provider_output = JDRequirementExtractionOutputV2(
        requirements=[
            _supported_requirement(
                source_locator=ProviderPdfLocator(page_number=1),
            )
        ]
    )

    locator = provider_output.requirements[0].source_locator
    assert isinstance(locator, ProviderPdfLocator)
    normalized = bind_jd_requirement_source_document(
        provider_output,
        document_id="fixture-jd-v2",
        parsed_text="Role: Engineer\nPython services are required.",
        is_pdf=True,
        page_texts=["Role: Engineer\nPython services are required."],
    )
    normalized_locator = normalized.requirements[0].source_locator
    assert isinstance(normalized_locator, NativePdfLocator)
    assert normalized_locator.document_id == "fixture-jd-v2"
    assert normalized_locator.page_number == 1
    assert "start_offset" not in normalized_locator.model_dump()
    assert "end_offset" not in normalized_locator.model_dump()


def test_requirement_v2_provider_contracts_are_format_specific() -> None:
    text_schema = JDRequirementExtractionOutputV2Text.model_json_schema()
    pdf_schema = JDRequirementExtractionOutputV2Pdf.model_json_schema()

    assert "ProviderTextLocator" in str(text_schema["$defs"])
    assert "SourceLocator" not in str(text_schema["$defs"])
    assert "ProviderPdfLocator" not in str(text_schema["$defs"])
    assert "SourceLocator" not in str(pdf_schema["$defs"])
    assert "ProviderPdfLocator" in str(pdf_schema["$defs"])


def test_requirement_v2_text_provider_locator_can_omit_backend_owned_offsets() -> None:
    from app.extraction.jd_requirement_validation import bind_jd_requirement_source_document

    payload = _supported_requirement(document_id="provider-placeholder").model_dump(mode="json")
    payload["source_locator"] = {"section": "requirements"}
    provider_output = JDRequirementExtractionOutputV2Text.model_validate(
        {"requirements": [payload]}, strict=False
    )

    normalized = bind_jd_requirement_source_document(
        provider_output,
        document_id="fixture-jd-v2",
        parsed_text="Role: Engineer\nPython services are required.",
    )

    locator = normalized.requirements[0].source_locator
    assert isinstance(locator, SourceLocator)
    assert locator.document_id == "fixture-jd-v2"
    assert locator.section == "requirements"
    assert (locator.start_offset, locator.end_offset) == (15, 21)


def test_requirement_v2_provider_contract_requires_requirement_id() -> None:
    payload = _supported_requirement().model_dump(mode="json")
    payload.pop("requirement_id")

    with pytest.raises(ValueError, match="requirement_id"):
        JDRequirementExtractionOutputV2Text.model_validate(
            {"requirements": [payload]}, strict=False
        )


def test_requirement_v2_pdf_persists_page_locator_without_global_offsets() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-pdf-page"))
        gateway = RecordingJdV2Gateway(
            JDRequirementExtractionOutputV2(
                requirements=[
                    _supported_requirement(
                        source_locator=NativePdfLocator(
                            document_id="provider-placeholder",
                            page_number=2,
                        )
                    )
                ]
            )
        )
        source = FixtureDocument(
            document_id="fixture-jd-v2",
            kind=DocumentKind.JD,
            content="Role: Engineer\nPython services are required.",
            content_type="application/pdf",
            raw_bytes=b"%PDF-1.4",
            page_count=2,
            page_texts=["Role: Engineer", "Python services are required."],
        )

        worker = ExtractionWorker(
            repository,
            SingleJdSource(source),
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )
        assert await worker.run_once() is True

        job = await repository.get_job("job-jd-v2-pdf-page")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        profile = await repository.get_profile(job.profile_id or "")
        assert profile is not None
        assert isinstance(profile.output, JDRequirementExtractionOutputV2)
        locator = profile.output.requirements[0].source_locator
        assert isinstance(locator, NativePdfLocator)
        assert locator.document_id == "fixture-jd-v2"
        assert locator.page_number == 2

    asyncio.run(scenario())


def test_requirement_v2_pdf_rejects_invalid_page() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-pdf-invalid-page"))
        gateway = RecordingJdV2Gateway(
            JDRequirementExtractionOutputV2(
                requirements=[
                    _supported_requirement(
                        source_locator=NativePdfLocator(
                            document_id="provider-placeholder",
                            page_number=3,
                        )
                    )
                ]
            )
        )
        source = FixtureDocument(
            document_id="fixture-jd-v2",
            kind=DocumentKind.JD,
            content="Role: Engineer\nPython services are required.",
            content_type="application/pdf",
            raw_bytes=b"%PDF-1.4",
            page_count=2,
            page_texts=["Role: Engineer", "Python services are required."],
        )

        worker = ExtractionWorker(
            repository,
            SingleJdSource(source),
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )
        assert await worker.run_once() is True
        job = await repository.get_job("job-jd-v2-pdf-invalid-page")
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.error_details == {
            "failure_stage": "requirement_v2_validation",
            "failure_code": "native_pdf_invalid_page",
        }

    asyncio.run(scenario())


def test_requirement_v2_pdf_allows_duplicate_excerpt_on_claimed_page() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-pdf-duplicate-page"))
        gateway = RecordingJdV2Gateway(
            JDRequirementExtractionOutputV2(
                requirements=[
                    _supported_requirement(
                        source_locator=NativePdfLocator(
                            document_id="provider-placeholder",
                            page_number=1,
                        )
                    )
                ]
            )
        )
        source = FixtureDocument(
            document_id="fixture-jd-v2",
            kind=DocumentKind.JD,
            content="Python Python",
            content_type="application/pdf",
            raw_bytes=b"%PDF-1.4",
            page_count=1,
            page_texts=["Python Python"],
        )

        worker = ExtractionWorker(
            repository,
            SingleJdSource(source),
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )
        assert await worker.run_once() is True
        job = await repository.get_job("job-jd-v2-pdf-duplicate-page")
        assert job is not None and job.status is JobStatus.SUCCEEDED

    asyncio.run(scenario())


def test_requirement_v2_oversized_pdf_uses_native_full_document_without_chunk_fallback() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-large-pdf"))
        gateway = RecordingJdV2Gateway(
            JDRequirementExtractionOutputV2(
                requirements=[
                    _supported_requirement(
                        source_locator=NativePdfLocator(
                            document_id="provider-placeholder",
                            page_number=1,
                        )
                    )
                ]
            )
        )
        source = SingleJdSource(
            FixtureDocument(
                document_id="fixture-jd-v2",
                kind=DocumentKind.JD,
                content="Python " + ("x" * 12_001),
                content_type="application/pdf",
                raw_bytes=b"%PDF-1.4",
                page_count=1,
                page_texts=["Python " + ("x" * 12_001)],
            )
        )
        worker = ExtractionWorker(
            repository,
            source,
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )

        assert await worker.run_once() is True
        job = await repository.get_job("job-jd-v2-large-pdf")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        assert len(gateway.requests) == 1
        assert gateway.requests[0].document is not None
        assert gateway.requests[0].payload["input_mode"] == "native_pdf"

    asyncio.run(scenario())


def test_requirement_v2_oversized_input_fails_closed_without_chunk_or_legacy_fallback() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(_job("job-jd-v2-large"))
        gateway = RecordingJdV2Gateway()
        source = SingleJdSource(
            FixtureDocument(
                document_id="fixture-jd-v2",
                kind=DocumentKind.JD,
                content="x" * 12_001,
            )
        )
        worker = ExtractionWorker(
            repository,
            source,
            gateway,
            jd_extraction_mode=JdExtractionMode.REQUIREMENT_V2,
        )

        assert await worker.run_once() is True
        job = await repository.get_job("job-jd-v2-large")
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.error_category == "jd_requirement_v2_oversized_input"
        assert gateway.requests == []

    asyncio.run(scenario())
