from __future__ import annotations

from scripts.validate_human_questions import load_jsonl, validate_records
from scripts.validate_human_scores import validate_score_records


def test_human_question_slots_have_required_distribution(test_settings):
    records = load_jsonl(test_settings.root_dir / "evaluation" / "human_questions.jsonl")
    events = load_jsonl(test_settings.data_dir / "history_events.jsonl")
    sources = load_jsonl(test_settings.data_dir / "sources.jsonl")

    failures = validate_records(
        records,
        {record["id"] for record in events},
        {record["source_id"] for record in sources},
        require_final=False,
    )

    assert failures == []
    assert len(records) == 80
    assert sum(record["review_status"] == "draft" for record in records) == 80


def test_release_gate_rejects_unfinished_human_questions(test_settings):
    records = load_jsonl(test_settings.root_dir / "evaluation" / "human_questions.jsonl")
    events = load_jsonl(test_settings.data_dir / "history_events.jsonl")
    sources = load_jsonl(test_settings.data_dir / "sources.jsonl")

    failures = validate_records(
        records,
        {record["id"] for record in events},
        {record["source_id"] for record in sources},
        require_final=True,
    )

    assert len(failures) == 80
    assert all("still draft" in failure for failure in failures)


def test_manual_score_sheet_has_30_draft_slots(test_settings):
    scores = load_jsonl(test_settings.root_dir / "evaluation" / "human_scores.jsonl")
    questions = load_jsonl(test_settings.root_dir / "evaluation" / "human_questions.jsonl")

    assert validate_score_records(
        scores,
        {record["id"] for record in questions},
        require_final=False,
    ) == []
    release_failures = validate_score_records(
        scores,
        {record["id"] for record in questions},
        require_final=True,
    )
    assert len(release_failures) == 30
