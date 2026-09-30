import pytest

from app.extraction.stage1_reuse import (
    build_reusable_stage1_artifact,
    load_reusable_stage1_facts,
)
from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
)


def facts() -> ExperimentalCvFacts:
    return ExperimentalCvFacts(
        document_id="doc-1",
        experiences=[
            ExperimentalExperienceFact(
                experience_id="exp-1",
                role="Backend Engineer",
                statements=[
                    ExperimentalStatement(
                        statement_id="stmt-1",
                        text="Built internal APIs.",
                        document_id="doc-1",
                        page_number=1,
                    )
                ],
            )
        ],
    )


def test_stage1_reuse_artifact_requires_explicit_privacy_approval() -> None:
    with pytest.raises(ValueError, match="stage1_artifact_persistence_not_approved"):
        build_reusable_stage1_artifact(
            fixture_id="fixture-1",
            fixture_sha256="a" * 64,
            facts=facts(),
            privacy_approved=False,
        )


def test_reuse_rejects_fixture_checksum_mismatch() -> None:
    artifact = build_reusable_stage1_artifact(
        fixture_id="fixture-1",
        fixture_sha256="a" * 64,
        facts=facts(),
        privacy_approved=True,
    )
    with pytest.raises(ValueError, match="stage1_fixture_checksum_mismatch"):
        load_reusable_stage1_facts(
            artifact,
            fixture_id="fixture-1",
            fixture_sha256="b" * 64,
            page_count=1,
        )


def test_reuse_rejects_tampered_fact_identity() -> None:
    artifact = build_reusable_stage1_artifact(
        fixture_id="fixture-1",
        fixture_sha256="a" * 64,
        facts=facts(),
        privacy_approved=True,
    ).model_copy(update={"fact_identity": "0" * 64})
    with pytest.raises(ValueError, match="stage1_fact_identity_mismatch"):
        load_reusable_stage1_facts(
            artifact,
            fixture_id="fixture-1",
            fixture_sha256="a" * 64,
            page_count=1,
        )
