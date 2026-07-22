# 独立人工评测集填写规范

`human_questions.jsonl` 只有 80 个空白标注槽位，不包含 AI 生成的问题。题目作者在撰写问题时不得查看项目的问题生成脚本，也不得直接改写事件字段。

1. 按预分配的 `category` 与 `history_scope` 独立撰写问题，并填写难度、预期事件 ID、允许来源 ID、必须事实、禁止事实和对话历史。
2. 作者填写 `author`。有第二位复核者时由另一人核对事件和来源映射，填写 `reviewer_id` 并将状态设为 `verified`；没有第二位复核者时只能使用 `single_author_review`。
3. 完成内容与复核状态后运行 `python -m scripts.sign_human_questions` 计算完整性签名；任何标注修改都会使旧签名失效。该哈希只能证明记录未变，不能替代真实人工身份审核。
4. 普通 CI 只校验槽位和配额；发布门禁执行 `python -m scripts.validate_human_questions --require-final`，80 条未全部完成时必须失败。
5. `human_scores.jsonl` 是 30 条生成回答的人工评分表。四个维度采用 0–2 分：事实支持、完整性、引用正确性、拒答合理性。LLM-as-judge 结果不得写入人工评分字段。

运行人工集：

```bash
python -m scripts.run_evaluation --suite human --enforce
python -m scripts.validate_human_scores --require-final
```

最终报告只能使用已经签名的人工集记录和实际运行结果。
