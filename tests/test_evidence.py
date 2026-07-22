from __future__ import annotations

import json

from app.database import EventRepository, load_evidence, load_sources


def test_evidence_metadata_covers_all_events(test_settings):
    sources = load_sources(test_settings.data_dir / "sources.jsonl")
    evidence = load_evidence(test_settings.data_dir / "event_evidence.jsonl", sources)
    events = [
        json.loads(line)
        for line in (test_settings.data_dir / "history_events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert len(sources) == 22
    assert len(evidence) == len(events) == 100
    assert sum(len(record["sources"]) >= 2 for record in evidence.values()) == 20
    assert all(record["memory_tip_provenance"] == "project_original" for record in evidence.values())


def test_repository_enriches_events_with_field_sources(test_settings):
    repository = EventRepository(test_settings.db_path)
    event = repository.by_names(["五四运动"])[0]

    assert len(event.sources) == 2
    assert event.evidence_status == "candidate"
    assert event.memory_tip_provenance == "project_original"
    assert set(event.claim_sources) == {"summary", "detail", "influence", "exam_points"}
    assert "summary" in event.sources[0].supported_fields
