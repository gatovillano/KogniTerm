from kogniterm.terminal.tui.tui_app import KogniTermTUI


class DummyInput:
    def __init__(self):
        self.id = "palette-input-field"
        self.value = "sk-test-secret"
        self.history_calls = 0

    def add_to_history(self, _text):
        self.history_calls += 1


class DummyEvent:
    def __init__(self, input_widget):
        self.input = input_widget
        self.value = input_widget.value


def test_modal_input_submit_is_ignored_by_chat_handler():
    app = KogniTermTUI.__new__(KogniTermTUI)
    modal_input = DummyInput()

    app.on_input_submitted(DummyEvent(modal_input))

    assert modal_input.history_calls == 0
    assert modal_input.value == "sk-test-secret"
