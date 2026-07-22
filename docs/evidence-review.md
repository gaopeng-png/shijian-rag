# 权威来源审核手册

## 状态定义

- `candidate`：脚本建立的候选映射，尚未逐字段人工核对。
- `single_author_review`：一名作者完成核对，但没有独立复核者；不得宣传为双人标注。
- `verified`：审核人、日期、来源定位均完整，可计入“已审核事件”。

## 单个事件的审核步骤

1. 打开 `data/event_evidence.jsonl` 中列出的每个 URL，确认发布机构和页面标题与 `sources.jsonl` 一致。
2. 分别核对 `summary`、`detail`、`influence`、`exam_points`。来源只支持其中部分字段时，不得把它列到其他字段。
3. 把“待人工核对具体章节或段落”替换为可复查的章节、页码、条款或页面小标题。
4. 对影响、评价等解释性结论优先寻找教材或学术机构来源；原始文献只能证明其直接记载的内容。
5. 填写 `reviewer_id`、ISO 日期 `reviewed_at`、`notes` 和状态。没有第二位核对者时只能标为 `single_author_review`。
6. 运行校验并重建索引：

```bash
python -m scripts.check_evidence
python -m scripts.init_database
python -m scripts.build_index --provider hash
```

正式发布前运行：

```bash
python -m scripts.check_evidence --require-verified
```

## 来源等级

- A：政府、档案馆、博物馆、国际组织和原始文献库。
- B：大学、学术机构、权威百科和正式教材。
- C：专业教育机构，只可补充。

Wikipedia、百度百科、个人博客和 AI 内容不得作为唯一来源。只提交来源元数据、定位和必要短摘要，不复制教材或史料全文。

## 链接维护

每周工作流运行 `python -m scripts.check_source_links --strict`。2xx/3xx 通过；403/429 记为人工复核，不因反爬阻断；永久 4xx/5xx 会失败。网络或证书异常单独列为 `unreachable`，审核者仍须在浏览器中复查。
