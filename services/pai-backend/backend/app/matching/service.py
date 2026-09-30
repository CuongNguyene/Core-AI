from datetime import datetime
from uuid import UUID, uuid4

from app.authorization.schemas import ActorContext, Role
from app.extraction.repository import ExtractionRepository
from app.extraction.schemas import DocumentKind, ReviewState
from app.matching.errors import (
    ExtractionProfileNotAcceptedError,
    PreliminaryMatchAccessDeniedError,
    PreliminaryMatchError,
    RoleProfileNotActiveError,
    SupersededInputError,
)
from app.matching.repository import PreliminaryMatchRepository, RoleProfileRepository
from app.matching.rules import evaluate_requirements
from app.matching.schemas import PreliminaryMatch, PreliminaryMatchStatus


class PreliminaryMatchService:
    def __init__(
        self,
        extraction_repository: ExtractionRepository,
        role_profiles: RoleProfileRepository,
        matches: PreliminaryMatchRepository,
    ) -> None:
        self._extraction_repository = extraction_repository
        self._role_profiles = role_profiles
        self._matches = matches

    async def review(
        self,
        match_id: str,
        *,
        actor: ActorContext,
        approved_gap_ids: list[str],
        expected_version: int,
        reviewed_at: datetime,
    ) -> PreliminaryMatch:
        if Role.REVIEWER not in actor.roles:
            raise PermissionError("reviewer_role_required")
        match = await self._matches.get(match_id)
        if match is None:
            raise KeyError(match_id)
        if match.actor_id != actor.actor_id and Role.REVIEWER not in actor.roles:
            raise PermissionError("preliminary_match_access_denied")
        return await self._matches.review(
            match_id,
            reviewer_id=actor.actor_id,
            approved_gap_ids=approved_gap_ids,
            expected_version=expected_version,
            reviewed_at=reviewed_at,
        )

    async def create(
        self, cv_profile_id: str, role_profile_id: str, actor_id: UUID, correlation_id: str
    ) -> PreliminaryMatch:
        try:
            return await self._create(cv_profile_id, role_profile_id, actor_id, correlation_id)
        except PreliminaryMatchError as exc:
            await self._matches.record_rejected_input(
                actor_id=actor_id,
                correlation_id=correlation_id,
                cv_profile_id=cv_profile_id,
                role_profile_id=role_profile_id,
                action=(
                    "MATCHING_REJECTED_INPUT_NOT_ACCEPTED"
                    if isinstance(exc, ExtractionProfileNotAcceptedError)
                    else "MATCHING_REJECTED_INPUT_INELIGIBLE"
                ),
            )
            raise

    async def _create(
        self, cv_profile_id: str, role_profile_id: str, actor_id: UUID, correlation_id: str
    ) -> PreliminaryMatch:
        cv_profile = await self._extraction_repository.get_profile(cv_profile_id)
        if cv_profile is None or cv_profile.review_state is not ReviewState.ACCEPTED:
            raise ExtractionProfileNotAcceptedError(cv_profile_id)
        if cv_profile.document_kind is not DocumentKind.CV:
            raise ExtractionProfileNotAcceptedError(cv_profile_id)
        if cv_profile.owner_actor_id != actor_id:
            raise PreliminaryMatchAccessDeniedError(cv_profile_id)
        if await self._extraction_repository.is_superseded(cv_profile_id):
            raise SupersededInputError(cv_profile_id)
        role_profile = await self._role_profiles.get_active(role_profile_id)
        if role_profile is None:
            raise RoleProfileNotActiveError(role_profile_id)
        jd_profile = await self._extraction_repository.get_profile(
            role_profile.source_jd_profile_id
        )
        if jd_profile is None or jd_profile.review_state is not ReviewState.ACCEPTED:
            raise ExtractionProfileNotAcceptedError(role_profile.source_jd_profile_id)
        if jd_profile.document_kind is not DocumentKind.JD:
            raise ExtractionProfileNotAcceptedError(role_profile.source_jd_profile_id)
        if jd_profile.version != role_profile.source_jd_profile_version:
            raise ExtractionProfileNotAcceptedError(role_profile.source_jd_profile_id)
        if await self._extraction_repository.is_superseded(jd_profile.id):
            raise SupersededInputError(jd_profile.id)
        evaluation = evaluate_requirements(cv_profile, role_profile)
        return await self._matches.create(
            PreliminaryMatch(
                id=str(uuid4()),
                cv_profile_id=cv_profile.id,
                cv_profile_version=cv_profile.version,
                jd_profile_id=jd_profile.id,
                jd_profile_version=jd_profile.version,
                role_profile_id=role_profile.id,
                role_profile_version=role_profile.version,
                rule_set_version=role_profile.rule_set_version,
                policy_version=role_profile.policy_version,
                actor_id=actor_id,
                correlation_id=correlation_id,
                status=PreliminaryMatchStatus.COMPLETED,
                criterion_results=evaluation.criterion_results,
                evidence_allocations=evaluation.allocations,
                preliminary_skill_gaps=evaluation.preliminary_skill_gaps,
            )
        )
