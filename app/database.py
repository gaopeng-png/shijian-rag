from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from app.models import Event, SourceCitation

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

SOURCE_FIELDS = (
    "source_id",
    "title",
    "publisher",
    "url",
    "source_type",
    "authority_level",
    "language",
    "accessed_at",
    "license_note",
)
CLAIM_FIELDS = {"summary", "detail", "influence", "exam_points"}


def _content_hash(record: dict[str, object], evidence: dict[str, object] | None = None) -> str:
    content = json.dumps(
        {
            "event": {
                key: record.get(key, "")
                for key in EVENT_FIELDS
                if key not in {"content_hash"}
            },
            "evidence": evidence or {},
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_event_records(
    path: Path,
    evidence_by_event: dict[str, dict[str, object]] | None = None,
    sources: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            missing = [field for field in EVENT_FIELDS[:-1] if field not in record]
            if missing:
                raise ValueError(f"{path}:{line_number} missing fields: {', '.join(missing)}")
            evidence = (evidence_by_event or {}).get(str(record["id"]), {})
            event_sources = evidence.get("sources", []) if isinstance(evidence, dict) else []
            if event_sources and sources:
                primary_id = str(event_sources[0].get("source_id", ""))
                primary = sources.get(primary_id)
                if primary:
                    record["source_title"] = primary["title"]
                    record["source_url"] = primary["url"]
            evidence_payload = {
                "evidence": evidence,
                "sources": {
                    source_id: sources[source_id]
                    for source_id in {
                        str(item.get("source_id", ""))
                        for item in event_sources
                        if isinstance(item, dict)
                    }
                    if sources and source_id in sources
                },
            }
            record["content_hash"] = _content_hash(record, evidence_payload)
            records.append(record)
    return records


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            records.append(record)
    return records


def load_sources(path: Path) -> dict[str, dict[str, str]]:
    sources: dict[str, dict[str, str]] = {}
    for index, record in enumerate(_load_jsonl(path), start=1):
        missing = [field for field in SOURCE_FIELDS if not str(record.get(field, "")).strip()]
        if missing:
            raise ValueError(f"{path}:{index} missing fields: {', '.join(missing)}")
        source = {field: str(record[field]).strip() for field in SOURCE_FIELDS}
        if source["source_id"] in sources:
            raise ValueError(f"{path}:{index} duplicate source_id: {source['source_id']}")
        if not source["url"].startswith("https://"):
            raise ValueError(f"{path}:{index} source URL must use HTTPS")
        if source["authority_level"] not in {"A", "B", "C"}:
            raise ValueError(f"{path}:{index} invalid authority_level")
        sources[source["source_id"]] = source
    return sources


def load_evidence(
    path: Path,
    sources: dict[str, dict[str, str]],
) -> dict[str, dict[str, object]]:
    evidence: dict[str, dict[str, object]] = {}
    for index, record in enumerate(_load_jsonl(path), start=1):
        event_id = str(record.get("event_id", "")).strip()
        if not event_id or event_id in evidence:
            raise ValueError(f"{path}:{index} missing or duplicate event_id")
        links = record.get("sources", [])
        claims = record.get("claim_sources", {})
        review = {
            "status": record.get("status", ""),
            "reviewer_id": record.get("reviewer_id", ""),
            "reviewed_at": record.get("reviewed_at", ""),
            "notes": record.get("notes", ""),
        }
        if not isinstance(links, list) or not links:
            raise ValueError(f"{path}:{index} must list at least one source")
        linked_ids = {
            str(link.get("source_id", ""))
            for link in links
            if isinstance(link, dict)
        }
        unknown = sorted(linked_ids - set(sources))
        if unknown:
            raise ValueError(f"{path}:{index} unknown sources: {', '.join(unknown)}")
        if not isinstance(claims, dict) or set(claims) != CLAIM_FIELDS:
            raise ValueError(
                f"{path}:{index} claim_sources must contain: {', '.join(sorted(CLAIM_FIELDS))}"
            )
        for field_name, source_ids in claims.items():
            if not isinstance(source_ids, list) or not source_ids:
                raise ValueError(f"{path}:{index} {field_name} requires source IDs")
            if not set(map(str, source_ids)).issubset(linked_ids):
                raise ValueError(f"{path}:{index} {field_name} references an unlinked source")
        if not isinstance(review, dict):
            raise ValueError(f"{path}:{index} review must be an object")
        status = str(review["status"]).strip()
        if status not in {"candidate", "single_author_review", "verified"}:
            raise ValueError(f"{path}:{index} invalid evidence status: {status or '<empty>'}")
        if status == "verified" and not all(
            str(review[field]).strip() for field in ("reviewer_id", "reviewed_at")
        ):
            raise ValueError(f"{path}:{index} verified evidence requires reviewer and date")
        if record.get("memory_tip_provenance") != "project_original":
            raise ValueError(
                f"{path}:{index} memory_tip_provenance must be project_original"
            )
        evidence[event_id] = record
    return evidence


def initialize_database(
    db_path: Path,
    data_path: Path,
    sources_path: Path | None = None,
    evidence_path: Path | None = None,
) -> dict[str, int | str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sources_file = sources_path or data_path.with_name("sources.jsonl")
    evidence_file = evidence_path or data_path.with_name("event_evidence.jsonl")
    sources = load_sources(sources_file)
    evidence = load_evidence(evidence_file, sources)
    records = load_event_records(data_path, evidence, sources)
    event_ids = {str(record["id"]) for record in records}
    unknown_events = sorted(set(evidence) - event_ids)
    if unknown_events:
        raise ValueError(f"{evidence_file} references unknown events: {', '.join(unknown_events)}")
    evidence_revision = hashlib.sha256(
        json.dumps(
            {"sources": sources, "evidence": evidence},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
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
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                publisher TEXT NOT NULL,
                url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                authority_level TEXT NOT NULL,
                language TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                license_note TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_sources (
                event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
                locator TEXT NOT NULL DEFAULT '',
                source_order INTEGER NOT NULL,
                PRIMARY KEY (event_id, source_id)
            );
            CREATE TABLE IF NOT EXISTS claim_sources (
                event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                field_name TEXT NOT NULL,
                source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
                PRIMARY KEY (event_id, field_name, source_id)
            );
            CREATE TABLE IF NOT EXISTS evidence_reviews (
                event_id TEXT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                reviewer_id TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                memory_tip_provenance TEXT NOT NULL DEFAULT 'project_original'
            );
            CREATE TABLE IF NOT EXISTS dataset_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
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
        conn.execute("DELETE FROM claim_sources")
        conn.execute("DELETE FROM event_sources")
        conn.execute("DELETE FROM evidence_reviews")
        conn.execute("DELETE FROM sources")
        if sources:
            conn.executemany(
                f"INSERT INTO sources ({', '.join(SOURCE_FIELDS)}) VALUES ({', '.join('?' for _ in SOURCE_FIELDS)})",
                [[source[field] for field in SOURCE_FIELDS] for source in sources.values()],
            )
        for event_id, record in evidence.items():
            for source_order, link in enumerate(record["sources"]):
                conn.execute(
                    "INSERT INTO event_sources(event_id, source_id, locator, source_order) VALUES (?, ?, ?, ?)",
                    (
                        event_id,
                        str(link["source_id"]),
                        str(link.get("locator", "")),
                        source_order,
                    ),
                )
            for field_name, source_ids in record["claim_sources"].items():
                conn.executemany(
                    "INSERT INTO claim_sources(event_id, field_name, source_id) VALUES (?, ?, ?)",
                    [(event_id, field_name, str(source_id)) for source_id in source_ids],
                )
            conn.execute(
                "INSERT INTO evidence_reviews("
                "event_id, status, reviewer_id, reviewed_at, notes, memory_tip_provenance"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    str(record.get("status", "candidate")),
                    str(record.get("reviewer_id", "")),
                    str(record.get("reviewed_at", "")),
                    str(record.get("notes", "")),
                    "project_original",
                ),
            )
        conn.execute(
            "INSERT INTO dataset_metadata(key, value) VALUES ('evidence_revision', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (evidence_revision,),
        )
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return {
        "loaded": len(records),
        "stored": int(count),
        "sources": len(sources),
        "evidence_records": len(evidence),
        "evidence_revision": evidence_revision,
    }


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
    def _rows_to_events(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[Event]:
        events = [Event(**{field: row[field] for field in EVENT_FIELDS}) for row in rows]
        event_ids = [event.id for event in events]
        if not event_ids:
            return events
        marks = ",".join("?" for _ in event_ids)
        source_rows = conn.execute(
            f"""
            SELECT es.event_id, es.locator, es.source_order,
                   s.source_id, s.title, s.publisher, s.url, s.source_type,
                   s.authority_level, s.language, s.accessed_at, s.license_note
            FROM event_sources es
            JOIN sources s ON s.source_id = es.source_id
            WHERE es.event_id IN ({marks})
            ORDER BY es.event_id, es.source_order
            """,
            event_ids,
        ).fetchall()
        claim_rows = conn.execute(
            f"SELECT event_id, field_name, source_id FROM claim_sources "
            f"WHERE event_id IN ({marks}) ORDER BY event_id, field_name, source_id",
            event_ids,
        ).fetchall()
        review_rows = conn.execute(
            f"SELECT * FROM evidence_reviews WHERE event_id IN ({marks})",
            event_ids,
        ).fetchall()

        claims_by_event: dict[str, dict[str, list[str]]] = {}
        supported: dict[tuple[str, str], list[str]] = {}
        for row in claim_rows:
            event_claims = claims_by_event.setdefault(row["event_id"], {})
            event_claims.setdefault(row["field_name"], []).append(row["source_id"])
            supported.setdefault((row["event_id"], row["source_id"]), []).append(
                row["field_name"]
            )
        sources_by_event: dict[str, list[SourceCitation]] = {}
        for row in source_rows:
            sources_by_event.setdefault(row["event_id"], []).append(
                SourceCitation(
                    source_id=row["source_id"],
                    title=row["title"],
                    publisher=row["publisher"],
                    url=row["url"],
                    source_type=row["source_type"],
                    authority_level=row["authority_level"],
                    language=row["language"],
                    accessed_at=row["accessed_at"],
                    license_note=row["license_note"],
                    locator=row["locator"],
                    supported_fields=supported.get((row["event_id"], row["source_id"]), []),
                )
            )
        reviews = {row["event_id"]: row for row in review_rows}
        enriched: list[Event] = []
        for event in events:
            review = reviews.get(event.id)
            enriched.append(
                event.model_copy(
                    update={
                        "sources": sources_by_event.get(event.id, []),
                        "claim_sources": claims_by_event.get(event.id, {}),
                        "evidence_status": review["status"] if review else "unreviewed",
                        "reviewer_id": review["reviewer_id"] if review else "",
                        "reviewed_at": review["reviewed_at"] if review else "",
                        "evidence_notes": review["notes"] if review else "",
                        "memory_tip_provenance": (
                            review["memory_tip_provenance"] if review else "project_original"
                        ),
                    }
                )
            )
        return enriched

    def count(self) -> int:
        if not self.ready:
            return 0
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def list_events(self) -> list[Event]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY year, name").fetchall()
            return self._rows_to_events(conn, rows)

    def get_many(self, ids: Iterable[str]) -> list[Event]:
        values = list(dict.fromkeys(ids))
        if not values:
            return []
        marks = ",".join("?" for _ in values)
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM events WHERE id IN ({marks})", values).fetchall()
            events = self._rows_to_events(conn, rows)
        by_id = {event.id: event for event in events}
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
            return self._rows_to_events(conn, rows)

    def by_names(self, names: list[str], limit: int = 20) -> list[Event]:
        if not names:
            return []
        marks = ",".join("?" for _ in names)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM events WHERE name IN ({marks}) ORDER BY year, name LIMIT ?",
                [*names, limit],
            ).fetchall()
            return self._rows_to_events(conn, rows)

    def by_people(self, people: list[str], limit: int = 20) -> list[Event]:
        if not people:
            return []
        clauses = " OR ".join("people LIKE ?" for _ in people)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM events WHERE {clauses} ORDER BY year, name LIMIT ?",
                [*[f"%{person}%" for person in people], limit],
            ).fetchall()
            return self._rows_to_events(conn, rows)

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
                return self._rows_to_events(conn, rows)
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
            events = self._rows_to_events(conn, rows)
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

    def source_count(self) -> int:
        if not self.ready:
            return 0
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])

    def verified_event_count(self) -> int:
        if not self.ready:
            return 0
        with self._connect() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM evidence_reviews WHERE status = 'verified'"
                ).fetchone()[0]
            )

    def evidence_revision(self) -> str:
        if not self.ready:
            return ""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM dataset_metadata WHERE key = 'evidence_revision'"
            ).fetchone()
        return str(row[0]) if row else ""

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
