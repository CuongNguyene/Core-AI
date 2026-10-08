"""Deterministic source-span matching and diagnostic metrics for EVAL-00."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.job_semantics_eval.contracts import ValidatedRequirementStatement
from app.job_semantics_eval.source_adapter import build_source_blocks

SOURCE_FIELD_RANK = {"JOB_DESCRIPTION": 0, "JOB_REQUIREMENTS": 1}
STATEMENT_TYPES = (
    "RESPONSIBILITY",
    "EXPERIENCE_REQUIREMENT",
    "EDUCATION_REQUIREMENT",
    "QUALIFICATION_REQUIREMENT",
    "BEHAVIORAL_REQUIREMENT",
    "OTHER",
)
CAPABILITY_RELEVANCE = ("CAPABILITY_BEARING", "NON_CAPABILITY", "UNCLEAR")


@dataclass(frozen=True)
class _Pair:
    gold: Mapping[str, Any]
    prediction: ValidatedRequirementStatement


@dataclass(frozen=True)
class _CaseMatch:
    case_id: str
    gold: tuple[Mapping[str, Any], ...]
    predictions: tuple[ValidatedRequirementStatement, ...]
    pairs: tuple[_Pair, ...]
    unmatched_gold: tuple[Mapping[str, Any], ...]
    unmatched_predictions: tuple[ValidatedRequirementStatement, ...]
    over_split_predictions: tuple[ValidatedRequirementStatement, ...]
    under_split_gold: tuple[Mapping[str, Any], ...]
    hallucinated_predictions: tuple[ValidatedRequirementStatement, ...]
    missed_gold: tuple[Mapping[str, Any], ...]
    exact: bool


def _gold_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["source_field"]), str(row["source_text"])


def _prediction_key(row: ValidatedRequirementStatement) -> tuple[str, str]:
    return row.source_field, row.source_text


def _prediction_order(row: ValidatedRequirementStatement) -> tuple[int, int, int, int]:
    return (
        SOURCE_FIELD_RANK[row.source_field],
        row.start_offset,
        row.end_offset,
        row.output_index,
    )


def _match_case(
    case: Mapping[str, Any], predictions: Sequence[ValidatedRequirementStatement]
) -> _CaseMatch:
    case_id = str(case["case_id"])
    source_blocks = build_source_blocks(case.get("target_job_source"))
    gold_rows_list = [
        dict(row) for row in case.get("expected_statements", ()) if isinstance(row, Mapping)
    ]
    text_by_field: dict[str, str] = {}
    for field in SOURCE_FIELD_RANK:
        field_blocks = [block for block in source_blocks if block.source_field == field]
        text_by_field[field] = "\n".join(block.text for block in field_blocks)
    occurrence_cursor: dict[str, int] = defaultdict(int)
    for row in sorted(
        gold_rows_list,
        key=lambda item: (
            SOURCE_FIELD_RANK.get(str(item.get("source_field")), 99),
            int(item.get("source_order", 0)),
        ),
    ):
        field = str(row["source_field"])
        source_text = str(row["source_text"])
        field_text = text_by_field.get(field, "")
        offset = field_text.find(source_text, occurrence_cursor[field])
        if offset < 0:
            offset = field_text.find(source_text)
        row["_start_offset"] = offset
        row["_end_offset"] = offset + len(source_text) if offset >= 0 else -1
        if offset >= 0:
            occurrence_cursor[field] = offset + len(source_text)

    gold_rows = tuple(
        sorted(
            gold_rows_list,
            key=lambda row: (
                SOURCE_FIELD_RANK.get(str(row.get("source_field")), 99),
                int(row.get("source_order", 0)),
                str(row.get("statement_id", "")),
            ),
        )
    )
    pred_rows = tuple(sorted(predictions, key=_prediction_order))
    gold_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    pred_groups: dict[tuple[str, str], list[ValidatedRequirementStatement]] = defaultdict(list)
    for gold_row in gold_rows:
        gold_groups[_gold_key(gold_row)].append(gold_row)
    for prediction in pred_rows:
        pred_groups[_prediction_key(prediction)].append(prediction)

    pairs: list[_Pair] = []
    matched_gold_ids: set[int] = set()
    matched_pred_ids: set[int] = set()
    for key, gold_group in gold_groups.items():
        pred_group = pred_groups.get(key, [])
        gold_group = sorted(
            gold_group, key=lambda row: (int(row["source_order"]), str(row.get("statement_id", "")))
        )
        pred_group = sorted(pred_group, key=_prediction_order)
        for gold, prediction in zip(gold_group, pred_group, strict=False):
            pairs.append(_Pair(gold=gold, prediction=prediction))
            matched_gold_ids.add(id(gold))
            matched_pred_ids.add(id(prediction))

    unmatched_gold = tuple(row for row in gold_rows if id(row) not in matched_gold_ids)
    unmatched_predictions = tuple(row for row in pred_rows if id(row) not in matched_pred_ids)

    over_split: list[ValidatedRequirementStatement] = []
    for prediction in unmatched_predictions:
        if any(
            row["source_field"] == prediction.source_field
            and int(row.get("_start_offset", -1)) <= prediction.start_offset
            and prediction.end_offset <= int(row.get("_end_offset", -1))
            and (prediction.start_offset, prediction.end_offset)
            != (int(row.get("_start_offset", -1)), int(row.get("_end_offset", -1)))
            for row in unmatched_gold
        ):
            over_split.append(prediction)

    under_split: list[Mapping[str, Any]] = []
    for gold in unmatched_gold:
        if any(
            prediction.source_field == gold["source_field"]
            and prediction.start_offset <= int(gold.get("_start_offset", -1))
            and int(gold.get("_end_offset", -1)) <= prediction.end_offset
            and (prediction.start_offset, prediction.end_offset)
            != (int(gold.get("_start_offset", -1)), int(gold.get("_end_offset", -1)))
            for prediction in unmatched_predictions
        ):
            under_split.append(gold)

    hallucinated = [row for row in unmatched_predictions if row not in over_split]
    missed = [row for row in unmatched_gold if row not in under_split]
    return _CaseMatch(
        case_id=case_id,
        gold=gold_rows,
        predictions=pred_rows,
        pairs=tuple(pairs),
        unmatched_gold=unmatched_gold,
        unmatched_predictions=unmatched_predictions,
        over_split_predictions=tuple(over_split),
        under_split_gold=tuple(under_split),
        hallucinated_predictions=tuple(hallucinated),
        missed_gold=tuple(missed),
        exact=len(gold_rows) == len(pred_rows) and len(pairs) == len(gold_rows),
    )


def _class_metrics(labels: Sequence[str], pairs: Sequence[_Pair], field: str) -> dict[str, object]:
    confusion: dict[str, Counter[str]] = {label: Counter() for label in labels}
    correct = 0
    for pair in pairs:
        gold_label = str(pair.gold[field])
        predicted_label = str(getattr(pair.prediction, field))
        if gold_label in confusion and predicted_label in labels:
            confusion[gold_label][predicted_label] += 1
            correct += gold_label == predicted_label
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(confusion[label].values()),
        }
    denominator = len(pairs)
    return {
        "accuracy": correct / denominator if denominator else 0.0,
        "matched_statement_count": denominator,
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else 0.0,
        "per_class": per_class,
        "confusion_matrix": {label: dict(confusion[label]) for label in labels},
    }


def _decomposition_metrics(matches: Sequence[_CaseMatch]) -> dict[str, float | int]:
    gold_count = sum(len(row.gold) for row in matches)
    pred_count = sum(len(row.predictions) for row in matches)
    exact_matches = sum(len(row.pairs) for row in matches)
    precision = exact_matches / pred_count if pred_count else (1.0 if gold_count == 0 else 0.0)
    recall = exact_matches / gold_count if gold_count else (1.0 if pred_count == 0 else 0.0)
    return {
        "gold_statement_count": gold_count,
        "predicted_statement_count": pred_count,
        "exact_span_match_count": exact_matches,
        "statement_precision": precision,
        "statement_recall": recall,
        "statement_f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
        "case_exact_decomposition_count": sum(row.exact for row in matches),
        "case_exact_decomposition_rate": (
            sum(row.exact for row in matches) / len(matches) if matches else 0.0
        ),
        "evaluated_case_count": len(matches),
        "over_split_statement_count": sum(len(row.over_split_predictions) for row in matches),
        "over_split_case_count": sum(bool(row.over_split_predictions) for row in matches),
        "over_split_case_rate": (
            sum(bool(row.over_split_predictions) for row in matches) / len(matches)
            if matches
            else 0.0
        ),
        "under_split_gold_statement_count": sum(len(row.under_split_gold) for row in matches),
        "under_split_case_count": sum(bool(row.under_split_gold) for row in matches),
        "under_split_case_rate": (
            sum(bool(row.under_split_gold) for row in matches) / len(matches) if matches else 0.0
        ),
        "hallucinated_statement_count": sum(len(row.hallucinated_predictions) for row in matches),
        "missed_statement_count": sum(len(row.missed_gold) for row in matches),
    }


def _slice_summary(
    all_cases: Sequence[Mapping[str, Any]],
    all_matches: Sequence[_CaseMatch],
    field: str,
) -> dict[str, object]:
    evaluated = {row.case_id: row for row in all_matches}
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in all_cases:
        value = case.get(field)
        if field == "boundary_tags":
            for tag in value if isinstance(value, list) else ():
                grouped[str(tag)].append(case)
        else:
            grouped[str(value)].append(case)
    result: dict[str, object] = {}
    for name, cases in sorted(grouped.items()):
        subset = [
            evaluated[str(case["case_id"])] for case in cases if str(case["case_id"]) in evaluated
        ]
        metrics = _decomposition_metrics(subset)
        pair_list = [pair for match in subset for pair in match.pairs]
        result[name] = {
            "case_count": len(cases),
            "evaluated_case_count": len(subset),
            "decomposition": metrics,
            "statement_type_accuracy": _class_metrics(STATEMENT_TYPES, pair_list, "statement_type")[
                "accuracy"
            ],
            "capability_relevance_accuracy": _class_metrics(
                CAPABILITY_RELEVANCE, pair_list, "capability_relevance"
            )["accuracy"],
        }
    return result


def evaluate_dataset(
    cases: Sequence[Mapping[str, Any]],
    predictions_by_case: Mapping[str, Sequence[ValidatedRequirementStatement]],
    *,
    execution_errors: Mapping[str, str] | None = None,
    raw_statement_counts: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Compute deterministic metrics; failed executions are reported, not semantic predictions."""
    case_ids = [str(case["case_id"]) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("dataset case IDs must be unique")
    unknown_prediction_ids = set(predictions_by_case) - set(case_ids)
    if unknown_prediction_ids:
        raise ValueError(f"unknown prediction case ID: {sorted(unknown_prediction_ids)[0]}")
    errors = dict(execution_errors or {})
    unknown_error_ids = set(errors) - set(case_ids)
    if unknown_error_ids:
        raise ValueError(f"unknown execution error case ID: {sorted(unknown_error_ids)[0]}")
    overlap = set(predictions_by_case) & set(errors)
    if overlap:
        raise ValueError(f"case cannot be both completed and errored: {sorted(overlap)[0]}")

    case_by_id = {str(case["case_id"]): case for case in cases}
    matches = [
        _match_case(case_by_id[case_id], predictions_by_case[case_id])
        for case_id in case_ids
        if case_id in predictions_by_case
    ]
    pairs = [pair for row in matches for pair in row.pairs]
    order_total = 0
    order_correct = 0
    for match in matches:
        ordering_pairs = match.pairs
        for index, left in enumerate(ordering_pairs):
            for right in ordering_pairs[index + 1 :]:
                if left.gold["source_field"] != right.gold["source_field"]:
                    continue
                gold_before = int(left.gold["source_order"]) < int(right.gold["source_order"])
                pred_left_before = _prediction_order(left.prediction) < _prediction_order(
                    right.prediction
                )
                if int(left.gold["source_order"]) == int(right.gold["source_order"]):
                    continue
                order_total += 1
                order_correct += gold_before == pred_left_before

    all_gold_texts = {
        (str(row["source_field"]), str(row["source_text"]))
        for case in cases
        for row in case.get("expected_statements", ())
        if isinstance(row, Mapping)
    }
    gold_texts = {text for _field, text in all_gold_texts}
    all_predictions = [prediction for row in matches for prediction in row.predictions]
    provenance_comparable = [row for row in all_predictions if row.source_text in gold_texts]
    provenance_correct = sum(
        (row.source_field, row.source_text) in all_gold_texts for row in provenance_comparable
    )
    raw_counts = dict(raw_statement_counts or {})
    valid_span_count = sum(len(row.predictions) for row in matches)
    raw_count = sum(
        raw_counts.get(case_id, len(predictions_by_case.get(case_id, ())))
        for case_id in predictions_by_case
    )
    errors_by_category = Counter(errors.values())

    return {
        "execution": {
            "attempted_cases": len(predictions_by_case) + len(errors),
            "completed_cases": len(predictions_by_case),
            "provider_errors": sum(
                not category.startswith("invalid_output") for category in errors.values()
            ),
            "invalid_output_cases": sum(
                category.startswith("invalid_output") for category in errors.values()
            ),
            "error_categories": dict(errors_by_category),
        },
        "decomposition": _decomposition_metrics(matches),
        "statement_type": _class_metrics(STATEMENT_TYPES, pairs, "statement_type"),
        "capability_relevance": _class_metrics(CAPABILITY_RELEVANCE, pairs, "capability_relevance"),
        "source_fidelity": {
            "raw_provider_statement_count": raw_count,
            "validated_statement_count": valid_span_count,
            "valid_source_span_rate": valid_span_count / raw_count if raw_count else 0.0,
            "unknown_block_reference_count": sum(
                count
                for category, count in errors_by_category.items()
                if category == "invalid_output_unknown_block"
            ),
            "invented_span_count": sum(
                count
                for category, count in errors_by_category.items()
                if category == "invalid_output_invented_span"
            ),
            "normalized_statement_fidelity_failures": sum(
                count
                for category, count in errors_by_category.items()
                if category == "invalid_output_normalization"
            ),
            "source_field_provenance_accuracy": (
                provenance_correct / len(provenance_comparable) if provenance_comparable else 0.0
            ),
            "source_field_provenance_comparable_count": len(provenance_comparable),
            "nullable_source_violations": sum(
                count
                for category, count in errors_by_category.items()
                if category == "invalid_output_nullable_source"
            ),
            "empty_field_hallucinations": sum(
                count
                for category, count in errors_by_category.items()
                if category == "empty_field_hallucination"
            ),
        },
        "source_order_accuracy": order_correct / order_total if order_total else 1.0,
        "source_order_comparison_count": order_total,
        "slices": {
            "domain": _slice_summary(cases, matches, "domain"),
            "language": _slice_summary(cases, matches, "language_profile"),
            "difficulty": _slice_summary(cases, matches, "difficulty"),
            "boundary_tag": _slice_summary(cases, matches, "boundary_tags"),
        },
    }
