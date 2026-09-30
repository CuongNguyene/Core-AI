"""Legacy IT/AI normalization vocabulary, frozen as domain pack ``it_ai@1``."""

import re
import unicodedata
from dataclasses import dataclass

from app.capability_analysis.domain_packs.contracts import DomainSemanticHints
from app.capability_analysis.semantic_core.contracts import EvidenceExpectation

_ALIASES: dict[str, str] = {
    "python": "python",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "nlp": "natural_language_processing",
    "natural language processing": "natural_language_processing",
    "kafka": "kafka",
    "apache kafka": "kafka",
    "spark": "spark",
    "apache spark": "spark",
    "ml": "machine_learning",
    "machine learning": "machine_learning",
    "dl": "deep_learning",
    "deep learning": "deep_learning",
    "computer science": "computer_science",
    "data science": "data_science",
    "khoa hoc du lieu": "data_science",
    "khoa hoc may tinh": "computer_science",
    "tri tue nhan tao": "artificial_intelligence",
    "docker": "docker",
    "kubernetes": "kubernetes",
    "mlops": "mlops",
    "ci/cd": "ci_cd",
    "model evaluation": "model_evaluation",
    "model design": "model_design",
    "model training": "model_training",
    "deployment": "deployment",
    "deploy": "deployment",
    "deployed": "deployment",
}


@dataclass(frozen=True, slots=True)
class ItAiDomainKnowledgePack:
    pack_id: str = "it_ai"
    version: str = "1"
    supported_domain: str = "information_technology_and_ai"
    status: str = "active"
    schema_version: str = "1"
    checksum: str = "sha256:it-ai-v1"

    def normalize_term(self, value: str) -> str:
        text = _clean(value)
        return _ALIASES.get(text, text.replace(" ", "_"))

    def expand_aliases(self, text: str) -> tuple[str, ...]:
        clean = _clean(text)
        concepts: set[str] = set()
        for alias, canonical in sorted(_ALIASES.items(), key=lambda item: -len(item[0])):
            if _contains_phrase(clean, alias):
                concepts.add(canonical)
        if re.search(
            r"\b(evaluat(?:e|ed|ing|ion)|benchmark(?:ed|ing)?)\b",
            clean,
        ) and re.search(r"\b(model|cnn|neural|machine learning|deep learning|ml|dl)\b", clean):
            concepts.add("model_evaluation")
        if re.search(r"\b(train(?:ed|ing)?|develop(?:ed|ing)?)\b", clean) and re.search(
            r"\b(model|cnn|neural|machine learning|deep learning|ml|dl)\b",
            clean,
        ):
            concepts.add("model_training")
        if re.search(
            r"\b(design(?:ed|ing)?|architect(?:ed|ure)?)\b",
            clean,
        ) and re.search(r"\b(model|cnn|neural|machine learning|deep learning|ml|dl)\b", clean):
            concepts.add("model_design")
        if clean in _ALIASES:
            concepts.add(_ALIASES[clean])
        return tuple(sorted(concepts))

    def map_requirement_phrase(self, phrase: str) -> DomainSemanticHints:
        concepts = self.expand_aliases(phrase)
        expectations = tuple(
            (concept, EvidenceExpectation.DEMONSTRATED_USAGE)
            for concept in concepts
            if concept == "docker"
        )
        return DomainSemanticHints(
            concepts=concepts,
            evidence_expectations=expectations,
        )

    def map_evidence_phrase(self, phrase: str) -> DomainSemanticHints:
        return DomainSemanticHints(concepts=self.expand_aliases(phrase))


def _clean(value: str) -> str:
    deaccented = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9+/]+", " ", deaccented).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


IT_AI_PACK = ItAiDomainKnowledgePack()
