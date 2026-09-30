from app.integration.schemas import CourseBlueprintV1


def development_course_blueprint() -> CourseBlueprintV1:
    """Return a safe, non-production blueprint for local adapter smoke tests."""
    return CourseBlueprintV1(
        blueprint_id="bp-python-001",
        version="1",
        title="Python Data Processing",
        summary="Development fixture for LMS projection tests.",
        estimated_duration_minutes=45,
        objectives=[
            {
                "objective_ref": "obj-001",
                "title": "Transform tabular data safely",
                "sequence": 1,
            }
        ],
        modules=[
            {
                "module_ref": "module-001",
                "title": "Module 1: Data preparation",
                "order": 1,
                "lessons": [
                    {
                        "lesson_ref": "lesson-001",
                        "title": "Lesson 1: Invalid values",
                        "order": 1,
                        "delivery_type": "TEXT",
                        "estimated_duration_minutes": 20,
                        "objective_refs": ["obj-001"],
                    }
                ],
            }
        ],
        assessment_references=[
            {"assessment_id": "assessment-001", "version": "1"}
        ],
    )
