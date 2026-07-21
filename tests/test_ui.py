from __future__ import annotations

from ui.gradio_app import _message_text


def test_gradio_rich_message_content_is_normalized():
    content = [{"text": "第一段", "type": "text"}, {"text": "第二段", "type": "text"}]
    assert _message_text(content) == "第一段\n第二段"
