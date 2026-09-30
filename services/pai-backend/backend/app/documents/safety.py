import asyncio
import struct
from contextlib import suppress
from io import BytesIO
from typing import Protocol
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader

from app.documents.parser import prepare_pdf_parser_input
from app.documents.schemas import DocumentKind


class DocumentSafetyInspector(Protocol):
    async def inspect(self, content: bytes, content_type: str, kind: DocumentKind) -> bool: ...


class DevelopmentDocumentSafetyInspector:
    """Development gate; replace with a malware scanner before production upload."""

    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes

    async def inspect(self, content: bytes, content_type: str, kind: DocumentKind) -> bool:
        if not content or len(content) > self._max_bytes:
            return False
        if kind is DocumentKind.CV or kind is DocumentKind.JD:
            if content_type == "application/pdf":
                return self._inspect_pdf(content)
            if (
                content_type
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                try:
                    with ZipFile(BytesIO(content)) as archive:
                        return "word/document.xml" in archive.namelist()
                except BadZipFile:
                    return False
        return False

    @staticmethod
    def _inspect_pdf(content: bytes) -> bool:
        try:
            parser_input, _ = prepare_pdf_parser_input(content)
        except ValueError:
            return False
        try:
            return bool(PdfReader(BytesIO(parser_input)).pages)
        except Exception:
            return False


class ClamAvDocumentSafetyInspector:
    """Production scanner that fails closed when ClamAV cannot scan a document."""

    def __init__(
        self,
        *,
        max_bytes: int,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> None:
        self._format_gate = DevelopmentDocumentSafetyInspector(max_bytes)
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds

    async def inspect(self, content: bytes, content_type: str, kind: DocumentKind) -> bool:
        if not await self._format_gate.inspect(content, content_type, kind):
            return False
        return await self._scan(content)

    async def _scan(self, content: bytes) -> bool:
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout_seconds,
            )
            writer.write(b"zINSTREAM\0")
            writer.write(struct.pack("!I", len(content)))
            writer.write(content)
            writer.write(struct.pack("!I", 0))
            await asyncio.wait_for(writer.drain(), timeout=self._timeout_seconds)
            response = await asyncio.wait_for(
                reader.readuntil(b"\0"), timeout=self._timeout_seconds
            )
            return response.rstrip(b"\0").endswith(b": OK")
        except (OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
            return False
        finally:
            if writer is not None:
                writer.close()
                with suppress(OSError):
                    await writer.wait_closed()
