from __future__ import annotations

import argparse
import concurrent.futures
import json
import urllib.error
import urllib.request
from pathlib import Path

from app.config import ROOT_DIR
from app.database import load_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check authoritative source links")
    parser.add_argument("--sources", type=Path, default=ROOT_DIR / "data" / "sources.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "evaluation" / "source_links.json")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def check(url: str, timeout: float) -> tuple[str, int | None, str]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "shijian-rag-link-check/1.1 (+metadata-only)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
        return ("passed" if 200 <= status < 400 else "failed", status, "")
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 429}:
            return "manual_review", exc.code, "website denied automated access"
        return "failed", exc.code, str(exc.reason)
    except (urllib.error.URLError, TimeoutError) as exc:
        return "unreachable", None, str(exc.reason if hasattr(exc, "reason") else exc)


def main() -> None:
    args = parse_args()
    sources = load_sources(args.sources.resolve())
    def check_one(item: tuple[str, dict[str, str]]) -> dict[str, object]:
        source_id, source = item
        state, status_code, detail = check(source["url"], args.timeout)
        return {
            "source_id": source_id,
            "url": source["url"],
            "state": state,
            "status_code": status_code,
            "detail": detail,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(check_one, sources.items()))
    summary = {
        state: sum(result["state"] == state for result in results)
        for state in ("passed", "manual_review", "unreachable", "failed")
    }
    payload = {"summary": summary, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if args.strict and summary["failed"]:
        raise SystemExit("one or more source links returned a permanent HTTP error")


if __name__ == "__main__":
    main()
