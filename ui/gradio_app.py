from __future__ import annotations

import os
from typing import Any

import gradio as gr
import pandas as pd

from app.config import Settings
from app.models import ChatMessage, QARequest
from app.service import QAService


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        ).strip()
    if isinstance(content, dict):
        return str(content.get("text", content))
    return str(content)


def _citation_markdown(response: Any) -> str:
    if not response.citations:
        return response.answer
    sources = ["\n\n---\n**资料来源**"]
    for citation in response.citations:
        link = f"（{citation.source_url}）" if citation.source_url else ""
        sources.append(
            f"- [{citation.ref}] {citation.name} · {citation.year_text} · "
            f"{citation.source_title}{link}"
        )
    sources.append(
        f"\n`检索: {response.retrieval_mode}` · `耗时: {response.latency_ms:.1f} ms`"
        + (" · `本地降级回答`" if response.degraded else "")
    )
    return response.answer + "\n".join(sources)


def build_demo(settings: Settings | None = None) -> gr.Blocks:
    resolved = settings or Settings.from_env()
    service = QAService(resolved)
    def chat(message: str, history: list[dict[str, str]] | None):
        history = history or []
        if not message.strip():
            return history, ""
        conversation = [
            ChatMessage(role=item["role"], content=_message_text(item["content"]))
            for item in history[-8:]
            if item.get("role") in {"user", "assistant"}
        ]
        response = service.answer(QARequest(question=message, history=conversation))
        return [
            *history,
            {"role": "user", "content": message},
            {"role": "assistant", "content": _citation_markdown(response)},
        ], ""

    def status_text() -> str:
        health = service.health()
        return (
            "### 系统状态\n\n"
            f"- 状态：`{health.status}`\n"
            f"- 历史事件：`{health.event_count}` 条\n"
            f"- 向量检索：`{'已就绪' if health.vector_ready else '未构建'}`\n"
            f"- Embedding：`{health.embedding_provider}`\n"
            f"- Qwen：`{'已配置' if health.llm_configured else '本地降级模式'}`\n"
            f"- 说明：{health.detail or '所有核心服务正常'}"
        )

    events = service.repository.list_events() if service.repository.ready else []
    table = pd.DataFrame(
        [
            {
                "事件": event.name,
                "年份": event.year_text,
                "地区": event.region,
                "范围": event.scope,
                "人物": event.people,
                "关键词": event.keywords,
            }
            for event in events
        ]
    )

    with gr.Blocks(
        title="史鉴 RAG｜历史事件智能问答系统",
        elem_id="history-shell",
    ) as demo:
        gr.HTML(
            """
            <section id="history-hero">
                <h1>史鉴 RAG · 历史事件智能问答系统</h1>
                <p>混合检索、事件级引用、无答案拒答与模型故障降级，让每个历史回答都有据可查。</p>
                <div class="hero-tags">
                    <span>SQLite FTS5</span><span>Chroma 向量检索</span>
                    <span>RRF 融合排序</span><span>Qwen 生成</span><span>可溯源引用</span>
                </div>
            </section>
            """
        )
        with gr.Row(equal_height=True):
            with gr.Column(scale=8, min_width=620):
                with gr.Group(elem_id="chat-panel", elem_classes=["panel-card"]):
                    chatbot = gr.Chatbot(
                        label="可溯源历史问答",
                        height=500,
                        value=[],
                        elem_id="history-chatbot",
                    )
                    with gr.Group(elem_id="input-panel"):
                        user_input = gr.Textbox(
                            label="输入年份、事件、人物或比较问题",
                            placeholder="例如：1919 年发生了什么？ / 五四运动的影响是什么？",
                            lines=2,
                            elem_id="history-input",
                        )
                        with gr.Row():
                            send_btn = gr.Button("发送", variant="primary", elem_id="send-btn")
                            clear_btn = gr.Button("清空对话", elem_id="clear-btn")
            with gr.Column(scale=3, min_width=360):
                with gr.Group(elem_id="side-panel", elem_classes=["panel-card"]):
                    gr.Markdown(status_text())
                    gr.Markdown(
                        """
                        ### 推荐问题

                        - 1919 年发生了什么大事？
                        - 五四运动的影响是什么？
                        - 孙中山参与了哪些事件？
                        - 鸦片战争和甲午中日战争有什么区别？
                        - 2025 年发生了什么历史事件？
                        """
                    )
                    gr.Examples(
                        examples=[
                            "1919 年发生了什么大事？",
                            "五四运动的影响是什么？",
                            "鸦片战争为什么爆发？",
                            "孙中山参与了哪些事件？",
                            "工业革命怎么记？",
                        ],
                        inputs=user_input,
                        label="点击填入",
                    )
        with gr.Accordion("查看本地历史事件库", open=False, elem_id="status-panel"):
            gr.Dataframe(value=table, interactive=False, label="可溯源事件数据")

        send_btn.click(chat, inputs=[user_input, chatbot], outputs=[chatbot, user_input])
        user_input.submit(chat, inputs=[user_input, chatbot], outputs=[chatbot, user_input])
        clear_btn.click(lambda: ([], ""), outputs=[chatbot, user_input])
    return demo


def main() -> None:
    local_no_proxy = "127.0.0.1,localhost,::1"
    os.environ["NO_PROXY"] = ",".join(
        value for value in (os.getenv("NO_PROXY"), local_no_proxy) if value
    )
    os.environ["no_proxy"] = ",".join(
        value for value in (os.getenv("no_proxy"), local_no_proxy) if value
    )
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    settings = Settings.from_env()
    demo = build_demo(settings)
    css_path = settings.root_dir / "style.css"
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        css=css,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
