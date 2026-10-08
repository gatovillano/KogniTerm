import sys
from unittest.mock import patch, MagicMock
from kogniterm.terminal.cli import run_cli, CLIHandler


def test_cli_subcommand_dispatches_handle_cli():
    with patch.object(sys, "argv", ["kogniterm", "cli"]):
        with patch.object(CLIHandler, "handle_cli") as mock_handle_cli:
            result = run_cli()
            assert result is True
            mock_handle_cli.assert_called_once_with([])


def test_cli_subcommand_with_arguments():
    with patch.object(sys, "argv", ["kogniterm", "cli", "explicame", "este", "archivo"]):
        with patch.object(CLIHandler, "handle_cli") as mock_handle_cli:
            result = run_cli()
            assert result is True
            mock_handle_cli.assert_called_once_with(["explicame", "este", "archivo"])


def test_desktop_dispatches_handle_desktop():
    with patch.object(sys, "argv", ["kogniterm", "desktop", "--dev"]):
        with patch.object(CLIHandler, "handle_desktop") as mock_handle_desktop:
            result = run_cli()
            assert result is True
            mock_handle_desktop.assert_called_once_with(["--dev"])


def test_desktopv3_alias_dispatches_handle_desktop():
    for alias in ("desktopv3", "desktop-v3"):
        with patch.object(sys, "argv", ["kogniterm", alias]):
            with patch.object(CLIHandler, "handle_desktop") as mock_handle_desktop:
                result = run_cli()
                assert result is True
                mock_handle_desktop.assert_called_once_with([])
