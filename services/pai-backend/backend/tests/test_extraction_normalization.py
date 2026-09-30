from app.extraction.normalization import canonicalize_entity, normalization_key


def test_pytorch_aliases_share_one_canonical_entity() -> None:
    assert canonicalize_entity("pytorch") == "PyTorch"
    assert canonicalize_entity("PyTorch framework") == "PyTorch"
    assert canonicalize_entity("torch") == "PyTorch"


def test_normalization_key_is_case_and_whitespace_insensitive() -> None:
    assert normalization_key("  FastAPI   framework ") == "fastapi framework"


def test_unknown_entity_keeps_original_display_value() -> None:
    assert canonicalize_entity("Custom Internal Tool") == "Custom Internal Tool"
