from typing import Protocol
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.role_registry.models import RoleJDRecord, RoleJDVersionRecord, RoleRecord
from app.role_registry.schemas import Role, RoleJD, RoleJDVersion, RoleStatus, RoleSummary


class RoleRegistryRepository(Protocol):
    async def create_role(self, role: Role) -> Role: ...
    async def get_role(self, role_id: UUID, organization_id: UUID) -> Role | None: ...
    async def update_role(self, role: Role) -> Role: ...
    async def search_roles(self, organization_id: UUID, query: str | None) -> list[RoleSummary]: ...
    async def create_jd_version(self, version: RoleJDVersion) -> RoleJDVersion: ...
    async def list_jd_versions(self, role_id: UUID) -> list[RoleJDVersion]: ...
    async def get_document_jd_version(self, document_id: UUID) -> RoleJDVersion | None: ...
    async def get_jd_version(self, version_id: UUID) -> RoleJDVersion | None: ...


class InMemoryRoleRegistryRepository:
    def __init__(self) -> None:
        self.roles: dict[UUID, Role] = {}
        self.jds: dict[UUID, RoleJD] = {}
        self.versions: dict[UUID, RoleJDVersion] = {}

    async def create_role(self, role: Role) -> Role:
        self.roles[role.id] = role
        return role

    async def get_role(self, role_id: UUID, organization_id: UUID) -> Role | None:
        role = self.roles.get(role_id)
        return role if role and role.organization_id == organization_id else None

    async def update_role(self, role: Role) -> Role:
        self.roles[role.id] = role
        return role

    async def search_roles(self, organization_id: UUID, query: str | None) -> list[RoleSummary]:
        needle = query.casefold() if query else None
        results = []
        for role in self.roles.values():
            if role.organization_id != organization_id:
                continue
            if needle and needle not in f"{role.role_code} {role.title}".casefold():
                continue
            versions = [item for item in self.versions.values() if item.role_id == role.id]
            results.append(
                RoleSummary(
                    id=role.id,
                    organization_id=role.organization_id,
                    role_code=role.role_code,
                    title=role.title,
                    status=role.status,
                    jd_version_count=len(versions),
                    current_jd_version=max((item.version for item in versions), default=None),
                )
            )
        return sorted(results, key=lambda item: item.role_code)

    async def create_jd_version(self, version: RoleJDVersion) -> RoleJDVersion:
        if any(item.document_id == version.document_id for item in self.versions.values()):
            raise ValueError("Document is already attached")
        self.versions[version.id] = version
        return version

    async def list_jd_versions(self, role_id: UUID) -> list[RoleJDVersion]:
        return sorted(
            (item for item in self.versions.values() if item.role_id == role_id),
            key=lambda item: item.version,
            reverse=True,
        )

    async def get_document_jd_version(self, document_id: UUID) -> RoleJDVersion | None:
        return next((item for item in self.versions.values() if item.document_id == document_id), None)

    async def get_jd_version(self, version_id: UUID) -> RoleJDVersion | None:
        return self.versions.get(version_id)


class SqlAlchemyRoleRegistryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_role(self, role: Role) -> Role:
        async with self._session_factory() as session, session.begin():
            session.add(
                RoleRecord(
                    id=role.id,
                    organization_id=role.organization_id,
                    role_code=role.role_code,
                    title=role.title,
                    description=role.description,
                    status=role.status.value,
                    created_by=role.created_by,
                    created_at=role.created_at,
                    updated_at=role.updated_at,
                    active_role_profile_id=role.active_role_profile_id,
                )
            )
        return role

    async def get_role(self, role_id: UUID, organization_id: UUID) -> Role | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(RoleRecord).where(
                    RoleRecord.id == role_id, RoleRecord.organization_id == organization_id
                )
            )
            return _role(record) if record else None

    async def update_role(self, role: Role) -> Role:
        async with self._session_factory() as session, session.begin():
            record = await session.get(RoleRecord, role.id, with_for_update=True)
            if record is None or record.organization_id != role.organization_id:
                raise KeyError(role.id)
            record.title = role.title
            record.description = role.description
            record.status = role.status.value
            record.active_role_profile_id = role.active_role_profile_id
            record.updated_at = role.updated_at
        return role

    async def search_roles(self, organization_id: UUID, query: str | None) -> list[RoleSummary]:
        async with self._session_factory() as session:
            statement = select(RoleRecord).where(RoleRecord.organization_id == organization_id)
            if query:
                pattern = f"%{query}%"
                statement = statement.where(
                    or_(RoleRecord.role_code.ilike(pattern), RoleRecord.title.ilike(pattern))
                )
            records = list((await session.scalars(statement.order_by(RoleRecord.role_code))).all())
            results: list[RoleSummary] = []
            for record in records:
                versions = list(
                    (
                        await session.scalars(
                            select(RoleJDVersionRecord)
                            .join(RoleJDRecord, RoleJDRecord.id == RoleJDVersionRecord.role_jd_id)
                            .where(RoleJDRecord.role_id == record.id)
                        )
                    ).all()
                )
                results.append(
                    RoleSummary(
                        id=record.id,
                        organization_id=record.organization_id,
                        role_code=record.role_code,
                        title=record.title,
                        status=RoleStatus(record.status),
                        jd_version_count=len(versions),
                        current_jd_version=max((item.version for item in versions), default=None),
                    )
                )
            return results

    async def create_jd_version(self, version: RoleJDVersion) -> RoleJDVersion:
        async with self._session_factory() as session, session.begin():
            role_jd = await session.scalar(
                select(RoleJDRecord)
                .where(RoleJDRecord.role_id == version.role_id)
                .with_for_update()
            )
            if role_jd is None:
                role_jd = RoleJDRecord(id=version.role_jd_id, role_id=version.role_id)
                session.add(role_jd)
                await session.flush()
            if role_jd.id != version.role_jd_id:
                raise ValueError("Role JD identity mismatch")
            existing = await session.scalar(
                select(RoleJDVersionRecord).where(RoleJDVersionRecord.document_id == version.document_id)
            )
            if existing is not None:
                raise ValueError("Document is already attached")
            next_version = await session.scalar(
                select(func.max(RoleJDVersionRecord.version)).where(
                    RoleJDVersionRecord.role_jd_id == role_jd.id
                )
            )
            version = version.model_copy(
                update={"role_jd_id": role_jd.id, "version": (next_version or 0) + 1}
            )
            session.add(
                RoleJDVersionRecord(
                    id=version.id,
                    role_jd_id=version.role_jd_id,
                    version=version.version,
                    document_id=version.document_id,
                    created_by=version.created_by,
                    created_at=version.created_at,
                )
            )
        return version

    async def list_jd_versions(self, role_id: UUID) -> list[RoleJDVersion]:
        async with self._session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(RoleJDVersionRecord)
                        .join(RoleJDRecord, RoleJDRecord.id == RoleJDVersionRecord.role_jd_id)
                        .where(RoleJDRecord.role_id == role_id)
                        .order_by(RoleJDVersionRecord.version.desc())
                    )
                ).all()
            )
            return [
                RoleJDVersion(
                    id=row.id,
                    role_jd_id=row.role_jd_id,
                    role_id=role_id,
                    version=row.version,
                    document_id=row.document_id,
                    created_by=row.created_by,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def get_document_jd_version(self, document_id: UUID) -> RoleJDVersion | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RoleJDVersionRecord).where(RoleJDVersionRecord.document_id == document_id)
            )
            if row is None:
                return None
            role_id = await session.scalar(
                select(RoleJDRecord.role_id).where(RoleJDRecord.id == row.role_jd_id)
            )
            if role_id is None:
                return None
            return RoleJDVersion(
                id=row.id,
                role_jd_id=row.role_jd_id,
                role_id=role_id,
                version=row.version,
                document_id=row.document_id,
                created_by=row.created_by,
                created_at=row.created_at,
            )

    async def get_jd_version(self, version_id: UUID) -> RoleJDVersion | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RoleJDVersionRecord).where(RoleJDVersionRecord.id == version_id)
            )
            if row is None:
                return None
            role_id = await session.scalar(
                select(RoleJDRecord.role_id).where(RoleJDRecord.id == row.role_jd_id)
            )
            if role_id is None:
                return None
            return RoleJDVersion(
                id=row.id,
                role_jd_id=row.role_jd_id,
                role_id=role_id,
                version=row.version,
                document_id=row.document_id,
                created_by=row.created_by,
                created_at=row.created_at,
            )


def _role(record: RoleRecord) -> Role:
    return Role(
        id=record.id,
        organization_id=record.organization_id,
        role_code=record.role_code,
        title=record.title,
        description=record.description,
        status=RoleStatus(record.status),
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        active_role_profile_id=record.active_role_profile_id,
    )
