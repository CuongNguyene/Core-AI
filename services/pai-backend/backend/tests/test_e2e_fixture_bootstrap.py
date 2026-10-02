from uuid import UUID

from sqlalchemy import String

from app.extraction.models import ExtractionJobRecord
from scripts.bootstrap_e2e_fixtures import _document_id_for_persistence


def test_e2e_fixture_serializes_uuid_document_id_for_text_persistence() -> None:
    document_id = UUID("08b10000-0000-4000-8000-000000000005")

    assert isinstance(ExtractionJobRecord.__table__.c.document_id.type, String)
    assert _document_id_for_persistence(document_id) == str(document_id)
