from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from app.api import create_app


def test_health_and_qa_contract(test_settings):
    with TestClient(create_app(test_settings)) as client:
        health = client.get("/healthz")
        response = client.post("/api/v1/qa", json={"question": "1919 年发生了什么？"})
    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["event_count"] == 100
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_mode"] == "exact_year"
    assert payload["citations"][0]["name"] == "五四运动"
    assert payload["trace_id"]


def test_validation_rejects_empty_question(test_settings):
    with TestClient(create_app(test_settings)) as client:
        response = client.post("/api/v1/qa", json={"question": ""})
    assert response.status_code == 422


def test_health_returns_503_when_database_is_missing(test_settings, tmp_path):
    storage = tmp_path / "missing-storage"
    settings = replace(
        test_settings,
        storage_dir=storage,
        db_path=storage / "missing.db",
        chroma_dir=storage / "chroma",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/healthz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unhealthy"
    assert payload["database_ready"] is False
    assert payload["event_count"] == 0
