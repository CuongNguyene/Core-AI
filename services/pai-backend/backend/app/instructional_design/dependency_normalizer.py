"""Explicit normalization boundary for assessment dependency representations."""

import unicodedata
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    AssessmentDependencyRole,
    AssessmentDependencyStatus,
    AssessmentSpec,
    CanonicalAssessmentDependency,
    DependencyProvenance,
    DependencySource,
    DependencySourceType,
    DesignFinding,
    DesignFindingSeverity,
)


class CanonicalAssessmentDependencies(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    assessment_id: str = Field(min_length=1)
    dependencies: list[CanonicalAssessmentDependency] = Field(default_factory=list)
    findings: list[DesignFinding] = Field(default_factory=list)


def normalize_capability_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def normalize_assessment_dependencies(
    assessment: AssessmentSpec,
    *,
    dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
) -> CanonicalAssessmentDependencies:
    """Merge only explicit duplicate representations; never infer equivalence."""

    grouped: dict[tuple[str, AssessmentDependencyRole], CanonicalAssessmentDependency] = {}
    legacy_values = {
        normalize_capability_text(value): value for value in assessment.required_capability_refs
    }
    typed_values = {
        normalize_capability_text(item.capability): item
        for item in assessment.required_capabilities
    }
    findings: list[DesignFinding] = []
    if set(legacy_values) != set(typed_values) and legacy_values and typed_values:
        findings.append(
            DesignFinding(
                code="conflicting_dependency_semantics",
                severity=DesignFindingSeverity.ERROR,
                entity_type="assessment",
                entity_id=assessment.id,
                field="required_capabilities",
                message=(
                    "Legacy and typed assessment dependency representations contain "
                    "different semantic capability values."
                ),
            )
        )

    for normalized_value, value in legacy_values.items():
        key = (normalized_value, AssessmentDependencyRole.REQUIRED_CAPABILITY)
        grouped[key] = CanonicalAssessmentDependency(
            capability_ref=normalized_value,
            dependency_role=AssessmentDependencyRole.REQUIRED_CAPABILITY,
            provenance=DependencyProvenance(
                sources=[
                    DependencySource(
                        type=DependencySourceType.LEGACY_COMPATIBILITY,
                        source_ref=assessment.id,
                        original_value=value,
                    )
                ]
            ),
            objective_ids=list(assessment.objective_ids),
            status=AssessmentDependencyStatus.CONFIRMED,
        )
    for normalized_value, requirement in typed_values.items():
        key = (normalized_value, AssessmentDependencyRole.REQUIRED_CAPABILITY)
        source = DependencySource(
            type=DependencySourceType.TYPED_REQUIRED_CAPABILITY,
            source_ref=assessment.id,
            original_value=requirement.capability,
        )
        if key in grouped:
            grouped[key] = grouped[key].model_copy(
                update={
                    "provenance": DependencyProvenance(
                        sources=[*grouped[key].provenance.sources, source]
                    )
                }
            )
        else:
            grouped[key] = CanonicalAssessmentDependency(
                capability_ref=normalized_value,
                dependency_role=AssessmentDependencyRole.REQUIRED_CAPABILITY,
                provenance=DependencyProvenance(sources=[source]),
                objective_ids=list(requirement.objective_ids),
                status=AssessmentDependencyStatus.CONFIRMED,
            )
    for candidate in dependency_candidates:
        if not set(candidate.required_for_refs) & (
            set(assessment.objective_ids) | {assessment.id}
        ):
            continue
        normalized_value = normalize_capability_text(candidate.capability)
        key = (normalized_value, AssessmentDependencyRole.SUPPORTING_DEPENDENCY)
        source = DependencySource(
            type=DependencySourceType.DEPENDENCY_CANDIDATE,
            source_ref=assessment.id,
            original_value=candidate.capability,
        )
        if key in grouped:
            grouped[key] = grouped[key].model_copy(
                update={
                    "provenance": DependencyProvenance(
                        sources=[*grouped[key].provenance.sources, source]
                    )
                }
            )
        else:
            grouped[key] = CanonicalAssessmentDependency(
                capability_ref=normalized_value,
                dependency_role=AssessmentDependencyRole.SUPPORTING_DEPENDENCY,
                provenance=DependencyProvenance(sources=[source]),
                objective_ids=list(assessment.objective_ids),
                status=AssessmentDependencyStatus.CANDIDATE,
            )
    return CanonicalAssessmentDependencies(
        assessment_id=assessment.id,
        dependencies=list(grouped.values()),
        findings=findings,
    )
