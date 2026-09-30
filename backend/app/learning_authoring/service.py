from typing import Protocol

from app.authorization.schemas import ActorContext
from app.capability_analysis.errors import CapabilityAnalysisAccessDeniedError
from app.capability_analysis.schemas import CombinedGapPortfolio, TargetGap, TargetType
from app.instructional_blueprint.generator import (
    DeterministicInstructionalBlueprintGenerator,
    InstructionalBlueprintGenerator,
    InstructionalBlueprintInput,
)
from app.learning.mapper import map_learning_need_to_objective
from app.learning.schemas import LearningObjective
from app.learning_need_profile.projection import LearningNeedProjectionService
from app.learning_need_profile.schemas import LearningNeedProfile
from app.matching.schemas import RoleCompetencyProfile, RoleRequirement

from .schemas import (
    InstructionalBlueprintProjection,
    LearningNeedProfileProjection,
    LearningObjectiveProjection,
)


class LearningAuthoringNotFoundError(Exception):
    """Raised when a read-only authoring reference cannot be reconstructed."""


class LearningAuthoringAccessDeniedError(Exception):
    """Raised when the actor cannot read the source authoring artifact."""


class CapabilityAnalysisReader(Protocol):
    async def get(self, portfolio_id: str, actor: ActorContext) -> CombinedGapPortfolio: ...


class RoleProfileReader(Protocol):
    async def get_version(
        self, role_profile_id: str, version: str
    ) -> RoleCompetencyProfile | None: ...


class LearningAuthoringService:
    def __init__(
        self,
        *,
        capability_analyses: CapabilityAnalysisReader,
        role_profiles: RoleProfileReader,
        generator: InstructionalBlueprintGenerator | None = None,
        learning_need_projection: LearningNeedProjectionService | None = None,
    ) -> None:
        self._capability_analyses = capability_analyses
        self._role_profiles = role_profiles
        self._generator = generator or DeterministicInstructionalBlueprintGenerator()
        self._learning_need_projection = learning_need_projection or LearningNeedProjectionService()

    async def get_learning_need(
        self, artifact_id: str, actor: ActorContext
    ) -> LearningNeedProfileProjection:
        learning_need, _requirement = await self._resolve_learning_need(artifact_id, actor)
        return LearningNeedProfileProjection(
            id=learning_need.id,
            candidate_reference=learning_need.candidate_reference,
            target_reference=learning_need.target_reference,
            learner_context=learning_need.learner_context,
            competency=learning_need.competency,
            current_state=learning_need.current_state,
            target_state=learning_need.target_state,
            gap=learning_need.gap,
            missing_knowledge=learning_need.missing_knowledge,
            priority=learning_need.priority,
            confidence=learning_need.confidence,
            source_gap_refs=learning_need.source_gap_refs,
            evidence_references=learning_need.current_state.evidence_refs,
        )

    async def get_learning_objective(
        self, artifact_id: str, actor: ActorContext
    ) -> LearningObjectiveProjection:
        learning_need_id = self._parse_prefixed_id(
            artifact_id, "objective-", "learning_objective_not_found"
        )
        try:
            learning_need, requirement = await self._resolve_learning_need(
                learning_need_id, actor
            )
        except LearningAuthoringNotFoundError as exc:
            raise LearningAuthoringNotFoundError(
                "learning_objective_not_found"
            ) from exc
        try:
            objective = map_learning_need_to_objective(
                learning_need=learning_need,
                sequence=1,
                measurable_outcome=requirement.assessment_recommendation,
                # Course-authoring objectives use the existing numeric learning
                # scale. The role contract also permits the bounded named target
                # level "production", which maps to the top of that scale here.
                allow_named_target_level=True,
            )
            return LearningObjectiveProjection.model_validate(objective.model_dump())
        except ValueError as exc:
            if str(exc) != "learning_need_target_level_required":
                raise
            # A JD requirement may intentionally omit a target level. Preserve
            # that absence in the authoring projection instead of inventing one;
            # GAP_DRIVEN curriculum planning only needs the source-grounded
            # statement/outcome and does not score this field.
            return LearningObjectiveProjection(
                id=f"objective-{learning_need.id}",
                learning_need_ref=learning_need.id,
                statement=learning_need.gap.description,
                bloom_level=None,
                evidence_required=None,
                competency_id=learning_need.competency.id,
                current_level=None,
                target_level=None,
                measurable_outcome=requirement.assessment_recommendation,
                gap_id=learning_need.source_gap_refs[0],
                sequence=1,
            )

    async def get_instructional_blueprint(
        self, artifact_id: str, actor: ActorContext
    ) -> InstructionalBlueprintProjection:
        objective_id = self._parse_prefixed_id(
            artifact_id,
            "instructional-blueprint-",
            "instructional_blueprint_not_found",
        )
        try:
            objective_projection = await self.get_learning_objective(objective_id, actor)
        except LearningAuthoringNotFoundError as exc:
            raise LearningAuthoringNotFoundError(
                "instructional_blueprint_not_found"
            ) from exc
        if objective_projection.target_level is None:
            raise LearningAuthoringNotFoundError("instructional_blueprint_not_found")
        objective = LearningObjective.model_validate(objective_projection.model_dump())
        learning_need, _requirement = await self._resolve_learning_need(
            objective_projection.learning_need_ref, actor
        )
        generated = await self._generator.generate(
            InstructionalBlueprintInput(
                learning_need=learning_need,
                objective=objective,
            )
        )
        return InstructionalBlueprintProjection.model_validate(generated.model_dump())

    async def _resolve_learning_need(
        self, artifact_id: str, actor: ActorContext
    ) -> tuple[LearningNeedProfile, RoleRequirement]:
        analysis_id, gap_id = self._parse_learning_need_id(artifact_id)
        try:
            portfolio = await self._capability_analyses.get(analysis_id, actor)
        except (CapabilityAnalysisAccessDeniedError, PermissionError) as exc:
            raise LearningAuthoringAccessDeniedError(
                "learning_authoring_access_denied"
            ) from exc
        except (KeyError, ValueError) as exc:
            raise LearningAuthoringNotFoundError("learning_need_not_found") from exc

        gap = self._find_gap(portfolio, gap_id)
        if gap is None:
            raise LearningAuthoringNotFoundError("learning_need_not_found")
        target_version = self._target_version(portfolio, gap)
        if target_version is None:
            raise LearningAuthoringNotFoundError("learning_need_not_found")
        target = await self._role_profiles.get_version(gap.target_id, target_version)
        if target is None:
            raise LearningAuthoringNotFoundError("learning_need_not_found")
        requirement = next(
            (item for item in target.requirements if item.id == gap.requirement_id),
            None,
        )
        if requirement is None:
            raise LearningAuthoringNotFoundError("learning_need_not_found")
        try:
            learning_need = self._learning_need_projection.project_one(
                portfolio=portfolio,
                gap=gap,
                requirement=requirement,
            )
            if learning_need is None:
                raise LearningAuthoringNotFoundError("learning_need_not_found")
        except (ValueError, IndexError) as exc:
            raise LearningAuthoringNotFoundError("learning_need_not_found") from exc
        return learning_need, requirement

    @staticmethod
    def _parse_learning_need_id(artifact_id: str) -> tuple[str, str]:
        if not artifact_id.startswith("learning-need:"):
            raise LearningAuthoringNotFoundError("learning_need_not_found")
        parts = artifact_id.split(":", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise LearningAuthoringNotFoundError("learning_need_not_found")
        return parts[1], parts[2]

    @staticmethod
    def _parse_prefixed_id(artifact_id: str, prefix: str, code: str) -> str:
        if not artifact_id.startswith(prefix) or len(artifact_id) == len(prefix):
            raise LearningAuthoringNotFoundError(code)
        return artifact_id[len(prefix) :]

    @staticmethod
    def _find_gap(portfolio: CombinedGapPortfolio, gap_id: str) -> TargetGap | None:
        analyses = [portfolio.current_role]
        if portfolio.future_role is not None:
            analyses.append(portfolio.future_role)
        return next(
            (
                gap
                for analysis in analyses
                for gap in analysis.gaps
                if gap.id == gap_id
            ),
            None,
        )

    @staticmethod
    def _target_version(
        portfolio: CombinedGapPortfolio, gap: TargetGap
    ) -> str | None:
        if gap.target_type is TargetType.CURRENT_ROLE:
            return portfolio.current_target_version
        return portfolio.future_target_version
