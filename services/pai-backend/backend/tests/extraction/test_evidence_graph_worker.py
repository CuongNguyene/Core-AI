import asyncio
from uuid import uuid4

from app.authorization.fixtures import LEARNER_ID
from app.extraction.fixtures import FixtureDocument
from app.extraction.prompts import CV_ENTITY_RELATION_SCHEMA_ID
from app.extraction.relation import (
    EntityRelation,
    EntityRelationOutput,
    RelationType,
    SectionEvidenceOutput,
)
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import DocumentKind, ExtractionJob, JobStatus
from app.extraction.worker import ExtractionWorker
from app.model_gateway.contracts import (
    InferenceAuditMetadata,
    InferenceRequest,
    ModelUsage,
    StructuredInferenceResponse,
)


class _Source:
    async def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        return FixtureDocument(
            document_id=document_id,
            kind=kind,
            content="SKILLS\nPython\nPROJECTS\nBuilt academic research work using PyTorch",
        )


class _GraphGateway:
    async def infer_structured(self, request: InferenceRequest, output_schema: type[object]):
        audit = InferenceAuditMetadata(
            provider="mock",
            model="graph-test",
            prompt_template_id=request.prompt_template_id,
            prompt_template_version=request.prompt_template_version,
            output_schema_id=request.output_contract.schema_id if request.output_contract else None,
            output_schema_version=request.output_contract.schema_version
            if request.output_contract
            else None,
            policy_version="privacy-v1",
            correlation_id=request.correlation_id,
            routing_decision="restricted_local_only",
            attempt_count=1,
            latency_ms=0,
            usage=ModelUsage(input_tokens=1, output_tokens=1),
            outcome="succeeded",
        )
        if request.prompt_template_id == CV_ENTITY_RELATION_SCHEMA_ID:
            parsed = EntityRelationOutput(
                relations=[
                    EntityRelation(
                        subject="PyTorch",
                        relation=RelationType.USED_IN,
                        object="academic research work",
                        evidence_excerpt="Built academic research work using PyTorch",
                        confidence=0.9,
                    )
                ]
            )
        else:
            parsed = SectionEvidenceOutput(entities=[])
        return StructuredInferenceResponse(parsed=parsed, audit=audit)


def test_worker_persists_graph_when_feature_flag_enabled() -> None:
    async def scenario() -> None:
        repository = InMemoryExtractionRepository()
        await repository.enqueue(
            ExtractionJob(
                id="graph-job",
                document_id="graph-cv",
                document_kind=DocumentKind.CV,
                owner_actor_id=LEARNER_ID,
                correlation_id=str(uuid4()),
                status=JobStatus.QUEUED,
            )
        )
        worker = ExtractionWorker(
            repository,
            _Source(),
            _GraphGateway(),
            evidence_graph_runtime_enabled=True,
        )
        assert await worker.run_once() is True
        job = await repository.get_job("graph-job")
        assert job is not None and job.profile_id is not None
        profile = await repository.get_profile(job.profile_id)
        assert profile is not None and profile.candidate_profile is not None
        assert profile.candidate_profile.skills[0].evidence[0].context.value == "used_in_research"

    asyncio.run(scenario())
