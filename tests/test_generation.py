from __future__ import annotations

from dataclasses import replace

import httpx
from openai import APITimeoutError

from app.generation import AnswerGenerator
from app.models import QueryIntent, SearchHit


def test_model_timeout_returns_traceable_local_fallback(test_settings, monkeypatch):
    class FakeCompletions:
        @staticmethod
        def create(**_kwargs):
            raise APITimeoutError(request=httpx.Request("POST", "https://example.test"))

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app.generation.OpenAI", FakeClient)
    settings = replace(
        test_settings,
        use_llm=True,
        qwen_api_key="dummy",
    )
    event = __import__("app.database", fromlist=["EventRepository"]).EventRepository(
        test_settings.db_path
    ).by_names(["五四运动"])[0]
    result = AnswerGenerator(settings).generate(
        "五四运动有什么影响？",
        QueryIntent(intents=["impact"]),
        [SearchHit(event=event, score=1.0, matched_by=["exact_name"])],
        [],
    )

    assert result.error == "model_timeout"
    assert "[E1]" in result.answer
