"""Exact versioned registry for explicitly referenced domain packs."""

from collections.abc import Iterable

from app.capability_analysis.domain_packs.contracts import (
    DomainKnowledgePack,
    DomainPackReference,
)


class DomainPackUnavailableError(ValueError):
    code = "domain_pack_unavailable"

    def __init__(self, pack_reference: DomainPackReference) -> None:
        self.pack_reference = pack_reference
        super().__init__(
            f"Domain knowledge pack is unavailable: "
            f"{pack_reference.pack_id}@{pack_reference.version}"
        )


class DomainPackRegistry:
    def __init__(self, packs: Iterable[DomainKnowledgePack] = ()) -> None:
        self._packs: dict[tuple[str, str], DomainKnowledgePack] = {}
        for pack in packs:
            key = (pack.pack_id, pack.version)
            if key in self._packs:
                raise ValueError(f"Duplicate domain knowledge pack: {pack.pack_id}@{pack.version}")
            self._packs[key] = pack

    def resolve(self, reference: DomainPackReference) -> DomainKnowledgePack:
        try:
            return self._packs[(reference.pack_id, reference.version)]
        except KeyError as exc:
            raise DomainPackUnavailableError(reference) from exc

    def has_pack_id(self, pack_id: str) -> bool:
        return any(key[0] == pack_id for key in self._packs)

    def resolve_ordered(
        self,
        references: Iterable[DomainPackReference],
    ) -> tuple[DomainKnowledgePack, ...]:
        return tuple(self.resolve(reference) for reference in references)
