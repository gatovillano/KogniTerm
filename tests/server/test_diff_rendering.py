import pytest
import asyncio
from unittest.mock import MagicMock
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from kogniterm.server.session_pool import ServerUI, extract_thinking_and_response
from kogniterm.utils.diff_renderer import DiffRenderer

def test_extract_thinking_and_response_diff_panel():
    diff_renderer = DiffRenderer()
    diff_content = "--- a/test.py\n+++ b/test.py\n@@ -1,2 +1,2 @@\n-old line\n+new line"
    diff_table = diff_renderer.render_diff_from_string(diff_content, "test.py")

    title_text = "✅ Diff aplicado: test.py"
    subtitle = Text("Operación: edit_file", style="dim cyan")
    panel = Panel(Group(subtitle, Text(""), diff_table), title=title_text)

    thinking, response = extract_thinking_and_response(panel)
    
    assert thinking == ""
    assert "### ✅ Diff aplicado: test.py" in response
    # Verify no raw ANSI escape sequences [32m or [0m in response
    assert "[32m" not in response
    assert "\x1b" not in response

@pytest.mark.asyncio
async def test_server_ui_diff_message():
    loop = asyncio.get_event_loop()
    ui = ServerUI(loop=loop, session_id="test-diff-session")
    pushed_messages = []
    
    def fake_push(event_type, data, agent_id=None):
        if event_type == "message":
            pushed_messages.append(data.get("text", ""))

    ui._push = fake_push
    
    diff_md = "### ✅ Cambios aplicados en `test.py`\n**Operación:** `edit_file`\n\n```diff\n--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new\n```"
    ui.print_message(diff_md)
    
    assert len(pushed_messages) == 1
    assert "```diff" in pushed_messages[0]
    assert "--- a/test.py" in pushed_messages[0]
