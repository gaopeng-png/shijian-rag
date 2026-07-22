from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date

from app.config import Settings


class HardRateLimitError(RuntimeError):
    def __init__(self, retry_after: int = 60):
        super().__init__("request_rate_limit")
        self.retry_after = retry_after


@dataclass(slots=True)
class ModelLease:
    guard: DemoGuard
    allowed: bool
    reason: str | None = None
    reserved_tokens: int = 0
    released: bool = False

    def complete(self, actual_tokens: int = 0) -> None:
        if self.released or not self.allowed:
            return
        self.released = True
        self.guard._finish_model_call(self.reserved_tokens, max(0, actual_tokens))


class DemoGuard:
    """Thread-safe public demo limits; raw client identifiers are never retained."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._llm_requests: dict[str, deque[float]] = defaultdict(deque)
        self._semaphore = threading.BoundedSemaphore(settings.demo_max_llm_concurrency)
        self._usage_db = settings.runtime_dir / "demo_usage.db"
        if settings.public_demo_mode:
            settings.runtime_dir.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._usage_db) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS daily_usage (day TEXT PRIMARY KEY, tokens INTEGER NOT NULL)"
                )

    def hash_client(self, client_identifier: str) -> str:
        value = f"{self.settings.client_hash_salt}:{client_identifier or 'unknown'}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _prune(values: deque[float], now: float) -> None:
        while values and now - values[0] >= 60:
            values.popleft()

    def register_request(self, client_identifier: str) -> str:
        client_hash = self.hash_client(client_identifier)
        if not self.settings.public_demo_mode:
            return client_hash
        now = time.monotonic()
        with self._lock:
            requests = self._requests[client_hash]
            self._prune(requests, now)
            if len(requests) >= self.settings.demo_hard_requests_per_minute:
                raise HardRateLimitError()
            requests.append(now)
        return client_hash

    def _reserve_daily_tokens(self, amount: int) -> bool:
        today = date.today().isoformat()
        with sqlite3.connect(self._usage_db) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT tokens FROM daily_usage WHERE day = ?", (today,)
            ).fetchone()
            used = int(row[0]) if row else 0
            if used + amount > self.settings.demo_daily_token_budget:
                conn.rollback()
                return False
            conn.execute(
                "INSERT INTO daily_usage(day, tokens) VALUES (?, ?) "
                "ON CONFLICT(day) DO UPDATE SET tokens=excluded.tokens",
                (today, used + amount),
            )
            conn.commit()
        return True

    def begin_model_call(self, client_hash: str) -> ModelLease:
        if not self.settings.public_demo_mode:
            return ModelLease(self, allowed=True)
        now = time.monotonic()
        with self._lock:
            requests = self._llm_requests[client_hash]
            self._prune(requests, now)
            if len(requests) >= self.settings.demo_llm_requests_per_minute:
                return ModelLease(self, allowed=False, reason="llm_rate_limit")
            if not self._semaphore.acquire(blocking=False):
                return ModelLease(self, allowed=False, reason="llm_concurrency_limit")
            reservation = max(1000, self.settings.llm_max_tokens * 3)
            if not self._reserve_daily_tokens(reservation):
                self._semaphore.release()
                return ModelLease(
                    self,
                    allowed=False,
                    reason="daily_token_budget_exhausted",
                )
            requests.append(now)
        return ModelLease(self, allowed=True, reserved_tokens=reservation)

    def _finish_model_call(self, reserved_tokens: int, actual_tokens: int) -> None:
        try:
            if self.settings.public_demo_mode and reserved_tokens:
                today = date.today().isoformat()
                with sqlite3.connect(self._usage_db) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    row = conn.execute(
                        "SELECT tokens FROM daily_usage WHERE day = ?", (today,)
                    ).fetchone()
                    used = int(row[0]) if row else 0
                    adjusted = max(0, used - reserved_tokens + actual_tokens)
                    conn.execute(
                        "INSERT INTO daily_usage(day, tokens) VALUES (?, ?) "
                        "ON CONFLICT(day) DO UPDATE SET tokens=excluded.tokens",
                        (today, adjusted),
                    )
                    conn.commit()
        finally:
            if self.settings.public_demo_mode:
                self._semaphore.release()

    def daily_token_usage(self) -> int:
        if not self.settings.public_demo_mode or not self._usage_db.is_file():
            return 0
        with sqlite3.connect(self._usage_db) as conn:
            row = conn.execute(
                "SELECT tokens FROM daily_usage WHERE day = ?", (date.today().isoformat(),)
            ).fetchone()
        return int(row[0]) if row else 0
