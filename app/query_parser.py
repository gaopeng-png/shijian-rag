from __future__ import annotations

import re

from app.database import EventRepository
from app.models import QueryIntent

YEAR_PATTERN = re.compile(r"公元前\s*(\d{1,4})|前\s*(\d{1,4})|(?<!\d)(\d{3,4})(?:\s*年)?(?!\d)")
STOP_PHRASES = {
    "发生了什么",
    "发生什么",
    "有什么",
    "哪一年",
    "这一年",
    "大事",
    "历史",
    "事件",
    "怎么记",
    "怎么背",
    "为什么",
    "原因",
    "背景",
    "影响",
    "意义",
    "经过",
    "结果",
    "介绍一下",
    "请问",
}


class QueryParser:
    def __init__(self, repository: EventRepository):
        self.repository = repository

    def parse(self, question: str) -> QueryIntent:
        question = question.strip()
        years: list[int] = []
        for match in YEAR_PATTERN.findall(question):
            value = next(part for part in match if part)
            year = int(value)
            if match[0] or match[1]:
                year = -year
            if year not in years:
                years.append(year)

        names, known_people = self.repository.entities()
        matched_names = [name for name in names if name in question]
        event_names = [
            name
            for name in matched_names
            if not any(name != other and name in other for other in matched_names)
        ]
        people = [person for person in known_people if person in question]

        intents: list[str] = []
        intent_words = {
            "cause": ("原因", "背景", "为什么", "起因", "爆发"),
            "process": ("经过", "过程", "结果"),
            "impact": ("影响", "意义", "作用"),
            "memory": ("记忆", "怎么记", "怎么背", "口诀", "考点"),
            "compare": ("比较", "区别", "联系", "异同", "对比"),
        }
        for intent, words in intent_words.items():
            if any(word in question for word in words):
                intents.append(intent)
        if not intents:
            intents.append("overview")

        cleaned = YEAR_PATTERN.sub(" ", question)
        for phrase in sorted(STOP_PHRASES, key=len, reverse=True):
            cleaned = cleaned.replace(phrase, " ")
        segments = re.split(r"[，。！？、,.!?；;：:\s]|(?:的|和|与|及|对)", cleaned)
        terms = [*event_names, *people]
        for segment in segments:
            segment = segment.strip()
            if len(segment) >= 2 and segment not in terms:
                terms.append(segment)

        scope = None
        if "中国史" in question or "中国" in question:
            scope = "中国史"
        elif "世界史" in question or "世界" in question:
            scope = "世界史"

        is_followup = any(word in question for word in ("它", "该事件", "上述", "这个事件", "那它"))
        return QueryIntent(
            years=years,
            event_names=event_names,
            people=people,
            terms=terms,
            intents=intents,  # type: ignore[arg-type]
            scope=scope,
            is_followup=is_followup,
        )
