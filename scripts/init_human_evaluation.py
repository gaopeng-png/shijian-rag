from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import ROOT_DIR

CATEGORY_COUNTS = {
    "year_or_name": 8,
    "semantic_paraphrase": 12,
    "person": 8,
    "cause": 10,
    "impact": 10,
    "comparison": 8,
    "followup": 8,
    "ambiguous": 6,
    "unanswerable": 10,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create blank, human-authored evaluation worksheets")
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT_DIR / "evaluation" / "human_questions.jsonl",
    )
    parser.add_argument(
        "--scores",
        type=Path,
        default=ROOT_DIR / "evaluation" / "human_scores.jsonl",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def write_jsonl(path: Path, records: list[dict[str, object]], force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"refusing to overwrite {path}; pass --force intentionally")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    questions: list[dict[str, object]] = []
    index = 0
    for category, count in CATEGORY_COUNTS.items():
        for _ in range(count):
            index += 1
            questions.append(
                {
                    "id": f"human-{index:03d}",
                    "category": category,
                    "history_scope": "china" if index <= 56 else "world",
                    "difficulty": "",
                    "question": "",
                    "expected_event_ids": [],
                    "allowed_source_ids": [],
                    "required_facts": [],
                    "forbidden_facts": [],
                    "should_refuse": category == "unanswerable",
                    "conversation_history": [],
                    "author": "",
                    "reviewer_id": "",
                    "reviewed_at": "",
                    "review_status": "draft",
                    "annotation_signature": "",
                }
            )
    scores = [
        {
            "score_id": f"human-score-{index:02d}",
            "case_id": "",
            "answer_snapshot_hash": "",
            "factual_support": None,
            "completeness": None,
            "citation_correctness": None,
            "refusal_reasonableness": None,
            "scorer": "",
            "scored_at": "",
            "status": "draft",
            "notes": "",
        }
        for index in range(1, 31)
    ]
    write_jsonl(args.questions, questions, args.force)
    write_jsonl(args.scores, scores, args.force)
    print(
        json.dumps(
            {
                "question_slots": len(questions),
                "score_slots": len(scores),
                "content": "blank_requires_independent_human_authoring",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
