from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from app.config import Settings
from app.models import ChatMessage, QARequest
from app.query_parser import QueryParser
from app.service import QAService
from scripts.validate_human_questions import load_jsonl, validate_records
from scripts.validate_human_scores import score_metrics, validate_score_records


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline retrieval and grounding evaluation")
    parser.add_argument("--suite", choices=("regression", "human", "all"), default="regression")
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce", action="store_true", help="Fail when suite thresholds are missed")
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


def normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    if "should_answer" in case:
        return case
    return {
        **case,
        "history": case.get("conversation_history", []),
        "expected_facts": case.get("required_facts", []),
        "should_answer": not bool(case.get("should_refuse", False)),
    }


def evaluate_cases(cases: list[dict[str, Any]], service: QAService) -> dict[str, Any]:
    hit_scores: list[float] = []
    reciprocal_ranks: list[float] = []
    exact_recall: list[float] = []
    citation_scores: list[float] = []
    source_scores: list[float] = []
    fact_scores: list[float] = []
    forbidden_fact_scores: list[float] = []
    refusal_scores: list[float] = []
    latencies: list[float] = []
    failures: list[dict[str, object]] = []
    baseline_hits: list[float] = []
    baseline_reciprocal_ranks: list[float] = []
    baseline_refusals: list[float] = []

    normalized_cases = [normalize_case(case) for case in cases]
    for case in normalized_cases:
        request = QARequest(
            question=case["question"],
            history=[ChatMessage(**message) for message in case.get("history", [])],
        )
        response = service.answer(request, client_identifier="offline-evaluation")
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
            if case["category"] in {"year", "event_name", "year_or_name"}:
                exact_recall.append(float(bool(ranked) and ranked[0] in expected))
            cited_refs = {f"[E{index}]" for index in range(1, len(response.citations) + 1)}
            citation_scores.append(
                float(bool(cited_refs) and all(ref in response.answer for ref in cited_refs))
            )
            allowed_sources = set(map(str, case.get("allowed_source_ids", [])))
            if allowed_sources:
                cited_sources = {
                    source.source_id
                    for citation in response.citations
                    if citation.event_id in expected
                    for source in citation.sources
                }
                source_scores.append(
                    float(bool(cited_sources) and cited_sources.issubset(allowed_sources))
                )
            facts = case.get("expected_facts", [])
            if facts:
                fact_scores.append(float(all(fact in response.answer for fact in facts)))
            forbidden = case.get("forbidden_facts", [])
            if forbidden:
                forbidden_fact_scores.append(
                    float(not any(fact in response.answer for fact in forbidden))
                )
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
        "case_count": len(normalized_cases),
        "answerable_count": sum(bool(case["should_answer"]) for case in normalized_cases),
        "unanswerable_count": sum(not bool(case["should_answer"]) for case in normalized_cases),
        "hit_at_5": round(mean(hit_scores), 4),
        "mrr_at_5": round(mean(reciprocal_ranks), 4),
        "exact_recall_at_1": round(mean(exact_recall), 4),
        "citation_coverage": round(mean(citation_scores), 4),
        "source_citation_correctness": round(mean(source_scores), 4),
        "fact_support_rate": round(mean(fact_scores), 4),
        "forbidden_fact_avoidance": round(mean(forbidden_fact_scores), 4),
        "refusal_accuracy": round(mean(refusal_scores), 4),
        "retrieval_p50_ms": round(percentile(latencies, 0.50), 3),
        "retrieval_p95_ms": round(percentile(latencies, 0.95), 3),
        "failed_cases": len(failures),
        "baseline_hit_at_5": round(mean(baseline_hits), 4),
        "baseline_mrr_at_5": round(mean(baseline_reciprocal_ranks), 4),
        "baseline_refusal_accuracy": round(mean(baseline_refusals), 4),
    }
    return {"metrics": metrics, "failures": failures}


def enforce_thresholds(suite: str, metrics: dict[str, Any]) -> None:
    thresholds = (
        {
            "hit_at_5": 0.85,
            "mrr_at_5": 0.75,
            "exact_recall_at_1": 0.95,
            "refusal_accuracy": 0.85,
            "source_citation_correctness": 0.90,
        }
        if suite == "human"
        else {
            "hit_at_5": 0.90,
            "mrr_at_5": 0.80,
            "exact_recall_at_1": 1.00,
            "citation_coverage": 0.90,
            "fact_support_rate": 0.90,
            "refusal_accuracy": 0.90,
        }
    )
    missed = [
        f"{name}={metrics[name]} < {minimum}"
        for name, minimum in thresholds.items()
        if float(metrics[name]) < minimum
    ]
    if float(metrics["retrieval_p95_ms"]) >= 200:
        missed.append(f"retrieval_p95_ms={metrics['retrieval_p95_ms']} >= 200")
    if missed:
        raise SystemExit(f"{suite} acceptance thresholds missed: " + "; ".join(missed))


def write_report(suite: str, payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_name = "HUMAN_REPORT.md" if suite == "human" else "REPORT.md"
    metrics = payload["metrics"]
    lines = [
                f"# 史鉴 RAG {'独立人工集' if suite == 'human' else '自动回归集'}评测报告",
                "",
                "> 指标由关闭大模型的可复现检索模式生成。人工集报告只接受签名完成的人工题目。",
                "",
                "| 指标 | 结果 |",
                "| --- | ---: |",
                *[f"| {key} | {value} |" for key, value in metrics.items()],
                "",
                "P95 仅代表本机本地检索，不包含网络模型调用耗时。",
            ]
    if "manual_generation_review" in payload:
        lines.extend(
            [
                "",
                "## 30 条生成回答人工评分",
                "",
                "| 指标 | 结果 |",
                "| --- | ---: |",
                *[
                    f"| {key} | {value} |"
                    for key, value in payload["manual_generation_review"].items()
                ],
            ]
        )
    (output_path.parent / report_name).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def validate_human_suite(path: Path, root: Path) -> list[dict[str, Any]]:
    records = load_jsonl(path)
    event_ids = {str(record["id"]) for record in load_jsonl(root / "data" / "history_events.jsonl")}
    source_ids = {
        str(record["source_id"]) for record in load_jsonl(root / "data" / "sources.jsonl")
    }
    failures = validate_records(
        records,
        event_ids,
        source_ids,
        require_final=True,
    )
    if failures:
        preview = "; ".join(failures[:5])
        raise SystemExit(
            f"human suite is not ready ({len(failures)} validation errors): {preview}"
        )
    return records


def main() -> None:
    args = parse_args()
    base = Settings.from_env()
    settings = Settings.from_env(use_llm=False, public_demo_mode=False)
    service = QAService(settings)
    suites = ("regression", "human") if args.suite == "all" else (args.suite,)
    combined: dict[str, Any] = {}
    for suite in suites:
        if args.questions and len(suites) == 1:
            questions_path = args.questions.resolve()
        else:
            filename = "questions.jsonl" if suite == "regression" else "human_questions.jsonl"
            questions_path = (base.root_dir / "evaluation" / filename).resolve()
        cases = (
            validate_human_suite(questions_path, base.root_dir)
            if suite == "human"
            else load_jsonl(questions_path)
        )
        payload = evaluate_cases(cases, service)
        if suite == "human":
            score_records = load_jsonl(base.root_dir / "evaluation" / "human_scores.jsonl")
            score_failures = validate_score_records(
                score_records,
                {str(case["id"]) for case in cases},
                require_final=args.enforce,
            )
            if score_failures:
                preview = "; ".join(score_failures[:5])
                raise SystemExit(
                    f"human answer scores are not ready ({len(score_failures)} errors): {preview}"
                )
            payload["manual_generation_review"] = score_metrics(score_records)
        default_name = "results.json" if suite == "regression" else "human_results.json"
        output_path = (
            args.output.resolve()
            if args.output and len(suites) == 1
            else base.root_dir / "evaluation" / default_name
        )
        write_report(suite, payload, output_path)
        print(json.dumps({suite: payload["metrics"]}, ensure_ascii=False, indent=2))
        if args.enforce:
            enforce_thresholds(suite, payload["metrics"])
        combined[suite] = payload
    if len(suites) > 1:
        (base.root_dir / "evaluation" / "all_results.json").write_text(
            json.dumps(combined, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
