from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from kogniterm.core.agent_state import AgentState
from kogniterm.terminal.tui.tui_app import KogniTermTUI


class DummyChatLog:
    def __init__(self):
        self.calls = []

    def clear(self):
        self.calls.append(("clear", None))

    def write_user_message(self, text):
        self.calls.append(("user", text))

    def write_agent_message(self, text):
        self.calls.append(("agent", text))

    def write_message(self, renderable):
        self.calls.append(("message", renderable))


class DummyNode:
    def __init__(self):
        self.display = True
        self.focused = False

    def focus(self):
        self.focused = True


def test_restore_history_into_chat_hides_splash_and_rehydrates_messages():
    app = KogniTermTUI.__new__(KogniTermTUI)
    app.HISTORY_TOOL_PREVIEW_LIMIT = 4000
    app.agent_state = AgentState(
        messages=[
            SystemMessage(content="Resumen de la conversación anterior: hiciste cambios"),
            HumanMessage(content="hola"),
            AIMessage(
                content="Ejecutando herramientas...",
                tool_calls=[{"name": "read_file_tool", "args": {}, "id": "call_1"}],
            ),
            AIMessage(content="respuesta"),
            ToolMessage(content="salida tool", tool_call_id="call_1"),
        ]
    )
    app.chat_log = DummyChatLog()
    app._splash_visible = True

    splash = DummyNode()
    bottom = DummyNode()
    chat_input = DummyNode()

    def query_one(selector, *_args):
        if selector == "#splash_overlay":
            return splash
        if selector == "#bottom_container":
            return bottom
        if selector == "#chat_input":
            return chat_input
        raise AssertionError(f"selector inesperado: {selector}")

    app.query_one = query_one

    app._restore_history_into_chat()

    assert app.chat_log.calls[0] == ("clear", None)
    assert any(kind == "message" for kind, content in app.chat_log.calls if content is not None)
    assert ("user", "hola") in app.chat_log.calls
    assert ("agent", "respuesta") in app.chat_log.calls
    assert ("message", "🛠️ Herramientas usadas: read_file_tool") in app.chat_log.calls
    assert app._splash_visible is False
    assert splash.display is False
    assert bottom.display is True
    assert chat_input.focused is True
