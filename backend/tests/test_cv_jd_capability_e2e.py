from pathlib import Path

import pytest

from scripts.run_cv_jd_capability_e2e import (
    E2EConfig,
    E2EPreflightError,
    assert_scenario,
    validate_e2e_inputs,
)


def test_e2e_preflight_checks_both_operator_file_hashes(tmp_path: Path) -> None:
    cv = tmp_path / "candidate.pdf"
    jd = tmp_path / "role.pdf"
    cv.write_bytes(b"cv bytes")
    jd.write_bytes(b"jd bytes")
    config = E2EConfig(
        api_base_url="http://testserver",
        cv_path=cv,
        cv_sha256="0" * 64,
        jd_path=jd,
        jd_sha256="0" * 64,
    )

    with pytest.raises(E2EPreflightError, match="CV sha256 mismatch"):
        validate_e2e_inputs(config)


def test_e2e_asserts_preview_and_official_modes_without_final_decision() -> None:
    base = {
        "id": "portfolio-1",
        "current_role": {
            "usage_mode": "preview",
            "target_type": "current_role",
            "assessments": [],
            "gaps": [],
        },
    }
    assert_scenario(base, "preview")
    base["current_role"]["usage_mode"] = "official"
    assert_scenario(base, "official")
    base["readiness_score"] = 0.8
    with pytest.raises(AssertionError, match="combined decision"):
        assert_scenario(base, "official")
