from app.extraction.fixture_integrity import fingerprint_bytes


def test_pdf_fingerprint_is_safe_and_contains_no_document_content() -> None:
    fingerprint = fingerprint_bytes(
        fixture_name="reference.pdf",
        document_id="doc-1",
        storage_key="documents/doc-1/object",
        filename="reference.pdf",
        mime_type="application/pdf",
        content=b"%PDF-1.4\n%%EOF",
        page_count=1,
        input_mode="native_pdf",
    )

    assert fingerprint.file_size == 14
    assert len(fingerprint.sha256) == 64
    assert fingerprint.page_count == 1
    assert "PDF-1.4" not in fingerprint.model_dump_json()
