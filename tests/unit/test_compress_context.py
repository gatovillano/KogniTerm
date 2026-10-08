"""Regresión para /compress: el historial comprimido debe conservar contexto.

Cubre los defectos que hacían que el agente "no supiera de qué se hablaba":
1. Marcadores de resumen no reconocidos en cadena (📊 Previous..., 🎯 RESUMEN...).
2. Pérdida del objetivo inicial del usuario.
3. Corte a mitad de un par AI(tool_calls)+ToolMessage.
"""

import os
import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from kogniterm.core.history_manager import HistoryManager


@pytest.fixture
def hm(tmp_path):
    return HistoryManager(
        history_file_path=str(tmp_path / "h.json"),
        max_history_messages=50,
        max_history_chars=75000,
    )


def _long_session():
    hist = [SystemMessage(content="base del sistema")]
    hist.append(HumanMessage(content="OBJETIVO: migrar la API a FastAPI"))
    for i in range(8):
        hist.append(AIMessage(content=f"paso {i}"))
        hist.append(HumanMessage(content=f"pregunta intermedia {i} sobre autenticación"))
        hist.append(
            AIMessage(content="", tool_calls=[{"name": "execute_command", "args": {"command": f"pytest {i}"}, "id": f"call_{i}"}])
        )
        hist.append(ToolMessage(content=f"ok {i}\n" * 50, tool_call_id=f"call_{i}"))
    return hist


def test_legacy_markers_are_detected(hm):
    for content in [
        "📊 Previous conversation summary (compressed history):\n\nresumen viejo",
        "🎯 RESUMEN DE LA CONVERSACIÓN Y ACCIONES ANTERIORES:\nresumen viejo",
        "Resumen forzado de la conversación: resumen viejo",
        "Resumen de conversación previa: resumen viejo",
        f"{HistoryManager.SUMMARY_MARKER}\n\nresumen viejo",
    ]:
        body = HistoryManager.is_summary_message(SystemMessage(content=content))
        assert body is not None and "resumen viejo" in body, content
    # Un system normal no debe detectarse
    assert HistoryManager.is_summary_message(SystemMessage(content="Eres un asistente")) is None
    assert HistoryManager.is_summary_message(HumanMessage(content="hola")) is None


def test_build_compressed_history_keeps_goal_and_pairs(hm):
    hist = _long_session()
    new = hm.build_compressed_history(
        hist, "resumen de prueba", keep_recent=10,
        base_system_message=SystemMessage(content="base"),
    )
    # Estructura: base + resumen + objetivo + recents
    assert isinstance(new[0], SystemMessage) and new[0].content == "base"
    assert HistoryManager.is_summary_message(new[1]) is not None
    goals = [m for m in new if isinstance(m, HumanMessage) and "OBJETIVO" in str(m.content)]
    assert len(goals) == 1, "el objetivo inicial debe conservarse exactamente una vez"
    # Sin ToolMessages huérfanos al inicio
    assert not isinstance(new[2], ToolMessage)
    # Todos los Tool conservados tienen su AI con tool_call correspondiente
    ai_ids = {tc.get("id") for m in new if isinstance(m, AIMessage) and m.tool_calls for tc in m.tool_calls}
    for m in new:
        if isinstance(m, ToolMessage):
            assert m.tool_call_id in ai_ids, f"Tool huérfano: {m.tool_call_id}"
    # Ningún AI con tool_calls queda sin sus Tools
    for i, m in enumerate(new):
        if isinstance(m, AIMessage) and m.tool_calls:
            expected = {tc.get("id") for tc in m.tool_calls if tc.get("id")}
            following = {t.tool_call_id for t in new[i + 1:] if isinstance(t, ToolMessage)}
            assert expected & following, "AI con tool_calls sin respuesta Tool a continuación"


def test_old_summaries_are_skipped_not_duplicated(hm):
    hist = _long_session()
    hist.insert(1, SystemMessage(content=f"{HistoryManager.SUMMARY_MARKER}\n\nresumen anterior"))
    new = hm.build_compressed_history(hist, "resumen nuevo", keep_recent=10)
    summaries = [m for m in new if HistoryManager.is_summary_message(m) is not None]
    assert len(summaries) == 1, "solo debe quedar el resumen consolidado"
    assert "resumen nuevo" in str(summaries[0].content)
