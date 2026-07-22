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
    assert payload["citations"][0]["source_title"]
    assert payload["citations"][0]["sources"][0]["publisher"]
    assert payload["degraded_reason"] == "llm_disabled"
    assert payload["trace_id"]


def test_readiness_and_meta_contract(test_settings):
    with TestClient(create_app(test_settings)) as client:
        ready = client.get("/readyz")
        meta = client.get("/api/v1/meta")

    assert ready.status_code == 200
    assert ready.json()["vector_ready"] is True
    assert meta.status_code == 200
    assert meta.json()["event_count"] == 100
    assert meta.json()["source_count"] == 22
    assert meta.json()["verified_event_count"] == 0
    assert len(meta.json()["evidence_revision"]) == 12


def test_gradio_is_mounted_at_root(test_settings):
    with TestClient(create_app(test_settings, mount_ui=True)) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "史鉴 RAG" in response.text


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


def test_ready_returns_503_when_vector_index_is_missing(test_settings, tmp_path):
    settings = replace(test_settings, chroma_dir=tmp_path / "missing-chroma")

    with TestClient(create_app(settings)) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["database_ready"] is True
    assert response.json()["vector_ready"] is False


def test_public_hard_rate_limit_returns_429(test_settings, tmp_path):
    settings = replace(
        test_settings,
        public_demo_mode=True,
        demo_hard_requests_per_minute=1,
        runtime_dir=tmp_path / "runtime",
        client_hash_salt="test-only-salt",
    )
    with TestClient(create_app(settings)) as client:
        first = client.post("/api/v1/qa", json={"question": "五四运动"})
        second = client.post("/api/v1/qa", json={"question": "五四运动"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"


def test_public_rate_limit_uses_original_forwarded_client(test_settings, tmp_path):
    settings = replace(
        test_settings,
        public_demo_mode=True,
        demo_hard_requests_per_minute=1,
        runtime_dir=tmp_path / "runtime",
        client_hash_salt="test-only-salt",
    )
    with TestClient(create_app(settings)) as client:
        first = client.post(
            "/api/v1/qa",
            json={"question": "五四运动"},
            headers={"x-forwarded-for": "203.0.113.1, 10.0.0.1"},
        )
        same_client = client.post(
            "/api/v1/qa",
            json={"question": "五四运动"},
            headers={"x-forwarded-for": "203.0.113.1, 10.0.0.2"},
        )
        different_client = client.post(
            "/api/v1/qa",
            json={"question": "五四运动"},
            headers={"x-forwarded-for": "203.0.113.2, 10.0.0.2"},
        )

    assert first.status_code == 200
    assert same_client.status_code == 429
    assert different_client.status_code == 200


def test_public_llm_rate_limit_degrades_instead_of_429(test_settings, tmp_path):
    settings = replace(
        test_settings,
        use_llm=True,
        qwen_api_key="dummy",
        public_demo_mode=True,
        demo_llm_requests_per_minute=0,
        runtime_dir=tmp_path / "runtime",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/qa", json={"question": "五四运动"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["degraded"] is True
    assert payload["degraded_reason"] == "llm_rate_limit"
    assert payload["citations"][0]["sources"]
