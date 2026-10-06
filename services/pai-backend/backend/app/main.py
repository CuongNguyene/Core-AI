from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import SecretStr
from starlette.types import ExceptionHandler

from app.assessment.api import router as assessment_router
from app.assessment.repository import SqlAlchemyAssessmentRepository
from app.authorization.api import router as delegation_router
from app.authorization.fixtures import ORG_PAI_ID
from app.authorization.policy import CompetencyAuthorizationPolicy
from app.authorization.repository import SqlAlchemyDelegationRepository, SqlAlchemySubjectRepository
from app.candidate.api import router as candidate_router
from app.candidate.repository import SqlAlchemyCandidateRepository
from app.candidate.service import CandidateService
from app.candidate_semantics.prompts import register_candidate_semantics
from app.candidate_source.api import router as candidate_source_router
from app.candidate_source.repository import SqlAlchemyCandidateSourceRepository
from app.capability_analysis.api import router as capability_analysis_router
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.capability_analysis.domain_packs.registry import DomainPackRegistry
from app.capability_analysis.repository import SqlAlchemyCapabilityGapPortfolioRepository
from app.capability_analysis.service import CapabilityGapAnalysisService
from app.competency.api import router as competency_router
from app.competency.repository import SqlAlchemyCompetencyRepository
from app.competency.service import CompetencyDecisionService
from app.content_generation.repository import SqlAlchemyContentGenerationRepository
from app.content_generation.service import ContentGenerationService
from app.course_authoring.brief_revision_repository import (
    SqlAlchemyAuthoringBriefRevisionRepository,
)
from app.course_authoring.brief_revision_service import AuthoringBriefRevisionService
from app.course_authoring.conversation_service import (
    AuthoringConversationService,
    register_authoring_conversation_contracts,
)
from app.course_authoring.repository import SqlAlchemyCourseAuthoringRepository
from app.course_authoring.revision_service import CourseDraftRevisionService
from app.course_authoring.service import CourseAuthoringService
from app.course_generation.context import CourseGenerationContextBuilder
from app.course_generation.contracts import register_course_generation_contracts
from app.course_generation.dispatch import SqlAlchemyCourseGenerationDispatchRepository
from app.course_generation.dispatcher import ArqCourseGenerationDispatcher
from app.course_generation.generator import ModelGatewayLessonContentGenerator
from app.course_generation.hierarchical_service import HierarchicalCourseGenerationService
from app.course_recommendation.execution_service import CourseRecommendationExecutionService
from app.course_recommendation.repository import SqlAlchemyCourseRecommendationExecutionRepository
from app.credential.api import router as credential_router
from app.credential.evaluators import (
    CompetencyCredentialEvaluator,
    CompletionCredentialEvaluator,
    LearningAchievementCredentialEvaluator,
)
from app.credential.fixtures import competency_policy_fixture
from app.credential.policy import CredentialAuthorizationPolicy
from app.credential.providers import (
    UnavailableCompletionAssertionProvider,
    UnavailableLearningOutcomeAssertionProvider,
)
from app.credential.repository import SqlAlchemyCredentialRepository
from app.credential.schemas import CredentialType
from app.credential.service import CredentialPolicyRegistry, CredentialService
from app.curriculum_planning.planner import ModelGatewayCurriculumPlanner
from app.curriculum_planning.revision_service import CurriculumRevisionService
from app.curriculum_planning.service import CurriculumPlanningService
from app.documents.api import router as document_router
from app.documents.repository import SqlAlchemyDocumentRepository
from app.documents.safety import ClamAvDocumentSafetyInspector, DevelopmentDocumentSafetyInspector
from app.documents.source import CompositeDocumentSource
from app.documents.storage import InMemoryDocumentBlobStore, MinioDocumentBlobStore
from app.extraction.api import router as extraction_router
from app.extraction.capability_discovery import register_capability_discovery
from app.extraction.ext_03a8_selection_semantics import register_selection_semantics
from app.extraction.fixtures import FixtureDocumentSource
from app.extraction.prompts import register_extraction_contracts
from app.extraction.repository import SqlAlchemyExtractionRepository
from app.extraction.two_stage_capability_schema import register_two_stage_experiment
from app.instructional_design.contracts import register_instructional_design_experiment_contracts
from app.integration.capability_gap_api import router as capability_gap_integration_router
from app.integration.content_generation_api import router as content_generation_router
from app.integration.course_authoring_api import router as course_authoring_router
from app.integration.course_recommendation_api import router as course_recommendation_router
from app.integration.fixtures import development_course_blueprint
from app.integration.identity_bridge import (
    CandidateIdentityBridgeService,
    HttpLmsIdentityResolver,
    SqlAlchemyCandidateIdentityLinkRepository,
)
from app.integration.identity_bridge_api import router as identity_bridge_router
from app.integration.learning_authoring_api import router as learning_authoring_router
from app.integration.learning_path_api import router as learning_path_integration_router
from app.integration.nonce_store import SqlAlchemyActorContextNonceStore
from app.integration.repository import SqlAlchemyIntegrationRepository
from app.integration.router import router as integration_router
from app.integration.service import IntegrationService
from app.learning.api import router as learning_router
from app.learning.repository import SqlAlchemyLearningPathRepository
from app.learning.service import LearningPathService
from app.learning_authoring.service import LearningAuthoringService
from app.matching.api import router as matching_router
from app.matching.repository import (
    SqlAlchemyPreliminaryMatchRepository,
    SqlAlchemyRoleProfileRepository,
)
from app.matching.service import PreliminaryMatchService
from app.model_gateway.ctpai_gateway import CTPAIGatewayProvider
from app.model_gateway.gemini import GeminiProvider
from app.model_gateway.local_vllm import LocalVLLMProvider
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.providers import ModelProvider, ProviderRegistry
from app.model_gateway.routing import RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.model_gateway.service import ModelGatewayService
from app.privacy.service import LocalPIIInspector, PrivacyService
from app.role_profile_authoring.api import router as role_profile_authoring_router
from app.role_profile_authoring.repository import SqlAlchemyRoleProfileDraftRepository
from app.role_profile_authoring.service import RoleProfileAuthoringService
from app.role_registry.api import router as role_registry_router
from app.role_registry.repository import SqlAlchemyRoleRegistryRepository
from app.role_registry.service import RoleRegistryService
from app.semantic_policy.api import router as semantic_policy_router
from app.semantic_policy.repository import SqlAlchemySemanticPolicyRepository
from app.semantic_policy.service import SemanticPolicyResolver
from app.shared.config import Settings
from app.shared.database import Database
from app.shared.errors import (
    APIError,
    CorrelationIdMiddleware,
    api_error_handler,
    http_exception_handler,
    request_validation_error_handler,
    unhandled_exception_handler,
)
from app.shared.health import router as health_router
from app.shared.logging import configure_logging


def _build_model_provider(
    *,
    provider_id: str,
    endpoint: str,
    api_key: SecretStr,
    model: str,
    timeout_seconds: float,
    max_retries: int,
    max_tokens: int,
    thinking_level: str = "high",
    retry_delay_seconds: float = 0.05,
) -> ModelProvider:
    """Select the protocol adapter from the configured model endpoint shape."""
    if "generativelanguage.googleapis.com" in endpoint or provider_id == "gemini":
        return GeminiProvider(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_tokens=max_tokens,
            thinking_level=thinking_level,
            retry_delay_seconds=retry_delay_seconds,
            provider_id="gemini",
        )
    if endpoint.rstrip("/").endswith("/v1"):
        return LocalVLLMProvider(
            provider_id=provider_id,
            base_url=endpoint,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    return CTPAIGatewayProvider(
        endpoint=endpoint,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        max_tokens=max_tokens,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        dispatcher = getattr(app.state, "course_generation_dispatcher", None)
        if dispatcher is not None:
            await dispatcher.close()
        database = cast(Database, app.state.database)
        await database.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings()
    configure_logging(active_settings.log_level)
    app = FastAPI(title=active_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = active_settings
    app.state.database = Database(active_settings.database_url)
    app.state.actor_context_nonce_store = SqlAlchemyActorContextNonceStore(
        app.state.database.session_factory
    )
    app.state.fixture_document_source = FixtureDocumentSource.default()
    app.state.document_repository = SqlAlchemyDocumentRepository(app.state.database.session_factory)
    try:
        app.state.document_blob_store = MinioDocumentBlobStore(
            endpoint=active_settings.object_storage_endpoint,
            access_key=active_settings.object_storage_access_key,
            secret_key=active_settings.object_storage_secret_key.get_secret_value(),
            bucket=active_settings.object_storage_bucket,
            secure=active_settings.object_storage_secure,
        )
    except ModuleNotFoundError:
        if active_settings.app_env != "development":
            raise
        app.state.document_blob_store = InMemoryDocumentBlobStore()
    if active_settings.document_scanner == "clamav":
        app.state.document_safety_inspector = ClamAvDocumentSafetyInspector(
            max_bytes=active_settings.document_max_bytes,
            host=active_settings.clamav_host,
            port=active_settings.clamav_port,
            timeout_seconds=active_settings.clamav_timeout_seconds,
        )
    else:
        app.state.document_safety_inspector = DevelopmentDocumentSafetyInspector(
            active_settings.document_max_bytes
        )
    app.state.document_source = CompositeDocumentSource(
        app.state.document_repository,
        app.state.document_blob_store,
        app.state.fixture_document_source,
    )
    prompt_templates = PromptTemplateRegistry()
    output_schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompt_templates, output_schemas)
    register_two_stage_experiment(prompt_templates, output_schemas)
    register_selection_semantics(prompt_templates, output_schemas)
    register_capability_discovery(prompt_templates, output_schemas)
    register_instructional_design_experiment_contracts(prompt_templates, output_schemas)
    register_course_generation_contracts(prompt_templates, output_schemas)
    register_authoring_conversation_contracts(prompt_templates, output_schemas)
    register_candidate_semantics(prompt_templates, output_schemas)
    providers = ProviderRegistry()
    configured_provider = _build_model_provider(
        provider_id=active_settings.model_provider,
        endpoint=active_settings.vllm_base_url,
        api_key=active_settings.vllm_api_key,
        model=active_settings.vllm_model,
        timeout_seconds=active_settings.vllm_timeout_seconds,
        max_retries=active_settings.vllm_max_retries,
        max_tokens=active_settings.vllm_max_tokens,
        thinking_level=active_settings.gemini_thinking_level,
        retry_delay_seconds=active_settings.model_retry_base_delay_seconds,
    )
    providers.register(configured_provider)
    app.state.model_provider_id = configured_provider.provider_id
    app.state.model_gateway = ModelGatewayService(
        prompt_templates=prompt_templates,
        output_schemas=output_schemas,
        privacy_gateway=PrivacyService(
            LocalPIIInspector(),
            policy_version=active_settings.privacy_policy_version,
            external_public_data_enabled=active_settings.external_ai_enabled,
        ),
        routing_policy=RoutingPolicy(
            external_ai_enabled=active_settings.external_ai_enabled,
            external_restricted_data_approved=active_settings.external_restricted_data_approved,
            external_provider_id=(
                configured_provider.provider_id
                if configured_provider.is_external
                else (active_settings.external_ai_provider or "vilao-external")
            ),
            configured_provider_id=configured_provider.provider_id,
        ),
        providers=providers,
        model=active_settings.vllm_model,
        max_structured_repair_retries=active_settings.structured_output_repair_retries,
    )
    app.state.subject_repository = SqlAlchemySubjectRepository(app.state.database.session_factory)
    app.state.delegation_repository = SqlAlchemyDelegationRepository(
        app.state.database.session_factory
    )
    app.state.assessment_repository = SqlAlchemyAssessmentRepository(
        app.state.database.session_factory
    )
    app.state.competency_repository = SqlAlchemyCompetencyRepository(
        app.state.database.session_factory
    )
    app.state.competency_policy = CompetencyAuthorizationPolicy(
        app.state.subject_repository,
        app.state.delegation_repository,
        app.state.assessment_repository,
    )
    app.state.competency_decision_service = CompetencyDecisionService(
        app.state.competency_repository,
        app.state.assessment_repository,
        app.state.competency_policy,
    )
    app.state.extraction_repository = SqlAlchemyExtractionRepository(
        app.state.database.session_factory,
        app.state.document_source,
    )
    app.state.candidate_repository = SqlAlchemyCandidateRepository(
        app.state.database.session_factory
    )
    app.state.candidate_source_repository = SqlAlchemyCandidateSourceRepository(
        app.state.database.session_factory
    )
    app.state.candidate_service = CandidateService(
        app.state.candidate_repository,
        app.state.document_repository,
        app.state.extraction_repository,
    )
    app.state.candidate_identity_bridge_service = CandidateIdentityBridgeService(
        app.state.candidate_repository,
        HttpLmsIdentityResolver(active_settings),
        SqlAlchemyCandidateIdentityLinkRepository(app.state.database.session_factory),
    )
    app.state.role_profile_repository = SqlAlchemyRoleProfileRepository(
        app.state.database.session_factory
    )
    app.state.semantic_policy_repository = SqlAlchemySemanticPolicyRepository(
        app.state.database.session_factory
    )
    app.state.domain_pack_registry = DomainPackRegistry((IT_AI_PACK,))
    app.state.semantic_policy_resolver = SemanticPolicyResolver(
        app.state.semantic_policy_repository,
        (IT_AI_PACK,),
    )
    app.state.role_registry_repository = SqlAlchemyRoleRegistryRepository(
        app.state.database.session_factory
    )
    app.state.role_registry_service = RoleRegistryService(
        app.state.role_registry_repository,
        app.state.document_repository,
        app.state.extraction_repository,
    )
    app.state.role_profile_draft_repository = SqlAlchemyRoleProfileDraftRepository(
        app.state.database.session_factory,
        app.state.extraction_repository,
        app.state.role_profile_repository,
        semantic_policy_resolver=app.state.semantic_policy_resolver,
        role_registry=app.state.role_registry_repository,
        documents=app.state.document_repository,
    )
    app.state.role_profile_authoring_service = RoleProfileAuthoringService(
        app.state.role_profile_draft_repository
    )
    app.state.preliminary_match_repository = SqlAlchemyPreliminaryMatchRepository(
        app.state.database.session_factory
    )
    app.state.preliminary_match_service = PreliminaryMatchService(
        app.state.extraction_repository,
        app.state.role_profile_repository,
        app.state.preliminary_match_repository,
    )
    app.state.capability_gap_portfolio_repository = SqlAlchemyCapabilityGapPortfolioRepository(
        app.state.database.session_factory
    )
    app.state.capability_gap_analysis_service = CapabilityGapAnalysisService(
        app.state.extraction_repository,
        app.state.role_profile_repository,
        app.state.capability_gap_portfolio_repository,
        candidates=app.state.candidate_repository,
        role_registry=app.state.role_registry_repository,
        domain_pack_registry=app.state.domain_pack_registry,
        semantic_policy_resolver=app.state.semantic_policy_resolver,
    )
    app.state.learning_path_repository = SqlAlchemyLearningPathRepository(
        app.state.database.session_factory
    )
    app.state.learning_path_service = LearningPathService(
        competency_records=app.state.competency_repository,
        role_profiles=app.state.role_profile_repository,
        matches=app.state.preliminary_match_repository,
        paths=app.state.learning_path_repository,
        capability_analyses=app.state.capability_gap_portfolio_repository,
        profiles=app.state.extraction_repository,
    )
    app.state.learning_authoring_service = LearningAuthoringService(
        capability_analyses=app.state.capability_gap_analysis_service,
        role_profiles=app.state.role_profile_repository,
    )
    app.state.course_authoring_repository = SqlAlchemyCourseAuthoringRepository(
        app.state.database.session_factory
    )
    app.state.course_recommendation_execution_repository = (
        SqlAlchemyCourseRecommendationExecutionRepository(app.state.database.session_factory)
    )
    app.state.course_recommendation_execution_service = CourseRecommendationExecutionService(
        repository=app.state.course_recommendation_execution_repository
    )
    app.state.authoring_brief_revision_repository = SqlAlchemyAuthoringBriefRevisionRepository(
        app.state.database.session_factory
    )
    app.state.authoring_brief_revision_service = AuthoringBriefRevisionService(
        app.state.authoring_brief_revision_repository
    )
    app.state.course_authoring_service = CourseAuthoringService(
        repository=app.state.course_authoring_repository,
        references=app.state.learning_authoring_service,
        brief_revisions=app.state.authoring_brief_revision_service,
        conversation=AuthoringConversationService(
            gateway=app.state.model_gateway,
            requested_provider=app.state.model_provider_id,
            output_token_budget=active_settings.course_generation_max_tokens,
        ),
    )
    app.state.content_generation_service = ContentGenerationService()
    app.state.content_generation_repository = SqlAlchemyContentGenerationRepository(
        app.state.database.session_factory
    )
    app.state.course_generation_dispatch_repository = SqlAlchemyCourseGenerationDispatchRepository(
        app.state.database.session_factory
    )
    app.state.course_generation_dispatcher = ArqCourseGenerationDispatcher(
        active_settings.redis_queue_url
    )
    context_builder = CourseGenerationContextBuilder(app.state.learning_authoring_service)
    curriculum_planner = ModelGatewayCurriculumPlanner(
        gateway=app.state.model_gateway,
        requested_provider=app.state.model_provider_id,
        correlation_id="curriculum-planning",
        output_token_budget=active_settings.course_generation_max_tokens,
        temperature=0.2,
    )
    app.state.curriculum_planning_service = CurriculumPlanningService(
        authoring=app.state.course_authoring_service,
        context_builder=context_builder,
        planner=curriculum_planner,
        repository=app.state.content_generation_repository,
        brief_revisions=app.state.authoring_brief_revision_repository,
    )
    app.state.curriculum_revision_service = CurriculumRevisionService(
        repository=app.state.content_generation_repository,
        brief_revisions=app.state.authoring_brief_revision_repository,
    )
    app.state.course_generation_service = HierarchicalCourseGenerationService(
        authoring=app.state.course_authoring_service,
        context_builder=context_builder,
        generator=ModelGatewayLessonContentGenerator(
            gateway=app.state.model_gateway,
            requested_provider=app.state.model_provider_id,
            correlation_id="course-generation",
            output_token_budget=active_settings.course_generation_max_tokens,
            temperature=0.2,
        ),
        repository=app.state.content_generation_repository,
        provider=app.state.model_provider_id,
        model=active_settings.vllm_model,
        max_concurrency=2,
        stale_run_after_seconds=active_settings.generation_timeout_seconds + 60,
        generation_timeout_seconds=active_settings.generation_timeout_seconds,
        enforce_content_quality=active_settings.course_generation_quality_validation_enabled,
        curriculum_planner=curriculum_planner,
        dispatcher=app.state.course_generation_dispatcher,
        dispatches=app.state.course_generation_dispatch_repository,
    )
    app.state.course_draft_revision_service = CourseDraftRevisionService(
        repository=app.state.content_generation_repository,
        authoring=app.state.course_authoring_service,
    )
    app.state.integration_repository = SqlAlchemyIntegrationRepository(
        app.state.database.session_factory
    )
    app.state.integration_service = IntegrationService(
        app.state.integration_repository,
        blueprint_source=app.state.learning_path_repository,
    )
    if active_settings.app_env == "development":
        app.state.integration_service.register_blueprint(development_course_blueprint())
    app.state.credential_repository = SqlAlchemyCredentialRepository(
        app.state.database.session_factory
    )
    credential_policy = competency_policy_fixture(ORG_PAI_ID)
    app.state.credential_service = CredentialService(
        repository=app.state.credential_repository,
        registry=CredentialPolicyRegistry([credential_policy]),
        evaluators={
            CredentialType.COMPETENCY: CompetencyCredentialEvaluator(
                app.state.competency_repository
            ),
            CredentialType.COMPLETION: CompletionCredentialEvaluator(
                UnavailableCompletionAssertionProvider()
            ),
            CredentialType.LEARNING_ACHIEVEMENT: LearningAchievementCredentialEvaluator(
                UnavailableLearningOutcomeAssertionProvider()
            ),
        },
        authorization=CredentialAuthorizationPolicy(app.state.delegation_repository),
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(APIError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, request_validation_error_handler)
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health_router)
    app.include_router(document_router)
    app.include_router(delegation_router)
    app.include_router(assessment_router)
    app.include_router(competency_router)
    app.include_router(extraction_router)
    app.include_router(candidate_router)
    app.include_router(candidate_source_router)
    app.include_router(matching_router)
    app.include_router(role_profile_authoring_router)
    app.include_router(role_registry_router)
    app.include_router(semantic_policy_router)
    app.include_router(capability_analysis_router)
    app.include_router(learning_router)
    app.include_router(credential_router)
    app.include_router(integration_router)
    app.include_router(capability_gap_integration_router)
    app.include_router(learning_path_integration_router)
    app.include_router(identity_bridge_router)
    app.include_router(learning_authoring_router)
    app.include_router(content_generation_router)
    app.include_router(course_authoring_router)
    app.include_router(course_recommendation_router)
    return app


app = create_app()
