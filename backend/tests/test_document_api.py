import asyncio
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from docx import Document
from httpx import ASGITransport, AsyncClient

from app.authorization.fixtures import LEARNER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.documents.parser import parse_document
from app.documents.repository import InMemoryDocumentRepository
from app.documents.safety import ClamAvDocumentSafetyInspector, DevelopmentDocumentSafetyInspector
from app.documents.schemas import DocumentKind
from app.documents.storage import InMemoryDocumentBlobStore
from app.main import create_app


def _docx_bytes() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", "<w:document/>")
    return output.getvalue()


def test_docx_parser_returns_normalized_text() -> None:
    payload = BytesIO()
    document = Document()
    document.add_paragraph("Backend Engineer")
    document.save(payload)

    assert (
        parse_document(
            payload.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        == "Backend Engineer"
    )


def test_upload_docx_returns_safe_quarantined_metadata() -> None:
    async def scenario() -> None:
        app = create_app()
        app.state.subject_repository = InMemorySubjectRepository.fixture()
        app.state.document_repository = InMemoryDocumentRepository()
        app.state.document_blob_store = InMemoryDocumentBlobStore()
        app.state.document_safety_inspector = DevelopmentDocumentSafetyInspector(1024 * 1024)
        app.state.settings.document_retention_days = 30
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents",
                headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
                files={
                    "file": (
                        "candidate-private.docx",
                        _docx_bytes(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                data={"document_kind": "cv"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "clean"
        assert "candidate-private" not in response.text
        assert "object_key" in body

    asyncio.run(scenario())


def test_upload_docx_accepts_generic_browser_mime_type() -> None:
    async def scenario() -> None:
        app = create_app()
        app.state.subject_repository = InMemorySubjectRepository.fixture()
        app.state.document_repository = InMemoryDocumentRepository()
        app.state.document_blob_store = InMemoryDocumentBlobStore()
        app.state.document_safety_inspector = DevelopmentDocumentSafetyInspector(1024 * 1024)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents",
                headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
                files={"file": ("candidate.docx", _docx_bytes(), "application/octet-stream")},
                data={"document_kind": "cv"},
            )

        assert response.status_code == 201
        assert response.json()["content_type"] == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    asyncio.run(scenario())


def test_upload_rejects_unsupported_content_without_persisting_document() -> None:
    async def scenario() -> None:
        repository = InMemoryDocumentRepository()
        app = create_app()
        app.state.subject_repository = InMemorySubjectRepository.fixture()
        app.state.document_repository = repository
        app.state.document_blob_store = InMemoryDocumentBlobStore()
        app.state.document_safety_inspector = DevelopmentDocumentSafetyInspector(1024 * 1024)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents",
                headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
                files={"file": ("bad.txt", b"not a document", "text/plain")},
                data={"document_kind": "jd"},
            )

        assert response.status_code == 415
        assert await repository.get(uuid4()) is None

    asyncio.run(scenario())


def test_clamav_scanner_accepts_clean_docx_and_rejects_infected_response() -> None:
    async def scenario() -> None:
        responses = iter((b"stream: OK\0", b"stream: Eicar-Test-Signature FOUND\0"))

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            assert await reader.readuntil(b"\0") == b"zINSTREAM\0"
            while True:
                length = int.from_bytes(await reader.readexactly(4), "big")
                if length == 0:
                    break
                await reader.readexactly(length)
            writer.write(next(responses))
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        try:
            port = server.sockets[0].getsockname()[1]
            scanner = ClamAvDocumentSafetyInspector(
                max_bytes=1024 * 1024,
                host="127.0.0.1",
                port=port,
                timeout_seconds=1,
            )
            content = _docx_bytes()
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            assert await scanner.inspect(content, content_type, DocumentKind.CV) is True
            assert await scanner.inspect(content, content_type, DocumentKind.CV) is False
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())
