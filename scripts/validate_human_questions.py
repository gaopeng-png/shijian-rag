from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR
from scripts.init_human_evaluation import CATEGORY_COUNTS

EXPECTED_SCOPES = {"china": 56, "world": 24}
SIGNED_FIELDS = (
    "id",
    "category",
    "history_scope",
    "difficulty",
    "question",
    "expected_event_ids",
    "allowed_source_ids",
    "required_facts",
    "forbidden_facts",
    "should_refuse",
    "conversation_history",
    "author",
    "reviewer_id",
    "reviewed_at",
    "review_status",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def annotation_signature(record: dict[str, Any]) -> str:
    payload = {field: record.get(field) for field in SIGNED_FIELDS}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_records(
    records: list[dict[str, Any]],
    event_ids: set[str],
    source_ids: set[str],
    *,
    require_final: bool,
) -> list[str]:
    failures: list[str] = []
    if len(records) != 80:
        failures.append(f"expected 80 records, found {len(records)}")
    ids = [str(record.get("id", "")) for record in records]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        failures.append("question IDs must be non-empty and unique")
    categories = {
        category: sum(record.get("category") == category for record in records)
        for category in CATEGORY_COUNTS
    }
    if categories != CATEGORY_COUNTS:
        failures.append(f"category distribution mismatch: {categories}")
    scopes = {
        scope: sum(record.get("history_scope") == scope for record in records)
        for scope in EXPECTED_SCOPES
    }
    if scopes != EXPECTED_SCOPES:
        failures.append(f"history scope distribution mismatch: {scopes}")

    for record in records:
        case_id = str(record.get("id", "<missing>"))
        status = record.get("review_status")
        if status not in {"draft", "single_author_review", "verified"}:
            failures.append(f"{case_id}: invalid review_status")
            continue
        if status == "draft":
            if require_final:
                failures.append(f"{case_id}: still draft")
            continue
        if not str(record.get("question", "")).strip():
            failures.append(f"{case_id}: question is empty")
        if record.get("difficulty") not in {"easy", "medium", "hard"}:
            failures.append(f"{case_id}: invalid difficulty")
        expected = set(map(str, record.get("expected_event_ids", [])))
        allowed = set(map(str, record.get("allowed_source_ids", [])))
        if expected - event_ids:
            failures.append(f"{case_id}: unknown expected event IDs")
        if allowed - source_ids:
            failures.append(f"{case_id}: unknown allowed source IDs")
        if not record.get("should_refuse") and not expected:
            failures.append(f"{case_id}: answerable question needs expected events")
        if not record.get("should_refuse") and not allowed:
            failures.append(f"{case_id}: answerable question needs allowed sources")
        if not str(record.get("author", "")).strip():
            failures.append(f"{case_id}: author is required")
        if status == "verified":
            if not str(record.get("reviewer_id", "")).strip():
                failures.append(f"{case_id}: verified record needs reviewer_id")
            if record.get("reviewer_id") == record.get("author"):
                failures.append(f"{case_id}: verifier must differ from author")
        if not str(record.get("reviewed_at", "")).strip():
            failures.append(f"{case_id}: reviewed_at is required")
        if record.get("annotation_signature") != annotation_signature(record):
            failures.append(f"{case_id}: signature is missing or stale")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate independent human evaluation labels")
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT_DIR / "evaluation" / "human_questions.jsonl",
    )
    parser.add_argument("--require-final", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_jsonl(args.questions.resolve())
    events = load_jsonl(ROOT_DIR / "data" / "history_events.jsonl")
    sources = load_jsonl(ROOT_DIR / "data" / "sources.jsonl")
    failures = validate_records(
        records,
        {str(record["id"]) for record in events},
        {str(record["source_id"]) for record in sources},
        require_final=args.require_final,
    )
    statuses = {
        status: sum(record.get("review_status") == status for record in records)
        for status in ("draft", "single_author_review", "verified")
    }
    print(
        json.dumps(
            {"record_count": len(records), "statuses": statuses, "failures": failures},
            ensure_ascii=False,
            indent=2,
        )
    )
    if failures:
        raise SystemExit("human evaluation validation failed")


if __name__ == "__main__":
    main()
