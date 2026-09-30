import asyncio
from uuid import UUID

from app.authorization.fixtures import LEARNER_ID
from app.extraction.capability_discovery import (
    DISCOVERY_PROMPT_ID,
    CapabilityDiscoveryOutput,
)
from app.extraction.capability_taxonomy import TaxonomySelectedCapability, TaxonomySelection
from app.extraction.fixtures import FixtureDocument
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.router import CvExtractionPipeline
from app.extraction.schemas import (
    DocumentKind,
    ExtractionJob,
    JobStatus,
)
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
)
from app.extraction.worker import ExtractionWorker
from app.model_gateway.contracts import (
    InferenceAuditMetadata,
    InferenceRequest,
    ModelUsage,
    StructuredInferenceResponse,
)


class NativePdfLongCvSource:
    def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        return FixtureDocument(
            document_id=document_id,
            kind=kind,
            content="x" * 13_000,
            content_type="application/pdf",
            raw_bytes=b"pdf-bytes",
            page_count=1,
        )


class TwoStageGateway:
    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []

    async def infer_structured(self, request: InferenceRequest, output_schema: type[object]) -> StructuredInferenceResponse[object]:
        self.requests.append(request)
        audit = InferenceAuditMetadata(
            provider="mock",
            model="gemini-3.5-flash-lite",
            prompt_template_id=request.prompt_template_id,
            prompt_template_version=request.prompt_template_version,
            output_schema_id=request.output_contract.schema_id if request.output_contract else "unknown",
            output_schema_version=request.output_contract.schema_version if request.output_contract else "unknown",
            policy_version="privacy-v1",
            correlation_id=request.correlation_id,
            routing_decision="restricted_local_only",
            attempt_count=1,
            latency_ms=0,
            usage=ModelUsage(input_tokens=1, output_tokens=1),
            outcome="succeeded",
        )
        if request.prompt_template_id == "cv_fact_extraction_experiment":
            parsed: object = ExperimentalCvFacts(
                document_id="fixture-cv-long",
                experiences=[
                    ExperimentalExperienceFact(
                        experience_id="exp-1",
                        role="Project Manager",
                        statements=[
                            ExperimentalStatement(
                                statement_id="stmt-1",
                                text="Owned project planning and delivery.",
                                document_id="fixture-cv-long",
                                page_number=1,
                            )
                        ],
                    )
                ],
            )
        elif request.prompt_template_id == DISCOVERY_PROMPT_ID:
            parsed = CapabilityDiscoveryOutput(
                capabilities=[
                    {
                        "raw_name": "Talent Acquisition",
                        "supporting_statement_ids": ["stmt-1"],
                    }
                ]
            )
        else:
            parsed = TaxonomySelection(
                taxonomy_id="professional_capability_core",
                taxonomy_version="0.1",
                capabilities=[
                    TaxonomySelectedCapability(
                        capability_id="project_management",
                        supporting_statement_ids=["stmt-1"],
                    )
                ],
            )
        return StructuredInferenceResponse(parsed=parsed, audit=audit)


def test_two_stage_long_native_pdf_does_not_split_or_call_stage2_twice() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="job-two-stage",
                document_id="fixture-cv-long",
                document_kind=DocumentKind.CV,
                owner_actor_id=LEARNER_ID,
                correlation_id=str(UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")),
                status=JobStatus.QUEUED,
            )
        )
        gateway = TwoStageGateway()
        worker = ExtractionWorker(
            repository,
            NativePdfLongCvSource(),
            gateway,  # type: ignore[arg-type]
            pipeline_mode=CvExtractionPipeline.TWO_STAGE,
        )

        assert await worker.run_once() is True
        job = await repository.get_job("job-two-stage")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        assert [request.prompt_template_id for request in gateway.requests] == [
            "cv_fact_extraction_experiment",
            "cv_capability_selection_criteria",
        ]
        assert gateway.requests[0].document is not None
        assert gateway.requests[0].payload["input_mode"] == "native_pdf"
        assert gateway.requests[0].output_contract is not None
        assert gateway.requests[0].output_contract.schema_id == "cv_fact_extraction_experiment"

    asyncio.run(scenario())


def test_two_stage_discovery_preserves_grounded_out_of_taxonomy_capability() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="job-discovery",
                document_id="fixture-cv-long",
                document_kind=DocumentKind.CV,
                owner_actor_id=LEARNER_ID,
                correlation_id=str(UUID("3fa85f64-5717-4562-b3fc-2c963f66afa7")),
                status=JobStatus.QUEUED,
            )
        )
        gateway = TwoStageGateway()
        worker = ExtractionWorker(
            repository,
            NativePdfLongCvSource(),
            gateway,  # type: ignore[arg-type]
            pipeline_mode=CvExtractionPipeline.TWO_STAGE,
            capability_mode="discovery",
        )

        assert await worker.run_once() is True
        job = await repository.get_job("job-discovery")
        assert job is not None and job.status is JobStatus.SUCCEEDED
        profile = await repository.get_profile(job.profile_id or "")
        assert profile is not None
        assert [request.prompt_template_id for request in gateway.requests] == [
            "cv_fact_extraction_experiment",
            DISCOVERY_PROMPT_ID,
        ]
        assert len(profile.output.capabilities) == 1  # type: ignore[union-attr]
        capability = profile.output.capabilities[0]  # type: ignore[union-attr]
        assert capability.raw_name == "Talent Acquisition"
        assert capability.mapping_status.value == "unmapped_but_grounded"
        assert capability.evidence
        assert profile.audit["capability_mode"] == "discovery"

    asyncio.run(scenario())
