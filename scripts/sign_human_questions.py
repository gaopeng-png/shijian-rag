from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import ROOT_DIR
from scripts.validate_human_questions import annotation_signature, load_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh integrity hashes for reviewed human labels")
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT_DIR / "evaluation" / "human_questions.jsonl",
    )
    parser.add_argument("--id", action="append", dest="ids", help="Only sign selected case IDs")
    args = parser.parse_args()
    path = args.questions.resolve()
    records = load_jsonl(path)
    selected = set(args.ids or [])
    signed = 0
    for record in records:
        if selected and record["id"] not in selected:
            continue
        if record.get("review_status") == "draft":
            continue
        record["annotation_signature"] = annotation_signature(record)
        signed += 1
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    print(json.dumps({"signed": signed, "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
