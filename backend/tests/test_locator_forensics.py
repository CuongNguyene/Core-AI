from app.extraction.chunking import TextChunk
from app.extraction.fixtures import FixtureDocument
from app.extraction.locator_forensics import collect_locator_forensics
from app.extraction.schemas import DocumentKind, SectionType
from app.extraction.worker import ExtractionWorker


def _chunk(text: str) -> TextChunk:
    return TextChunk(
        ordinal=3,
        section_type=SectionType.UNKNOWN,
        text=text,
        start_offset=4000,
        end_offset=4000 + len(text),
    )


def test_forensics_separates_whitespace_probe_without_resolving() -> None:
    chunk = _chunk("Built  internal APIs")
    document = FixtureDocument(document_id="doc-1", kind=DocumentKind.CV, content=chunk.text)

    result = collect_locator_forensics(
        chunk,
        document,
        "Built internal APIs",
        provider_input_text=chunk.text,
    )

    assert result["raw_match_count"] == 0
    assert result["diagnostic_matches"]["whitespace"]["matched"] is True
    assert result["diagnostic_matches"]["whitespace"]["match_count"] == 1
    assert result["locator_status"] == "unresolved"
    assert result["failure_class"] == "WHITESPACE"


def test_forensics_marks_wrong_text_representation() -> None:
    chunk = _chunk("Built APIs")
    document = FixtureDocument(document_id="doc-2", kind=DocumentKind.CV, content=chunk.text)

    result = collect_locator_forensics(
        chunk,
        document,
        "Missing excerpt",
        provider_input_text="Different text sent to model",
    )

    assert result["provider_input_text_hash"] != result["locator_source_text_hash"]
    assert result["failure_class"] == "WRONG_TEXT_REPRESENTATION"


def test_worker_writes_forensics_only_to_explicit_debug_directory(tmp_path) -> None:
    worker = ExtractionWorker(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        locator_forensics_enabled=True,
        locator_forensics_dir=str(tmp_path),
    )

    worker._write_locator_forensics("job-1", [{"model_source_excerpt": "private text"}])

    artifact = (tmp_path / "job-1.json").read_text(encoding="utf-8")
    assert '"job_id": "job-1"' in artifact
    assert "private text" in artifact
