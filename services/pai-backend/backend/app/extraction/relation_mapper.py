from app.extraction.evidence import EvidenceContext
from app.extraction.relation import RelationType


def map_relation_to_evidence_context(
    relation: RelationType | str,
    subject: str,
    object: str,
    section_type: str | None = None,
    source_excerpt: str | None = None,
) -> EvidenceContext:
    """Map an explicit relation to a conservative evidence context.

    Object text and section metadata are considered evidence hints, never
    permission to infer a stronger claim. Production is emitted only for an
    explicit deployment/production signal.
    """
    relation_value = relation.value if isinstance(relation, RelationType) else relation.casefold()
    context_text = " ".join(
        value.casefold() for value in (object, section_type or "", source_excerpt or "")
    )
    if relation_value == RelationType.OWNED.value:
        return EvidenceContext.OWNED_SYSTEM
    if relation_value == RelationType.LED.value:
        return EvidenceContext.LED_TEAM
    if relation_value == RelationType.STUDIED.value:
        return EvidenceContext.STUDIED
    if relation_value == RelationType.PUBLISHED.value:
        return EvidenceContext.MENTIONED
    if relation_value == RelationType.DEPLOYED.value:
        return (
            EvidenceContext.USED_IN_PRODUCTION
            if _contains_any(context_text, "production", "live", "serving", "deployed")
            else EvidenceContext.USED_IN_PROJECT
        )
    if relation_value in {RelationType.USED_IN.value, RelationType.WORKED_ON.value}:
        if _contains_any(context_text, "research project", "research work"):
            return EvidenceContext.USED_IN_RESEARCH
        if _contains_any(context_text, "project"):
            return EvidenceContext.USED_IN_PROJECT
        if _contains_any(context_text, "research", "academic", "thesis", "paper"):
            return EvidenceContext.USED_IN_RESEARCH
        return EvidenceContext.USED_IN_PROJECT
    return EvidenceContext.MENTIONED


def _contains_any(value: str, *terms: str) -> bool:
    return any(term in value for term in terms)
