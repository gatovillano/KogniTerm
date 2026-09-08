"""Módulo de Capabilities de KogniTerm: Herramientas nativas de alta velocidad en memoria."""

from kogniterm.capabilities.registry import (
    ToolDefinition,
    ToolRegistry,
    default_tool_registry,
    tool,
)
from kogniterm.capabilities.terminal import execute_command, run_shell
from kogniterm.capabilities.file_editor import (
    read_file,
    edit_file,
    replace_all_file,
    create_file,
    delete_file,
    list_directory,
)
from kogniterm.capabilities.web import web_fetch, web_search
from kogniterm.capabilities.code_tools import code_analysis, codebase_search

__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "default_tool_registry",
    "tool",
    "execute_command",
    "run_shell",
    "read_file",
    "edit_file",
    "replace_all_file",
    "create_file",
    "delete_file",
    "list_directory",
    "web_fetch",
    "web_search",
    "code_analysis",
    "codebase_search",
]
