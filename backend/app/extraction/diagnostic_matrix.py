"""Deterministic evaluator for the EXT-03A.1 extraction matrix."""

from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, Field

InputMode = Literal["native_pdf", "whole_parsed_text"]
ThinkingLevel = Literal["high", "medium"]

CAPABILITY_FAMILIES: tuple[str, ...] = (
    "Project Management",
    "Product Management",
    "eCommerce",
    "Omnichannel Commerce",
    "Order Management",
    "Warehouse Management",
    "Delivery / Logistics Management",
    "Operations Planning",
    "Digital Platform Development",
    "Team Leadership",
    "Process Optimization",
)

_ALIASES: dict[str, tuple[str, ...]] = {
    "Project Management": ("project management", "project delivery", "project development"),
    "Product Management": ("product management", "product ownership"),
    "eCommerce": ("ecommerce", "e-commerce", "electronic commerce"),
    "Omnichannel Commerce": ("omnichannel", "omni channel", "o2o commerce"),
    "Order Management": ("order management", "order fulfillment"),
    "Warehouse Management": ("warehouse management", "warehouse operations"),
    "Delivery / Logistics Management": ("delivery", "logistics management", "delivery operations"),
    "Operations Planning": ("operations planning", "operational planning"),
    "Digital Platform Development": ("digital platform", "platform development", "software development"),
    "Team Leadership": ("team leadership", "team management", "people management"),
    "Process Optimization": ("process optimization", "process improvement"),
}


class MatrixTokenUsage(BaseModel):
    input_tokens: int | None = None
    thinking_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class MatrixRun(BaseModel):
    run_id: str
    input_mode: InputMode
    thinking: ThinkingLevel
    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    success: bool
    failure_stage: str | None = None
    failure_code: str | None = None
    latency_ms: int = Field(ge=0)
    token_usage: MatrixTokenUsage
    finish_reason: str | None = None
    counts: dict[str, int]
    quality: dict[str, int | float]
    capability_names: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    education_summary: list[str] = Field(default_factory=list)
    capability_coverage: dict[str, str] = Field(default_factory=dict)
    experience_recall: str | None = None
    education_recall: str | None = None
    candidate_profile_created: bool = False


def capability_coverage(names: Iterable[str]) -> dict[str, str]:
    normalized = [name.casefold().strip() for name in names]
    result: dict[str, str] = {}
    for family, aliases in _ALIASES.items():
        if any(alias in name or name in alias for alias in aliases for name in normalized):
            result[family] = "FOUND"
        else:
            result[family] = "NOT_FOUND"
    return result


def classify_experience_recall(count: int) -> str:
    if count >= 6:
        return "HIGH"
    if count >= 4:
        return "MEDIUM"
    return "LOW"


def education_recall(count: int, expected: int = 2) -> str:
    return f"{count}/{expected}"


def duplicate_count(names: Iterable[str]) -> int:
    values = [name.casefold().strip() for name in names]
    return len(values) - len(set(values))


def recommend(runs: Iterable[MatrixRun]) -> dict[str, str]:
    completed = [run for run in runs if run.success]
    if not completed:
        return {
            "best_input_mode": "unknown",
            "best_thinking": "unknown",
            "primary_blocker": "TECHNICAL_RUNTIME",
            "next_action": "REASSESS_NATIVE_PDF_DEFAULT",
        }

    def score(run: MatrixRun) -> tuple[int, int, int, int]:
        found = sum(value == "FOUND" for value in run.capability_coverage.values())
        return (
            found,
            int(run.counts.get("education", 0)),
            int(run.counts.get("experience", 0)),
            -run.latency_ms,
        )

    best = max(completed, key=score)
    high = [run for run in completed if run.thinking == "high"]
    medium = [run for run in completed if run.thinking == "medium"]
    high_score = max((score(run) for run in high), default=(0, 0, 0, 0))
    medium_score = max((score(run) for run in medium), default=(0, 0, 0, 0))
    all_low_recall = all(sum(value == "FOUND" for value in run.capability_coverage.values()) <= 2 for run in completed)
    if all_low_recall:
        blocker = "PROMPT_SCHEMA_RECALL"
    elif medium_score > high_score:
        blocker = "THINKING_CONFIGURATION"
    elif score(best)[:3] > score(next((run for run in completed if run.input_mode != best.input_mode), best))[:3]:
        blocker = "INPUT_REPRESENTATION"
    else:
        blocker = "NO_CLEAR_BLOCKER"
    next_action = (
        "CHANGE_DEFAULT_TO_MEDIUM_AND_RUN_MULTI_CV"
        if blocker == "THINKING_CONFIGURATION"
        else "REASSESS_NATIVE_PDF_DEFAULT"
        if blocker == "INPUT_REPRESENTATION"
        else "PROCEED_TO_EXT_03A_2_PROMPT_COVERAGE_CALIBRATION"
        if blocker == "PROMPT_SCHEMA_RECALL"
        else "RUN_MULTI_CV_WITH_CURRENT_NATIVE_CONFIGURATION"
    )
    return {
        "best_input_mode": best.input_mode,
        "best_thinking": best.thinking,
        "primary_blocker": blocker,
        "next_action": next_action,
    }


def matrix_markdown(runs: Iterable[MatrixRun], decision: Mapping[str, str]) -> str:
    rows = [
        "# EXT-03A.1 Diagnostic Matrix",
        "",
        "## Results",
        "",
        "| Input | Thinking | Success | Exp | Capabilities | Tools | Education | Grounding | Unsupported | Latency |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        rows.append(
            f"| {run.input_mode} | {run.thinking} | {run.success} | "
            f"{run.counts.get('experience', 0)} | {run.counts.get('capabilities', 0)} | "
            f"{run.counts.get('tools_platforms', 0)} | {run.counts.get('education', 0)} | "
            f"{run.quality.get('grounded_capability_rate', 0)} | "
            f"{run.quality.get('unsupported_capability_count', 0)} | {run.latency_ms}ms |"
        )
    rows.extend(
        [
            "",
            "## Decision",
            "",
            *(f"- {key}: {value}" for key, value in decision.items()),
            "",
            "This artifact contains safe counts, names and metrics only; no document text or raw model response.",
        ]
    )
    return "\n".join(rows) + "\n"
