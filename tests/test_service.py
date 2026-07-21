from __future__ import annotations

from app.models import ChatMessage, QARequest
from app.service import QAService


def test_local_fallback_is_cited_and_structured(test_settings):
    response = QAService(test_settings).answer(QARequest(question="五四运动的影响是什么？"))
    assert response.degraded is True
    assert response.refused is False
    assert response.citations[0].name == "五四运动"
    assert "[E1]" in response.answer
    assert response.retrieval_mode == "exact_name"


def test_unanswerable_question_is_refused(test_settings):
    response = QAService(test_settings).answer(QARequest(question="2025 年发生了什么？"))
    assert response.refused is True
    assert response.citations == []
    assert "暂不生成事实性回答" in response.answer


def test_followup_reuses_previous_user_entity(test_settings):
    response = QAService(test_settings).answer(
        QARequest(
            question="它的影响是什么？",
            history=[ChatMessage(role="user", content="请介绍五四运动")],
        )
    )
    assert response.retrieved_events[0].name == "五四运动"
