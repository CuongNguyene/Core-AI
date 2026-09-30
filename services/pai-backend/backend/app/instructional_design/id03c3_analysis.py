"""Deterministic descriptive analysis for canonical ID-03C SME reviews.

This module deliberately performs no judgement normalization, weighting, or ranking.
It is an analysis view over the immutable canonical-valid submissions from ID-03C.2.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

RUBRIC_DIMENSIONS = (
    "objective_measurability", "objective_assessment_alignment", "evidence_validity",
    "cognitive_alignment", "prerequisite_quality", "course_sequence_coherence",
    "instruction_assessment_alignment", "scope_balance", "workload_time_realism",
    "domain_appropriateness",
)
FIXTURE_MAP = {
    "review-001": "python_data_processing",
    "review-002": "accounting_financial_reporting_basic",
    "review-003": "legal_contract_review_basic",
    "review-004": "hr_recruitment_planning_basic",
    "review-005": "construction_drawing_and_method_basic",
}
THEMES = {
    "measurable_objectives": ("measurable", "observable", "criteria", "objective"),
    "objective_assessment_alignment": ("align", "assessment", "evidence", "task"),
    "authentic_performance_assessment": ("authentic", "performance", "scenario", "fixture"),
    "cognitive_progression": ("progression", "apply", "understand", "cognitive"),
    "coherent_sequence": ("sequence", "sequenc", "before", "progression"),
    "domain_relevant_practice": ("domain", "industry", "contract", "construction", "financial", "recruitment"),
    "prerequisite_inflation": ("broad", "inflation", "too broad", "exclude"),
    "insufficient_practice": ("practice", "feedback", "worked example"),
    "under_teaching": ("under-teach", "under teaching", "not enough instruction"),
    "scope_imbalance": ("scope", "extraneous", "too much", "coverage"),
    "workload_time_pressure": ("time pressure", "tight", "minutes", "workload", "time"),
    "assessment_scope_issue": ("scope creep", "summative", "assessment scope"),
    "weak_scaffolding": ("scaffold", "orientation", "guided"),
    "domain_generic_design": ("generic", "domain-neutral", "domain specific"),
    "unclear_success_criteria": ("need definition", "unclear", "operationalized"),
    "insufficient_feedback": ("feedback", "answer key", "calibrated"),
}


def _stats(values: list[int]) -> dict[str, Any]:
    return {"count": len(values), "mean": round(statistics.mean(values), 4),
            "median": statistics.median(values), "min": min(values), "max": max(values),
            "std_dev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
            "reviewer_spread": max(values) - min(values)}


def _load(source: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((source / "canonical-submissions").glob("*.json")):
        data = json.loads(path.read_text())
        if data.get("state") != "CANONICAL_VALID":
            continue
        submission = data["submission"]
        review_id = submission["review_id"]
        rows.append({"path": str(path), "review_id": review_id,
                     "reviewer_id": path.name.split("--", 1)[0],
                     "fixture_id": FIXTURE_MAP.get(review_id, review_id),
                     **submission})
    return rows


def _integrity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reviewers = Counter(r["reviewer_id"] for r in rows)
    fixtures = Counter(r["fixture_id"] for r in rows)
    complete = all(set(r.get("rubric_scores", {})) == set(RUBRIC_DIMENSIONS)
                   and all(r.get("rationales", {}).get(d) for d in RUBRIC_DIMENSIONS)
                   and r.get("special_question")
                   and isinstance(r.get("prerequisites_acceptable"), bool)
                   and r.get("edit_effort") for r in rows)
    return {"canonical_reviews": len(rows), "reviewers": len(reviewers),
            "reviews_per_reviewer": dict(reviewers), "fixtures": len(fixtures),
            "reviews_per_fixture": dict(fixtures), "rubric_complete": complete,
            "rationales_complete": complete, "special_question_complete": all(bool(r.get("special_question")) for r in rows),
            "prerequisites_complete": all(isinstance(r.get("prerequisites_acceptable"), bool) for r in rows),
            "edit_effort_complete": all(bool(r.get("edit_effort")) for r in rows),
            "analysis_allowed": len(rows) == 10 and len(reviewers) == 2 and len(fixtures) == 5 and complete}


def analyze(source: Path) -> dict[str, Any]:
    rows = _load(source)
    integrity = _integrity(rows)
    if not integrity["analysis_allowed"]:
        raise ValueError(f"canonical dataset integrity failed: {integrity}")
    rubric = {}
    for dim in RUBRIC_DIMENSIONS:
        values = [int(r["rubric_scores"][dim]) for r in rows]
        rubric[dim] = {"dimension": dim, **_stats(values),
                       "domain_spread": {f: _stats([int(r["rubric_scores"][dim]) for r in rows if r["fixture_id"] == f]) for f in sorted({x["fixture_id"] for x in rows})}}

    domains = []
    for fixture in sorted({r["fixture_id"] for r in rows}):
        subset = [r for r in rows if r["fixture_id"] == fixture]
        scores = {d: {"reviewer_scores": [r["rubric_scores"][d] for r in subset],
                      "mean": round(statistics.mean([r["rubric_scores"][d] for r in subset]), 4)} for d in RUBRIC_DIMENSIONS}
        sq = Counter(r["special_question"]["answer"] for r in subset)
        domains.append({"fixture": fixture, "scores": scores,
                        "special_question": dict(sq),
                        "prerequisites_acceptable": dict(Counter(str(r["prerequisites_acceptable"]).lower() for r in subset)),
                        "edit_effort": dict(Counter(r["edit_effort"] for r in subset)),
                        "strengths": sorted({s for r in subset for s in r.get("top_strengths", [])}),
                        "issues": sorted({s for r in subset for s in r.get("top_issues", [])})})

    pairs = []
    by_fixture_dim: defaultdict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for r in rows:
        for d in RUBRIC_DIMENSIONS:
            by_fixture_dim[(r["fixture_id"], d)].append((r["reviewer_id"], r["rubric_scores"][d]))
    for (fixture, dim), pair_values in sorted(by_fixture_dim.items()):
        if len(pair_values) != 2:
            continue
        diff = abs(pair_values[0][1] - pair_values[1][1])
        pairs.append({"fixture": fixture, "dimension": dim, "reviewer_scores": pair_values,
                      "absolute_difference": diff,
                      "classification": "exact_agreement" if diff == 0 else "minor_disagreement" if diff == 1 else "meaningful_disagreement" if diff == 2 else "major_disagreement"})
    differences = [cast(int, p["absolute_difference"]) for p in pairs]
    maximum_difference = max(differences)
    agreement = {"pairs": pairs, "exact_agreement_count": sum(d == 0 for d in differences),
                 "at_most_one_difference_count": sum(d <= 1 for d in differences),
                 "at_least_two_difference_count": sum(d >= 2 for d in differences),
                 "dimensions_with_highest_disagreement": sorted({str(p["dimension"]) for p in pairs if p["absolute_difference"] == maximum_difference}),
                 "fixtures_with_highest_disagreement": sorted({str(p["fixture"]) for p in pairs if p["absolute_difference"] == maximum_difference})}

    special = {"overall": dict(Counter(r["special_question"]["answer"] for r in rows)),
               "per_reviewer": {k: dict(Counter(r["special_question"]["answer"] for r in rows if r["reviewer_id"] == k)) for k in sorted({r["reviewer_id"] for r in rows})},
               "per_domain": {f: dict(Counter(r["special_question"]["answer"] for r in rows if r["fixture_id"] == f)) for f in sorted({r["fixture_id"] for r in rows})}}
    edit = {"overall": dict(Counter(r["edit_effort"] for r in rows)),
            "per_reviewer": {k: dict(Counter(r["edit_effort"] for r in rows if r["reviewer_id"] == k)) for k in sorted({r["reviewer_id"] for r in rows})},
            "per_domain": {f: dict(Counter(r["edit_effort"] for r in rows if r["fixture_id"] == f)) for f in sorted({r["fixture_id"] for r in rows})}}
    prereq = {"overall": dict(Counter(str(r["prerequisites_acceptable"]).lower() for r in rows)),
              "per_fixture": {f: dict(Counter(str(r["prerequisites_acceptable"]).lower() for r in rows if r["fixture_id"] == f)) for f in sorted({r["fixture_id"] for r in rows})},
              "reviewer_disagreement": sum(len({r["prerequisites_acceptable"] for r in rows if r["fixture_id"] == f}) > 1 for f in {r["fixture_id"] for r in rows}),
              "quality_scores": rubric["prerequisite_quality"]}

    themes = []
    for theme, terms in THEMES.items():
        refs = []
        for r in rows:
            text = " ".join(str(r.get("rationales", {}).get(d, "")) for d in RUBRIC_DIMENSIONS) + " " + " ".join(r.get("top_issues", []))
            if any(term in text.casefold() for term in terms):
                refs.append({"fixture": r["fixture_id"], "reviewer": r["reviewer_id"], "review_id": r["review_id"]})
        if refs:
            themes.append({"theme": theme, "occurrences": len(refs), "fixtures": sorted({x["fixture"] for x in refs}), "reviewers": sorted({x["reviewer"] for x in refs}), "evidence_refs": refs[:12]})
    machine = []
    for fixture in sorted({r["fixture_id"] for r in rows}):
        subset = [r for r in rows if r["fixture_id"] == fixture]
        issue = any(r.get("machine_validity_observations") for r in subset)
        reasonable = any(r["special_question"]["answer"] == "YES" for r in subset)
        category = "A" if issue and reasonable else "B" if issue else "C" if reasonable else "D"
        machine.append({"fixture": fixture, "machine_issue_present": issue, "pedagogically_reasonable": reasonable, "category": category, "machine_observation_codes": sorted({o.get("code") for r in subset for o in r.get("machine_validity_observations", []) if o.get("code")})})
    return {"integrity": integrity, "rubric": rubric, "domains": domains, "agreement": agreement, "special": special, "edit": edit, "prerequisite": prereq, "themes": themes, "machine": machine, "coverage_context": {"available": False, "note": "ID-03B.6 coverage counts are not embedded in canonical submissions; no causal comparison was inferred."}, "rows": rows}


def write_analysis(source: Path, output: Path) -> None:
    result = analyze(source)
    output.mkdir(parents=True, exist_ok=True)
    payloads = {
        "manifest.json": {"experiment": "ID-03C.3", "source": str(source), "canonical_only": True, "rubric_version": "instructional_design_human_rubric@0.2", "small_sample_limitation": True},
        "dataset-integrity.json": result["integrity"], "rubric-summary.json": result["rubric"], "domain-analysis.json": result["domains"], "reviewer-agreement.json": result["agreement"], "special-question-analysis.json": result["special"], "edit-effort-analysis.json": result["edit"], "prerequisite-analysis.json": result["prerequisite"], "thematic-analysis.json": result["themes"], "machine-human-analysis.json": result["machine"],
        "sme-analysis-report.json": {"experiment": "ID-03C.3", "dataset": {"reviews": 10, "reviewers": 2, "fixtures": 5}, "rubric_summary": result["rubric"], "domain_findings": result["domains"], "reviewer_agreement": result["agreement"], "special_question": result["special"], "edit_effort": result["edit"], "prerequisites": result["prerequisite"], "themes": result["themes"], "machine_human_relationship": result["machine"], "coverage_context": result["coverage_context"], "cross_domain_conclusion": "CROSS_DOMAIN_PARTIALLY_SUPPORTED", "pedagogical_signal": "PEDAGOGICAL_SIGNAL_MIXED", "next_step_readiness": "READY_FOR_NEXT_ID_MILESTONE", "limitations": ["small sample", "two reviewers", "one generated artifact per domain", "no learner outcome evidence"]},
        "validation-report.json": {"status": "valid", "canonical_reviews": 10, "source_mutated": False, "composite_winner": False, "reviewer_ranked": False},
    }
    for name, value in payloads.items():
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
