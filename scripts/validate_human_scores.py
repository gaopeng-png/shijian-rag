from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR
from scripts.validate_human_questions import load_jsonl

SCORE_FIELDS = (
    "factual_support",
    "completeness",
    "citation_correctness",
    "refusal_reasonableness",
)


def validate_score_records(
    records: list[dict[str, Any]],
    question_ids: set[str],
    *,
    require_final: bool,
) -> list[str]:
    failures: list[str] = []
    if len(records) != 30:
        failures.append(f"expected 30 score records, found {len(records)}")
    score_ids = [str(record.get("score_id", "")) for record in records]
    if len(score_ids) != len(set(score_ids)) or any(not value for value in score_ids):
        failures.append("score IDs must be non-empty and unique")
    completed_case_ids: list[str] = []
    for record in records:
        score_id = str(record.get("score_id", "<missing>"))
        status = record.get("status")
        if status not in {"draft", "scored"}:
            failures.append(f"{score_id}: invalid status")
            continue
        if status == "draft":
            if require_final:
                failures.append(f"{score_id}: still draft")
            continue
        case_id = str(record.get("case_id", ""))
        completed_case_ids.append(case_id)
        if case_id not in question_ids:
            failures.append(f"{score_id}: unknown case_id")
        if not str(record.get("answer_snapshot_hash", "")).strip():
            failures.append(f"{score_id}: answer_snapshot_hash is required")
        if not str(record.get("scorer", "")).strip() or not str(
            record.get("scored_at", "")
        ).strip():
            failures.append(f"{score_id}: scorer and scored_at are required")
        for field in SCORE_FIELDS:
            if record.get(field) not in {0, 1, 2}:
                failures.append(f"{score_id}: {field} must be 0, 1, or 2")
    if len(completed_case_ids) != len(set(completed_case_ids)):
        failures.append("each completed score must reference a distinct case")
    return failures


def score_metrics(records: list[dict[str, Any]]) -> dict[str, float | int]:
    completed = [record for record in records if record.get("status") == "scored"]
    metrics: dict[str, float | int] = {"scored_answer_count": len(completed)}
    for field in SCORE_FIELDS:
        values = [int(record[field]) for record in completed if record.get(field) in {0, 1, 2}]
        metrics[f"{field}_mean_0_to_2"] = round(statistics.fmean(values), 4) if values else 0.0
        metrics[f"{field}_pass_rate"] = (
            round(statistics.fmean(value >= 1 for value in values), 4) if values else 0.0
        )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate 30 manually scored generated answers")
    parser.add_argument(
        "--scores",
        type=Path,
        default=ROOT_DIR / "evaluation" / "human_scores.jsonl",
    )
    parser.add_argument("--require-final", action="store_true")
    args = parser.parse_args()
    records = load_jsonl(args.scores.resolve())
    questions = load_jsonl(ROOT_DIR / "evaluation" / "human_questions.jsonl")
    failures = validate_score_records(
        records,
        {str(record["id"]) for record in questions},
        require_final=args.require_final,
    )
    print(
        json.dumps(
            {"metrics": score_metrics(records), "failures": failures},
            ensure_ascii=False,
            indent=2,
        )
    )
    if failures:
        raise SystemExit("human score validation failed")


if __name__ == "__main__":
    main()
