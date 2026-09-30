import re

_CANONICAL_ALIASES = {
    "pytorch": "PyTorch",
    "pytorch framework": "PyTorch",
    "torch": "PyTorch",
    "torch framework": "PyTorch",
}


def canonicalize_entity(value: str) -> str:
    """Return a stable display name without changing source evidence."""
    cleaned = _collapse_whitespace(value)
    return _CANONICAL_ALIASES.get(_alias_key(cleaned), cleaned)


def normalization_key(value: str) -> str:
    """Return the comparison key used for evidence deduplication."""
    return _alias_key(canonicalize_entity(value))


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _alias_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
