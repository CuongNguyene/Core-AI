"""Safe, content-free fingerprints for extraction fixture verification."""

import hashlib

from pydantic import BaseModel, ConfigDict, Field


class SafeDocumentFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    fixture_name: str
    document_id: str
    storage_key: str
    filename: str
    mime_type: str
    file_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int | None = Field(default=None, ge=0)
    input_mode: str


def fingerprint_bytes(
    *,
    fixture_name: str,
    document_id: str,
    storage_key: str,
    filename: str,
    mime_type: str,
    content: bytes,
    page_count: int | None,
    input_mode: str,
) -> SafeDocumentFingerprint:
    return SafeDocumentFingerprint(
        fixture_name=fixture_name,
        document_id=document_id,
        storage_key=storage_key,
        filename=filename,
        mime_type=mime_type,
        file_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        page_count=page_count,
        input_mode=input_mode,
    )
