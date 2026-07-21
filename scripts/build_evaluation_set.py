from __future__ import annotations

import json
from collections import defaultdict

from app.config import Settings
from app.database import EventRepository


def main() -> None:
    settings = Settings.from_env()
    repository = EventRepository(settings.db_path)
    events = repository.list_events()
    cases: list[dict[str, object]] = []

    by_year: dict[int, list[str]] = defaultdict(list)
    for event in events:
        by_year[event.year].append(event.id)
        cases.append(
            {
                "id": f"event-{event.id}",
                "category": "event_name",
                "question": f"请介绍{event.name}",
                "expected_event_ids": [event.id],
                "expected_facts": [event.name],
                "should_answer": True,
                "history": [],
            }
        )

    for index, (year, event_ids) in enumerate(sorted(by_year.items())):
        year_text = f"公元前{abs(year)}年" if year < 0 else f"{year}年"
        cases.append(
            {
                "id": f"year-{index:03d}",
                "category": "year",
                "question": f"{year_text}发生了什么大事？",
                "expected_event_ids": event_ids,
                "expected_facts": [],
                "should_answer": True,
                "history": [],
            }
        )

    for index, event in enumerate(events[:20]):
        for category, question in (
            ("cause", f"{event.name}为什么发生？"),
            ("impact", f"{event.name}有什么历史影响？"),
        ):
            cases.append(
                {
                    "id": f"{category}-{index:03d}",
                    "category": category,
                    "question": question,
                    "expected_event_ids": [event.id],
                    "expected_facts": [event.name],
                    "should_answer": True,
                    "history": [],
                }
            )

    for index, event in enumerate(events[:30]):
        keywords = [item.strip() for item in event.keywords.replace("，", ",").split(",") if item.strip()]
        clue = "、".join(keywords[:2])
        cases.append(
            {
                "id": f"semantic-{index:03d}",
                "category": "semantic",
                "question": f"与{clue}相关的是哪一历史事件？",
                "expected_event_ids": [event.id],
                "expected_facts": [event.name],
                "should_answer": True,
                "history": [],
            }
        )

    for index, event in enumerate(events[:10]):
        cases.append(
            {
                "id": f"memory-{index:03d}",
                "category": "memory",
                "question": f"{event.name}怎么记？",
                "expected_event_ids": [event.id],
                "expected_facts": [event.name],
                "should_answer": True,
                "history": [],
            }
        )
        cases.append(
            {
                "id": f"followup-{index:03d}",
                "category": "followup",
                "question": "它的影响是什么？",
                "expected_event_ids": [event.id],
                "expected_facts": [event.name],
                "should_answer": True,
                "history": [{"role": "user", "content": f"请介绍{event.name}"}],
            }
        )

    for index in range(0, 20, 2):
        first, second = events[index], events[index + 1]
        cases.append(
            {
                "id": f"compare-{index // 2:03d}",
                "category": "compare",
                "question": f"比较{first.name}和{second.name}",
                "expected_event_ids": [first.id, second.id],
                "expected_facts": [first.name, second.name],
                "should_answer": True,
                "history": [],
            }
        )

    used_people: set[str] = set()
    for event in events:
        for person in event.people.replace("，", "、").split("、"):
            person = person.strip()
            if len(person) < 2 or person in used_people:
                continue
            relevant = [candidate.id for candidate in events if person in candidate.people]
            cases.append(
                {
                    "id": f"person-{len(used_people):03d}",
                    "category": "person",
                    "question": f"{person}参与了哪些历史事件？",
                    "expected_event_ids": relevant,
                    "expected_facts": [],
                    "should_answer": True,
                    "history": [],
                }
            )
            used_people.add(person)
            if len(used_people) >= 15:
                break
        if len(used_people) >= 15:
            break

    unknown_questions = [
        "2025年发生了什么重大历史事件？",
        "公元前9999年发生了什么？",
        "火星殖民战争的影响是什么？",
        "量子王朝是谁建立的？",
        "大西洋帝国第一次改革是什么？",
        "银河会议为什么召开？",
        "请介绍不存在的青铜网络革命",
        "虚构人物张三丰二世参与了什么事件？",
        "3024年的工业革命有什么影响？",
        "月球统一战争怎么记？",
    ]
    for index, question in enumerate(unknown_questions):
        cases.append(
            {
                "id": f"unanswerable-{index:03d}",
                "category": "unanswerable",
                "question": question,
                "expected_event_ids": [],
                "expected_facts": [],
                "should_answer": False,
                "history": [],
            }
        )

    output = settings.root_dir / "evaluation" / "questions.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {len(cases)} evaluation cases to {output}")


if __name__ == "__main__":
    main()
