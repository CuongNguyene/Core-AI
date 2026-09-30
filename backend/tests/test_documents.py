import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from pypdf import PdfWriter

from app.documents.parser import parse_document, prepare_pdf_parser_input
from app.documents.safety import DevelopmentDocumentSafetyInspector
from app.documents.schemas import DocumentKind, DocumentStatus, StoredDocument
from app.documents.storage import InMemoryDocumentBlobStore, object_key_for


def test_object_key_is_opaque_and_does_not_contain_filename_or_actor() -> None:
    actor_id = uuid4()

    key = object_key_for(uuid4(), actor_id, "my CV – secret.pdf")

    assert "secret" not in key
    assert str(actor_id) not in key
    assert key.startswith("documents/")


def test_safety_inspector_accepts_pdf_and_docx_signatures() -> None:
    async def scenario() -> None:
        inspector = DevelopmentDocumentSafetyInspector(max_bytes=1024)
        docx = BytesIO()
        with ZipFile(docx, "w") as archive:
            archive.writestr("word/document.xml", "<w:document/>")

        pdf = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=10, height=10)
        writer.write(pdf)
        assert await inspector.inspect(
            b"\xef\xbb\xbf\n \t" + pdf.getvalue(), "application/pdf", DocumentKind.CV
        )
        assert await inspector.inspect(
            docx.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            DocumentKind.JD,
        )

    asyncio.run(scenario())


def test_safety_inspector_rejects_mismatched_or_oversized_content() -> None:
    async def scenario() -> None:
        inspector = DevelopmentDocumentSafetyInspector(max_bytes=4)

        assert not await inspector.inspect(b"not-pdf", "application/pdf", DocumentKind.CV)
        assert not await inspector.inspect(b"%PDF-1.7", "application/pdf", DocumentKind.CV)

    asyncio.run(scenario())


def test_safety_inspector_rejects_pdf_signature_without_parseable_document() -> None:
    async def scenario() -> None:
        inspector = DevelopmentDocumentSafetyInspector(max_bytes=1024)

        assert not await inspector.inspect(b"\n%PDF-1.7\nbody", "application/pdf", DocumentKind.CV)

    asyncio.run(scenario())


def test_pdf_parser_input_strips_bounded_prefix_without_mutating_raw_bytes() -> None:
    raw = b"\r\n \t%PDF-1.7\nbody"
    prepared, removed = prepare_pdf_parser_input(raw)

    assert prepared == b"%PDF-1.7\nbody"
    assert removed == 4
    assert raw == b"\r\n \t%PDF-1.7\nbody"


def test_pdf_parser_input_accepts_bom_and_whitespace() -> None:
    prepared, removed = prepare_pdf_parser_input(b"\xef\xbb\xbf\n%PDF-1.7")

    assert prepared == b"%PDF-1.7"
    assert removed == 4


def test_real_pdf_parser_accepts_prefixed_minimal_pdf() -> None:
    pdf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=10, height=10)
    writer.write(pdf)

    with pytest.raises(ValueError, match="document_text_empty"):
        parse_document(b"\n%PDF-" + pdf.getvalue().split(b"%PDF-", 1)[1], "application/pdf")


def test_pdf_parser_input_rejects_untrusted_prefix() -> None:
    with pytest.raises(ValueError, match="invalid_pdf_header"):
        prepare_pdf_parser_input(b"x" * 32 + b"%PDF-1.7")


def test_document_eligibility_requires_clean_and_non_expired() -> None:
    now = datetime.now(UTC)
    document = StoredDocument(
        id=uuid4(),
        owner_actor_id=uuid4(),
        organization_id=uuid4(),
        kind=DocumentKind.CV,
        content_type="application/pdf",
        byte_size=10,
        sha256="a" * 64,
        object_key="documents/opaque",
        status=DocumentStatus.CLEAN,
        retention_until=now + timedelta(days=1),
    )

    assert document.is_extractable(now)
    assert not document.model_copy(update={"status": DocumentStatus.QUARANTINED}).is_extractable(
        now
    )
    assert not document.model_copy(
        update={"retention_until": now - timedelta(seconds=1)}
    ).is_extractable(now)


def test_in_memory_blob_store_round_trip() -> None:
    async def scenario() -> None:
        store = InMemoryDocumentBlobStore()
        payload = b"%PDF-1.7\nfixture"

        await store.put("documents/opaque", payload, "application/pdf")

        assert await store.get("documents/opaque") == payload

    asyncio.run(scenario())
