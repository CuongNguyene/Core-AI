from app.main import create_app


def test_openapi_request_has_no_candidate_profile_or_role_payload() -> None:
    openapi = create_app().openapi()
    schema = openapi["components"]["schemas"]["CreateCapabilityGapAnalysisRequest"]

    assert set(schema["properties"]) == {
        "cv_profile_id",
        "current_target_profile_id",
        "future_target_profile_id",
        "correlation_id",
    }
    assert "/capability-gap-portfolios" in openapi["paths"]


def test_openapi_exposes_candidate_role_product_adapter() -> None:
    openapi = create_app().openapi()

    assert "/api/v1/integration/candidates/{candidate_id}/roles/{role_id}/capability-analyses" in openapi["paths"]
