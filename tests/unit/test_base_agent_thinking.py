import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from kogniterm.core.agents.base_agent import BaseAgentNode


def test_finalize_display_no_keyerror():
    terminal_ui = MagicMock()
    terminal_ui.is_tui = True
    terminal_ui.stop_live = MagicMock()

    # Case 1: Empty state (before any streaming)
    s_state_empty = {
        "full_response": "",
        "total_response": "",
        "full_thinking": "",
        "final_ai_message": None,
        "text_streamed": False,
        "thinking_streamed": False,
        "thinking_active": False,
        "last_update": 0,
        "update_throttle": 0.05
    }
    # Must not raise KeyError
    BaseAgentNode._finalize_display(s_state_empty, terminal_ui, is_tui=True)

    # Case 2: Only thinking streamed (no text_streamed)
    s_state_thinking_only = {
        "full_response": "",
        "total_response": "",
        "full_thinking": "Thinking step...",
        "final_ai_message": None,
        "text_streamed": False,
        "thinking_streamed": True,
        "thinking_active": True,
        "last_update": 0,
        "update_throttle": 0.05
    }
    BaseAgentNode._finalize_display(s_state_thinking_only, terminal_ui, is_tui=True)
    assert terminal_ui.stop_live.called


def test_process_chunk_sequential_thinking():
    terminal_ui = MagicMock()
    terminal_ui.is_tui = True
    terminal_ui.stop_live = MagicMock()
    terminal_ui.print_stream = MagicMock()

    s_state = {
        "full_response": "",
        "total_response": "",
        "full_thinking": "",
        "final_ai_message": None,
        "text_streamed": False,
        "thinking_streamed": False,
        "thinking_active": False,
        "last_update": 0,
        "update_throttle": 0.05
    }

    # 1. First thought chunk
    BaseAgentNode._process_chunk("__THINKING__:First plan", s_state, terminal_ui, is_tui=True, live=None)
    assert s_state["thinking_active"] is True
    assert s_state["thinking_streamed"] is True
    assert "First plan" in s_state["full_thinking"]

    # 2. Transition to text chunk
    BaseAgentNode._process_chunk("Hello user", s_state, terminal_ui, is_tui=True, live=None)
    assert s_state["thinking_active"] is False
    assert s_state["text_streamed"] is True
    assert terminal_ui.stop_live.called

    # 3. Subsequent thought chunk (sequential thinking inside same response)
    BaseAgentNode._process_chunk("__THINKING__:Second plan", s_state, terminal_ui, is_tui=True, live=None)
    assert s_state["thinking_active"] is True
    assert s_state["full_thinking"] == "Second plan"
