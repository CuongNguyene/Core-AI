"""Generate the safe Python dependency trace from a recovered Smoke-4 result."""

import argparse
import json
from pathlib import Path


def build_trace(results_path: Path) -> dict[str, object]:
    data = json.loads(results_path.read_text(encoding="utf-8"))
    snapshot = next(
        item["snapshot"]
        for item in data["results"]
        if item["run"]["fixture_id"] == "python_data_processing"
    )
    objectives = {item["id"]: item for item in snapshot["objectives"]}
    assessments = {item["id"]: item for item in snapshot["assessments"]}
    prerequisites = snapshot["prerequisites"]
    modules = snapshot["course_outline"]["modules"]
    lessons = snapshot["lessons"]
    finding_groups: dict[tuple[str, str], dict[str, object]] = {}
    for finding in snapshot["quality_report"]["findings"]:
        if finding["code"] != "assessment_dependency_not_covered":
            continue
        assessment = assessments[finding["entity_id"]]
        group_key = (assessment["id"], finding["message"])
        finding_groups.setdefault(group_key, {"fields": []})["fields"].append(
            finding["field"]
        )
    entries: list[dict[str, object]] = []
    for (assessment_id, _), group in finding_groups.items():
        assessment = assessments[assessment_id]
        objective_refs = assessment["objective_ids"]
        linked_prerequisites = [
            item
            for item in prerequisites
            if set(item["required_for_refs"]) & (set(objective_refs) | {assessment["id"]})
        ]
        linked_modules = [
            item for item in modules if set(item["objective_ids"]) & set(objective_refs)
        ]
        module_ids = {item["id"] for item in linked_modules}
        linked_lessons = [
            item
            for item in lessons
            if item["module_id"] in module_ids
            and set(item["objective_ids"]) & set(objective_refs)
        ]
        capabilities = [item["name"] for item in assessment.get("required_capabilities", [])]
        capabilities.extend(assessment.get("required_capability_refs", []))
        entries.append(
            {
                "finding": "assessment_dependency_not_covered",
                "severity": "error",
                "quality_gate_fields": sorted(set(group["fields"])),
                "objective": [
                    {"id": ref, "performance": objectives[ref]["performance"]}
                    for ref in objective_refs
                ],
                "assessment": {"id": assessment["id"], "role": assessment["role"]},
                "required_capability": {
                    "values": list(dict.fromkeys(capabilities)),
                    "brief_known": snapshot["brief"]["learner_state"]["known"],
                },
                "dependency_candidate": {
                    "persisted": False,
                    "status": "not_available_in_snapshot",
                    "reason": (
                        "AssessmentDesignOutput dependency_candidates are not retained "
                        "in ExperimentRunResult snapshots."
                    ),
                },
                "prerequisite": [
                    {
                        "id": item["id"],
                        "status": item["status"],
                        "basis": item["basis"],
                        "required_for_refs": item["required_for_refs"],
                    }
                    for item in linked_prerequisites
                ],
                "course_module": [
                    {"id": item["id"], "objective_ids": item["objective_ids"]}
                    for item in linked_modules
                ],
                "lessons": [
                    {
                        "id": item["id"],
                        "module_id": item["module_id"],
                        "objective_ids": item["objective_ids"],
                    }
                    for item in linked_lessons
                ],
                "root_cause": "assessment_scope_creep",
                "secondary_observation": "missing_dependency_propagation",
                "validator_correct": True,
                "rationale": (
                    "The assessment requires capability strings not exactly covered by "
                    "the brief learner-known set; corresponding prerequisites remain "
                    "model_proposed/candidate, and no dependency candidate is available "
                    "in the persisted snapshot."
                ),
            }
        )
    return {
        "schema_version": "smoke4-dependency-trace@0.1",
        "experiment_id": data["manifest"]["experiment_id"],
        "fixture_id": "python_data_processing",
        "source": "results-recovered.json",
        "entries": entries,
        "summary": {
            "finding_count": sum(
                len(group["fields"]) for group in finding_groups.values()
            ),
            "unique_requirement_count": len(entries),
            "duplicate_projection_count": sum(
                max(0, len(set(group["fields"])) - 1)
                for group in finding_groups.values()
            ),
            "root_causes": {
                "assessment_scope_creep": len(entries),
                "missing_dependency_propagation": len(entries),
                "lesson_under_generation": 0,
                "validator_false_positive": 0,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(build_trace(args.results), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
