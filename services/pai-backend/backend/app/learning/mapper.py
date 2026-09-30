from app.learning.schemas import LearningObjective
from app.learning_need_profile.schemas import LearningNeedProfile


def _level_value(value: str | None, field_name: str) -> int | None:
    if value is None:
        return None
    if value not in {"1", "2", "3", "4", "5"}:
        raise ValueError(f"{field_name}_invalid")
    return int(value)


def map_learning_need_to_objective(
    *,
    learning_need: LearningNeedProfile,
    sequence: int,
    measurable_outcome: str | None = None,
    allow_named_target_level: bool = False,
) -> LearningObjective:
    current_level = _level_value(
        learning_need.current_state.level,
        "learning_need_current_level",
    )
    target_level_value = learning_need.target_state.level
    target_level: int | None
    if allow_named_target_level and target_level_value == "production":
        target_level = 5
    else:
        target_level = _level_value(
            target_level_value, "learning_need_target_level"
        )
    if target_level is None:
        raise ValueError("learning_need_target_level_required")

    return LearningObjective(
        id=f"objective-{learning_need.id}",
        learning_need_ref=learning_need.id,
        statement=learning_need.gap.description,
        bloom_level=None,
        evidence_required=None,
        competency_id=learning_need.competency.id,
        current_level=current_level,
        target_level=target_level,
        measurable_outcome=(
            learning_need.gap.description
            if measurable_outcome is None
            else measurable_outcome
        ),
        gap_id=learning_need.source_gap_refs[0],
        sequence=sequence,
    )
