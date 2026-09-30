"""Evaluation-only deterministic evidence gate for EXT-03A.10.

The gate evaluates only the statement references selected by Stage 2.  It is
not a second extraction pass and never searches the rest of a CV for rescue
evidence.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.extraction.capability_taxonomy import (
    TAXONOMY_ID,
    TAXONOMY_VERSION,
    TaxonomySelection,
    get_taxonomy,
    merge_taxonomy_selections,
)
from app.extraction.two_stage_capability_schema import ExperimentalCvFacts

GATE_ID = "capability_evidence_gate"
GATE_VERSION = "0.1"


class GateIntegrityError(ValueError):
    """Raised when a replay input cannot be safely evaluated."""


@dataclass(frozen=True)
class GateDecision:
    capability_id: str
    accepted: bool
    reason_code: str
    accepted_statement_ids: list[str]
    rejected_statement_ids: list[str]


@dataclass(frozen=True)
class GateReplayResult:
    accepted_capabilities: list[str]
    decisions: list[GateDecision]


@dataclass(frozen=True)
class GateRule:
    capability_id: str
    predicate: Callable[[str], tuple[bool, str]]


@dataclass(frozen=True)
class CapabilityEvidenceGateSet:
    gate_id: str
    version: str
    taxonomy_id: str
    taxonomy_version: str
    rules: tuple[GateRule, ...]


def _selection_metrics(selected_ids: list[str], expected_ids: list[str]) -> dict[str, float | int]:
    expected = set(expected_ids)
    selected = len(selected_ids)
    supported = sum(item in expected for item in selected_ids)
    precision = supported / selected if selected else 0.0
    recall = len(set(selected_ids) & expected) / len(expected) if expected else 0.0
    return {
        "selected": selected,
        "supported": supported,
        "unsupported": selected - supported,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def calculate_replay_metrics(
    *, before_ids: list[str], after_ids: list[str], expected_ids: list[str]
) -> dict[str, dict[str, float | int]]:
    """Calculate the same bounded before/after metrics for offline replay."""
    return {
        "before": _selection_metrics(before_ids, expected_ids),
        "after": _selection_metrics(after_ids, expected_ids),
    }


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _team_leadership(text: str) -> tuple[bool, str]:
    value = _normalise(text)
    if _matches(value, (r"\bmanaged?\s+(?:a\s+)?team\b", r"\bled\s+(?:a\s+)?team\b", r"\bsupervised?\s+(?:staff|employees|people)\b", r"\b(?:coached|mentored|hired|developed)\s+(?:team|staff|employees|people)\b", r"\bmanaged?\s+\d+\s+(?:direct reports?|people|employees)\b")):
        return True, "ACCEPT_DIRECT_ACTION"
    if _matches(value, (r"\bmanager\b", r"\bdirector\b", r"\bhead of\b")) and not _matches(value, (r"\bmanaged?\s+(?:a\s+)?team\b", r"\bled\s+(?:a\s+)?team\b")):
        return False, "REJECT_TITLE_ONLY"
    if _matches(value, (r"\bcross[- ]functional team", r"\bworked with (?:a )?team", r"\bcoordinated? with departments?")):
        return False, "REJECT_GENERIC_MANAGEMENT"
    return False, "REJECT_NO_DIRECT_EVIDENCE"


def _warehouse_management(text: str) -> tuple[bool, str]:
    value = _normalise(text)
    if _matches(value, (r"\bmanaged?\s+(?:the\s+)?warehouse", r"\bwarehouse\s+(?:operations?|process|strategy|workflow)", r"\binventory\s+(?:operations?|management|control)", r"\bfulfillment\s+operations?")):
        return True, "ACCEPT_OWNERSHIP"
    if _matches(value, (r"\bsales\b", r"\bdistribution\b", r"\bdeliver(?:y|ies)\b", r"\blogistics\b", r"\border(?:s| management)?\b")):
        return False, "REJECT_DOMAIN_ASSOCIATION"
    return False, "REJECT_NO_DIRECT_EVIDENCE"


def _digital_platform_development(text: str) -> tuple[bool, str]:
    value = _normalise(text)
    if _matches(value, (r"\b(?:built|designed|developed|implemented|launched)\b.*\b(?:platform|system|application|software)\b", r"\bplatform delivery\b")):
        return True, "ACCEPT_DIRECT_ACTION"
    if _matches(value, (r"\bused?\b", r"\badministrated?\b", r"\bshopify\b", r"\bsap\b", r"\bodoo\b", r"\berp\b")):
        return False, "REJECT_TOOL_ONLY"
    return False, "REJECT_NO_DIRECT_EVIDENCE"


def _process_optimization(text: str) -> tuple[bool, str]:
    value = _normalise(text)
    if _matches(value, (r"\b(?:optim(?:ized|ise)|redesigned|streamlined|improved|automated)\b", r"\breduced\s+(?:cycle time|processing time|errors?|cost)\b")):
        return True, "ACCEPT_OUTCOME"
    return False, "REJECT_NO_DIRECT_EVIDENCE"


def _product_management(text: str) -> tuple[bool, str]:
    value = _normalise(text)
    if _matches(value, (r"\bproduct\s+(?:roadmap|strategy|lifecycle|ownership)\b", r"\bprioriti[sz](?:ed|ation|ing)\b.*\bfeatures?\b", r"\bowned?\s+the\s+product\b")):
        return True, "ACCEPT_OWNERSHIP"
    if _matches(value, (r"\bsold?\b", r"\bselling\b", r"\bproduct catalog\b", r"\bused?\s+(?:a\s+)?product\b")):
        return False, "REJECT_DOMAIN_ASSOCIATION"
    return False, "REJECT_NO_DIRECT_EVIDENCE"


def _project_management(text: str) -> tuple[bool, str]:
    value = _normalise(text)
    if _matches(value, (r"\bproject\s+(?:planning|delivery|execution|management)\b", r"\bowned?\s+.*\bproject\b", r"\b(?:scope|timeline|resources?|stakeholders?)\b.*\bproject\b")):
        return True, "ACCEPT_OWNERSHIP"
    if _matches(value, (r"\bparticipated?\s+in\s+(?:a\s+)?project\b", r"\bproject\s+manager\b")):
        return False, "REJECT_NO_DIRECT_EVIDENCE"
    return False, "REJECT_NO_DIRECT_EVIDENCE"


def build_gate_set() -> CapabilityEvidenceGateSet:
    return CapabilityEvidenceGateSet(
        gate_id=GATE_ID,
        version=GATE_VERSION,
        taxonomy_id=TAXONOMY_ID,
        taxonomy_version=TAXONOMY_VERSION,
        rules=tuple(
            GateRule(capability_id=capability_id, predicate=predicate)
            for capability_id, predicate in (
                ("team_leadership", _team_leadership),
                ("warehouse_management", _warehouse_management),
                ("digital_platform_development", _digital_platform_development),
                ("process_optimization", _process_optimization),
                ("product_management", _product_management),
                ("project_management", _project_management),
            )
        ),
    )


def _statement_map(facts: ExperimentalCvFacts) -> dict[str, str]:
    return {
        statement.statement_id: statement.text
        for experience in facts.experiences
        for statement in experience.statements
    }


def _validate_integrity(
    capability_id: str,
    statement_ids: list[str],
    facts: ExperimentalCvFacts,
    gate_set: CapabilityEvidenceGateSet,
) -> dict[str, str]:
    taxonomy = get_taxonomy(gate_set.taxonomy_id, gate_set.taxonomy_version)
    known_capabilities = {item.id for item in taxonomy.capabilities}
    if capability_id not in known_capabilities:
        raise GateIntegrityError(f"unknown_capability_id:{capability_id}")
    statements = _statement_map(facts)
    missing = sorted(set(statement_ids) - statements.keys())
    if missing:
        raise GateIntegrityError(f"unknown_statement_ref:{missing[0]}")
    return statements


def gate_capability(
    capability_id: str,
    statement_ids: list[str],
    facts: ExperimentalCvFacts,
    gate_set: CapabilityEvidenceGateSet,
) -> GateDecision:
    statements = _validate_integrity(capability_id, statement_ids, facts, gate_set)
    rule = next((item for item in gate_set.rules if item.capability_id == capability_id), None)
    ordered_ids = list(dict.fromkeys(statement_ids))
    if rule is None:
        return GateDecision(capability_id, True, "NO_GATE_DEFINED", ordered_ids, [])

    accepted: list[str] = []
    rejected: list[str] = []
    reasons: list[str] = []
    for statement_id in ordered_ids:
        is_strong, reason = rule.predicate(statements[statement_id])
        reasons.append(reason)
        (accepted if is_strong else rejected).append(statement_id)
    if accepted:
        return GateDecision(capability_id, True, reasons[ordered_ids.index(accepted[0])], accepted, rejected)
    return GateDecision(capability_id, False, reasons[0] if reasons else "REJECT_NO_DIRECT_EVIDENCE", [], rejected)


def apply_capability_evidence_gate(
    selection: TaxonomySelection,
    facts: ExperimentalCvFacts,
    gate_set: CapabilityEvidenceGateSet,
) -> GateReplayResult:
    if selection.taxonomy_id != gate_set.taxonomy_id or selection.taxonomy_version != gate_set.taxonomy_version:
        raise GateIntegrityError("taxonomy_mismatch")
    merged = merge_taxonomy_selections(selection)
    decisions = [
        gate_capability(item.capability_id, item.supporting_statement_ids, facts, gate_set)
        for item in merged.capabilities
    ]
    return GateReplayResult(
        accepted_capabilities=[item.capability_id for item in decisions if item.accepted],
        decisions=decisions,
    )


def gate_set_artifact(gate_set: CapabilityEvidenceGateSet) -> dict[str, object]:
    definitions = {item.id: item for item in get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION).capabilities}
    return {
        "gate_id": gate_set.gate_id,
        "version": gate_set.version,
        "taxonomy_id": gate_set.taxonomy_id,
        "taxonomy_version": gate_set.taxonomy_version,
        "rules": [
            {
                "capability_id": rule.capability_id,
                "display_name": definitions[rule.capability_id].name,
                "status": "EXPLICIT_GATE",
            }
            for rule in gate_set.rules
        ],
        "pass_through": [
            item.id
            for item in get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION).capabilities
            if item.id not in {rule.capability_id for rule in gate_set.rules}
        ],
    }
