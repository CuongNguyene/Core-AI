from app.learning.repository import SqlAlchemyLearningPathRepository
from scripts.bootstrap_e2e_fixtures import (
    HISTORICAL_LEARNING_PATH_ID,
    _historical_learning_path_record,
    fixture_manifest,
)


def test_fixture_manifest_exposes_jd_and_role_profile_workspace_ids_without_secrets() -> None:
    manifest = fixture_manifest()

    assert manifest["acceptedJdProfileId"] == "e2e-jd-profile-08b1"
    assert manifest["roleProfileDraftId"] == "e2e-role-profile-draft-08b1"
    assert manifest["roleProfileDraftRoleId"] == "08b10000-0000-4000-8000-000000000002"
    assert manifest["roleProfileDraftJdVersionId"] == "08b10000-0000-4000-8000-000000000004"
    assert manifest["historicalLearningPathId"] == HISTORICAL_LEARNING_PATH_ID
    assert all("password" not in key.lower() and "token" not in key.lower() for key in manifest)


def test_historical_learning_path_fixture_is_readable_by_the_existing_projection() -> None:
    path = SqlAlchemyLearningPathRepository._from_record(_historical_learning_path_record())

    assert path.id == HISTORICAL_LEARNING_PATH_ID
    assert path.version == 1
    assert path.source_type.value == "capability_analysis"
    assert path.capability_analysis_id == "cap-demo-08b1-historical"
    assert str(path.subject_id) == "00000000-0000-0000-0000-000000000004"
    assert path.source_gap_ids
