import asyncio
import inspect
import json
import logging
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.candidate.service import CandidateService
from app.extraction.capability_discovery import (
    DISCOVERY_PROMPT_ID,
    CapabilityDiscoveryOutput,
    canonicalize_capabilities,
)
from app.extraction.capability_projection import (
    bind_v2_document_evidence,
    project_v2_to_candidate_profile,
    validate_v2_document_evidence,
)
from app.extraction.capability_taxonomy import (
    TaxonomySelection,
    merge_taxonomy_selections,
    validate_taxonomy_selection,
)
from app.extraction.chunking import split_document, split_sections
from app.extraction.ext_03a8_selection_semantics import CRITERIA_PROMPT_ID
from app.extraction.fixtures import DocumentSource, FixtureDocument
from app.extraction.graph_merge import merge_relation_evidence, profile_from_legacy_cv
from app.extraction.jd_requirement_validation import (
    bind_jd_requirement_source_document,
    validate_requirement_v2_output,
)
from app.extraction.merge import (
    ChunkLocatorError,
    map_full_document_output,
    merge_chunk_outputs,
)
from app.extraction.prompts import (
    CHUNK_EXTRACTION_SCHEMA_VERSION,
    CV_CHUNK_SCHEMA_ID,
    CV_ENTITY_RELATION_SCHEMA_ID,
    CV_FULL_SCHEMA_ID,
    CV_SECTION_EVIDENCE_SCHEMA_ID,
    FULL_EXTRACTION_SCHEMA_V2_VERSION,
    FULL_EXTRACTION_SCHEMA_VERSION,
    JD_CHUNK_SCHEMA_ID,
    JD_FULL_SCHEMA_ID,
    JD_REQUIREMENT_PDF_SCHEMA_ID,
    JD_REQUIREMENT_SCHEMA_ID,
    JD_REQUIREMENT_SCHEMA_VERSION,
    JD_REQUIREMENT_TEXT_SCHEMA_ID,
    RELATION_EXTRACTION_SCHEMA_VERSION,
)
from app.extraction.relation import EntityRelationOutput, SectionEvidenceOutput
from app.extraction.relation_graph import (
    relation_output_to_graph_input,
    section_evidence_to_graph_input,
)
from app.extraction.repository import ExtractionRepository
from app.extraction.router import (
    CvExtractionPipeline,
    ExtractionInputMode,
    ExtractionMode,
    JdExtractionMode,
    choose_extraction_mode,
)
from app.extraction.schemas import (
    CVChunkExtractionOutput,
    CVExtractionOutput,
    CVFullExtractionOutput,
    CVFullExtractionOutputV2,
    DocumentKind,
    ExtractionJob,
    ExtractionStage,
    ExtractionProfile,
    JDChunkExtractionOutput,
    JDExtractionOutput,
    JDFullExtractionOutput,
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionOutputV2Pdf,
    JDRequirementExtractionOutputV2Text,
    ReviewState,
)
from app.extraction.structure import detect_document_structure
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    validate_facts_references,
)
from app.extraction.two_stage_composer import compose_discovered_output, compose_two_stage_output
from app.model_gateway.contracts import (
    DataClassification,
    DocumentInput,
    InferenceAuditMetadata,
    InferencePurpose,
    InferenceRequest,
    ModelGateway,
    OutputContract,
)
from app.model_gateway.errors import (
    ProviderOutputBudgetError,
    ProviderResponseError,
    ProviderTimeoutError,
    StructuredOutputFailedError,
)


@dataclass(frozen=True, slots=True)
class _ChunkDefinition:
    purpose: InferencePurpose
    prompt_template_id: str
    output_schema: type[CVChunkExtractionOutput] | type[JDChunkExtractionOutput]


class _ExtractionStopped(Exception):
    """Job was already transitioned to a terminal failure state."""


class ExtractionWorker:
    """Claims one job at a time; never runs in the FastAPI request path."""

    def __init__(
        self,
        repository: ExtractionRepository,
        document_source: DocumentSource,
        model_gateway: ModelGateway,
        output_token_budget: int = 2048,
        evidence_graph_runtime_enabled: bool = False,
        locator_forensics_enabled: bool = False,
        locator_forensics_dir: str | None = None,
        candidate_service: CandidateService | None = None,
        extraction_mode: ExtractionMode | None = None,
        full_prompt_version: str | None = None,
        pipeline_mode: CvExtractionPipeline | str = CvExtractionPipeline.LEGACY_V2,
        capability_mode: str = "bounded",
        jd_extraction_mode: JdExtractionMode | str = JdExtractionMode.LEGACY_FULL,
        heartbeat_seconds: float = 15.0,
    ) -> None:
        self._repository = repository
        self._document_source = document_source
        self._model_gateway = model_gateway
        self._output_token_budget = output_token_budget
        self._evidence_graph_runtime_enabled = evidence_graph_runtime_enabled
        self._locator_forensics_enabled = locator_forensics_enabled
        self._locator_forensics_dir = Path(locator_forensics_dir) if locator_forensics_dir else None
        self._candidate_service = candidate_service
        self._extraction_mode = extraction_mode
        self._full_prompt_version = full_prompt_version or FULL_EXTRACTION_SCHEMA_V2_VERSION
        self._pipeline_mode = CvExtractionPipeline(pipeline_mode)
        if capability_mode not in {"bounded", "discovery"}:
            raise ValueError("unsupported_two_stage_capability_mode")
        self._capability_mode = capability_mode
        self._jd_extraction_mode = JdExtractionMode(jd_extraction_mode)
        self._heartbeat_seconds = heartbeat_seconds

    @staticmethod
    def _safe_failure_details(stage: str, code: str) -> dict[str, object]:
        return {"failure_stage": stage, "failure_code": code}

    @staticmethod
    def _provider_failure_category(error: ProviderResponseError) -> str:
        return (
            "model_rate_limited"
            if "HTTP 429" in str(error)
            else "provider_response_invalid"
        )

    async def run_once(self) -> bool:
        job = await self._repository.claim_next()
        if job is None:
            return False

        heartbeat = asyncio.create_task(self._heartbeat(job.id))
        try:
            document_result = self._document_source.get(job.document_id, job.document_kind)
            document = (
                await document_result if inspect.isawaitable(document_result) else document_result
            )
            await self._repository.update_progress(job.id, ExtractionStage.EXTRACTING)
            if self._evidence_graph_runtime_enabled and job.document_kind is DocumentKind.CV:
                await self._run_graph_extraction(job, document)
                return True
            output: (
                CVExtractionOutput
                | CVFullExtractionOutputV2
                | JDExtractionOutput
                | JDRequirementExtractionOutputV2
            )
            if (
                job.document_kind is DocumentKind.CV
                and self._pipeline_mode is CvExtractionPipeline.TWO_STAGE
            ):
                output, audits = await self._run_two_stage_extraction(job, document)
                mode = ExtractionMode.FULL_DOCUMENT
                chunk_count = 0
            elif (
                job.document_kind is DocumentKind.JD
                and self._jd_extraction_mode is JdExtractionMode.REQUIREMENT_V2
            ):
                output, audits = await self._run_requirement_v2_extraction(job, document)
                mode = ExtractionMode.FULL_DOCUMENT
                chunk_count = 0
            else:
                mode = self._extraction_mode or choose_extraction_mode(document.content)
                if mode is ExtractionMode.FULL_DOCUMENT:
                    output, audits = await self._run_full_document_extraction(job, document)
                    chunk_count = 0
                else:
                    output, audits, chunk_count = await self._run_chunk_extraction(job, document)

            audit = self._aggregate_audit(audits, chunk_count, mode)
            audit["input_mode"] = self._input_mode(
                document,
                mode,
                jd_requirement_v2=(
                    job.document_kind is DocumentKind.JD
                    and self._jd_extraction_mode is JdExtractionMode.REQUIREMENT_V2
                ),
            ).value
            audit["pipeline_mode"] = self._pipeline_mode.value
            if job.document_kind is DocumentKind.JD:
                audit["jd_extraction_mode"] = self._jd_extraction_mode.value
            if isinstance(output, CVFullExtractionOutputV2):
                audit.update(
                    {
                        "schema_version": self._full_prompt_version,
                        "capabilities_extracted": len(output.capabilities),
                        "tools_extracted": len(output.tools_platforms),
                        "experience_items_extracted": len(output.experience),
                        "education_items_extracted": len(output.education),
                    "grounded_capabilities": sum(
                        bool(item.evidence) for item in output.capabilities
                    ),
                    "capability_mode": self._capability_mode,
                    "mapped_count": sum(item.mapping_status.value == "mapped" for item in output.capabilities),
                    "unmapped_count": sum(
                        item.mapping_status.value == "unmapped_but_grounded"
                        for item in output.capabilities
                    ),
                    "rejected_count": 0,
                }
            )
            await self._repository.update_progress(job.id, ExtractionStage.VALIDATING)
            try:
                candidate_profile = (
                    project_v2_to_candidate_profile(output, document.content)
                    if isinstance(output, CVFullExtractionOutputV2)
                    else profile_from_legacy_cv(output)
                    if isinstance(output, CVExtractionOutput)
                    else None
                )
            except ValueError as exc:
                await self._repository.mark_failed(
                    job.id,
                    "compatibility_projection_failed",
                    self._safe_failure_details("compatibility_projection", str(exc)),
                )
                return True
            await self._repository.update_progress(job.id, ExtractionStage.PERSISTING)
            profile = ExtractionProfile(
                id=str(uuid4()),
                job_id=job.id,
                document_id=job.document_id,
                document_kind=job.document_kind,
                owner_actor_id=job.owner_actor_id,
                version=1,
                review_state=ReviewState.PENDING_REVIEW,
                output=output,
                candidate_profile=candidate_profile,
                audit=audit,
            )
            await self._repository.mark_succeeded(job.id, profile)
            if self._candidate_service is not None:
                await self._candidate_service.associate_extraction_profile(profile.id)
        except _ExtractionStopped:
            pass
        except KeyError:
            await self._repository.mark_failed(job.id, "fixture_document_not_found")
        except Exception as exc:
            logging.getLogger(__name__).error(
                "extraction_unclassified_failure exception_type=%s", type(exc).__name__
            )
            await self._repository.mark_failed(
                job.id,
                "extraction_failed",
                {"failure_stage": "unknown", "failure_code": "unclassified_exception"},
            )
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        return True

    async def _heartbeat(self, job_id: str) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_seconds)
            await self._repository.touch(job_id)

    async def _run_two_stage_extraction(
        self, job: ExtractionJob, document: FixtureDocument
    ) -> tuple[CVFullExtractionOutputV2, list[InferenceAuditMetadata]]:
        if document.kind is not DocumentKind.CV or document.raw_bytes is None:
            await self._repository.mark_failed(
                job.id,
                "two_stage_native_pdf_required",
                self._safe_failure_details("pipeline_selection", "native_pdf_required"),
            )
            raise _ExtractionStopped from None
        stage1_request = self._full_request(
            job.correlation_id, CV_FULL_SCHEMA_ID, document
        ).model_copy(
            update={
                "prompt_template_id": "cv_fact_extraction_experiment",
                "prompt_template_version": "1",
                "output_contract": OutputContract(
                    schema_id="cv_fact_extraction_experiment",
                    schema_version="1",
                    strict=True,
                ),
            }
        )
        try:
            stage1 = await self._model_gateway.infer_structured(
                stage1_request, ExperimentalCvFacts
            )
            validate_facts_references(
                stage1.parsed,
                expected_document_id=document.document_id,
                page_count=document.page_count or 1,
            )
            if self._capability_mode == "discovery":
                stage2_prompt = DISCOVERY_PROMPT_ID
                stage2_schema = CapabilityDiscoveryOutput
                discovery_result = await self._model_gateway.infer_structured(
                    InferenceRequest(
                        purpose=InferencePurpose.CV_EXTRACTION,
                        data_classification=DataClassification.RESTRICTED,
                        prompt_template_id=stage2_prompt,
                        prompt_template_version="1.0",
                        payload={"facts": stage1.parsed.model_dump(mode="json")},
                        output_contract=OutputContract(
                            schema_id=stage2_prompt, schema_version="1.0", strict=True
                        ),
                        output_token_budget=16384,
                        correlation_id=job.correlation_id,
                    ),
                    stage2_schema,
                )
                discovered = canonicalize_capabilities(discovery_result.parsed, stage1.parsed)
                stage2_audit = discovery_result.audit
                composed = compose_discovered_output(
                    stage1.parsed, discovered, page_count=document.page_count or 1
                )
            else:
                bounded_result = await self._model_gateway.infer_structured(
                    InferenceRequest(
                        purpose=InferencePurpose.CV_EXTRACTION,
                        data_classification=DataClassification.RESTRICTED,
                        prompt_template_id=CRITERIA_PROMPT_ID,
                        prompt_template_version="1.0",
                        payload={"facts": stage1.parsed.model_dump(mode="json")},
                        output_contract=OutputContract(
                            schema_id=CRITERIA_PROMPT_ID, schema_version="1.0", strict=True
                        ),
                        output_token_budget=16384,
                        correlation_id=job.correlation_id,
                    ),
                    TaxonomySelection,
                )
                selection = merge_taxonomy_selections(bounded_result.parsed)
                validate_taxonomy_selection(selection, stage1.parsed)
                stage2_audit = bounded_result.audit
                composed = compose_two_stage_output(
                    stage1.parsed, selection, page_count=document.page_count or 1
                )
            composed = bind_v2_document_evidence(
                composed, document_id=document.document_id, document=document.content
            )
            validate_v2_document_evidence(
                composed,
                document.content,
                input_mode=self._input_mode(document, ExtractionMode.FULL_DOCUMENT),
                page_count=document.page_count,
                expected_document_id=document.document_id,
            )
            return composed, [stage1.audit, stage2_audit]
        except (ProviderTimeoutError, ProviderResponseError, StructuredOutputFailedError) as exc:
            category = type(exc).__name__.replace("Error", "").lower()
            await self._repository.mark_failed(job.id, f"two_stage_{category}")
            raise _ExtractionStopped from None
        except ValueError as exc:
            await self._repository.mark_failed(
                job.id,
                "two_stage_validation_failed",
                self._safe_failure_details("two_stage_validation", str(exc)),
            )
            raise _ExtractionStopped from None

    async def _run_full_document_extraction(
        self, job: ExtractionJob, document: FixtureDocument
    ) -> tuple[
        CVExtractionOutput | CVFullExtractionOutputV2 | JDExtractionOutput,
        list[InferenceAuditMetadata],
    ]:
        definition = self._full_definition_for(job.document_kind)
        request = self._full_request(job.correlation_id, definition[0], document)
        try:
            result = await self._model_gateway.infer_structured(request, definition[1])
        except ProviderOutputBudgetError:
            await self._repository.mark_failed(
                job.id,
                "provider_output_budget_exceeded",
                {"failure_stage": "provider_call", "failure_code": "provider_output_budget"},
            )
            raise _ExtractionStopped from None
        except ProviderTimeoutError:
            await self._repository.mark_failed(job.id, "provider_timeout")
            raise _ExtractionStopped from None
        except ProviderResponseError as exc:
            logging.getLogger(__name__).warning(
                "extraction_provider_response_failure job_id=%s document_kind=%s reason=%s",
                job.id,
                job.document_kind.value,
                str(exc),
            )
            await self._repository.mark_failed(
                job.id,
                self._provider_failure_category(exc),
                self._safe_failure_details("provider_call", str(exc)),
            )
            raise _ExtractionStopped from None
        except StructuredOutputFailedError as exc:
            await self._repository.mark_failed(
                job.id,
                f"invalid_structured_output:{exc.category}",
                self._diagnostic_details(exc.diagnostic),
            )
            raise _ExtractionStopped from None
        await self._repository.update_progress(job.id, ExtractionStage.VALIDATING)
        if isinstance(result.parsed, CVFullExtractionOutputV2):
            try:
                normalized = bind_v2_document_evidence(
                    result.parsed, document_id=document.document_id, document=document.content
                )
                validate_v2_document_evidence(
                    normalized,
                    document.content,
                    input_mode=self._input_mode(document, ExtractionMode.FULL_DOCUMENT),
                    page_count=document.page_count,
                    expected_document_id=document.document_id,
                )
            except ValueError as exc:
                await self._repository.mark_failed(
                    job.id,
                    "grounding_validation_failed",
                    {"failure_stage": "grounding_validation", "failure_code": str(exc)},
                )
                raise _ExtractionStopped from None
            return normalized, [result.audit]
        return map_full_document_output(document, result.parsed), [result.audit]

    async def _run_requirement_v2_extraction(
        self, job: ExtractionJob, document: FixtureDocument
    ) -> tuple[JDRequirementExtractionOutputV2, list[InferenceAuditMetadata]]:
        native_pdf = document.content_type == "application/pdf" and document.raw_bytes is not None
        if not native_pdf and choose_extraction_mode(document.content) is ExtractionMode.SECTION_BASED:
            await self._repository.mark_failed(
                job.id,
                "jd_requirement_v2_oversized_input",
                self._safe_failure_details("routing", "full_document_required"),
            )
            raise _ExtractionStopped from None
        provider_schema_id = (
            JD_REQUIREMENT_PDF_SCHEMA_ID if native_pdf else JD_REQUIREMENT_TEXT_SCHEMA_ID
        )
        provider_schema = (
            JDRequirementExtractionOutputV2Pdf
            if native_pdf
            else JDRequirementExtractionOutputV2Text
        )
        request = self._full_request(job.correlation_id, provider_schema_id, document)
        try:
            result = await self._model_gateway.infer_structured(
                request, provider_schema
            )
            if not isinstance(
                result.parsed,
                (
                    JDRequirementExtractionOutputV2,
                    JDRequirementExtractionOutputV2Pdf,
                    JDRequirementExtractionOutputV2Text,
                ),
            ):
                raise ValueError("invalid_jd_requirement_output")

            await self._repository.update_progress(job.id, ExtractionStage.VALIDATING)  
              
            normalized = bind_jd_requirement_source_document(
                result.parsed,
                document_id=document.document_id,
                parsed_text=document.content,
                is_pdf=document.content_type == "application/pdf",
                page_texts=document.page_texts,
            )
            validate_requirement_v2_output(
                normalized,
                expected_document_id=document.document_id,
                document_text=document.content,
                page_texts=document.page_texts,
            )
            return normalized, [result.audit]
        except ProviderTimeoutError:
            await self._repository.mark_failed(
                job.id,
                "jd_requirement_v2_provider_timeout",
                self._safe_failure_details("provider_call", "provider_timeout"),
            )
            raise _ExtractionStopped from None
        except ProviderResponseError as exc:
            await self._repository.mark_failed(
                job.id,
                f"jd_requirement_v2_{self._provider_failure_category(exc)}",
                self._safe_failure_details("provider_call", str(exc)),
            )
            raise _ExtractionStopped from None
        except StructuredOutputFailedError as exc:
            await self._repository.mark_failed(
                job.id,
                f"jd_requirement_v2_{exc.category}",
                self._diagnostic_details(exc.diagnostic),
            )
            raise _ExtractionStopped from None
        except ValueError as exc:
            await self._repository.mark_failed(
                job.id,
                "jd_requirement_v2_validation_failed",
                self._safe_failure_details("requirement_v2_validation", str(exc)),
            )
            raise _ExtractionStopped from None

    async def _run_chunk_extraction(
        self, job: ExtractionJob, document: FixtureDocument
    ) -> tuple[CVExtractionOutput | JDExtractionOutput, list[InferenceAuditMetadata], int]:
        chunks = split_document(document.content)
        if not chunks:
            raise ValueError("document is empty")
        await self._repository.update_progress(
            job.id,
            ExtractionStage.EXTRACTING,
            completed_units=0,
            total_units=len(chunks),
        )
        definition = self._definition_for(job.document_kind)
        parsed_outputs: list[CVChunkExtractionOutput | JDChunkExtractionOutput] = []
        audits: list[InferenceAuditMetadata] = []
        provider_input_text_by_ordinal: dict[int, str] = {}
        for completed_units, chunk in enumerate(chunks, start=1):
            request = self._request(job.correlation_id, definition.prompt_template_id, chunk.text)
            provider_input_text_by_ordinal[chunk.ordinal] = str(request.payload["document"])
            try:
                result = await self._model_gateway.infer_structured(request, definition.output_schema)
            except ProviderTimeoutError:
                await self._repository.mark_failed(job.id, f"chunk_{chunk.ordinal}:provider_timeout")
                raise _ExtractionStopped from None
            except ProviderResponseError as exc:
                logging.getLogger(__name__).warning(
                    "extraction_provider_response_failure job_id=%s document_kind=%s chunk=%s reason=%s",
                    job.id,
                    job.document_kind.value,
                    chunk.ordinal,
                    str(exc),
                )
                await self._repository.mark_failed(
                    job.id,
                    f"chunk_{chunk.ordinal}:provider_response_invalid",
                    self._safe_failure_details("provider_call", str(exc)),
                )
                raise _ExtractionStopped from None
            except StructuredOutputFailedError as exc:
                await self._repository.mark_failed(
                    job.id,
                    f"chunk_{chunk.ordinal}:invalid_structured_output:{exc.category}",
                    self._diagnostic_details(exc.diagnostic),
                )
                raise _ExtractionStopped from None
            parsed_outputs.append(result.parsed)
            audits.append(result.audit)
            await self._repository.update_progress(
                job.id,
                ExtractionStage.EXTRACTING,
                completed_units=completed_units,
                total_units=len(chunks),
            )
        await self._repository.update_progress(job.id, ExtractionStage.VALIDATING)
        try:
            locator_forensics: list[dict[str, object]] | None = (
                [] if self._locator_forensics_enabled else None
            )
            output = merge_chunk_outputs(
                document,
                chunks,
                parsed_outputs,
                forensics_records=locator_forensics,
                provider_input_text_by_ordinal=provider_input_text_by_ordinal,
            )
            if locator_forensics is not None:
                self._write_locator_forensics(job.id, locator_forensics)
        except ChunkLocatorError as exc:
            await self._repository.mark_failed(job.id, f"chunk_{exc.chunk_ordinal}:locator_resolution_failed")
            raise _ExtractionStopped from None
        except ValueError:
            await self._repository.mark_failed(job.id, f"chunk_{chunks[-1].ordinal}:extraction_failed")
            raise _ExtractionStopped from None
        return output, audits, len(chunks)

    def _write_locator_forensics(
        self, job_id: str, records: list[dict[str, object]]
    ) -> None:
        if self._locator_forensics_dir is None:
            return
        self._locator_forensics_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "locator_forensics@1",
            "job_id": job_id,
            "records": [dict(record, job_id=job_id) for record in records],
        }
        (self._locator_forensics_dir / f"{job_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _diagnostic_details(diagnostic: object | None) -> dict[str, object] | None:
        if diagnostic is None:
            return None
        model_dump = getattr(diagnostic, "model_dump", None)
        if not callable(model_dump):
            return None
        value = model_dump(mode="json")
        return value if isinstance(value, dict) else None

    async def _run_graph_extraction(self, job: object, document: object) -> None:
        # Runtime types are narrowed by the caller; keeping this method private
        # avoids widening the public DocumentSource protocol.
        from app.extraction.schemas import ExtractionJob

        assert isinstance(job, ExtractionJob)
        from app.extraction.fixtures import FixtureDocument

        assert isinstance(document, FixtureDocument)
        audits: list[InferenceAuditMetadata] = []
        try:
            full = await self._model_gateway.infer_structured(
                self._graph_request(
                    job.correlation_id, CV_ENTITY_RELATION_SCHEMA_ID, document.content
                ),
                EntityRelationOutput,
            )
            audits.append(full.audit)
            sections = detect_document_structure(document.content, document_type="cv").sections
            chunks = split_sections(document.content, sections) if sections else []
            await self._repository.update_progress(
                job.id,
                ExtractionStage.EXTRACTING,
                completed_units=1,
                total_units=len(chunks) + 1,
            )
            section_claims = []
            for completed_units, chunk in enumerate(chunks, start=2):
                result = await self._model_gateway.infer_structured(
                    self._graph_request(
                        job.correlation_id,
                        CV_SECTION_EVIDENCE_SCHEMA_ID,
                        chunk.text,
                        section_type=chunk.section_type.value,
                    ),
                    SectionEvidenceOutput,
                )
                audits.append(result.audit)
                section_claims.append(
                    section_evidence_to_graph_input(
                        result.parsed, document, chunk.section_type.value
                    )
                )
                await self._repository.update_progress(
                    job.id,
                    ExtractionStage.EXTRACTING,
                    completed_units=completed_units,
                    total_units=len(chunks) + 1,
                )
            graph_input = relation_output_to_graph_input(full.parsed, document)
            await self._repository.update_progress(job.id, ExtractionStage.VALIDATING)
            candidate_profile = merge_relation_evidence(graph_input, section_claims)
            await self._repository.update_progress(job.id, ExtractionStage.PERSISTING)
            profile = ExtractionProfile(
                id=str(uuid4()),
                job_id=job.id,
                document_id=job.document_id,
                document_kind=job.document_kind,
                owner_actor_id=job.owner_actor_id,
                version=1,
                review_state=ReviewState.PENDING_REVIEW,
                output=CVExtractionOutput(skills=[], experience=[], education=[]),
                candidate_profile=candidate_profile,
                audit=self._aggregate_audit(audits, len(audits)),
            )
            await self._repository.mark_succeeded(job.id, profile)
            if self._candidate_service is not None:
                await self._candidate_service.associate_extraction_profile(profile.id)
        except ProviderTimeoutError:
            await self._repository.mark_failed(job.id, "relation:provider_timeout")
        except ProviderResponseError as exc:
            logging.getLogger(__name__).warning(
                "extraction_provider_response_failure job_id=%s document_kind=%s stage=relation reason=%s",
                job.id,
                job.document_kind.value,
                str(exc),
            )
            await self._repository.mark_failed(
                job.id,
                "relation:provider_response_invalid",
                self._safe_failure_details("provider_call", str(exc)),
            )
        except StructuredOutputFailedError as exc:
            await self._repository.mark_failed(
                job.id,
                f"relation:invalid_structured_output:{exc.category}",
                self._diagnostic_details(exc.diagnostic),
            )
        except ValueError:
            await self._repository.mark_failed(job.id, "relation:locator_resolution_failed")

    def _graph_request(
        self,
        correlation_id: str,
        schema_id: str,
        content: str,
        section_type: str | None = None,
    ) -> InferenceRequest:
        payload: dict[str, object] = {"document": content}
        if section_type is not None:
            payload = {"section_type": section_type, "section_text": content}
        return InferenceRequest(
            purpose=InferencePurpose.CV_EXTRACTION,
            data_classification=DataClassification.RESTRICTED,
            prompt_template_id=schema_id,
            prompt_template_version=RELATION_EXTRACTION_SCHEMA_VERSION,
            payload=payload,
            output_contract=OutputContract(
                schema_id=schema_id,
                schema_version=RELATION_EXTRACTION_SCHEMA_VERSION,
                strict=True,
            ),
            output_token_budget=self._output_token_budget,
            correlation_id=correlation_id,
        )

    def _definition_for(self, kind: DocumentKind) -> _ChunkDefinition:
        if kind is DocumentKind.CV:
            return _ChunkDefinition(
                purpose=InferencePurpose.CV_EXTRACTION,
                prompt_template_id=CV_CHUNK_SCHEMA_ID,
                output_schema=CVChunkExtractionOutput,
            )
        return _ChunkDefinition(
            purpose=InferencePurpose.JD_EXTRACTION,
            prompt_template_id=JD_CHUNK_SCHEMA_ID,
            output_schema=JDChunkExtractionOutput,
        )

    @staticmethod
    def _full_definition_for(
        kind: DocumentKind,
    ) -> tuple[
        str,
        type[CVFullExtractionOutput]
        | type[CVFullExtractionOutputV2]
        | type[JDFullExtractionOutput],
    ]:
        if kind is DocumentKind.CV:
            return CV_FULL_SCHEMA_ID, CVFullExtractionOutputV2
        return JD_FULL_SCHEMA_ID, JDFullExtractionOutput

    def _full_request(
        self, correlation_id: str, schema_id: str, document: FixtureDocument
    ) -> InferenceRequest:
        purpose = (
            InferencePurpose.CV_EXTRACTION
            if schema_id == CV_FULL_SCHEMA_ID
            else InferencePurpose.JD_EXTRACTION
        )
        version = (
            self._full_prompt_version
            if schema_id == CV_FULL_SCHEMA_ID
            else JD_REQUIREMENT_SCHEMA_VERSION
            if schema_id
            in (JD_REQUIREMENT_SCHEMA_ID, JD_REQUIREMENT_TEXT_SCHEMA_ID, JD_REQUIREMENT_PDF_SCHEMA_ID)
            else FULL_EXTRACTION_SCHEMA_VERSION
        )
        # Honour the configured extraction ceiling. Schema-specific floors used
        # to inflate CV requests to 65,536 tokens and overload Gemini.
        output_token_budget = self._output_token_budget
        native_pdf = (
            (
                document.kind is DocumentKind.CV
                or schema_id
                in (JD_REQUIREMENT_SCHEMA_ID, JD_REQUIREMENT_TEXT_SCHEMA_ID, JD_REQUIREMENT_PDF_SCHEMA_ID)
            )
            and document.content_type == "application/pdf"
            and document.raw_bytes is not None
        )
        payload = (
            {
                "input_mode": ExtractionInputMode.NATIVE_PDF.value,
                "locator_mode": "native_pdf_page",
                "document_id": document.document_id,
            }
            if native_pdf
            else {
                "input_mode": ExtractionInputMode.WHOLE_PARSED_TEXT.value,
                "locator_mode": "parsed_text_offsets",
                "document_id": document.document_id,
                "document": document.content,
            }
        )
        return InferenceRequest(
            purpose=purpose,
            data_classification=DataClassification.RESTRICTED,
            prompt_template_id=schema_id,
            prompt_template_version=version,
            payload=payload,
            document=(
                DocumentInput(
                    media_type=document.content_type,
                    content=document.raw_bytes,
                    filename=f"{document.document_id}.pdf",
                )
                if native_pdf and document.content_type is not None and document.raw_bytes is not None
                else None
            ),
            output_contract=OutputContract(
                schema_id=schema_id,
                schema_version=version,
                strict=True,
            ),
            output_token_budget=output_token_budget,
            correlation_id=correlation_id,
        )

    def _request(
        self, correlation_id: str, schema_id: str, document_content: str
    ) -> InferenceRequest:
        purpose = (
            InferencePurpose.CV_EXTRACTION
            if schema_id == CV_CHUNK_SCHEMA_ID
            else InferencePurpose.JD_EXTRACTION
        )
        return InferenceRequest(
            purpose=purpose,
            data_classification=DataClassification.RESTRICTED,
            prompt_template_id=schema_id,
            prompt_template_version=CHUNK_EXTRACTION_SCHEMA_VERSION,
            payload={"document": document_content},
            output_contract=OutputContract(
                schema_id=schema_id,
                schema_version=CHUNK_EXTRACTION_SCHEMA_VERSION,
                strict=False,
            ),
            output_token_budget=self._output_token_budget,
            correlation_id=correlation_id,
        )

    def _input_mode(
        self,
        document: FixtureDocument,
        mode: ExtractionMode,
        *,
        jd_requirement_v2: bool = False,
    ) -> ExtractionInputMode:
        if (
            mode is ExtractionMode.FULL_DOCUMENT
            and (document.kind is DocumentKind.CV or jd_requirement_v2)
            and document.content_type == "application/pdf"
            and document.raw_bytes is not None
        ):
            return ExtractionInputMode.NATIVE_PDF
        return (
            ExtractionInputMode.WHOLE_PARSED_TEXT
            if mode is ExtractionMode.FULL_DOCUMENT
            else ExtractionInputMode.CHUNKED_TEXT
        )

    @staticmethod
    def _aggregate_audit(
        chunk_audits: list[InferenceAuditMetadata],
        chunk_count: int,
        mode: ExtractionMode | None = None,
    ) -> dict[str, object]:
        first = chunk_audits[0].model_dump(mode="json")
        first["chunk_count"] = chunk_count
        if mode is not None:
            first["strategy"] = mode.value
        first["attempt_count"] = sum(audit.attempt_count for audit in chunk_audits)
        first["latency_ms"] = sum(audit.latency_ms for audit in chunk_audits)
        first["usage"] = {
            "input_tokens": ExtractionWorker._sum_optional(
                audit.usage.input_tokens for audit in chunk_audits
            ),
            "output_tokens": ExtractionWorker._sum_optional(
                audit.usage.output_tokens for audit in chunk_audits
            ),
        }
        return first

    @staticmethod
    def _sum_optional(values: Iterable[int | None]) -> int | None:
        items = [value for value in values if isinstance(value, int)]
        return sum(items) if items else None
