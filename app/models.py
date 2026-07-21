from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Event(BaseModel):
    id: str
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
    source_title: str = "史鉴 RAG 项目内置历史事件资料"
    source_url: str = ""
    content_hash: str = ""

    @property
    def year_text(self) -> str:
        return f"公元前{abs(self.year)}年" if self.year < 0 else f"{self.year}年"

    def embedding_text(self) -> str:
        return "\n".join(
            [
                f"事件：{self.name}",
                f"年份：{self.year_text}",
                f"时期：{self.period}",
                f"地区：{self.region}",
                f"范围：{self.scope}",
                f"人物：{self.people}",
                f"关键词：{self.keywords}",
                f"概览：{self.summary}",
                f"背景与经过：{self.detail}",
                f"影响：{self.influence}",
                f"考试要点：{self.exam_points}",
                f"记忆提示：{self.memory_tip}",
            ]
        )


class QueryIntent(BaseModel):
    years: list[int] = Field(default_factory=list)
    event_names: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    intents: list[Literal["overview", "cause", "process", "impact", "memory", "compare"]] = (
        Field(default_factory=list)
    )
    scope: str | None = None
    is_followup: bool = False


class SearchHit(BaseModel):
    event: Event
    score: float
    matched_by: list[str]


class Citation(BaseModel):
    ref: str
    event_id: str
    name: str
    year: int
    year_text: str
    source_title: str
    source_url: str = ""
    excerpt: str


class RetrievedEvent(BaseModel):
    id: str
    name: str
    year: int
    summary: str
    score: float
    matched_by: list[str]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_events: list[RetrievedEvent]
    retrieval_mode: str
    trace_id: str
    latency_ms: float
    retrieval_ms: float
    generation_ms: float
    token_usage: int = 0
    degraded: bool = False
    refused: bool = False


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unhealthy"]
    database_ready: bool
    event_count: int
    vector_ready: bool
    embedding_provider: str
    llm_enabled: bool
    llm_configured: bool
    detail: str = ""
