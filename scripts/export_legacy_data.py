"""Export the original Python data module to reviewable JSONL files.

This is a one-time migration helper kept for data provenance. Runtime code reads
the JSONL files and never imports ``history_data.py``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from history_data import HISTORY_EVENTS, KNOWLEDGE_DOCS  # noqa: E402


def stable_event_id(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return f"evt-{digest}"


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    events: list[dict[str, object]] = []
    for event in HISTORY_EVENTS:
        record = asdict(event)
        record.update(
            {
                "id": stable_event_id(event.name),
                "source_title": "史鉴 RAG 项目内置历史事件资料",
                "source_url": "",
            }
        )
        events.append(record)

    knowledge = [
        {
            **doc,
            "id": f"knowledge-{doc['id']}",
            "source_title": "史鉴 RAG 项目内置学习方法资料",
            "source_url": "",
        }
        for doc in KNOWLEDGE_DOCS
    ]

    write_jsonl(ROOT / "data" / "history_events.jsonl", events)
    write_jsonl(ROOT / "data" / "knowledge_docs.jsonl", knowledge)
    print(f"exported {len(events)} events and {len(knowledge)} knowledge documents")


if __name__ == "__main__":
    main()
