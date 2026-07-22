# 在线演示部署

## 发布前门禁

```bash
python -m scripts.check_evidence --require-verified
python -m scripts.validate_human_questions --require-final
python -m scripts.validate_human_scores --require-final
python -m scripts.run_evaluation --suite all --enforce
```

任一命令失败都不能启用 `ENABLE_V11_DEPLOY`，也不能发布 v1.1.0。

## ModelScope（首选）

1. 完成 ModelScope 登录及平台要求的实名认证，创建 Docker 创空间。
2. 在创空间设置运行时环境变量：`DASHSCOPE_API_KEY`、`USE_LLM=true`、`PUBLIC_DEMO_MODE=true`、随机 `CLIENT_HASH_SALT`、`RUNTIME_DIR=/mnt/workspace/shijian-rag`。
3. GitHub 设置 Secret `MODELSCOPE_TOKEN`，Variables `MODELSCOPE_STUDIO_PATH`、`MODELSCOPE_DEMO_URL`。
4. 证据与人工集完成后设置 Repository Variable `ENABLE_V11_DEPLOY=true`。

创空间使用 `0.0.0.0:7860`；SQLite 与 Chroma 已在镜像构建阶段生成，持久目录只保存演示限流账本。

## Hugging Face（自动回退）

创建 Docker Space，设置同名运行时 Secret/Variables。GitHub 配置 Secret `HF_TOKEN` 和 Variables `HF_SPACE_ID`、`HF_DEMO_URL`。ModelScope 凭据缺失或同步失败时，工作流会推送到该 Space。

## 在线验收

```bash
python -m scripts.smoke_deployment https://your-demo.example --full-load
```

脚本检查根路径 UI、`/readyz`、`/meta`、五四运动来源引用、无答案拒答、20 次问答和五路并发。Qwen 模式下至少三路并发应以 `llm_concurrency_limit` 降级，确保同时只有两个模型调用。

在线地址可稳定访问后，才能更新 README、GitHub About、简历与 Release Notes。
