from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from app.config import Settings
from app.models import ChatMessage, QARequest
from app.query_parser import QueryParser
from app.service import QAService


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline retrieval and grounding evaluation")
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce", action="store_true", help="Fail when acceptance thresholds are missed")
    return parser.parse_args()


def baseline_ranked_ids(service: QAService, request: QARequest) -> list[str]:
    """Approximate the original rule/LIKE retriever for an honest comparison."""
    question = service._retrieval_question(request)
    intent = QueryParser(service.repository).parse(question)
    if intent.years:
        return [event.id for event in service.repository.by_years(intent.years, limit=5)]
    if intent.event_names:
        return [event.id for event in service.repository.by_names(intent.event_names, limit=5)]
    if intent.people:
        return [event.id for event in service.repository.by_people(intent.people, limit=5)]
    return [event.id for event in service.repository.search_like(intent.terms, limit=5)]


def main() -> None:
    args = parse_args()
    base = Settings.from_env()
    settings = Settings.from_env(use_llm=False)
    questions_path = (args.questions or base.root_dir / "evaluation" / "questions.jsonl").resolve()
    output_path = (args.output or base.root_dir / "evaluation" / "results.json").resolve()
    with questions_path.open(encoding="utf-8") as handle:
        cases = [json.loads(line) for line in handle if line.strip()]

    service = QAService(settings)
    hit_scores: list[float] = []
    reciprocal_ranks: list[float] = []
    exact_recall: list[float] = []
    citation_scores: list[float] = []
    fact_scores: list[float] = []
    refusal_scores: list[float] = []
    latencies: list[float] = []
    failures: list[dict[str, object]] = []
    baseline_hits: list[float] = []
    baseline_reciprocal_ranks: list[float] = []
    baseline_refusals: list[float] = []

    for case in cases:
        request = QARequest(
            question=case["question"],
            history=[ChatMessage(**message) for message in case.get("history", [])],
        )
        response = service.answer(request)
        ranked = [event.id for event in response.retrieved_events]
        baseline_ranked = baseline_ranked_ids(service, request)
        expected = set(case["expected_event_ids"])
        if case["should_answer"]:
            hit = float(any(event_id in expected for event_id in ranked[:5]))
            hit_scores.append(hit)
            first_rank = next(
                (rank for rank, event_id in enumerate(ranked, start=1) if event_id in expected),
                None,
            )
            reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)
            baseline_hits.append(float(any(event_id in expected for event_id in baseline_ranked[:5])))
            baseline_first_rank = next(
                (rank for rank, event_id in enumerate(baseline_ranked, start=1) if event_id in expected),
                None,
            )
            baseline_reciprocal_ranks.append(
                1.0 / baseline_first_rank if baseline_first_rank else 0.0
            )
            if case["category"] in {"year", "event_name"}:
                exact_recall.append(float(bool(ranked) and ranked[0] in expected))
            cited_refs = {f"[E{index}]" for index in range(1, len(response.citations) + 1)}
            citation_scores.append(
                float(bool(cited_refs) and all(ref in response.answer for ref in cited_refs))
            )
            facts = case.get("expected_facts", [])
            if facts:
                fact_scores.append(float(all(fact in response.answer for fact in facts)))
            if not hit:
                failures.append(
                    {
                        "id": case["id"],
                        "question": case["question"],
                        "expected": sorted(expected),
                        "retrieved": ranked,
                    }
                )
        else:
            refusal_scores.append(float(response.refused))
            baseline_refusals.append(float(not baseline_ranked))
            if not response.refused:
                failures.append(
                    {
                        "id": case["id"],
                        "question": case["question"],
                        "expected": "refusal",
                        "retrieved": ranked,
                    }
                )
        latencies.append(response.retrieval_ms)

    metrics = {
        "case_count": len(cases),
        "answerable_count": sum(bool(case["should_answer"]) for case in cases),
        "unanswerable_count": sum(not bool(case["should_answer"]) for case in cases),
        "hit_at_5": round(statistics.fmean(hit_scores), 4),
        "mrr_at_5": round(statistics.fmean(reciprocal_ranks), 4),
        "exact_recall_at_1": round(statistics.fmean(exact_recall), 4),
        "citation_coverage": round(statistics.fmean(citation_scores), 4),
        "fact_support_rate": round(statistics.fmean(fact_scores), 4),
        "refusal_accuracy": round(statistics.fmean(refusal_scores), 4),
        "retrieval_p50_ms": round(percentile(latencies, 0.50), 3),
        "retrieval_p95_ms": round(percentile(latencies, 0.95), 3),
        "failed_cases": len(failures),
        "baseline_hit_at_5": round(statistics.fmean(baseline_hits), 4),
        "baseline_mrr_at_5": round(statistics.fmean(baseline_reciprocal_ranks), 4),
        "baseline_refusal_accuracy": round(statistics.fmean(baseline_refusals), 4),
    }
    payload = {"metrics": metrics, "failures": failures}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = output_path.with_name("REPORT.md")
    report_path.write_text(
        "\n".join(
            [
                "# 史鉴 RAG 离线评测报告",
                "",
                "> 指标由 `python -m scripts.run_evaluation` 在关闭大模型的可复现模式下生成。",
                "",
                "| 指标 | 结果 |",
                "| --- | ---: |",
                *[f"| {key} | {value} |" for key, value in metrics.items()],
                "",
                "## 说明",
                "",
                "- Hit@5/MRR@5 衡量标注事件在前五个召回结果中的位置。",
                "- 引用覆盖率要求回答中的每个返回引用都有对应 `[E#]` 标记。",
                "- 事实支持率只检查评测集声明的关键事实，不等同于完整人工事实审查。",
                "- P95 仅代表本机本地检索，不包含网络模型调用耗时。",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if args.enforce:
        thresholds = {
            "hit_at_5": 0.90,
            "mrr_at_5": 0.80,
            "exact_recall_at_1": 1.00,
            "citation_coverage": 0.90,
            "fact_support_rate": 0.90,
            "refusal_accuracy": 0.90,
        }
        missed = [
            f"{name}={metrics[name]} < {minimum}"
            for name, minimum in thresholds.items()
            if float(metrics[name]) < minimum
        ]
        if float(metrics["retrieval_p95_ms"]) >= 200:
            missed.append(f"retrieval_p95_ms={metrics['retrieval_p95_ms']} >= 200")
        if missed:
            raise SystemExit("acceptance thresholds missed: " + "; ".join(missed))


if __name__ == "__main__":
    main()
