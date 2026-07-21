# 史鉴 RAG 离线评测报告

> 指标由 `python -m scripts.run_evaluation` 在关闭大模型的可复现模式下生成。

| 指标 | 结果 |
| --- | ---: |
| case_count | 321 |
| answerable_count | 311 |
| unanswerable_count | 10 |
| hit_at_5 | 1.0 |
| mrr_at_5 | 0.9984 |
| exact_recall_at_1 | 1.0 |
| citation_coverage | 1.0 |
| fact_support_rate | 1.0 |
| refusal_accuracy | 1.0 |
| retrieval_p50_ms | 0.576 |
| retrieval_p95_ms | 5.535 |
| failed_cases | 0 |
| baseline_hit_at_5 | 0.9968 |
| baseline_mrr_at_5 | 0.9895 |
| baseline_refusal_accuracy | 0.9 |

## 说明

- Hit@5/MRR@5 衡量标注事件在前五个召回结果中的位置。
- 引用覆盖率要求回答中的每个返回引用都有对应 `[E#]` 标记。
- 事实支持率只检查评测集声明的关键事实，不等同于完整人工事实审查。
- P95 仅代表本机本地检索，不包含网络模型调用耗时。