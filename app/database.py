from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from app.models import Event

EVENT_FIELDS = (
    "id",
    "name",
    "year",
    "period",
    "region",
    "scope",
    "people",
    "keywords",
    "summary",
    "detail",
    "influence",
    "exam_points",
    "memory_tip",
    "source_title",
    "source_url",
    "content_hash",
)


def _content_hash(record: dict[str, object]) -> str:
    content = json.dumps(
        {key: record.get(key, "") for key in EVENT_FIELDS if key not in {"content_hash"}},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_event_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            missing = [field for field in EVENT_FIELDS[:-1] if field not in record]
            if missing:
                raise ValueError(f"{path}:{line_number} missing fields: {', '.join(missing)}")
            record["content_hash"] = _content_hash(record)
            records.append(record)
    return records


def initialize_database(db_path: Path, data_path: Path) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    records = load_event_records(data_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                year INTEGER NOT NULL,
                period TEXT NOT NULL,
                region TEXT NOT NULL,
                scope TEXT NOT NULL,
                people TEXT NOT NULL,
                keywords TEXT NOT NULL,
                summary TEXT NOT NULL,
                detail TEXT NOT NULL,
                influence TEXT NOT NULL,
                exam_points TEXT NOT NULL,
                memory_tip TEXT NOT NULL,
                source_title TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                name, period, region, scope, people, keywords, summary, detail,
                influence, exam_points, memory_tip,
                content='events', content_rowid='rowid', tokenize='unicode61'
            )
            """
        )
        placeholders = ", ".join("?" for _ in EVENT_FIELDS)
        updates = ", ".join(
            f"{field}=excluded.{field}" for field in EVENT_FIELDS if field != "id"
        )
        sql = (
            f"INSERT INTO events ({', '.join(EVENT_FIELDS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}, updated_at=CURRENT_TIMESTAMP"
        )
        conn.executemany(sql, [[record[field] for field in EVENT_FIELDS] for record in records])
        ids = [str(record["id"]) for record in records]
        if ids:
            marks = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM events WHERE id NOT IN ({marks})", ids)
        conn.execute("INSERT INTO events_fts(events_fts) VALUES('rebuild')")
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return {"loaded": len(records), "stored": int(count)}


class EventRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._entity_cache: tuple[list[str], list[str]] | None = None

    @property
    def ready(self) -> bool:
        return self.db_path.is_file()

    def _connect(self) -> sqlite3.Connection:
        if not self.ready:
            raise FileNotFoundError(
                f"database not found: {self.db_path}; run `python -m scripts.init_database`"
            )
        uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _to_event(row: sqlite3.Row) -> Event:
        return Event(**{field: row[field] for field in EVENT_FIELDS})

    def count(self) -> int:
        if not self.ready:
            return 0
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def list_events(self) -> list[Event]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY year, name").fetchall()
        return [self._to_event(row) for row in rows]

    def get_many(self, ids: Iterable[str]) -> list[Event]:
        values = list(dict.fromkeys(ids))
        if not values:
            return []
        marks = ",".join("?" for _ in values)
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM events WHERE id IN ({marks})", values).fetchall()
        by_id = {row["id"]: self._to_event(row) for row in rows}
        return [by_id[event_id] for event_id in values if event_id in by_id]

    def by_years(self, years: list[int], limit: int = 20) -> list[Event]:
        if not years:
            return []
        marks = ",".join("?" for _ in years)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM events WHERE year IN ({marks}) ORDER BY year, name LIMIT ?",
                [*years, limit],
            ).fetchall()
        return [self._to_event(row) for row in rows]

    def by_names(self, names: list[str], limit: int = 20) -> list[Event]:
        if not names:
            return []
        marks = ",".join("?" for _ in names)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM events WHERE name IN ({marks}) ORDER BY year, name LIMIT ?",
                [*names, limit],
            ).fetchall()
        return [self._to_event(row) for row in rows]

    def by_people(self, people: list[str], limit: int = 20) -> list[Event]:
        if not people:
            return []
        clauses = " OR ".join("people LIKE ?" for _ in people)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM events WHERE {clauses} ORDER BY year, name LIMIT ?",
                [*[f"%{person}%" for person in people], limit],
            ).fetchall()
        return [self._to_event(row) for row in rows]

    def search_fts(self, terms: list[str], limit: int = 20) -> list[Event]:
        cleaned = [term.replace('"', "").strip() for term in terms if term.strip()]
        if not cleaned:
            return []
        query = " OR ".join(f'"{term}"' for term in cleaned[:8])
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT e.* FROM events_fts f
                    JOIN events e ON e.rowid = f.rowid
                    WHERE events_fts MATCH ?
                    ORDER BY bm25(events_fts)
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            return [self._to_event(row) for row in rows]
        except sqlite3.OperationalError:
            return []

    def search_like(self, terms: list[str], limit: int = 20) -> list[Event]:
        terms = [term.strip() for term in terms if len(term.strip()) >= 2][:8]
        if not terms:
            return []
        columns = ("name", "people", "keywords", "summary", "detail", "influence", "exam_points")
        clauses: list[str] = []
        params: list[str | int] = []
        for term in terms:
            clauses.append("(" + " OR ".join(f"{column} LIKE ?" for column in columns) + ")")
            params.extend([f"%{term}%"] * len(columns))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE " + " OR ".join(clauses) + " LIMIT ?",
                [*params, limit * 3],
            ).fetchall()
        events = [self._to_event(row) for row in rows]
        events.sort(
            key=lambda event: sum(
                1
                for term in terms
                if term in " ".join(
                    [event.name, event.people, event.keywords, event.summary, event.detail, event.influence]
                )
            ),
            reverse=True,
        )
        return events[:limit]

    def entities(self) -> tuple[list[str], list[str]]:
        if self._entity_cache is not None:
            return self._entity_cache
        events = self.list_events()
        names = sorted((event.name for event in events), key=len, reverse=True)
        people: set[str] = set()
        for event in events:
            people.update(
                item.strip()
                for item in re.split(r"[、,，及与和]", event.people)
                if len(item.strip()) >= 2
            )
        self._entity_cache = (names, sorted(people, key=len, reverse=True))
        return self._entity_cache
