import asyncio
import io
import secrets
from typing import Protocol
from uuid import UUID


class DocumentBlobStore(Protocol):
    async def put(self, object_key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, object_key: str) -> bytes: ...

    async def delete(self, object_key: str) -> None: ...


def object_key_for(document_id: UUID, actor_id: UUID, original_filename: str) -> str:
    """Use random opaque storage keys; input names and actor IDs never become keys."""
    del actor_id, original_filename
    return f"documents/{document_id}/{secrets.token_hex(16)}"


class InMemoryDocumentBlobStore:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        del content_type
        self._objects[object_key] = bytes(content)

    async def get(self, object_key: str) -> bytes:
        return self._objects[object_key]

    async def delete(self, object_key: str) -> None:
        self._objects.pop(object_key, None)


class MinioDocumentBlobStore:
    """Async boundary around the synchronous MinIO client."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        from minio import Minio

        self._bucket = bucket
        self._client = Minio(
            endpoint.removeprefix("http://").removeprefix("https://"),
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    async def put(self, object_key: str, content: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            object_key,
            io.BytesIO(content),
            len(content),
            content_type=content_type,
        )

    async def get(self, object_key: str) -> bytes:
        response = await asyncio.to_thread(self._client.get_object, self._bucket, object_key)
        try:
            return await asyncio.to_thread(response.read)
        finally:
            response.close()
            response.release_conn()

    async def delete(self, object_key: str) -> None:
        await asyncio.to_thread(self._client.remove_object, self._bucket, object_key)
