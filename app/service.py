from __future__ import annotations

import logging
import time
import uuid

from app.config import Settings
from app.database import EventRepository
from app.generation import AnswerGenerator
from app.logging_config import configure_logging
from app.models import (
    Citation,
    HealthResponse,
    QARequest,
    QAResponse,
    RetrievedEvent,
)
from app.retrieval import HybridRetriever
from app.vector_index import VectorIndex

LOGGER = logging.getLogger("shijian.qa")


class QAService:
    def __init__(self, settings: Settings):
        self.settings = settings
        configure_logging(settings.log_level)
        self.repository = EventRepository(settings.db_path)
        self.vector_index = VectorIndex(settings)
        self.retriever = HybridRetriever(
            self.repository,
            self.vector_index,
            limit=settings.retrieval_limit,
        )
        self.generator = AnswerGenerator(settings)

    def health(self) -> HealthResponse:
        database_ready = self.repository.ready
        event_count = self.repository.count() if database_ready else 0
        vector_ready = self.vector_index.ready
        if not database_ready:
            status = "unhealthy"
            detail = "数据库未初始化，请运行 python -m scripts.init_database"
        elif not vector_ready or not self.generator.configured:
            status = "degraded"
            details = []
            if not vector_ready:
                details.append("向量索引未就绪，仍可使用精确检索和 FTS5")
            if not self.generator.configured:
                details.append("模型未配置，使用可溯源本地模板回答")
            detail = "；".join(details)
        else:
            status = "ok"
            detail = ""
        return HealthResponse(
            status=status,
            database_ready=database_ready,
            event_count=event_count,
            vector_ready=vector_ready,
            embedding_provider=self.settings.embedding_provider,
            llm_enabled=self.settings.use_llm,
            llm_configured=self.generator.configured,
            detail=detail,
        )

    @staticmethod
    def _retrieval_question(request: QARequest) -> str:
        question = request.question.strip()
        followup_words = ("它", "该事件", "上述", "这个事件", "那它")
        if any(word in question for word in followup_words):
            previous_users = [message.content for message in request.history if message.role == "user"]
            if previous_users:
                return f"{previous_users[-1]}；追问：{question}"
        return question

    def answer(self, request: QARequest) -> QAResponse:
        if not self.repository.ready:
            raise FileNotFoundError(
                f"database not found: {self.settings.db_path}; run python -m scripts.init_database"
            )
        started = time.perf_counter()
        trace_id = uuid.uuid4().hex
        retrieval_question = self._retrieval_question(request)
        retrieval = self.retriever.retrieve(retrieval_question)
        generation = self.generator.generate(
            request.question.strip(), retrieval.intent, retrieval.hits, request.history
        )

        citations = [
            Citation(
                ref=f"E{index}",
                event_id=hit.event.id,
                name=hit.event.name,
                year=hit.event.year,
                year_text=hit.event.year_text,
                source_title=hit.event.source_title,
                source_url=hit.event.source_url,
                excerpt=hit.event.summary,
            )
            for index, hit in enumerate(retrieval.hits, start=1)
        ]
        retrieved_events = [
            RetrievedEvent(
                id=hit.event.id,
                name=hit.event.name,
                year=hit.event.year,
                summary=hit.event.summary,
                score=hit.score,
                matched_by=hit.matched_by,
            )
            for hit in retrieval.hits
        ]
        refused = not retrieval.hits
        degraded = bool(generation.error)
        latency_ms = (time.perf_counter() - started) * 1000
        response = QAResponse(
            answer=generation.answer,
            citations=citations,
            retrieved_events=retrieved_events,
            retrieval_mode=retrieval.mode,
            trace_id=trace_id,
            latency_ms=round(latency_ms, 3),
            retrieval_ms=round(retrieval.latency_ms, 3),
            generation_ms=round(generation.latency_ms, 3),
            token_usage=generation.token_usage,
            degraded=degraded,
            refused=refused,
        )
        LOGGER.info(
            "qa_completed",
            extra={
                "trace_id": trace_id,
                "retrieval_mode": retrieval.mode,
                "retrieval_ms": response.retrieval_ms,
                "generation_ms": response.generation_ms,
                "latency_ms": response.latency_ms,
                "hit_count": len(retrieval.hits),
                "degraded": degraded,
                "refused": refused,
                "token_usage": generation.token_usage,
                "fallback_reason": generation.error or None,
            },
        )
        return response
