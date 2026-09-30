from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_configuration_uses_project_script_directory() -> None:
    config = Config("alembic.ini")

    assert config.get_main_option("script_location") == "alembic"
    script_location = config.get_main_option("script_location")
    assert script_location is not None
    assert Path(script_location).is_dir()


def test_alembic_has_current_course_authoring_revision() -> None:
    config = Config("alembic.ini")

    assert ScriptDirectory.from_config(config).get_current_head() == "20260916_46"


def test_candidate_profile_governance_migration_is_additive_and_bounded() -> None:
    revision = Path(
        "alembic/versions/20260916_43_candidate_profile_governance_version.py"
    ).read_text()

    assert 'down_revision: str | Sequence[str] | None = "20260916_42"' in revision
    assert '"governance_version"' in revision
    assert '"uq_candidate_profile_governance_version"' in revision
    assert "current_profile_id = NULL" in revision
    assert 'drop_column("candidate_profiles", "profile_version")' not in revision


def test_capability_portfolio_owner_migration_handles_existing_rows() -> None:
    revision = Path("alembic/versions/20260806_16_capability_gap_portfolio_owner.py").read_text()

    assert 'sa.Column("owner_actor_id", sa.String(length=36), nullable=True)' in revision
    assert 'sa.Column("correlation_id", sa.String(length=64), nullable=True)' in revision


def test_candidate_domain_migration_contains_all_relationship_tables() -> None:
    revision = Path("alembic/versions/20260818_26_candidate_domain.py").read_text()

    assert 'down_revision: str | None = "20260818_25"' in revision
    for table in (
        '"candidates"',
        '"candidate_documents"',
        '"candidate_profiles"',
        '"candidate_claims"',
        '"candidate_evidence"',
    ):
        assert f'op.create_table(\n        {table}' in revision


def test_candidate_review_idempotency_migration_is_additive() -> None:
    revision = Path("alembic/versions/20260818_27_candidate_review_idempotency.py").read_text()

    assert 'down_revision: str | None = "20260818_26"' in revision
    assert '"candidate_review_actions"' in revision
    assert '"idempotency_key"' in revision
