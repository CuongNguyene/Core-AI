from pydantic import BaseModel, ConfigDict, Field

from app.extraction.normalization import canonicalize_entity, normalization_key


class NormalizedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    original_value: str = Field(min_length=1)
    canonical_value: str = Field(min_length=1)
    normalization_key: str = Field(min_length=1)


def normalize_entity(value: str) -> NormalizedEntity:
    canonical = canonicalize_entity(value)
    return NormalizedEntity(
        original_value=value,
        canonical_value=canonical,
        normalization_key=normalization_key(value),
    )
