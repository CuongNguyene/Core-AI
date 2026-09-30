from uuid import UUID

from app.documents.parser import parse_document, parse_pdf_pages
from app.documents.repository import DocumentRepository
from app.documents.schemas import DocumentKind as StoredDocumentKind
from app.documents.storage import DocumentBlobStore
from app.extraction.fixtures import FixtureDocument, FixtureDocumentSource
from app.extraction.schemas import DocumentKind, SourceLocator


class CompositeDocumentSource:
    """Resolves deterministic fixtures or eligible stored documents."""

    def __init__(
        self,
        documents: DocumentRepository,
        blobs: DocumentBlobStore,
        fixtures: FixtureDocumentSource | None = None,
    ) -> None:
        self._documents = documents
        self._blobs = blobs
        self._fixtures = fixtures or FixtureDocumentSource.default()

    async def get(self, document_id: str, kind: DocumentKind) -> FixtureDocument:
        if document_id.startswith("fixture-"):
            return self._fixtures.get(document_id, kind)
        try:
            stored_kind = StoredDocumentKind(kind.value)
            stored = await self._documents.get_extractable(UUID(document_id), stored_kind)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("document_not_extractable") from exc
        content = await self._blobs.get(stored.object_key)
        page_texts = parse_pdf_pages(content) if stored.content_type == "application/pdf" else None
        return FixtureDocument(
            document_id=document_id,
            kind=kind,
            content=parse_document(content, stored.content_type),
            content_type=stored.content_type,
            raw_bytes=content,
            page_count=len(page_texts) if page_texts is not None else None,
            page_texts=page_texts,
        )

    def locate(self, document: FixtureDocument, excerpt: str) -> SourceLocator:
        return self._fixtures.locate(document, excerpt)
