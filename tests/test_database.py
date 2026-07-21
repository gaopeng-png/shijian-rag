from __future__ import annotations

from app.database import EventRepository


def test_database_contains_reviewable_event_data(test_settings):
    repository = EventRepository(test_settings.db_path)
    assert repository.count() == 100
    event = repository.by_names(["五四运动"])[0]
    assert event.id.startswith("evt-")
    assert len(event.content_hash) == 64


def test_fts_and_people_search(test_settings):
    repository = EventRepository(test_settings.db_path)
    assert any(event.name == "五四运动" for event in repository.search_fts(["五四运动"]))
    assert any("孙中山" in event.people for event in repository.by_people(["孙中山"]))
