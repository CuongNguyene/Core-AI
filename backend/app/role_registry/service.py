from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.documents.repository import DocumentRepository
from app.documents.schemas import DocumentKind, StoredDocument
from app.extraction.repository import ExtractionRepository
from app.extraction.schemas import DocumentKind as ExtractionDocumentKind
from app.extraction.schemas import ExtractionJob, JobStatus
from app.role_registry.repository import RoleRegistryRepository
from app.role_registry.schemas import (
    CreateRoleRequest,
    Role,
    RoleJDVersion,
    RoleSummary,
    UpdateRoleRequest,
)


class RoleRegistryService:
    def __init__(
        self,
        repository: RoleRegistryRepository,
        documents: DocumentRepository | None = None,
        extraction: ExtractionRepository | None = None,
    ) -> None:
        self._repository = repository
        self._documents = documents
        self._extraction = extraction

    async def create_role(
        self, organization_id: UUID, actor_id: UUID, request: CreateRoleRequest
    ) -> Role:
        roles = await self._repository.search_roles(organization_id, None)
        role = Role(
            id=uuid4(),
            organization_id=organization_id,
            role_code=f"ROLE-{len(roles) + 1:06d}",
            title=request.title,
            description=request.description,
            created_by=actor_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return await self._repository.create_role(role)

    async def get_role(self, organization_id: UUID, role_id: UUID) -> Role:
        role = await self._repository.get_role(role_id, organization_id)
        if role is None:
            raise KeyError(role_id)
        return role

    async def update_role(
        self, organization_id: UUID, role_id: UUID, request: UpdateRoleRequest
    ) -> Role:
        role = await self.get_role(organization_id, role_id)
        return await self._repository.update_role(
            role.model_copy(
                update={
                    "title": request.title if request.title is not None else role.title,
                    "description": request.description
                    if request.description is not None
                    else role.description,
                    "status": request.status if request.status is not None else role.status,
                    "updated_at": datetime.now(UTC),
                }
            )
        )

    async def search_roles(self, organization_id: UUID, query: str | None) -> list[RoleSummary]:
        return await self._repository.search_roles(organization_id, query)

    async def attach_document_as_jd_version(
        self, role_id: UUID, document: StoredDocument
    ) -> RoleJDVersion:
        role = await self._repository.get_role(role_id, document.organization_id)
        if role is None:
            raise PermissionError("Document and Role must share the same organization")
        if document.kind is not DocumentKind.JD or not document.is_extractable():
            raise ValueError("Document is not an extractable JD")
        existing = await self._repository.get_document_jd_version(document.id)
        if existing is not None:
            raise ValueError("Document is already attached")
        versions = await self._repository.list_jd_versions(role_id)
        role_jd_id = versions[0].role_jd_id if versions else uuid4()
        version = RoleJDVersion(
            id=uuid4(),
            role_jd_id=role_jd_id,
            role_id=role_id,
            version=(versions[0].version + 1) if versions else 1,
            document_id=document.id,
            created_by=document.owner_actor_id,
            created_at=datetime.now(UTC),
        )
        created = await self._repository.create_jd_version(version)
        if self._extraction is not None:
            existing_job = await self._extraction.get_latest_job_for_document(
                str(document.id), ExtractionDocumentKind.JD
            )
            if existing_job is None:
                await self._extraction.enqueue(
                    ExtractionJob(
                        id=str(uuid4()),
                        document_id=str(document.id),
                        document_kind=ExtractionDocumentKind.JD,
                        owner_actor_id=document.owner_actor_id,
                        # extraction_jobs.correlation_id is legacy VARCHAR(36); the
                        # version UUID itself is a durable, bounded correlation value.
                        correlation_id=str(created.id),
                        status=JobStatus.QUEUED,
                    )
                )
        return created

    async def list_jd_versions(self, role_id: UUID, organization_id: UUID) -> list[RoleJDVersion]:
        await self.get_role(organization_id, role_id)
        return await self._repository.list_jd_versions(role_id)
