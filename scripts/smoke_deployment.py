from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.request


def request_json(url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def wait_ready(base_url: str, attempts: int) -> None:
    for _ in range(attempts):
        try:
            request_json(f"{base_url}/readyz")
            return
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(10)
    raise SystemExit("deployment did not become ready")


def qa(base_url: str, question: str) -> dict[str, object]:
    return request_json(f"{base_url}/api/v1/qa", {"question": question, "history": []})


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a deployed ShiJian RAG instance")
    parser.add_argument("base_url")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--full-load", action="store_true")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    wait_ready(base_url, args.attempts)

    if "史鉴 RAG" not in request_text(f"{base_url}/"):
        raise SystemExit("Gradio UI is not mounted at the deployment root")
    meta = request_json(f"{base_url}/api/v1/meta")
    if meta.get("event_count") != 100 or meta.get("source_count", 0) < 1:
        raise SystemExit(f"unexpected deployment metadata: {meta}")
    exact = qa(base_url, "五四运动的影响是什么？")
    citations = exact.get("citations", [])
    if not citations or not citations[0].get("sources"):
        raise SystemExit("exact query did not return authoritative source metadata")
    refused = qa(base_url, "2025年发生了什么历史事件？")
    if not refused.get("refused"):
        raise SystemExit("unanswerable query was not refused")

    responses = [exact, refused]
    if args.full_load:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            concurrent_responses = list(
                executor.map(
                    lambda _: qa(base_url, "鸦片战争为什么爆发？"),
                    range(5),
                )
            )
        responses.extend(concurrent_responses)
        concurrency_fallbacks = sum(
            response.get("degraded_reason") == "llm_concurrency_limit"
            for response in concurrent_responses
        )
        if meta.get("model_mode") == "qwen" and concurrency_fallbacks < 3:
            raise SystemExit("five-way test did not demonstrate the two-call concurrency limit")
        for _ in range(18):
            responses.append(qa(base_url, "五四运动的影响是什么？"))

    encoded = json.dumps(responses, ensure_ascii=False)
    if "DASHSCOPE_API_KEY" in encoded or "sk-" in encoded:
        raise SystemExit("a response may contain secret material")
    print(
        json.dumps(
            {
                "base_url": base_url,
                "responses": len(responses),
                "model_mode": meta.get("model_mode"),
                "status": "passed",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
