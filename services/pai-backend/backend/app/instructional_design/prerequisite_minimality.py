"""Deterministic integrity checks for model-proposed prerequisite dispositions."""

from collections import defaultdict
from collections.abc import Sequence

from app.instructional_design.schemas import (
    DesignFinding,
    DesignFindingSeverity,
    PrerequisiteBasis,
    PrerequisiteDisposition,
    PrerequisiteSpec,
    PrerequisiteStatus,
)


def validate_prerequisite_dispositions(
    prerequisites: Sequence[PrerequisiteSpec],
) -> list[DesignFinding]:
    """Validate provenance/governance without judging pedagogical truth."""

    findings: list[DesignFinding] = []
    by_source: defaultdict[str, set[PrerequisiteDisposition]] = defaultdict(set)
    for item in prerequisites:
        if item.disposition is None:
            continue
        if not item.source_dependency_refs:
            findings.append(DesignFinding(
                code="prerequisite_disposition_provenance_missing",
                severity=DesignFindingSeverity.ERROR,
                entity_type="prerequisite",
                entity_id=item.id,
                field="source_dependency_refs",
                message="Every prerequisite disposition must reference its source dependency.",
            ))
        for source_ref in item.source_dependency_refs:
            by_source[source_ref].add(item.disposition)
        if item.disposition is PrerequisiteDisposition.ENTRY_PREREQUISITE and not (item.rationale or "").strip():
            findings.append(DesignFinding(
                code="prerequisite_entry_rationale_missing",
                severity=DesignFindingSeverity.WARNING,
                entity_type="prerequisite",
                entity_id=item.id,
                field="rationale",
                message="An entry prerequisite candidate must explain why it is required before course entry.",
            ))
        if item.basis is PrerequisiteBasis.MODEL_PROPOSED and item.status is not PrerequisiteStatus.CANDIDATE:
            findings.append(DesignFinding(
                code="prerequisite_disposition_auto_confirmation",
                severity=DesignFindingSeverity.BLOCKING,
                entity_type="prerequisite",
                entity_id=item.id,
                field="status",
                message="Model-proposed prerequisite dispositions cannot be auto-confirmed.",
            ))
    for source_ref, dispositions in by_source.items():
        if len(dispositions) > 1:
            findings.append(DesignFinding(
                code="prerequisite_disposition_conflict",
                severity=DesignFindingSeverity.ERROR,
                entity_type="dependency_candidate",
                entity_id=source_ref,
                field="disposition",
                message="A source dependency has contradictory prerequisite dispositions.",
            ))
    return sorted(findings, key=lambda finding: (finding.code, finding.entity_id or ""))
