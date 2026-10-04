"""Synthetic catalogs used by contract and future recommendation tests."""

from app.course_catalog.schemas import (
    CourseAvailability,
    CourseCapability,
    CourseCapabilityProfile,
    CoursePrerequisite,
    CourseProfileStatus,
    CourseProvenance,
    CourseSourceType,
    CoverageType,
    ExternalCourse,
)

_COURSES = (
    ("software", "Python Foundations", "python", "beginner", "self_paced"),
    ("software", "API Design Basics", "api-design", "intermediate", "instructor_led"),
    ("software", "Data Modeling", "data-modeling", "intermediate", "self_paced"),
    ("software", "Secure Coding", "secure-coding", "advanced", "instructor_led"),
    ("software", "Testing Practices", "testing", None, "self_paced"),
    ("software", "Cloud Operations", "cloud-operations", "advanced", "self_paced"),
    ("sales", "Consultative Selling", "consultative-selling", "beginner", "instructor_led"),
    ("sales", "Pipeline Management", "pipeline-management", "intermediate", "self_paced"),
    ("sales", "Negotiation", "negotiation", "advanced", "instructor_led"),
    ("sales", "Customer Discovery", "customer-discovery", "beginner", "self_paced"),
    ("sales", "Account Planning", "account-planning", "intermediate", "self_paced"),
    ("sales", "Sales Coaching", "sales-coaching", None, "instructor_led"),
    ("finance", "Accounting Essentials", "accounting", "beginner", "self_paced"),
    ("finance", "Financial Reporting", "financial-reporting", "intermediate", "instructor_led"),
    ("finance", "Budgeting", "budgeting", "intermediate", "self_paced"),
    ("finance", "Risk Controls", "risk-controls", "advanced", "instructor_led"),
    ("finance", "Spreadsheet Analysis", "spreadsheet-analysis", "beginner", "self_paced"),
    ("finance", "Management Accounting", "management-accounting", None, "instructor_led"),
    ("hr", "Active Listening", "active-listening", "beginner", "self_paced"),
    ("hr", "Structured Interviewing", "structured-interviewing", "intermediate", "instructor_led"),
    ("hr", "Feedback Conversations", "feedback", "intermediate", "self_paced"),
    ("hr", "Conflict Resolution", "conflict-resolution", "advanced", "instructor_led"),
    ("hr", "Facilitation", "facilitation", None, "self_paced"),
    ("hr", "People Operations", "people-operations", "advanced", "instructor_led"),
)


def _provenance(course_ref: str, kind: str = "manual_mapping") -> CourseProvenance:
    return CourseProvenance(
        kind=kind,
        source_ref=course_ref,
        source_field="course_metadata",
        method="synthetic_fixture",
    )


def internal_course_catalog() -> tuple[CourseCapabilityProfile, ...]:
    profiles: list[CourseCapabilityProfile] = []
    for index, (domain, title, capability, level, delivery_mode) in enumerate(_COURSES, start=1):
        course_ref = f"frappe_lms:{domain}-{index:03d}"
        capabilities = [
            CourseCapability(
                capability_ref=f"capability:{capability}",
                coverage_type=CoverageType.DIRECT,
                target_level=level,
                provenance=[_provenance(course_ref)],
            )
        ]
        if index % 6 == 0:
            capabilities.append(
                CourseCapability(
                    capability_ref=f"capability:{domain}-foundations",
                    coverage_type=CoverageType.SUPPORTING,
                    target_level=None,
                    provenance=[_provenance(course_ref)],
                )
            )
        prerequisites = (
            [
                CoursePrerequisite(
                    kind="capability",
                    ref=f"capability:{domain}-foundations",
                    provenance=[_provenance(course_ref, "source_fact")],
                )
            ]
            if index % 4 == 0
            else []
        )
        profiles.append(
            CourseCapabilityProfile(
                id=f"course-profile:{domain}-{index:03d}",
                version=1,
                course_ref=course_ref,
                source_type=CourseSourceType.INTERNAL,
                source_system="frappe_lms",
                title_snapshot=title,
                description_snapshot=f"Synthetic {domain} course for contract tests.",
                capabilities=capabilities,
                prerequisites=prerequisites,
                duration_minutes=45 + (index % 5) * 30,
                delivery_mode=delivery_mode,
                language="en",
                availability=(
                    CourseAvailability.UNAVAILABLE if index == 24 else CourseAvailability.AVAILABLE
                ),
                status=CourseProfileStatus.ACTIVE,
                provenance=[_provenance(course_ref, "source_fact")],
            )
        )
    return tuple(profiles)


def external_course_catalog() -> tuple[ExternalCourse, ...]:
    courses: list[ExternalCourse] = []
    for index, (domain, title, _capability, _level, delivery_mode) in enumerate(_COURSES, start=1):
        provider_course_id = f"external-{domain}-{index:03d}"
        courses.append(
            ExternalCourse(
                provider_ref="mock_provider",
                provider_course_id=provider_course_id,
                title=title,
                description=f"Synthetic external {domain} course for contract tests.",
                duration_minutes=60 + (index % 4) * 45,
                delivery_mode=delivery_mode,
                language="en",
                availability=(
                    CourseAvailability.UNKNOWN if index == 24 else CourseAvailability.AVAILABLE
                ),
                course_url=f"https://example.invalid/courses/{provider_course_id}",
                provenance=[_provenance(provider_course_id, "provider_metadata")],
            )
        )
    return tuple(courses)
