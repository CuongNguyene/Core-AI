from app.course_catalog.fixtures import internal_course_catalog
from app.course_catalog.providers import MockExternalProvider
from app.course_catalog.schemas import CourseAvailability, CourseSourceType


def test_internal_catalog_is_deterministic_and_domain_neutral() -> None:
    first = internal_course_catalog()
    second = internal_course_catalog()

    assert first == second
    assert len(first) == 24
    assert {item.source_type for item in first} == {CourseSourceType.INTERNAL}
    assert {item.source_system for item in first} == {"frappe_lms"}
    assert {item.provenance[0].kind for item in first} <= {"source_fact", "manual_mapping"}
    assert {item.course_ref.split(":", 2)[1].rsplit("-", 1)[0] for item in first} >= {
        "software",
        "sales",
        "finance",
        "hr",
    }


def test_external_provider_is_deterministic_and_has_stable_lookup() -> None:
    provider = MockExternalProvider()

    first = provider.list_courses()
    second = provider.list_courses()

    assert first == second
    assert len(first) == 24
    assert all(item.provider_ref == "mock_provider" for item in first)
    assert provider.get_course("external-software-001") == first[0]


def test_catalogs_include_availability_and_learning_variation() -> None:
    internal = internal_course_catalog()
    external = MockExternalProvider().list_courses()

    assert any(item.availability is CourseAvailability.UNAVAILABLE for item in internal)
    assert any(item.availability is CourseAvailability.UNKNOWN for item in external)
    assert {item.delivery_mode for item in internal} >= {"self_paced", "instructor_led"}
    assert any(item.prerequisites for item in internal)
    assert any(item.target_level is None for item in internal)


def test_external_provider_does_not_make_network_or_model_calls() -> None:
    provider = MockExternalProvider()

    assert provider.list_courses()
    assert provider.network_calls == 0
    assert provider.model_calls == 0
