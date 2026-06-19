from unittest.mock import MagicMock, patch
import threading

from kogniterm.terminal.tui.tui_app import KogniTermTUI


def test_indexing_progress_schedules_same_thread_updates_with_call_next():
    app = KogniTermTUI.__new__(KogniTermTUI)
    app.call_next = MagicMock()
    app.query_one = MagicMock()
    app._thread_id = threading.get_ident()

    with patch('textual.app.App.call_from_thread') as mock_super_call:
        app._show_indexing_progress(1, 2, "CONTRIBUTING.md")

        app.call_next.assert_called_once()
        mock_super_call.assert_not_called()
        app.call_next.call_args.args[0]()

        label = app.query_one.return_value
        label.update.assert_called_once()
        assert "CONTRIBUTING.md" in label.update.call_args.args[0]


def test_indexing_progress_schedules_cross_thread_updates_with_call_from_thread():
    app = KogniTermTUI.__new__(KogniTermTUI)
    app.call_next = MagicMock()
    app._thread_id = 0
    started = threading.Event()
    finished = threading.Event()

    def call_from_worker():
        started.set()
        app._show_indexing_progress(1, 2, "CONTRIBUTING.md")
        finished.set()

    with patch('textual.app.App.call_from_thread') as mock_super_call:
        thread = threading.Thread(target=call_from_worker)
        thread.start()
        started.wait(timeout=5)
        thread.join(timeout=5)

        assert finished.is_set()
        mock_super_call.assert_called_once()
        app.call_next.assert_not_called()
