"""Backward-compatible access to the JSONL data source.

New runtime code reads ``data/history_events.jsonl`` through ``app.database``.
This module remains only for notebooks or code written against the original
``HISTORY_EVENTS`` constants.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass(slots=True)
class HistoryEvent:
    name: str
    year: int
    period: str
    region: str
    scope: str
    people: str
    keywords: str
    summary: str
    detail: str
    influence: str
    exam_points: str
    memory_tip: str


with (ROOT / "data" / "history_events.jsonl").open(encoding="utf-8") as handle:
    HISTORY_EVENTS = [
        HistoryEvent(
            **{
                field: record[field]
                for field in HistoryEvent.__dataclass_fields__
            }
        )
        for record in (json.loads(line) for line in handle if line.strip())
    ]

with (ROOT / "data" / "knowledge_docs.jsonl").open(encoding="utf-8") as handle:
    KNOWLEDGE_DOCS = [
        {
            "id": record["id"].removeprefix("knowledge-"),
            "title": record["title"],
            "text": record["text"],
        }
        for record in (json.loads(line) for line in handle if line.strip())
    ]
