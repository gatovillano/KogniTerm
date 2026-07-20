"""
Test for QuestionSelectorModal and ask_question_sync integration.
"""

import pytest
from kogniterm.terminal.tui.components.question_selector_modal import QuestionSelectorModal
from kogniterm.skills.bundled.ask_question.scripts.tool import ask_question


def test_question_selector_modal_init():
    modal = QuestionSelectorModal(
        question="¿Cómo proceder?",
        options=["Opción 1", "Opción 2", "Opción 3"],
        title="Test Title",
        allow_freeform=True,
    )
    assert modal.question == "¿Cómo proceder?"
    assert modal.options == ["Opción 1", "Opción 2", "Opción 3"]
    assert modal.title_text == "Test Title"
    assert modal.allow_freeform is True


def test_ask_question_tool_uses_ask_question_sync():
    class DummyTerminalUI:
        def __init__(self):
            self.called_with = None

        def ask_question_sync(self, question, options, title, allow_freeform):
            self.called_with = {
                "question": question,
                "options": options,
                "title": title,
                "allow_freeform": allow_freeform,
            }
            return options[1]  # Devuelve Opción 2

    dummy_ui = DummyTerminalUI()
    res = ask_question(
        question="¿Qué opción prefieres?",
        options=["Uno", "Dos", "Tres"],
        title="Consulta Test",
        allow_freeform=False,
        terminal_ui=dummy_ui,
    )

    assert res == "Dos"
    assert dummy_ui.called_with["question"] == "¿Qué opción prefieres?"
    assert dummy_ui.called_with["options"] == ["Uno", "Dos", "Tres"]
    assert dummy_ui.called_with["title"] == "Consulta Test"
    assert dummy_ui.called_with["allow_freeform"] is False
