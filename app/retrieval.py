from __future__ import annotations

import time
from dataclasses import dataclass

from app.database import EventRepository
from app.models import QueryIntent, SearchHit
from app.query_parser import QueryParser
from app.vector_index import VectorIndex


@dataclass(slots=True)
class RetrievalResult:
    hits: list[SearchHit]
    intent: QueryIntent
    mode: str
    latency_ms: float


class HybridRetriever:
    RRF_K = 60
    CHANNEL_WEIGHTS = {
        "exact_name": 4.0,
        "exact_year": 3.0,
        "exact_person": 2.5,
        "fts": 1.5,
        "like": 1.0,
        "vector": 1.0,
    }

    def __init__(
        self,
        repository: EventRepository,
        vector_index: VectorIndex | None = None,
        limit: int = 5,
    ):
        self.repository = repository
        self.vector_index = vector_index
        self.limit = limit
        self.parser = QueryParser(repository)

    def retrieve(self, question: str) -> RetrievalResult:
        started = time.perf_counter()
        intent = self.parser.parse(question)
        channels: dict[str, list[str]] = {}

        if intent.years:
            year_events = self.repository.by_years(intent.years, limit=self.limit)
            if intent.event_names:
                requested = set(intent.event_names)
                year_events = [event for event in year_events if event.name in requested]
            hits = [
                SearchHit(event=event, score=1.0 / rank, matched_by=["exact_year"])
                for rank, event in enumerate(year_events, start=1)
            ]
            return RetrievalResult(
                hits=hits,
                intent=intent,
                mode="exact_year" if hits else "no_match",
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        if intent.event_names:
            name_events = self.repository.by_names(intent.event_names, limit=self.limit)
            hits = [
                SearchHit(event=event, score=1.0 / rank, matched_by=["exact_name"])
                for rank, event in enumerate(name_events, start=1)
            ]
            return RetrievalResult(
                hits=hits,
                intent=intent,
                mode="exact_name",
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        if intent.people:
            channels["exact_person"] = [event.id for event in self.repository.by_people(intent.people)]

        fts_events = self.repository.search_fts(intent.terms, limit=20)
        if fts_events:
            channels["fts"] = [event.id for event in fts_events]
        like_events = self.repository.search_like(intent.terms, limit=20)
        if like_events:
            channels["like"] = [event.id for event in like_events]

        if self.vector_index and self.vector_index.ready:
            vector_hits = self.vector_index.search(question, limit=20)
            if vector_hits:
                channels["vector"] = [hit.event_id for hit in vector_hits]

        # A substring-only match on a generic word such as “召开” or “改革” is
        # not enough evidence for a factual answer. FTS phrase matches and
        # high-confidence vector matches can stand alone; LIKE is supporting
        # evidence only.
        if set(channels) == {"like"}:
            channels.clear()

        scores: dict[str, float] = {}
        matched_by: dict[str, list[str]] = {}
        for channel, event_ids in channels.items():
            weight = self.CHANNEL_WEIGHTS[channel]
            for rank, event_id in enumerate(dict.fromkeys(event_ids), start=1):
                scores[event_id] = scores.get(event_id, 0.0) + weight / (self.RRF_K + rank)
                matched_by.setdefault(event_id, []).append(channel)

        ranked_ids = sorted(scores, key=scores.get, reverse=True)[: self.limit]
        events = self.repository.get_many(ranked_ids)
        by_id = {event.id: event for event in events}
        hits = [
            SearchHit(event=by_id[event_id], score=scores[event_id], matched_by=matched_by[event_id])
            for event_id in ranked_ids
            if event_id in by_id
        ]
        used_channels = [channel for channel in self.CHANNEL_WEIGHTS if channel in channels]
        if len(used_channels) > 1:
            mode = "+".join(used_channels) + "+rrf"
        elif used_channels:
            mode = used_channels[0]
        else:
            mode = "no_match"
        latency_ms = (time.perf_counter() - started) * 1000
        return RetrievalResult(hits=hits, intent=intent, mode=mode, latency_ms=latency_ms)
