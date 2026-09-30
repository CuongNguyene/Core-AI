from dataclasses import dataclass

import pytest

from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    EvidenceSemantics,
    EvidenceSourceKind,
    RequirementSemantics,
    SemanticConstraint,
    SemanticConstraintDimension,
    SemanticConstraintOperator,
    SemanticContext,
)
from app.capability_analysis.semantic_core.retrieval import assess_retrieval, retrieve_candidates
from app.semantic_policy.repository import InMemorySemanticPolicyRepository
from app.semantic_policy.schemas import SemanticPolicy, SemanticPolicyRef, SemanticPolicyStatus
from app.semantic_policy.service import SemanticPolicyResolver


@dataclass(frozen=True)
class FixtureDomainPack:
    pack_id: str
    version: str
    phrases: dict[str, str]
    checksum: str
    status: str = "active"
    schema_version: str = "fixture-v1"
    supported_domain: str = "fixture"

    def normalize_term(self, value: str) -> str:
        return self.phrases.get(value.casefold(), value.casefold())

    def expand_aliases(self, text: str) -> tuple[str, ...]:
        return (self.normalize_term(text),)

    def map_requirement_phrase(self, phrase: str):
        from app.capability_analysis.domain_packs.contracts import DomainSemanticHints

        return DomainSemanticHints(concepts=(self.normalize_term(phrase),))

    def map_evidence_phrase(self, phrase: str):
        return self.map_requirement_phrase(phrase)


def _policy(policy_id: str, pack: FixtureDomainPack) -> SemanticPolicy:
    return SemanticPolicy(
        policy_id=policy_id,
        version="1",
        status=SemanticPolicyStatus.ACTIVE,
        domain_pack_id=pack.pack_id,
        domain_pack_version=pack.version,
        domain_pack_checksum=pack.checksum,
        description=f"{pack.supported_domain} fixture policy",
    )


def _requirement(
    requirement_id: str,
    concept: str,
    expectation: EvidenceExpectation,
    constraints: tuple[SemanticConstraint, ...] = (),
) -> RequirementSemantics:
    return RequirementSemantics(
        requirement_id=requirement_id,
        concepts=(concept,),
        behaviors=(),
        objects=(),
        constraints=constraints,
        evidence_expectation=expectation,
        source_requirement_ref=requirement_id,
        source_locator=None,
        provenance=(("fixture", requirement_id),),
        unresolved_fields=(),
    )


def _evidence(
    evidence_ref: str,
    concept: str,
    source_kind: EvidenceSourceKind,
    context: SemanticContext,
    participation: str | None = None,
) -> EvidenceSemantics:
    return EvidenceSemantics(
        evidence_ref=evidence_ref,
        concepts=(concept,),
        behaviors=(),
        objects=(),
        context=context,
        participation=participation,
        source_kind=source_kind,
        confidence=0.95,
        original_evidence_type="fixture",
        source_locator=None,
        source_value=concept,
        source_excerpt="deterministic accepted-extraction-equivalent evidence",
        provenance=(("fixture", evidence_ref),),
        unresolved_fields=(),
    )


@pytest.mark.asyncio
async def test_accounting_policy_e2e_preserves_education_practice_and_credential_context() -> None:
    pack = FixtureDomainPack(
        "accounting",
        "1",
        {
            "bachelor of accounting": "accounting_degree",
            "bachelor degree in accounting or finance": "accounting_degree",
            "studied ifrs": "ifrs_reporting",
            "prepared monthly financial statements": "ifrs_reporting",
            "cpa": "cpa",
        },
        "sha256:accounting-v1",
    )
    resolver = SemanticPolicyResolver(
        InMemorySemanticPolicyRepository([_policy("accounting-policy", pack)]),
        (pack,),
    )
    resolved = await resolver.resolve(
        SemanticPolicyRef(policy_id="accounting-policy", policy_version="1"),
        target_id="accounting-role",
        target_type="current_role",
    )
    assert resolved.domain_pack_checksum == "sha256:accounting-v1"

    degree = _requirement(
        "degree",
        "accounting_degree",
        EvidenceExpectation.EDUCATION,
        (SemanticConstraint(
            dimension=SemanticConstraintDimension.SOURCE_KIND,
            operator=SemanticConstraintOperator.ONE_OF,
            values=(EvidenceSourceKind.EDUCATION.value,),
            source_field="fixture",
        ),),
    )
    degree_candidates = retrieve_candidates(
        degree,
        (_evidence("degree-education", "accounting_degree", EvidenceSourceKind.EDUCATION, SemanticContext.STUDIED),),
    )
    assert assess_retrieval(degree, degree_candidates, 0.8).status.value == "supported"

    practice = _requirement("ifrs-practice", "ifrs_reporting", EvidenceExpectation.DEMONSTRATED_USAGE)
    education_only = retrieve_candidates(
        practice,
        (_evidence("ifrs-education", "ifrs_reporting", EvidenceSourceKind.EDUCATION, SemanticContext.STUDIED),),
    )
    assert assess_retrieval(practice, education_only, 0.8).eligible_candidate_count == 0
    work = retrieve_candidates(
        practice,
        (_evidence("ifrs-work", "ifrs_reporting", EvidenceSourceKind.EMPLOYMENT, SemanticContext.USED_IN_EMPLOYMENT),),
    )
    assert assess_retrieval(practice, work, 0.8).status.value == "supported"

    credential = _requirement("cpa", "cpa", EvidenceExpectation.CREDENTIAL)
    credential_candidates = retrieve_candidates(
        credential,
        (_evidence("cpa-credential", "cpa", EvidenceSourceKind.CREDENTIAL, SemanticContext.CREDENTIALED),),
    )
    assert assess_retrieval(credential, credential_candidates, 0.8).status.value == "supported"


@pytest.mark.asyncio
async def test_sales_policy_e2e_keeps_assistance_separate_from_ownership() -> None:
    pack = FixtureDomainPack(
        "sales",
        "1",
        {
            "own enterprise deals end-to-end": "enterprise_deal",
            "supported senior account executive": "enterprise_deal",
            "owned sales cycle": "enterprise_deal",
        },
        "sha256:sales-v1",
    )
    resolver = SemanticPolicyResolver(
        InMemorySemanticPolicyRepository([_policy("sales-policy", pack)]),
        (pack,),
    )
    resolved = await resolver.resolve(
        SemanticPolicyRef(policy_id="sales-policy", policy_version="1"),
        target_id="sales-role",
        target_type="current_role",
    )
    assert resolved.domain_pack_id == "sales"

    ownership = _requirement(
        "ownership",
        "enterprise_deal",
        EvidenceExpectation.OWNED_OUTCOME,
        (SemanticConstraint(
            dimension=SemanticConstraintDimension.PARTICIPATION,
            operator=SemanticConstraintOperator.ONE_OF,
            values=("own", "owned", "led"),
            source_field="fixture",
        ),),
    )
    assisted = retrieve_candidates(
        ownership,
        (_evidence("assisted", "enterprise_deal", EvidenceSourceKind.EMPLOYMENT, SemanticContext.USED_IN_EMPLOYMENT, "assist"),),
    )
    assert assess_retrieval(ownership, assisted, 0.8).eligible_candidate_count == 0
    owned = retrieve_candidates(
        ownership,
        (_evidence("owned", "enterprise_deal", EvidenceSourceKind.EMPLOYMENT, SemanticContext.USED_IN_EMPLOYMENT, "owned"),),
    )
    assert assess_retrieval(ownership, owned, 0.8).status.value == "supported"
