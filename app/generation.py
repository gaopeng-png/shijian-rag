from __future__ import annotations

import time
from dataclasses import dataclass

from openai import APITimeoutError, OpenAI, RateLimitError

from app.config import Settings
from app.models import ChatMessage, QueryIntent, SearchHit

SYSTEM_PROMPT = """你是“史鉴 RAG”，面向学生的历史问答助手。
只能根据用户消息中提供的可溯源资料回答，不得使用未提供的事实补全。
每个事实段落必须使用 [E1]、[E2] 这样的资料编号标注依据。
如果资料不足，请明确说明知识库未收录，不得猜测。
优先直接回答用户意图，再补充必要背景；语言准确、简洁、适合复习。
"""


@dataclass(slots=True)
class GenerationResult:
    answer: str
    latency_ms: float
    token_usage: int = 0
    error: str = ""


def build_context(hits: list[SearchHit]) -> str:
    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        event = hit.event
        blocks.append(
            "\n".join(
                [
                    f"[E{index}] 事件：{event.name}（{event.year_text}）",
                    f"人物：{event.people}",
                    f"概览：{event.summary}",
                    f"背景与经过：{event.detail}",
                    f"影响：{event.influence}",
                    f"考试要点：{event.exam_points}",
                    f"记忆提示：{event.memory_tip}",
                ]
            )
        )
    return "\n\n".join(blocks)


def local_answer(question: str, intent: QueryIntent, hits: list[SearchHit]) -> str:
    if not hits:
        return (
            "未在本地可溯源历史知识库中找到足够可靠的资料，因此暂不生成事实性回答。"
            "你可以换用更明确的年份、事件名称或人物重新提问。"
        )

    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        event = hit.event
        ref = f"[E{index}]"
        lines = [f"### {event.name}（{event.year_text}）{ref}"]
        if "cause" in intent.intents:
            lines.append(f"- 背景与原因：{event.detail} {ref}")
        elif "impact" in intent.intents:
            lines.append(f"- 历史影响：{event.influence} {ref}")
        elif "process" in intent.intents:
            lines.append(f"- 经过与结果：{event.detail} {ref}")
        elif "memory" in intent.intents:
            lines.extend(
                [
                    f"- 考试要点：{event.exam_points} {ref}",
                    f"- 记忆提示：{event.memory_tip} {ref}",
                ]
            )
        else:
            lines.extend(
                [
                    f"- 事件概览：{event.summary} {ref}",
                    f"- 背景与经过：{event.detail} {ref}",
                    f"- 历史影响：{event.influence} {ref}",
                    f"- 记忆提示：{event.memory_tip} {ref}",
                ]
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


class AnswerGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return self.settings.use_llm and bool(self.settings.qwen_api_key)

    def generate(
        self,
        question: str,
        intent: QueryIntent,
        hits: list[SearchHit],
        history: list[ChatMessage],
        force_local_reason: str | None = None,
    ) -> GenerationResult:
        started = time.perf_counter()
        if not hits:
            return GenerationResult(
                answer=local_answer(question, intent, hits),
                latency_ms=(time.perf_counter() - started) * 1000,
                error="no_retrieval_evidence",
            )
        if force_local_reason:
            return GenerationResult(
                answer=local_answer(question, intent, hits),
                latency_ms=(time.perf_counter() - started) * 1000,
                error=force_local_reason,
            )
        if not self.configured:
            reason = "llm_disabled" if not self.settings.use_llm else "api_key_missing"
            return GenerationResult(
                answer=local_answer(question, intent, hits),
                latency_ms=(time.perf_counter() - started) * 1000,
                error=reason,
            )

        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in history[-4:]
        )
        messages.append(
            {
                "role": "user",
                "content": f"用户问题：{question}\n\n可用资料：\n{build_context(hits)}",
            }
        )
        try:
            client = OpenAI(
                api_key=self.settings.qwen_api_key,
                base_url=self.settings.qwen_base_url,
                timeout=self.settings.llm_timeout_seconds,
                max_retries=1,
            )
            response = client.chat.completions.create(
                model=self.settings.qwen_model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.2,
                max_tokens=self.settings.llm_max_tokens,
            )
            answer = response.choices[0].message.content or ""
            if not any(f"[E{index}]" in answer for index in range(1, len(hits) + 1)):
                answer += "\n\n资料依据：" + "、".join(
                    f"[E{index}] {hit.event.name}" for index, hit in enumerate(hits, start=1)
                )
            usage = int(response.usage.total_tokens) if response.usage else 0
            return GenerationResult(
                answer=answer.strip(),
                latency_ms=(time.perf_counter() - started) * 1000,
                token_usage=usage,
            )
        except APITimeoutError:
            error = "model_timeout"
        except RateLimitError:
            error = "model_rate_limited"
        except Exception as exc:
            error = f"model_error:{type(exc).__name__}"
        return GenerationResult(
            answer=local_answer(question, intent, hits),
            latency_ms=(time.perf_counter() - started) * 1000,
            error=error,
        )
