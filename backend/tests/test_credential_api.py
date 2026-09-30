from app.main import create_app


def test_credential_routes_are_registered_with_safe_verification_endpoint() -> None:
    paths = create_app().openapi()["paths"]

    assert "/credential-requests" in paths
    assert "/credential-requests/{request_id}/approve" in paths
    assert "/credentials/{credential_id}/verify" in paths
