from collections.abc import Awaitable
from typing import Protocol

from pydantic import BaseModel

from app.extraction.schemas import DocumentKind, SourceLocator


class FixtureDocument(BaseModel):
    document_id: str
    kind: DocumentKind
    content: str
    content_type: str | None = None
    raw_bytes: bytes | None = None
    page_count: int | None = None
    page_texts: list[str] | None = None


class DocumentSource(Protocol):
    def get(
        self, document_id: str, kind: DocumentKind
    ) -> FixtureDocument | Awaitable[FixtureDocument]: ...


class FixtureDocumentSource:
    """Only simulated, non-PII documents are available to the PR-004 slice."""

    def __init__(self, documents: list[FixtureDocument]) -> None:
        self._documents = {document.document_id: document for document in documents}

    @classmethod
    def default(cls) -> "FixtureDocumentSource":
        return cls(
            [
                FixtureDocument(
                    document_id="fixture-cv-basic",
                    kind=DocumentKind.CV,
                    content=(
                        "Profile\n"
                        "Skills: Python, FastAPI\n"
                        "Experience: Built internal APIs with Python.\n"
                        "Education: Bachelor of Engineering."
                    ),
                ),
                FixtureDocument(
                    document_id="fixture-jd-basic",
                    kind=DocumentKind.JD,
                    content=(
                        "Role: Backend Engineer\n"
                        "Requirements: Python and FastAPI experience.\n"
                        "Responsibilities: Build reliable internal APIs.\n"
                        "Qualifications: Engineering degree."
                    ),
                ),
            ]
        )

    def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        document = self._documents.get(document_id)
        if document is None or document.kind is not kind:
            raise KeyError(document_id)
        return document

    def locate(self, document: FixtureDocument, excerpt: str) -> SourceLocator:
        start_offset = document.content.index(excerpt)
        return SourceLocator(
            document_id=document.document_id,
            section=self._section_for(document, start_offset),
            start_offset=start_offset,
            end_offset=start_offset + len(excerpt),
        )

    @staticmethod
    def _section_for(document: FixtureDocument, start_offset: int) -> str:
        preceding = document.content[:start_offset]
        return preceding.rsplit("\n", maxsplit=1)[-1].split(":", maxsplit=1)[0].lower() or "profile"
