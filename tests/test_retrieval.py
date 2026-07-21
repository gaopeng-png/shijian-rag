from __future__ import annotations

from app.database import EventRepository
from app.retrieval import HybridRetriever
from app.vector_index import VectorIndex


def build_retriever(settings):
    repository = EventRepository(settings.db_path)
    return HybridRetriever(repository, VectorIndex(settings), limit=5)


def test_exact_year_and_name_are_deterministic(test_settings):
    retriever = build_retriever(test_settings)
    by_year = retriever.retrieve("1919 年发生了什么大事？")
    by_name = retriever.retrieve("五四运动有什么影响？")
    assert by_year.hits[0].event.name == "五四运动"
    assert by_year.mode == "exact_year"
    assert by_name.hits[0].event.name == "五四运动"
    assert by_name.mode == "exact_name"


def test_unknown_explicit_year_is_not_filled_by_vector_search(test_settings):
    result = build_retriever(test_settings).retrieve("2025 年发生了什么历史事件？")
    assert result.hits == []
    assert result.mode == "no_match"


def test_person_query_uses_hybrid_rrf(test_settings):
    result = build_retriever(test_settings).retrieve("孙中山参与了哪些历史事件？")
    assert result.hits
    assert any("exact_person" in hit.matched_by for hit in result.hits)
    assert "rrf" in result.mode
