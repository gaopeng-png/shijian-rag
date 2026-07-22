# 史鉴 RAG 自动回归集评测报告

> 指标由关闭大模型的可复现检索模式生成。人工集报告只接受签名完成的人工题目。

| 指标 | 结果 |
| --- | ---: |
| case_count | 321 |
| answerable_count | 311 |
| unanswerable_count | 10 |
| hit_at_5 | 1.0 |
| mrr_at_5 | 0.9984 |
| exact_recall_at_1 | 1.0 |
| citation_coverage | 1.0 |
| source_citation_correctness | 0.0 |
| fact_support_rate | 1.0 |
| forbidden_fact_avoidance | 0.0 |
| refusal_accuracy | 1.0 |
| retrieval_p50_ms | 1.149 |
| retrieval_p95_ms | 7.824 |
| failed_cases | 0 |
| baseline_hit_at_5 | 0.9968 |
| baseline_mrr_at_5 | 0.9895 |
| baseline_refusal_accuracy | 0.9 |

P95 仅代表本机本地检索，不包含网络模型调用耗时。