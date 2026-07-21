# v1.0.0 Release Notes

## 主要功能

- 将 100 条事件和 8 条学习资料迁移到可审查 JSONL 数据源。
- 新增稳定事件 ID、内容哈希、SQLite UPSERT 和 FTS5 索引。
- 新增离线/Qwen Embedding、Chroma 增量索引与加权 RRF 混合检索。
- 新增事件级引用、无证据拒答、Qwen 故障降级和结构化日志。
- 新增 FastAPI `/api/v1/qa`、带状态码语义的 `/healthz` 与 Gradio 演示界面。
- 新增 321 条评测、Pytest、Docker、GitHub Actions 和密钥扫描。
- Docker 使用固定 UID `10001` 的非 root 用户运行，CI 启用最小权限与超时保护。

## 验证结果

- 12 项自动化测试通过。
- 离线评测 Hit@5 100%，MRR@5 99.84%，拒答准确率 100%。
- 本机本地检索 P95 5.54 ms。
- Docker 镜像 `shijian-rag:latest` 构建成功，容器健康检查与真实 `/api/v1/qa` 冒烟测试通过。

## 发布前清单

- 在 GitHub 仓库 Settings 中启用 Secret scanning 与 Dependabot。
- 上传演示 GIF/视频并把在线地址添加到仓库 About 和 README。
- 确认事件数据具备公开再分发权。
- 创建 `v1.0.0` tag，并把本文件内容粘贴到 GitHub Release。
