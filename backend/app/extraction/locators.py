from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_id: str = Field(min_length=1)
    section: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)

    @model_validator(mode="after")
    def require_increasing_offsets(self) -> "SourceLocator":
        if self.end_offset <= self.start_offset:
            raise ValueError("Source locator end offset must follow start offset")
        return self
