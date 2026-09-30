import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from app.authorization.schemas import ActorContext, Role
from app.candidate.repository import CandidateRepository
from app.candidate.schemas import Candidate
from app.capability_analysis.domain_packs.contracts import DomainKnowledgePack, DomainPackReference
from app.capability_analysis.domain_packs.registry import (
    DomainPackRegistry,
    DomainPackUnavailableError,
)
from app.capability_analysis.errors import (
    CandidateProfileNotAnalyzableError,
    CandidateProfileNotReadyProductError,
    CapabilityAnalysisAccessDeniedError,
    CapabilityAnalysisEligibilityError,
    CapabilityAnalysisIdempotencyConflictError,
    CapabilityAnalysisProductError,
    CurrentTargetNotUsableError,
    ExtractionProfileNotAcceptedError,
    FutureTargetNotUsableError,
    HumanAssistedReanalysisValidationError,
    RoleProfileNotActiveProductError,
    SemanticPolicyNotConfiguredError,
    SemanticPolicyUnavailableError,
    SupersededCapabilityProfileError,
)
from app.capability_analysis.evidence_index import build_evidence_index
from app.capability_analysis.repository import CapabilityGapPortfolioRepository
from app.capability_analysis.review_projection import build_capability_gap_review_projection
from app.capability_analysis.rules import (
    build_gap_overlap_links,
    build_preview_readiness,
    build_provisional_capability_profile,
    build_verification_queue,
    evaluate_target,
)
from app.capability_analysis.schemas import (
    CapabilityGapProfile,
    CapabilityGapProfileTrack,
    CombinedGapPortfolio,
    CreateCapabilityGapAnalysisRequest,
    HumanAssistedEvidenceSelection,
    HumanAssistedReanalysisContext,
    HumanAssistedReanalysisProvenance,
    HumanAssistedReanalysisResult,
    TargetSemanticPolicySnapshot,
    TargetType,
    TargetUsageMode,
)
from app.capability_analysis.semantic_core.adapters import adapt_evidence_index
from app.capability_analysis.semantic_core.contracts import EvidenceSemantics
from app.extraction.repository import ExtractionRepository
from app.extraction.schemas import DocumentKind, ExtractionProfile, ReviewState
from app.integration.capability_gap_schemas import (
    CandidateEvidenceOptionV1,
    CandidateEvidenceProjectionV1,
    CapabilityGapReviewProjectionV1,
    CapabilityReviewEvidenceV1,
)
from app.matching.repository import RoleProfileRepository
from app.matching.schemas import (
    RoleCompetencyProfile,
    RoleProfileStatus,
    SemanticPolicySelectionSource,
)
from app.role_registry.repository import RoleRegistryRepository
from app.role_registry.schemas import Role as RoleRecord
from app.semantic_policy.errors import SemanticPolicyError
from app.semantic_policy.service import SemanticPolicyResolver


@dataclass(frozen=True)
class CandidateRoleAnalysisResult:
    portfolio: CombinedGapPortfolio
    candidate: Candidate
    candidate_profile_id: str
    candidate_profile_version: int
    role: RoleRecord
    role_profile: RoleCompetencyProfile


class CapabilityGapAnalysisService:
    def __init__(
        self,
        extraction_profiles: ExtractionRepository,
        role_profiles: RoleProfileRepository,
        portfolios: CapabilityGapPortfolioRepository,
        *,
        candidates: CandidateRepository | None = None,
        role_registry: RoleRegistryRepository | None = None,
        domain_pack_registry: DomainPackRegistry,
        semantic_policy_resolver: SemanticPolicyResolver | None = None,
    ) -> None:
        self._extraction_profiles = extraction_profiles
        self._role_profiles = role_profiles
        self._portfolios = portfolios
        self._candidates = candidates
        self._role_registry = role_registry
        self._domain_pack_registry = domain_pack_registry
        self._semantic_policy_resolver = semantic_policy_resolver

    async def create(
        self,
        request: CreateCapabilityGapAnalysisRequest,
        actor: ActorContext,
        *,
        candidate_id: UUID | None = None,
        current_target_version: str | None = None,
        future_target_version: str | None = None,
        idempotency_key: str | None = None,
        human_assisted_context: HumanAssistedReanalysisContext | None = None,
        portfolio_owner_actor_id: UUID | None = None,
    ) -> CombinedGapPortfolio:
        try:
            cv_profile = (
                await self._accepted_cv_for_assisted_reanalysis(request.cv_profile_id)
                if human_assisted_context is not None
                else await self._accepted_owned_cv(request.cv_profile_id, actor)
            )
            current_target = await self._current_target(
                request.current_target_profile_id,
                current_target_version,
            )
            future_target = await self._future_target(
                request.future_target_profile_id,
                future_target_version,
            )
            current_semantic_policy, current_packs = await self._semantic_policy(
                current_target,
                TargetType.CURRENT_ROLE,
            )
            future_policy_and_packs = (
                await self._semantic_policy(future_target, TargetType.FUTURE_ROLE)
                if future_target is not None
                else None
            )
            try:
                capability_profile = build_provisional_capability_profile(cv_profile)
            except ValidationError as error:
                raise CandidateProfileNotAnalyzableError(
                    "Accepted CV profile has no analyzable capabilities."
                ) from error
            current = evaluate_target(
                capability_profile,
                current_target,
                TargetType.CURRENT_ROLE,
                self._current_usage_mode(current_target),
                domain_packs=current_packs,
                assisted_evidence_by_requirement=(
                    {
                        item.requirement_id: tuple(item.selected_evidence_refs)
                        for item in human_assisted_context.evidence_selections
                    }
                    if human_assisted_context is not None
                    else None
                ),
            )
            if current_target.status is RoleProfileStatus.PROVISIONAL:
                current = current.model_copy(
                    update={"warning_codes": ["current_target_profile_provisional"]}, deep=True
                )
            future = (
                evaluate_target(
                    capability_profile,
                    future_target,
                    TargetType.FUTURE_ROLE,
                    self._future_usage_mode(future_target),
                    domain_packs=future_policy_and_packs[1],
                )
                if future_target is not None and future_policy_and_packs is not None
                else None
            )
            profile = CapabilityGapProfile(
                id=request.correlation_id,
                cv_profile_id=cv_profile.id,
                cv_profile_version=cv_profile.version,
                current_target_version=current_target.version,
                future_target_version=future_target.version if future_target else None,
                owner_actor_id=portfolio_owner_actor_id or actor.actor_id,
                organization_id=actor.organization_id,
                correlation_id=request.correlation_id,
                candidate_id=candidate_id,
                idempotency_key=idempotency_key or request.correlation_id,
                current_role=CapabilityGapProfileTrack.from_target_gap_analysis(current),
                future_role=(
                    CapabilityGapProfileTrack.from_target_gap_analysis(future)
                    if future is not None
                    else None
                ),
                overlap_links=build_gap_overlap_links(current, future) if future else [],
                snapshot_schema_version=(
                    "capability-gap-preview-v1"
                    if current.usage_mode is TargetUsageMode.PREVIEW
                    else "capability-gap-v1"
                ),
                preview_readiness=(
                    build_preview_readiness(current)
                    if current.usage_mode is TargetUsageMode.PREVIEW
                    else None
                ),
                verification_queue=(
                    build_verification_queue(current)
                    if current.usage_mode is TargetUsageMode.PREVIEW
                    else []
                ),
                semantic_policies=(
                    (current_semantic_policy, future_policy_and_packs[0])
                    if future_policy_and_packs is not None
                    else (current_semantic_policy,)
                ),
            )
            persisted = await self._portfolios.create_profile(profile)
            return persisted.to_combined_gap_portfolio()
        except CapabilityAnalysisEligibilityError as error:
            await self._portfolios.record_rejected_input(
                portfolio_id=None,
                action=error.audit_action,
                metadata={
                    "cv_profile_id": request.cv_profile_id,
                    "current_target_profile_id": request.current_target_profile_id,
                    "future_target_profile_id": request.future_target_profile_id,
                    "correlation_id": request.correlation_id,
                },
            )
            raise

    async def create_human_assisted_reanalysis(
        self,
        *,
        source_analysis_id: str,
        evidence_selections: list[HumanAssistedEvidenceSelection],
        actor: ActorContext,
        idempotency_key: str,
    ) -> HumanAssistedReanalysisResult:
        """Create a new analysis using only selected evidence from its exact source."""
        source = await self.get(source_analysis_id, actor)
        if source.candidate_id is None:
            raise HumanAssistedReanalysisValidationError(
                "Human-assisted reanalysis requires a candidate-backed source analysis"
            )
        if idempotency_key == source_analysis_id:
            raise HumanAssistedReanalysisValidationError(
                "Human-assisted reanalysis must create a new analysis identity"
            )

        cv_profile = await self._extraction_profiles.get_profile(source.cv_profile_id)
        if (
            cv_profile is None
            or cv_profile.version != source.cv_profile_version
            or cv_profile.review_state is not ReviewState.ACCEPTED
            or cv_profile.candidate_profile is None
            or await self._extraction_profiles.is_superseded(cv_profile.id)
        ):
            raise HumanAssistedReanalysisValidationError(
                "Source analysis candidate profile version is no longer available"
            )

        current_target = await self._current_target(
            source.current_role.target_id, source.current_target_version
        )
        if current_target.version != source.current_target_version:
            raise HumanAssistedReanalysisValidationError(
                "Source analysis role profile version is no longer available"
            )

        requirements = {item.id: item for item in current_target.requirements}
        source_requirement_ids = {
            item.requirement_id for item in source.current_role.assessments
        }
        capability_profile = build_provisional_capability_profile(cv_profile)
        available_evidence_refs = {
            item.evidence_ref for item in capability_profile.semantic_evidence
        }
        normalized_selections: list[HumanAssistedEvidenceSelection] = []
        for selection in evidence_selections:
            requirement = requirements.get(selection.requirement_id)
            if requirement is None or selection.requirement_id not in source_requirement_ids:
                raise HumanAssistedReanalysisValidationError(
                    "Selected requirement is not part of the source analysis"
                )
            if requirement.criterion_dimension is None:
                raise HumanAssistedReanalysisValidationError(
                    "Context-only requirements cannot receive assisted scoring evidence"
                )
            missing_refs = set(selection.selected_evidence_refs) - available_evidence_refs
            if missing_refs:
                raise HumanAssistedReanalysisValidationError(
                    "Selected evidence is not canonical evidence for the source profile"
                )
            normalized_selections.append(selection)

        context = HumanAssistedReanalysisContext(
            source_analysis_id=source_analysis_id,
            evidence_selections=normalized_selections,
        )
        identity_payload = {
            "idempotency_key": idempotency_key,
            "source_analysis_id": source_analysis_id,
            "evidence_selections": [
                {
                    "requirement_id": selection.requirement_id,
                    "selected_evidence_refs": selection.selected_evidence_refs,
                }
                for selection in normalized_selections
            ],
        }
        identity_digest = hashlib.sha256(
            json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        # Keep the deterministic identity within the existing correlation-id contract.
        new_analysis_id = f"human-assisted-{identity_digest[:48]}"
        existing = await self._portfolios.get(new_analysis_id)
        if existing is not None:
            return HumanAssistedReanalysisResult(
                analysis=existing,
                provenance=HumanAssistedReanalysisProvenance(
                    source_analysis_id=source_analysis_id,
                    evidence_selections=normalized_selections,
                    reviewer_actor_id=actor.actor_id,
                ),
            )
        request = CreateCapabilityGapAnalysisRequest(
            cv_profile_id=source.cv_profile_id,
            current_target_profile_id=source.current_role.target_id,
            future_target_profile_id=(
                source.future_role.target_id if source.future_role is not None else None
            ),
            correlation_id=new_analysis_id,
        )
        analysis = await self.create(
            request,
            actor,
            candidate_id=source.candidate_id,
            current_target_version=source.current_target_version,
            future_target_version=source.future_target_version,
            idempotency_key=new_analysis_id,
            human_assisted_context=context,
            portfolio_owner_actor_id=source.owner_actor_id,
        )
        await self._portfolios.record_human_assisted_reanalysis(
            portfolio_id=analysis.id,
            source_analysis_id=source_analysis_id,
            evidence_selections=normalized_selections,
            reviewer_actor_id=actor.actor_id,
        )
        return HumanAssistedReanalysisResult(
            analysis=analysis,
            provenance=HumanAssistedReanalysisProvenance(
                source_analysis_id=source_analysis_id,
                evidence_selections=normalized_selections,
                reviewer_actor_id=actor.actor_id,
            ),
        )

    async def create_for_candidate(
        self,
        *,
        candidate_id: UUID,
        current_target_reference: str,
        future_target_reference: str | None,
        idempotency_key: str,
        actor: ActorContext,
    ) -> CombinedGapPortfolio:
        if self._candidates is None:
            raise CapabilityAnalysisAccessDeniedError("Candidate resolution is unavailable")
        candidate = await self._candidates.get(candidate_id)
        if candidate is None or candidate.organization_id != actor.organization_id:
            raise CapabilityAnalysisAccessDeniedError("Candidate is outside actor organization")
        if candidate.created_by_actor_id != actor.actor_id and Role.REVIEWER not in actor.roles:
            raise CapabilityAnalysisAccessDeniedError("Actor cannot analyze candidate")
        if candidate.current_profile_id is None:
            raise ExtractionProfileNotAcceptedError("Candidate has no current CV profile")
        cv_profile = await self._accepted_owned_cv(candidate.current_profile_id, actor)
        if candidate.current_profile_version not in {None, cv_profile.version}:
            raise SupersededCapabilityProfileError("Candidate current profile is stale")

        current_id, current_version = _parse_target_reference(current_target_reference)
        future_id, future_version = (
            _parse_target_reference(future_target_reference)
            if future_target_reference is not None
            else (None, None)
        )
        existing = await self._portfolios.get(idempotency_key)
        if existing is not None:
            if _same_analysis_request(
                existing,
                candidate_id=candidate_id,
                cv_profile_id=cv_profile.id,
                current_target_id=current_id,
                current_target_version=current_version,
                future_target_id=future_id,
                future_target_version=future_version,
            ):
                return existing
            raise CapabilityAnalysisIdempotencyConflictError(
                "Idempotency key was already used for another analysis request"
            )

        request = CreateCapabilityGapAnalysisRequest(
            cv_profile_id=cv_profile.id,
            current_target_profile_id=current_id,
            future_target_profile_id=future_id,
            correlation_id=idempotency_key,
        )
        try:
            return await self.create(
                request,
                actor,
                candidate_id=candidate_id,
                current_target_version=current_version,
                future_target_version=future_version,
                idempotency_key=idempotency_key,
            )
        except CapabilityAnalysisEligibilityError:
            raise
        except ValueError as error:
            existing = await self._portfolios.get(idempotency_key)
            if existing is not None and _same_analysis_request(
                existing,
                candidate_id=candidate_id,
                cv_profile_id=cv_profile.id,
                current_target_id=current_id,
                current_target_version=current_version,
                future_target_id=future_id,
                future_target_version=future_version,
            ):
                return existing
            raise CapabilityAnalysisIdempotencyConflictError(
                "Concurrent idempotency key collision"
            ) from error

    async def create_for_candidate_role(
        self,
        *,
        candidate_id: UUID,
        role_id: UUID,
        idempotency_key: str,
        actor: ActorContext,
    ) -> CandidateRoleAnalysisResult:
        """Resolve governed candidate/role snapshots before using the existing engine."""
        if self._role_registry is None:
            raise CapabilityAnalysisProductError("role_registry_unavailable")
        if self._candidates is None:
            raise CapabilityAnalysisProductError("candidate_registry_unavailable")
        candidate = await self._candidates.get(candidate_id)
        if candidate is None:
            raise CapabilityAnalysisProductError("candidate_not_found")
        if candidate.organization_id != actor.organization_id:
            raise CapabilityAnalysisProductError("candidate_role_organization_mismatch")
        if candidate.current_profile_id is None:
            raise CandidateProfileNotReadyProductError("candidate_profile_not_ready")
        role = await self._role_registry.get_role(role_id, actor.organization_id)
        if role is None:
            raise CapabilityAnalysisProductError("role_not_found")
        if role.organization_id != candidate.organization_id:
            raise CapabilityAnalysisProductError("candidate_role_organization_mismatch")
        if role.active_role_profile_id is None:
            raise RoleProfileNotActiveProductError("role_profile_not_active")
        active_profile = await self._role_profiles.get_active_for_role(role_id)
        if active_profile is None or active_profile.status is not RoleProfileStatus.ACTIVE:
            raise RoleProfileNotActiveProductError("role_profile_not_active")
        try:
            portfolio = await self.create_for_candidate(
                candidate_id=candidate_id,
                current_target_reference=f"{active_profile.id}@{active_profile.version}",
                future_target_reference=None,
                idempotency_key=idempotency_key,
                actor=actor,
            )
        except (ExtractionProfileNotAcceptedError, SupersededCapabilityProfileError) as error:
            raise CandidateProfileNotReadyProductError("candidate_profile_not_ready") from error
        return CandidateRoleAnalysisResult(
            portfolio=portfolio,
            candidate=candidate,
            candidate_profile_id=candidate.current_profile_id,
            candidate_profile_version=candidate.current_profile_version or 1,
            role=role,
            role_profile=active_profile,
        )

    async def get(self, portfolio_id: str, actor: ActorContext) -> CombinedGapPortfolio:
        portfolio = await self._portfolios.get(portfolio_id)
        if portfolio is None:
            raise KeyError(portfolio_id)
        if portfolio.organization_id != actor.organization_id:
            raise CapabilityAnalysisAccessDeniedError(
                "Actor organization does not own capability portfolio"
            )
        if portfolio.owner_actor_id != actor.actor_id and Role.REVIEWER not in actor.roles:
            raise CapabilityAnalysisAccessDeniedError("Actor cannot read capability portfolio")
        return portfolio

    async def list_for_candidate(
        self, candidate_id: UUID, actor: ActorContext
    ) -> tuple[CombinedGapPortfolio, ...]:
        if self._candidates is not None:
            candidate = await self._candidates.get(candidate_id)
            if candidate is None:
                raise CapabilityAnalysisProductError("candidate_not_found")
            if candidate.organization_id != actor.organization_id:
                raise CapabilityAnalysisAccessDeniedError(
                    "Actor organization does not own candidate"
                )
        return await self._portfolios.list_for_candidate(
            candidate_id,
            actor_id=actor.actor_id,
            organization_id=actor.organization_id,
        )

    async def list_for_role(
        self, role_id: UUID, actor: ActorContext
    ) -> tuple[CombinedGapPortfolio, ...]:
        if self._role_registry is not None:
            role = await self._role_registry.get_role(role_id, actor.organization_id)
            if role is None:
                raise CapabilityAnalysisProductError("role_not_found")
        profiles = await self._role_profiles.list_for_role(role_id)
        references = tuple((profile.id, profile.version) for profile in profiles)
        return await self._portfolios.list_for_target_references(
            references,
            actor_id=actor.actor_id,
            organization_id=actor.organization_id,
        )

    async def identity_projection(
        self, portfolio: CombinedGapPortfolio
    ) -> tuple[Candidate | None, RoleRecord | None]:
        """Resolve presentation identity without changing pinned analysis authority."""
        candidate = (
            await self._candidates.get(portfolio.candidate_id)
            if self._candidates is not None and portfolio.candidate_id is not None
            else None
        )
        if self._role_registry is None:
            return candidate, None
        target = await self._role_profiles.get_version(
            portfolio.current_role.target_id, portfolio.current_target_version
        )
        role = (
            await self._role_registry.get_role(target.role_id, portfolio.organization_id)
            if target is not None and target.role_id is not None
            else None
        )
        return candidate, role

    async def review_projection(
        self, portfolio: CombinedGapPortfolio
    ) -> CapabilityGapReviewProjectionV1:
        """Build the read-only review projection from the exact target version."""
        target = await self._role_profiles.get_version(
            portfolio.current_role.target_id, portfolio.current_target_version
        )
        if target is None:
            raise CurrentTargetNotUsableError("The analyzed role profile version is unavailable")
        await self._accepted_jd_source(target, CurrentTargetNotUsableError)
        profile = await self._extraction_profiles.get_profile(portfolio.cv_profile_id)
        if profile is None:
            raise ExtractionProfileNotAcceptedError("The analyzed CV profile is unavailable")
        evidence = adapt_evidence_index(build_evidence_index(profile))
        evidence_by_ref = {
            item.evidence_ref: item for item in evidence
        }
        projected_evidence = {
            ref: CapabilityReviewEvidenceV1(
                reference=ref,
                excerpt=item.source_excerpt,
                section=item.source_locator.section if item.source_locator else None,
                context=item.context.value,
                confidence=item.confidence,
            )
            for ref, item in evidence_by_ref.items()
        }
        return build_capability_gap_review_projection(portfolio, target, projected_evidence)

    async def candidate_evidence_projection(
        self, portfolio: CombinedGapPortfolio
    ) -> CandidateEvidenceProjectionV1:
        """Return bounded canonical evidence from the exact source profile version."""
        profile = await self._accepted_cv_for_assisted_reanalysis(portfolio.cv_profile_id)
        if profile.version != portfolio.cv_profile_version:
            raise HumanAssistedReanalysisValidationError(
                "Source analysis candidate profile version is no longer available"
            )
        capability_profile = build_provisional_capability_profile(profile)
        items = []
        for evidence in capability_profile.semantic_evidence:
            evidence_type = getattr(
                evidence.original_evidence_type, "value", evidence.original_evidence_type
            )
            source_label = {
                "employment": "Employment",
                "education": "Education",
                "skill": "Skill",
                "project": "Project",
                "credential": "Credential",
            }.get(evidence.source_kind)
            label = (evidence.source_value or evidence.source_kind).strip()[:256]
            excerpt = evidence.source_excerpt[:500] if evidence.source_excerpt else None
            items.append(
                CandidateEvidenceOptionV1(
                    evidence_ref=evidence.evidence_ref,
                    evidence_type=str(evidence_type),
                    label=label,
                    source_label=source_label,
                    excerpt=excerpt,
                )
            )
        return CandidateEvidenceProjectionV1(analysis_id=portfolio.id, items=items)

    async def evidence_for_gap(
        self, portfolio: CombinedGapPortfolio, gap_id: str
    ) -> tuple[EvidenceSemantics, ...]:
        tracks = [portfolio.current_role] + ([portfolio.future_role] if portfolio.future_role else [])
        gap = next((item for track in tracks if track is not None for item in track.gaps if item.id == gap_id), None)
        if gap is None:
            raise KeyError(gap_id)
        profile = await self._extraction_profiles.get_profile(portfolio.cv_profile_id)
        if profile is None:
            return ()
        # TargetGap references are the canonical semantic-core evidence refs.
        # Resolve against the same semantic evidence projection used during
        # analysis; do not parse refs or fall back to legacy observation IDs.
        semantic_evidence = adapt_evidence_index(build_evidence_index(profile))
        references = set(gap.matched_evidence_refs)
        return tuple(
            item for item in semantic_evidence if item.evidence_ref in references
        )

    async def _accepted_owned_cv(self, profile_id: str, actor: ActorContext) -> ExtractionProfile:
        profile = await self._extraction_profiles.get_profile(profile_id)
        if (
            profile is None
            or profile.document_kind is not DocumentKind.CV
            or profile.review_state is not ReviewState.ACCEPTED
            or profile.candidate_profile is None
        ):
            raise ExtractionProfileNotAcceptedError("CV profile is not accepted")
        if profile.owner_actor_id != actor.actor_id:
            raise CapabilityAnalysisAccessDeniedError("Actor does not own CV profile")
        if await self._extraction_profiles.is_superseded(profile_id):
            raise SupersededCapabilityProfileError("CV profile is superseded")
        return profile

    async def _accepted_cv_for_assisted_reanalysis(
        self, profile_id: str
    ) -> ExtractionProfile:
        profile = await self._extraction_profiles.get_profile(profile_id)
        if (
            profile is None
            or profile.document_kind is not DocumentKind.CV
            or profile.review_state is not ReviewState.ACCEPTED
            or profile.candidate_profile is None
        ):
            raise HumanAssistedReanalysisValidationError(
                "Source analysis candidate profile is not accepted"
            )
        return profile

    async def _current_target(
        self, profile_id: str, version: str | None = None
    ) -> RoleCompetencyProfile:
        target = (
            await self._role_profiles.get_version(profile_id, version)
            if version is not None
            else await self._role_profiles.get_preferred_target(profile_id)
        )
        if target is None:
            raise CurrentTargetNotUsableError("Current role target is unavailable")
        await self._accepted_jd_source(target, CurrentTargetNotUsableError)
        return target

    async def _future_target(
        self, profile_id: str | None, version: str | None = None
    ) -> RoleCompetencyProfile | None:
        if profile_id is None:
            return None
        target = (
            await self._role_profiles.get_version(profile_id, version)
            if version is not None
            else await self._role_profiles.get_preferred_target(profile_id)
        )
        if target is None:
            latest = await self._role_profiles.get_latest(profile_id)
            if latest is None or latest.status in {
                RoleProfileStatus.DRAFT,
                RoleProfileStatus.RETIRED,
            }:
                raise FutureTargetNotUsableError("Future role target is not usable")
            raise FutureTargetNotUsableError("Future role target is unavailable")
        await self._accepted_jd_source(target, FutureTargetNotUsableError)
        return target

    async def _accepted_jd_source(
        self, target: RoleCompetencyProfile, error_type: type[CapabilityAnalysisEligibilityError]
    ) -> None:
        source = await self._extraction_profiles.get_profile(target.source_jd_profile_id)
        if (
            source is None
            or source.document_kind is not DocumentKind.JD
            or source.review_state is not ReviewState.ACCEPTED
            or source.version != target.source_jd_profile_version
        ):
            raise error_type("Role target has no accepted JD source at the required version")

    async def _semantic_policy(
        self,
        target: RoleCompetencyProfile,
        target_type: TargetType,
    ) -> tuple[TargetSemanticPolicySnapshot, tuple[DomainKnowledgePack, ...]]:
        if target.semantic_policy_ref is not None:
            if self._semantic_policy_resolver is None:
                raise SemanticPolicyNotConfiguredError(
                    "Semantic policy resolver is not configured for this role profile"
                )
            try:
                resolved = await self._semantic_policy_resolver.resolve(
                    target.semantic_policy_ref,
                    target_id=target.id,
                    target_type=target_type.value,
                )
                pack_ref = DomainPackReference(
                    pack_id=resolved.domain_pack_id,
                    version=resolved.domain_pack_version,
                )
                resolved_pack = self._domain_pack_registry.resolve(pack_ref)
            except SemanticPolicyError as error:
                raise SemanticPolicyUnavailableError(
                    "The role profile semantic policy is not usable"
                ) from error
            return (
                TargetSemanticPolicySnapshot(
                    target_id=target.id,
                    target_version=target.version,
                    target_type=target_type,
                    core_version=resolved.core_version,
                    pack_refs=(pack_ref,),
                    selection_source=SemanticPolicySelectionSource.PROFILE_METADATA,
                    policy_id=resolved.policy_id,
                    policy_version=resolved.policy_version,
                    pack_checksum=resolved.domain_pack_checksum,
                ),
                (resolved_pack,),
            )
        if target.semantic_policy is not None:
            core_version = target.semantic_policy.core_version
            pack_refs = target.semantic_policy.pack_refs
            selection_source = SemanticPolicySelectionSource.PROFILE_METADATA
        else:
            mapping = await self._role_profiles.get_semantic_policy_mapping(
                target.id,
                target.version,
            )
            if mapping is None:
                raise SemanticPolicyNotConfiguredError(
                    "Semantic policy is not configured for this role profile version"
                )
            core_version = mapping.core_version
            pack_refs = mapping.pack_refs
            selection_source = mapping.selection_source
        try:
            resolved_packs = self._domain_pack_registry.resolve_ordered(pack_refs)
        except DomainPackUnavailableError as error:
            raise SemanticPolicyUnavailableError(
                "A referenced semantic policy pack is unavailable"
            ) from error
        return (
            TargetSemanticPolicySnapshot(
                target_id=target.id,
                target_version=target.version,
                target_type=target_type,
                core_version=core_version,
                pack_refs=pack_refs,
                selection_source=selection_source,
            ),
            resolved_packs,
        )

    @staticmethod
    def _current_usage_mode(target: RoleCompetencyProfile) -> TargetUsageMode:
        return (
            TargetUsageMode.OFFICIAL
            if target.status is RoleProfileStatus.ACTIVE
            else TargetUsageMode.PREVIEW
        )

    @staticmethod
    def _future_usage_mode(target: RoleCompetencyProfile) -> TargetUsageMode:
        return (
            TargetUsageMode.OFFICIAL
            if target.status is RoleProfileStatus.ACTIVE
            else TargetUsageMode.PREVIEW
        )


def _parse_target_reference(reference: str | None) -> tuple[str, str | None]:
    if reference is None:
        return (None, None)  # type: ignore[return-value]
    if "@" not in reference:
        return reference, None
    profile_id, version = reference.rsplit("@", 1)
    if not profile_id or not version:
        raise CurrentTargetNotUsableError("Target reference is invalid")
    return profile_id, version


def _same_analysis_request(
    portfolio: CombinedGapPortfolio,
    *,
    candidate_id: UUID,
    cv_profile_id: str,
    current_target_id: str,
    current_target_version: str | None,
    future_target_id: str | None,
    future_target_version: str | None,
) -> bool:
    return (
        portfolio.candidate_id == candidate_id
        and portfolio.cv_profile_id == cv_profile_id
        and portfolio.current_role.target_id == current_target_id
        and (
            current_target_version is None
            or portfolio.current_target_version == current_target_version
        )
        and (
            portfolio.future_role is None
            if future_target_id is None
            else portfolio.future_role is not None
            and portfolio.future_role.target_id == future_target_id
            and (
                future_target_version is None
                or portfolio.future_target_version == future_target_version
            )
        )
    )
