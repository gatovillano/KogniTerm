import pytest
from rich.panel import Panel
from rich.markdown import Markdown
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget

def test_chat_log_sequential_thinking_reset():
    chat = ChatLogWidget()
    assert chat._active_thinking_widget is None

    # Step 1: Thinking panel 1
    panel1 = Panel(Markdown("Pensando paso 1..."), title="💭 Pensando...")
    chat.write_stream(panel1)
    
    thinking_widget_1 = chat._active_thinking_widget
    assert thinking_widget_1 is not None

    # Update thinking 1
    panel1_updated = Panel(Markdown("Pensando paso 1 más detalles..."), title="💭 Pensando...")
    chat.write_stream(panel1_updated)
    assert chat._active_thinking_widget is thinking_widget_1

    # Stop stream / End of thought 1
    chat.stop_stream()
    assert chat._active_thinking_widget is None

    # Step 2: Response text or Tool output
    chat.write_tool_notification("execute_command", "ls -la")
    assert chat._active_thinking_widget is None

    # Step 3: Thinking panel 2 (from step 2 of loop)
    panel2 = Panel(Markdown("Pensando paso 2..."), title="💭 Pensando...")
    chat.write_stream(panel2)

    thinking_widget_2 = chat._active_thinking_widget
    assert thinking_widget_2 is not None
    assert thinking_widget_2 is not thinking_widget_1
