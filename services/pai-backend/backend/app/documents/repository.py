from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.documents.models import DocumentRecord
from app.documents.schemas import DocumentKind, DocumentStatus, StoredDocument


class DocumentRepository(Protocol):
    async def create(self, document: StoredDocument) -> StoredDocument: ...

    async def get(self, document_id: UUID) -> StoredDocument | None: ...

    async def mark_status(self, document_id: UUID, status: DocumentStatus) -> StoredDocument: ...

    async def get_extractable(self, document_id: UUID, kind: DocumentKind) -> StoredDocument: ...


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self._documents: dict[UUID, StoredDocument] = {}

    async def create(self, document: StoredDocument) -> StoredDocument:
        if document.id in self._documents:
            raise ValueError("Document already exists")
        self._documents[document.id] = document.model_copy(deep=True)
        return document.model_copy(deep=True)

    async def get(self, document_id: UUID) -> StoredDocument | None:
        document = self._documents.get(document_id)
        return document.model_copy(deep=True) if document else None

    async def mark_status(self, document_id: UUID, status: DocumentStatus) -> StoredDocument:
        document = self._documents[document_id]
        updated = document.model_copy(update={"status": status})
        self._documents[document_id] = updated
        return updated.model_copy(deep=True)

    async def get_extractable(self, document_id: UUID, kind: DocumentKind) -> StoredDocument:
        document = self._documents[document_id]
        now = datetime.now(UTC)
        if document.kind is not kind or not document.is_extractable(now):
            raise ValueError("Document is not eligible for extraction")
        return document.model_copy(deep=True)


class SqlAlchemyDocumentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, document: StoredDocument) -> StoredDocument:
        async with self._session_factory() as session, session.begin():
            session.add(self._to_record(document))
        return document.model_copy(deep=True)

    async def get(self, document_id: UUID) -> StoredDocument | None:
        async with self._session_factory() as session:
            record = await session.get(DocumentRecord, document_id)
            return self._from_record(record) if record is not None else None

    async def mark_status(self, document_id: UUID, status: DocumentStatus) -> StoredDocument:
        async with self._session_factory() as session, session.begin():
            record = await session.get(DocumentRecord, document_id, with_for_update=True)
            if record is None:
                raise KeyError(document_id)
            record.status = status.value
            return self._from_record(record)

    async def get_extractable(self, document_id: UUID, kind: DocumentKind) -> StoredDocument:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(DocumentRecord).where(
                    DocumentRecord.id == document_id,
                    DocumentRecord.document_kind == kind.value,
                    DocumentRecord.status == DocumentStatus.CLEAN.value,
                    DocumentRecord.retention_until > datetime.now(UTC),
                )
            )
            if record is None:
                raise ValueError("Document is not eligible for extraction")
            return self._from_record(record)

    @staticmethod
    def _to_record(document: StoredDocument) -> DocumentRecord:
        return DocumentRecord(
            id=document.id,
            owner_actor_id=document.owner_actor_id,
            organization_id=document.organization_id,
            document_kind=document.kind.value,
            content_type=document.content_type,
            byte_size=document.byte_size,
            sha256=document.sha256,
            object_key=document.object_key,
            status=document.status.value,
            retention_until=document.retention_until,
            created_at=document.created_at,
        )

    @staticmethod
    def _from_record(record: DocumentRecord) -> StoredDocument:
        return StoredDocument(
            id=record.id,
            owner_actor_id=record.owner_actor_id,
            organization_id=record.organization_id,
            kind=DocumentKind(record.document_kind),
            content_type=record.content_type,
            byte_size=record.byte_size,
            sha256=record.sha256,
            object_key=record.object_key,
            status=DocumentStatus(record.status),
            retention_until=record.retention_until,
            created_at=record.created_at,
        )
