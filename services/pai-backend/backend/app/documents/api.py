import hashlib
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.documents.repository import DocumentRepository
from app.documents.safety import DocumentSafetyInspector
from app.documents.schemas import DocumentKind, DocumentStatus, StoredDocument
from app.documents.storage import DocumentBlobStore, object_key_for
from app.extraction.auth import DevelopmentActor, get_development_actor
from app.shared.config import Settings
from app.shared.errors import APIError

router = APIRouter(tags=["documents"])

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _normalize_content_type(content_type: str | None, filename: str | None) -> str:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized not in {"", "application/octet-stream"}:
        return normalized
    if (filename or "").lower().endswith(".docx"):
        return DOCX_CONTENT_TYPE
    return normalized


def _repository(request: Request) -> DocumentRepository:
    repository = getattr(request.app.state, "document_repository", None)
    if repository is None:
        raise APIError(503, "document_service_unavailable", "Document service is not ready.")
    return cast(DocumentRepository, repository)


def _blob_store(request: Request) -> DocumentBlobStore:
    store = getattr(request.app.state, "document_blob_store", None)
    if store is None:
        raise APIError(503, "document_storage_unavailable", "Document storage is not ready.")
    return cast(DocumentBlobStore, store)


def _inspector(request: Request) -> DocumentSafetyInspector:
    inspector = getattr(request.app.state, "document_safety_inspector", None)
    if inspector is None:
        raise APIError(503, "document_scanner_unavailable", "Document scanner is not ready.")
    return cast(DocumentSafetyInspector, inspector)


@router.post("/documents", response_model=StoredDocument, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_kind: DocumentKind = Form(...),
    actor: DevelopmentActor = Depends(get_development_actor),
) -> StoredDocument:
    settings = cast(Settings, request.app.state.settings)
    content_type = _normalize_content_type(file.content_type, file.filename)
    content = await file.read(settings.document_max_bytes + 1)
    if not await _inspector(request).inspect(content, content_type, document_kind):
        raise APIError(415, "document_format_rejected", "Document format or safety checks failed.")

    now = datetime.now(UTC)
    document_id = uuid4()
    document = StoredDocument(
        id=document_id,
        owner_actor_id=actor.actor_id,
        organization_id=actor.organization_id,
        kind=document_kind,
        content_type=content_type,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        object_key=object_key_for(document_id, actor.actor_id, file.filename or "document"),
        status=DocumentStatus.QUARANTINED,
        retention_until=now + timedelta(days=settings.document_retention_days),
        created_at=now,
    )
    await _blob_store(request).put(document.object_key, content, content_type)
    await _repository(request).create(document)
    return await _repository(request).mark_status(document.id, DocumentStatus.CLEAN)
