from __future__ import annotations

from dataclasses import replace

import pytest

from app.demo_guard import DemoGuard, HardRateLimitError


def test_guard_never_returns_raw_client_identifier(test_settings, tmp_path):
    guard = DemoGuard(
        replace(
            test_settings,
            public_demo_mode=True,
            runtime_dir=tmp_path,
            client_hash_salt="test-salt",
        )
    )
    client_hash = guard.register_request("203.0.113.42")

    assert client_hash != "203.0.113.42"
    assert len(client_hash) == 16


def test_guard_enforces_hard_request_limit(test_settings, tmp_path):
    guard = DemoGuard(
        replace(
            test_settings,
            public_demo_mode=True,
            runtime_dir=tmp_path,
            demo_hard_requests_per_minute=1,
        )
    )
    guard.register_request("client")
    with pytest.raises(HardRateLimitError):
        guard.register_request("client")


def test_guard_degrades_on_concurrency_and_daily_budget(test_settings, tmp_path):
    guard = DemoGuard(
        replace(
            test_settings,
            public_demo_mode=True,
            runtime_dir=tmp_path,
            demo_max_llm_concurrency=1,
            demo_daily_token_budget=1000,
            llm_max_tokens=100,
        )
    )
    client_hash = guard.hash_client("client")
    first = guard.begin_model_call(client_hash)
    concurrent = guard.begin_model_call(client_hash)

    assert first.allowed is True
    assert concurrent.reason == "llm_concurrency_limit"
    first.complete(actual_tokens=1000)
    exhausted = guard.begin_model_call(client_hash)
    assert exhausted.reason == "daily_token_budget_exhausted"
