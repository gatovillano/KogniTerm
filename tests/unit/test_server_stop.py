import os
import signal
from unittest import mock
from pathlib import Path
from kogniterm.server.__main__ import stop_server, is_running, is_kogniterm_process, find_pid_by_port
from kogniterm.server.app import run_server


def test_pid_file_creation_and_removal(tmp_path):
    # Mock Path.home to use a temp directory
    mock_home = tmp_path / "home"
    mock_home.mkdir()
    
    with mock.patch("pathlib.Path.home", return_value=mock_home), \
         mock.patch("uvicorn.run") as mock_run:
        
        # Start server (mocked)
        run_server(port=9999)
        
        pid_file = mock_home / ".kogniterm" / "server_9999.pid"
        assert pid_file.exists()
        assert pid_file.read_text().strip() == str(os.getpid())
        
        # When python exits, atexit would clean it up. Let's manually trigger cleanup.
        # But we can also test stop_server with a mock process.


def test_is_running():
    with mock.patch("os.kill") as mock_kill:
        mock_kill.return_value = None
        assert is_running(12345) is True
        
        mock_kill.side_effect = OSError()
        assert is_running(12345) is False


def test_stop_server_success(tmp_path):
    mock_home = tmp_path / "home"
    mock_home.mkdir()
    
    pid_file = mock_home / ".kogniterm" / "server_8888.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text("12345")
    
    with mock.patch("pathlib.Path.home", return_value=mock_home), \
         mock.patch("kogniterm.server.__main__.is_running", side_effect=[True, False, False, False]), \
         mock.patch("kogniterm.server.__main__.is_kogniterm_process", return_value=True), \
         mock.patch("os.kill") as mock_kill:
        
        stop_server(port=8888)
        
        # Should call kill with SIGTERM
        mock_kill.assert_any_call(12345, signal.SIGTERM)
        # pid file should be removed
        assert not pid_file.exists()


def test_stop_server_no_pid_file_but_port_active(tmp_path):
    mock_home = tmp_path / "home"
    mock_home.mkdir()
    
    with mock.patch("pathlib.Path.home", return_value=mock_home), \
         mock.patch("kogniterm.server.__main__.find_pid_by_port", return_value=[54321]), \
         mock.patch("kogniterm.server.__main__.is_running", side_effect=[True, False, False, False]), \
         mock.patch("kogniterm.server.__main__.is_kogniterm_process", return_value=True), \
         mock.patch("os.kill") as mock_kill:
        
        stop_server(port=8888)
        
        # Should call kill with SIGTERM on process found via port
        mock_kill.assert_any_call(54321, signal.SIGTERM)
