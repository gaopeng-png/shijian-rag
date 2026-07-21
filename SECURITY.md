# Security Policy

## Secrets

项目只从环境变量读取 DashScope Key。不要在 issue、日志、截图、JSONL、`.env.example` 或提交历史中包含真实密钥。若密钥曾被提交，应立即在服务商控制台吊销，而不是仅删除文件。

## Public deployment

当前仓库是教学演示版本。公开部署前应增加请求限流、来源域名限制、调用预算、依赖漏洞扫描和服务监控。

## Reporting

请通过 GitHub Security Advisory 私下报告密钥泄漏、依赖漏洞或可导致服务滥用的问题，不要在公开 issue 中披露利用细节。
