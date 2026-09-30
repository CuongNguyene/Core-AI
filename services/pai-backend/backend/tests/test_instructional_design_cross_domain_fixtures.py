import pytest
from pydantic import ValidationError

from app.instructional_design.fixtures import (
    CrossDomainDifficulty,
    CrossDomainDomain,
    CrossDomainFixture,
    CrossDomainFixtureMetadata,
    CrossDomainIndustryFamily,
    CrossDomainLearningType,
    cross_domain_validation_fixtures,
)


def test_cross_domain_fixture_requires_domain_metadata() -> None:
    with pytest.raises(ValidationError, match="domain"):
        CrossDomainFixtureMetadata.model_validate(
            {
                "fixture_id": "missing-domain",
                "industry_family": "technology",
                "learning_type": "procedural_technical_skill",
                "difficulty": "medium",
                "description": "A fixture without its domain.",
            }
        )


def test_cross_domain_fixture_accepts_valid_controlled_metadata() -> None:
    metadata = CrossDomainFixtureMetadata(
        fixture_id="accounting_financial_reporting_basic",
        domain=CrossDomainDomain.ACCOUNTING,
        industry_family=CrossDomainIndustryFamily.FINANCE,
        learning_type=CrossDomainLearningType.REGULATED_PROFESSIONAL_SKILL,
        difficulty=CrossDomainDifficulty.MEDIUM,
        description="Prepare and analyze basic financial reports.",
    )

    assert metadata.domain is CrossDomainDomain.ACCOUNTING


def test_cross_domain_fixture_rejects_unsupported_learning_type() -> None:
    with pytest.raises(ValidationError, match="learning_type"):
        CrossDomainFixtureMetadata.model_validate(
            {
                "fixture_id": "unsupported-type",
                "domain": "accounting",
                "industry_family": "finance",
                "learning_type": "universal_soft_skill",
                "difficulty": "medium",
                "description": "An unsupported experiment category.",
            }
        )


def test_cross_domain_fixture_rejects_generated_content() -> None:
    fixture = cross_domain_validation_fixtures()["python_data_processing"]

    with pytest.raises(ValidationError, match="lessons"):
        CrossDomainFixture.model_validate(
            {
                **fixture.model_dump(mode="json"),
                "lessons": [{"id": "generated-lesson"}],
            }
        )


def test_initial_cross_domain_registry_has_five_brief_only_fixtures() -> None:
    fixtures = cross_domain_validation_fixtures()

    assert set(fixtures) == {
        "python_data_processing",
        "accounting_financial_reporting_basic",
        "legal_contract_review_basic",
        "hr_recruitment_planning_basic",
        "construction_drawing_and_method_basic",
    }
    assert all(set(item.model_dump()) == {"metadata", "brief"} for item in fixtures.values())
    assert {item.metadata.domain for item in fixtures.values()} == {
        CrossDomainDomain.IT_AI,
        CrossDomainDomain.ACCOUNTING,
        CrossDomainDomain.LEGAL_COMPLIANCE,
        CrossDomainDomain.HR_MANAGEMENT,
        CrossDomainDomain.CONSTRUCTION_ENGINEERING,
    }


def test_cross_domain_fixture_metadata_id_matches_registry_key() -> None:
    fixtures = cross_domain_validation_fixtures()

    assert all(key == item.metadata.fixture_id for key, item in fixtures.items())


def test_cross_domain_registry_exposes_controlled_analysis_matrix() -> None:
    fixtures = cross_domain_validation_fixtures()

    assert fixtures["python_data_processing"].metadata.learning_type is (
        CrossDomainLearningType.PROCEDURAL_TECHNICAL_SKILL
    )
    assert fixtures["accounting_financial_reporting_basic"].metadata.learning_type is (
        CrossDomainLearningType.REGULATED_PROFESSIONAL_SKILL
    )
    assert fixtures["legal_contract_review_basic"].metadata.difficulty is CrossDomainDifficulty.HIGH
    assert fixtures["hr_recruitment_planning_basic"].metadata.learning_type is (
        CrossDomainLearningType.SCENARIO_BASED_PROFESSIONAL_SKILL
    )
    assert fixtures["construction_drawing_and_method_basic"].metadata.learning_type is (
        CrossDomainLearningType.PROCEDURAL_SAFETY_SKILL
    )
