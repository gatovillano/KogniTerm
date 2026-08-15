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
