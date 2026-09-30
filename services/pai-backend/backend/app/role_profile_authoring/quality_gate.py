import re
from collections import Counter, defaultdict

from app.matching.schemas import RequirementClassification, RoleRequirement
from app.role_profile_authoring.schemas import (
    ApprovalEligibility,
    QualityFindingSeverity,
    QualityGateResult,
    RequirementFinding,
    SummaryFinding,
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def evaluate_role_profile_draft(
    requirements: list[RoleRequirement],
    *,
    source_jd_profile_id: str | None,
    source_jd_profile_version: int | None,
    source_schema: str | None,
    source_version: str | None,
) -> tuple[QualityGateResult, list[RequirementFinding], ApprovalEligibility]:
    findings = [
        *_structural_findings(requirements),
        *_source_chain_findings(
            requirements,
            source_jd_profile_id=source_jd_profile_id,
            source_jd_profile_version=source_jd_profile_version,
            source_schema=source_schema,
            source_version=source_version,
        ),
        *_legacy_authoring_findings(requirements, source_schema),
    ]
    summary_findings = aggregate_requirement_findings(findings)
    has_blocking = any(item.severity is QualityFindingSeverity.BLOCKING for item in findings)
    active_ready = not findings
    return (
        QualityGateResult(passed=active_ready, summary_findings=summary_findings),
        findings,
        ApprovalEligibility(
            can_create_draft=True,
            can_approve_provisional=not has_blocking,
            can_approve_active=active_ready,
        ),
    )


def validate_role_profile_requirements(requirements: list[RoleRequirement]) -> QualityGateResult:
    """Validate standalone requirements; draft validation also checks provenance."""
    findings = _structural_findings(requirements)
    return QualityGateResult(
        passed=not findings,
        summary_findings=aggregate_requirement_findings(findings),
    )


def aggregate_requirement_findings(findings: list[RequirementFinding]) -> list[SummaryFinding]:
    grouped: dict[tuple[str, QualityFindingSeverity, str], list[RequirementFinding]] = defaultdict(list)
    for finding in findings:
        grouped[(finding.code, finding.severity, finding.message)].append(finding)
    return [
        SummaryFinding(
            code=code,
            severity=severity,
            affected_requirement_count=len({item.requirement_id for item in items}),
            affected_requirement_ids=_affected_ids(items),
            message=message,
        )
        for (code, severity, message), items in sorted(grouped.items())
    ]


def _affected_ids(findings: list[RequirementFinding]) -> list[str] | None:
    ids = sorted({item.requirement_id for item in findings if item.requirement_id is not None})
    return ids or None


def _structural_findings(requirements: list[RoleRequirement]) -> list[RequirementFinding]:
    findings: list[RequirementFinding] = []
    if not requirements:
        findings.append(_finding(None, "no_requirements", QualityFindingSeverity.BLOCKING, None))
    counts = Counter(item.id for item in requirements)
    for item in requirements:
        if not _IDENTIFIER.fullmatch(item.id):
            findings.append(_finding(item.id, "invalid_requirement_id", QualityFindingSeverity.ERROR, "id"))
        if not item.evidence_terms:
            findings.append(_finding(item.id, "empty_evidence_terms", QualityFindingSeverity.ERROR, "evidence_terms"))
        if not 0 <= item.confidence_threshold <= 1:
            findings.append(_finding(item.id, "invalid_threshold", QualityFindingSeverity.ERROR, "confidence_threshold"))
        if not item.assessment_recommendation.strip():
            findings.append(_finding(item.id, "empty_recommendation", QualityFindingSeverity.ERROR, "assessment_recommendation"))
        if not item.rubric_version.strip():
            findings.append(_finding(item.id, "empty_rubric_version", QualityFindingSeverity.ERROR, "rubric_version"))
        if item.modality == "responsibility" and item.criterion_dimension is not None:
            findings.append(
                _finding(
                    item.id,
                    "responsibility_dimension_must_be_null",
                    QualityFindingSeverity.ERROR,
                    "criterion_dimension",
                )
            )
        elif item.criterion_dimension is None and item.modality not in {
            "responsibility",
            "unspecified",
        }:
            findings.append(
                _finding(
                    item.id,
                    "missing_criterion_dimension",
                    QualityFindingSeverity.ERROR,
                    "criterion_dimension",
                )
            )
    if any(count > 1 for count in counts.values()):
        findings.append(_finding(None, "duplicate_requirement_id", QualityFindingSeverity.ERROR, "id"))
    return findings


def _source_chain_findings(
    requirements: list[RoleRequirement],
    *,
    source_jd_profile_id: str | None,
    source_jd_profile_version: int | None,
    source_schema: str | None,
    source_version: str | None,
) -> list[RequirementFinding]:
    if not source_jd_profile_id or not source_jd_profile_version or not source_schema or not source_version:
        return [_finding(None, "legacy_missing_provenance", QualityFindingSeverity.BLOCKING, "source_chain")]
    findings: list[RequirementFinding] = []
    for requirement in requirements:
        if requirement.source_requirement_ref is None:
            findings.append(
                _finding(requirement.id, "legacy_missing_provenance", QualityFindingSeverity.BLOCKING, "source_requirement_ref")
            )
        if requirement.source_locator is None:
            findings.append(
                _finding(requirement.id, "legacy_missing_provenance", QualityFindingSeverity.BLOCKING, "source_locator")
            )
    return findings


def _legacy_authoring_findings(
    requirements: list[RoleRequirement], source_schema: str | None
) -> list[RequirementFinding]:
    if source_schema != "legacy_v1":
        return []
    findings: list[RequirementFinding] = []
    for requirement in requirements:
        for code, field, value in (
            ("legacy_missing_modality", "modality", requirement.modality),
            ("legacy_missing_logical_group", "logical_group", requirement.logical_group),
            ("legacy_missing_target_level", "target_level", requirement.target_level),
            ("legacy_missing_observable_behavior", "observable_behaviors", requirement.observable_behaviors),
            ("legacy_missing_evidence_constraints", "evidence_constraints", requirement.evidence_constraints),
        ):
            if not value:
                findings.append(_finding(requirement.id, code, QualityFindingSeverity.WARNING, field))
        if requirement.classification is RequirementClassification.UNCLASSIFIED:
            findings.append(
                _finding(requirement.id, "legacy_uncertain_priority", QualityFindingSeverity.WARNING, "classification")
            )
    return findings


def _finding(
    requirement_id: str | None,
    code: str,
    severity: QualityFindingSeverity,
    field: str | None,
) -> RequirementFinding:
    return RequirementFinding(
        requirement_id=requirement_id,
        code=code,
        severity=severity,
        field=field,
        message=_message(code),
    )


def _message(code: str) -> str:
    return {
        "legacy_missing_provenance": "Source chain must be preserved before approval.",
        "legacy_missing_modality": "Modality requires reviewer authoring.",
        "legacy_missing_logical_group": "Logical grouping requires reviewer authoring.",
        "legacy_missing_target_level": "Target level requires reviewer authoring.",
        "legacy_missing_observable_behavior": "Observable behavior requires reviewer authoring.",
        "legacy_missing_evidence_constraints": "Evidence constraints require reviewer authoring.",
        "legacy_uncertain_priority": "Legacy source does not establish requirement priority.",
        "missing_criterion_dimension": "Candidate-evaluable requirements require a criterion dimension.",
        "responsibility_dimension_must_be_null": "Responsibilities must not be scored as candidate dimensions.",
    }.get(code, code.replace("_", " ") + ".")
