"""Immutable contracts for explicitly selected domain knowledge packs."""

from dataclasses import dataclass
from typing import Protocol

from app.capability_analysis.semantic_core.contracts import EvidenceExpectation


@dataclass(frozen=True, slots=True)
class DomainPackReference:
    pack_id: str
    version: str


@dataclass(frozen=True, slots=True)
class DomainSemanticHints:
    """Normalization hints only; assessment status remains owned by the core."""

    concepts: tuple[str, ...]
    evidence_expectations: tuple[tuple[str, EvidenceExpectation], ...] = ()

    def expectation_for(self, concept: str) -> EvidenceExpectation:
        return next(
            (
                expectation
                for hinted_concept, expectation in self.evidence_expectations
                if hinted_concept == concept
            ),
            EvidenceExpectation.UNKNOWN,
        )


class DomainKnowledgePack(Protocol):
    @property
    def pack_id(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def supported_domain(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def schema_version(self) -> str: ...

    @property
    def checksum(self) -> str: ...

    def normalize_term(self, value: str) -> str: ...

    def expand_aliases(self, text: str) -> tuple[str, ...]: ...

    def map_requirement_phrase(self, phrase: str) -> DomainSemanticHints: ...

    def map_evidence_phrase(self, phrase: str) -> DomainSemanticHints: ...
