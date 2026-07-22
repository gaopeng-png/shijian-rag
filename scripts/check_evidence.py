from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import ROOT_DIR
from app.database import load_evidence, load_sources

PRIORITY_EVENTS = {
    "秦统一六国",
    "鸦片战争",
    "南京条约签订",
    "甲午中日战争",
    "辛亥革命",
    "五四运动",
    "中国共产党成立",
    "南京大屠杀",
    "抗日战争胜利",
    "中华人民共和国成立",
    "改革开放",
    "文艺复兴",
    "哥伦布到达美洲",
    "法国大革命",
    "工业革命",
    "美国独立宣言发表",
    "第一次世界大战爆发",
    "第二次世界大战结束",
    "俄国十月革命",
    "联合国成立",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate source and field-evidence metadata")
    parser.add_argument("--data-dir", type=Path, default=ROOT_DIR / "data")
    parser.add_argument(
        "--require-verified",
        action="store_true",
        help="Release gate: require every event to have a signed verified review",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    events = [
        json.loads(line)
        for line in (data_dir / "history_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    sources = load_sources(data_dir / "sources.jsonl")
    evidence = load_evidence(data_dir / "event_evidence.jsonl", sources)
    event_by_id = {str(event["id"]): event for event in events}
    failures: list[str] = []

    if set(event_by_id) != set(evidence):
        failures.append("evidence event IDs must exactly match the event dataset")
    for event_id, record in evidence.items():
        event = event_by_id.get(event_id, {})
        linked_ids = [str(item["source_id"]) for item in record["sources"]]
        if not any(sources[source_id]["authority_level"] in {"A", "B"} for source_id in linked_ids):
            failures.append(f"{event_id} has no A/B source")
        if event.get("name") in PRIORITY_EVENTS:
            publishers = {sources[source_id]["publisher"] for source_id in linked_ids}
            if len(linked_ids) < 2 or len(publishers) < 2:
                failures.append(f"{event_id} priority event needs two independent sources")
        if args.require_verified and record["status"] != "verified":
            failures.append(f"{event_id} is not verified")

    statuses: dict[str, int] = {}
    for record in evidence.values():
        status = str(record["status"])
        statuses[status] = statuses.get(status, 0) + 1
    report = {
        "event_count": len(events),
        "source_count": len(sources),
        "evidence_count": len(evidence),
        "priority_count": len(PRIORITY_EVENTS),
        "review_statuses": statuses,
        "release_ready": not failures and statuses.get("verified", 0) == len(events),
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit("evidence validation failed")


if __name__ == "__main__":
    main()
