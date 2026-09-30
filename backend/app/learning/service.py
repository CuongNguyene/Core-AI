import hashlib
import json
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID, uuid4

from app.authorization.schemas import ActorContext
from app.capability_analysis.schemas import CombinedGapPortfolio
from app.competency.schemas import CompetencyLevelStatus, CompetencyRecord
from app.learning.errors import (
    LearningPathNotDraftError,
    LearningPathNotFoundError,
    LearningPathNotReadyForReviewError,
    LearningPathReviewRequiredError,
    LearningPathStaleError,
    LearningPathValidationError,
    LearningPathVersionConflictError,
)
from app.learning.generator import (
    ContentBlueprintGenerator,
    ContentGenerationRequest,
    FakeContentBlueprintGenerator,
)
from app.learning.graph import validate_prerequisite_graph
from app.learning.mapper import map_learning_need_to_objective
from app.learning.repository import LearningPathRepository
from app.learning.schemas import (
    CapabilityAnalysisLearningPathRequest,
    LearningObjective,
    LearningPath,
    LearningPathRequest,
    LearningPathSourceType,
    LearningPathStatus,
    LearningPathValidation,
    LearningPathValidationFinding,
)
from app.learning_need_profile.mapper import map_target_gap_to_learning_need
from app.matching.schemas import PreliminaryMatch, RoleCompetencyProfile, RoleProfileStatus


class CompetencyReader(Protocol):
    async def get_record(self, record_id: UUID) -> CompetencyRecord | None: ...


class RoleProfileReader(Protocol):
    async def get_version(
        self, role_profile_id: str, version: str
    ) -> RoleCompetencyProfile | None: ...


class MatchReader(Protocol):
    async def get(self, match_id: str) -> PreliminaryMatch | None: ...


class CapabilityAnalysisReader(Protocol):
    async def get(self, analysis_id: str) -> CombinedGapPortfolio | None: ...

    async def get_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> CombinedGapPortfolio | None: ...


class ProfileReader(Protocol):
    async def get_profile(self, profile_id: str) -> object | None: ...


class LearningPathService:
    def __init__(
        self,
        *,
        competency_records: CompetencyReader,
        role_profiles: RoleProfileReader,
        matches: MatchReader,
        paths: LearningPathRepository,
        capability_analyses: CapabilityAnalysisReader | None = None,
        profiles: ProfileReader | None = None,
        generator: ContentBlueprintGenerator | None = None,
    ) -> None:
        self._competency_records = competency_records
        self._role_profiles = role_profiles
        self._matches = matches
        self._paths = paths
        self._capability_analyses = capability_analyses
        self._profiles = profiles
        self._generator = generator or FakeContentBlueprintGenerator()

    async def create(self, *, actor: ActorContext, request: LearningPathRequest) -> LearningPath:
        path = await self._build(actor=actor, request=request)
        return await self._paths.create(path)

    async def create_from_capability_analysis(
        self,
        *,
        actor: ActorContext,
        request: CapabilityAnalysisLearningPathRequest,
        idempotency_key: str | None = None,
        request_fingerprint: str | None = None,
    ) -> LearningPath:
        if self._capability_analyses is None:
            raise LearningPathValidationError("capability_analysis_unavailable")
        analysis = await self._capability_analyses.get(request.capability_analysis_id)
        if analysis is None:
            raise LearningPathValidationError("capability_analysis_not_found")
        if analysis.owner_actor_id != actor.actor_id or analysis.organization_id != actor.organization_id:
            raise LearningPathValidationError("capability_analysis_access_denied")
        if analysis.candidate_id is None:
            raise LearningPathValidationError("capability_analysis_candidate_missing")
        actionable = [
            gap for gap in analysis.current_role.gaps
            if gap.recommendation and gap.recommendation.strip()
        ]
        if not actionable:
            raise LearningPathValidationError("no_actionable_capability_gaps")
        target = await self._role_profiles.get_version(
            analysis.current_role.target_id, analysis.current_target_version
        )
        if target is None or target.status is not RoleProfileStatus.ACTIVE:
            raise LearningPathValidationError("capability_analysis_target_not_active")
        requirements = {item.id: item for item in target.requirements}
        objectives: list[LearningObjective] = []
        findings: list[LearningPathValidationFinding] = []
        for sequence, gap in enumerate(actionable, start=1):
            requirement = requirements.get(gap.requirement_id)
            if requirement is None:
                findings.append(LearningPathValidationFinding(
                    code="target_level_missing",
                    message=f"Target level is missing for actionable gap {gap.id}.",
                ))
                continue
            if requirement.target_level not in {"1", "2", "3", "4", "5"}:
                raise LearningPathValidationError("capability_analysis_target_level_required")
            learning_need = map_target_gap_to_learning_need(
                portfolio=analysis,
                gap=gap,
                requirement=requirement,
            )
            objectives.append(
                map_learning_need_to_objective(
                    learning_need=learning_need,
                    sequence=sequence,
                    measurable_outcome=requirement.assessment_recommendation,
                )
            )
        if findings:
            raise LearningPathValidationError("capability_analysis_validation_failed")
        generated = await self._generator.generate(
            ContentGenerationRequest(
                target_profile_id=target.id,
                target_profile_version=target.version,
                preliminary_match_id=None,
                objectives=objectives,
                target_completion_date=request.target_completion_date,
                policy_version=target.policy_version,
            )
        )
        validate_prerequisite_graph(generated.prerequisite_nodes, generated.prerequisite_edges)
        validation = LearningPathValidation(valid=True, ready_for_review=True)
        return await self._paths.create(LearningPath(
            id=str(uuid4()),
            version=1,
            status=LearningPathStatus.DRAFT,
            subject_id=actor.actor_id,
            organization_id=actor.organization_id,
            target_profile_id=target.id,
            target_profile_version=target.version,
            preliminary_match_id=None,
            verified_competency_record_ids=[],
            approved_gap_ids=[gap.id for gap in actionable],
            development_goal=request.development_goal,
            target_completion_date=request.target_completion_date,
            objectives=objectives,
            prerequisite_nodes=generated.prerequisite_nodes,
            prerequisite_edges=generated.prerequisite_edges,
            learning_objects=generated.learning_objects,
            lessons=generated.lessons,
            modules=generated.modules,
            blueprints=generated.blueprints,
            generator_version=generated.generator_version,
            policy_version=target.policy_version,
            correlation_id=analysis.correlation_id,
            created_by=actor.actor_id,
            created_at=datetime.now(UTC),
            source_type=LearningPathSourceType.CAPABILITY_ANALYSIS,
            capability_analysis_id=analysis.id,
            capability_analysis_version=analysis.analysis_version,
            source_candidate_id=analysis.candidate_id,
            source_profile_id=analysis.cv_profile_id,
            source_profile_version=analysis.cv_profile_version,
            source_target_id=target.id,
            source_target_version=target.version,
            source_gap_ids=[gap.id for gap in actionable],
            source_evidence_refs=[ref for gap in actionable for ref in gap.matched_evidence_refs],
            source_recommendation_refs=[gap.recommendation for gap in actionable if gap.recommendation],
            validation=validation,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        ))

    async def create_for_candidate(
        self,
        *,
        actor: ActorContext,
        candidate_id: UUID,
        development_goal: str,
        target_completion_date: date,
        idempotency_key: str,
    ) -> LearningPath:
        if not idempotency_key:
            raise LearningPathValidationError("idempotency_key_required")
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "candidate_id": str(candidate_id),
                    "development_goal": development_goal,
                    "target_completion_date": target_completion_date.isoformat(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        existing = await self._paths.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise LearningPathValidationError("learning_path_idempotency_conflict")
            return existing
        if self._capability_analyses is None:
            raise LearningPathValidationError("capability_analysis_unavailable")
        analysis = await self._capability_analyses.get_for_candidate(
            candidate_id, actor_id=actor.actor_id, organization_id=actor.organization_id
        )
        if analysis is None:
            raise LearningPathValidationError("capability_analysis_not_found")
        internal = CapabilityAnalysisLearningPathRequest(
            capability_analysis_id=analysis.id,
            development_goal=development_goal,
            target_completion_date=target_completion_date,
        )
        try:
            return await self.create_from_capability_analysis(
                actor=actor,
                request=internal,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
        except ValueError as exc:
            winner = await self._paths.get_by_idempotency_key(idempotency_key)
            if winner is not None and winner.request_fingerprint == fingerprint:
                return winner
            raise LearningPathValidationError("learning_path_idempotency_conflict") from exc

    async def get(self, path_id: str, *, actor: ActorContext) -> LearningPath:
        path = await self._paths.get(path_id)
        if path is None:
            raise LearningPathNotFoundError("learning_path_not_found")
        if path.subject_id != actor.actor_id or path.organization_id != actor.organization_id:
            raise LearningPathValidationError("learning_path_access_denied")
        stale, reasons = await self._stale_metadata(path)
        return path.model_copy(
            update={"is_stale": stale, "stale_reasons": reasons}, deep=True
        )

    async def review(
        self, path_id: str, *, actor: ActorContext, expected_version: int
    ) -> LearningPath:
        path = await self._require_owned(path_id, actor, expected_version)
        self._require_reviewable(path)
        stale, reasons = await self._stale_metadata(path)
        if stale:
            raise LearningPathStaleError(",".join(reasons))
        return await self._paths.review(path.id, actor.actor_id, expected_version)

    async def approve(
        self, path_id: str, *, actor: ActorContext, expected_version: int
    ) -> LearningPath:
        path = await self._require_owned(path_id, actor, expected_version)
        self._require_reviewable(path)
        if not path.reviewed or path.reviewed_version != path.version:
            raise LearningPathReviewRequiredError("learning_path_review_required")
        stale, reasons = await self._stale_metadata(path)
        if stale:
            raise LearningPathStaleError(",".join(reasons))
        try:
            return await self._paths.approve(path.id, actor.actor_id, expected_version)
        except ValueError as exc:
            raise LearningPathVersionConflictError("learning_path_version_conflict") from exc

    async def regenerate_from_capability_analysis(
        self,
        path_id: str,
        *,
        actor: ActorContext,
        request: CapabilityAnalysisLearningPathRequest,
    ) -> LearningPath:
        current = await self._paths.get(path_id)
        if current is None:
            raise LearningPathNotFoundError("learning_path_not_found")
        if current.subject_id != actor.actor_id or current.organization_id != actor.organization_id:
            raise LearningPathValidationError("learning_path_access_denied")
        if current.status is not LearningPathStatus.ACTIVE:
            raise LearningPathNotDraftError("learning_path_not_active")
        generated = await self.create_from_capability_analysis(actor=actor, request=request)
        successor = generated.model_copy(
            update={"id": current.id, "version": current.version + 1}, deep=True
        )
        return await self._paths.create(successor)

    async def _require_owned(
        self, path_id: str, actor: ActorContext, expected_version: int
    ) -> LearningPath:
        path = await self._paths.get(path_id)
        if path is None:
            raise LearningPathNotFoundError("learning_path_not_found")
        if path.subject_id != actor.actor_id or path.organization_id != actor.organization_id:
            raise LearningPathValidationError("learning_path_access_denied")
        if path.version != expected_version:
            raise LearningPathVersionConflictError("learning_path_version_conflict")
        return path

    @staticmethod
    def _require_reviewable(path: LearningPath) -> None:
        if path.status is not LearningPathStatus.DRAFT:
            raise LearningPathNotDraftError("learning_path_not_draft")
        if path.source_type is not LearningPathSourceType.CAPABILITY_ANALYSIS:
            raise LearningPathNotReadyForReviewError("learning_path_not_ready_for_review")
        if not path.validation.valid or not path.validation.ready_for_review:
            raise LearningPathNotReadyForReviewError("learning_path_not_ready_for_review")

    async def _stale_metadata(self, path: LearningPath) -> tuple[bool, list[str]]:
        if path.source_type is not LearningPathSourceType.CAPABILITY_ANALYSIS:
            return False, []
        reasons: list[str] = []
        if self._capability_analyses is None or path.capability_analysis_id is None:
            reasons.append("SOURCE_UNAVAILABLE")
        else:
            analysis = await self._capability_analyses.get(path.capability_analysis_id)
            if analysis is None:
                reasons.append("SOURCE_UNAVAILABLE")
            else:
                if analysis.analysis_version != path.capability_analysis_version:
                    reasons.append("CAPABILITY_ANALYSIS_VERSION_CHANGED")
                if analysis.cv_profile_version != path.source_profile_version:
                    reasons.append("PROFILE_VERSION_CHANGED")
                if analysis.current_target_version != path.source_target_version:
                    reasons.append("TARGET_VERSION_CHANGED")

        if self._profiles is None or path.source_profile_id is None:
            reasons.append("SOURCE_UNAVAILABLE")
        else:
            profile = await self._profiles.get_profile(path.source_profile_id)
            profile_version = getattr(profile, "version", None) if profile is not None else None
            if profile_version is None:
                reasons.append("SOURCE_UNAVAILABLE")
            elif profile_version != path.source_profile_version:
                reasons.append("PROFILE_VERSION_CHANGED")

        target = None
        if path.source_target_id is None or path.source_target_version is None:
            reasons.append("SOURCE_UNAVAILABLE")
        else:
            target = await self._role_profiles.get_version(
                path.source_target_id, path.source_target_version
            )
            if target is None:
                reasons.append("SOURCE_UNAVAILABLE")
            preferred_reader = getattr(self._role_profiles, "get_preferred_target", None)
            if target is not None and preferred_reader is not None:
                preferred = await preferred_reader(path.source_target_id)
                if preferred is None:
                    reasons.append("SOURCE_UNAVAILABLE")
                elif preferred.version != path.source_target_version:
                    reasons.append("TARGET_VERSION_CHANGED")
        return bool(reasons), list(dict.fromkeys(reasons))

    async def supersede(
        self,
        path_id: str,
        *,
        actor: ActorContext,
        request: LearningPathRequest,
    ) -> LearningPath:
        current = await self._paths.get(path_id)
        if current is None:
            raise LearningPathValidationError("learning_path_not_found")
        if current.subject_id != actor.actor_id or current.organization_id != actor.organization_id:
            raise LearningPathValidationError("learning_path_access_denied")
        path = await self._build(actor=actor, request=request)
        successor = path.model_copy(
            update={"id": path_id, "version": current.version + 1}, deep=True
        )
        return await self._paths.supersede(path_id, successor)

    async def _build(self, *, actor: ActorContext, request: LearningPathRequest) -> LearningPath:
        if actor.actor_id != request.subject_id:
            raise LearningPathValidationError("subject_mismatch")
        target = await self._role_profiles.get_version(
            request.target_profile_id, request.target_profile_version
        )
        if target is None or target.status is not RoleProfileStatus.ACTIVE:
            raise LearningPathValidationError("target_profile_not_active")
        match = await self._matches.get(request.preliminary_match_id)
        if match is None:
            raise LearningPathValidationError("preliminary_match_not_found")
        if match.status.value != "reviewed":
            raise LearningPathValidationError("preliminary_match_not_reviewed")
        if match.actor_id != actor.actor_id:
            raise LearningPathValidationError("preliminary_match_subject_mismatch")
        if match.role_profile_id != target.id or match.role_profile_version != target.version:
            raise LearningPathValidationError("preliminary_match_target_mismatch")
        if not set(request.approved_gap_ids).issubset(set(match.approved_gap_ids)):
            raise LearningPathValidationError("gap_not_approved")

        requirements = {requirement.id: requirement for requirement in target.requirements}
        criterion_results = {item.requirement_id: item for item in match.criterion_results}
        for gap_id in request.approved_gap_ids:
            requirement = requirements.get(gap_id)
            result = criterion_results.get(gap_id)
            if requirement is None or result is None:
                raise LearningPathValidationError("gap_not_in_target_profile")
            if result.confidence is None or result.confidence < requirement.confidence_threshold:
                raise LearningPathValidationError("gap_confidence_insufficient")

        records: list[CompetencyRecord] = []
        for record_id in request.verified_competency_record_ids:
            record = await self._competency_records.get_record(record_id)
            if record is None:
                raise LearningPathValidationError("verified_competency_not_found")
            if record.status is not CompetencyLevelStatus.VERIFIED:
                raise LearningPathValidationError("verified_competency_required")
            if (
                record.subject_id != actor.actor_id
                or record.organization_id != actor.organization_id
            ):
                raise LearningPathValidationError("verified_competency_scope_mismatch")
            if (
                record.valid_until is None
                or record.valid_until.date() < request.target_completion_date
            ):
                raise LearningPathValidationError("verified_competency_expired")
            records.append(record)

        levels = {record.competency_id: record.level for record in records}
        objectives = [
            LearningObjective(
                id=f"objective-{gap_id}",
                competency_id=gap_id,
                current_level=levels.get(gap_id),
                target_level=min((levels.get(gap_id) or 1) + 1, 5),
                measurable_outcome=f"Demonstrate {gap_id} at the next target level",
                gap_id=gap_id,
                sequence=index,
            )
            for index, gap_id in enumerate(request.approved_gap_ids, start=1)
        ]
        generated = await self._generator.generate(
            ContentGenerationRequest(
                target_profile_id=target.id,
                target_profile_version=target.version,
                preliminary_match_id=match.id,
                objectives=objectives,
                target_completion_date=request.target_completion_date,
                policy_version=target.policy_version,
            )
        )
        validate_prerequisite_graph(generated.prerequisite_nodes, generated.prerequisite_edges)
        path = LearningPath(
            id=str(uuid4()),
            version=1,
            status=LearningPathStatus.ACTIVE,
            subject_id=actor.actor_id,
            organization_id=actor.organization_id,
            target_profile_id=target.id,
            target_profile_version=target.version,
            preliminary_match_id=match.id,
            verified_competency_record_ids=[record.id for record in records],
            approved_gap_ids=request.approved_gap_ids,
            development_goal=request.development_goal,
            target_completion_date=request.target_completion_date,
            objectives=objectives,
            prerequisite_nodes=generated.prerequisite_nodes,
            prerequisite_edges=generated.prerequisite_edges,
            learning_objects=generated.learning_objects,
            lessons=generated.lessons,
            modules=generated.modules,
            blueprints=generated.blueprints,
            generator_version=generated.generator_version,
            policy_version=target.policy_version,
            correlation_id=request.correlation_id,
            created_by=actor.actor_id,
            created_at=datetime.now(UTC),
        )
        return path
