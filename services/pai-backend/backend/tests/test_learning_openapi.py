from app.main import create_app


def test_learning_routes_are_in_openapi() -> None:
    paths = create_app().openapi()["paths"]

    assert "/learning-paths" in paths
    assert "/learning-paths/{path_id}" in paths
    assert "/learning-paths/{path_id}/supersede" in paths
