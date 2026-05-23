"""
SHIM DE COMPATIBILIDAD — kogniterm.terminal.terminal_ui

Este módulo re-exporta todo desde kogniterm.ui.terminal_ui para
mantener compatibilidad retroactiva con el código existente durante
la migración a la arquitectura cliente-servidor.

La implementación canónica ahora vive en: kogniterm/ui/terminal_ui.py
"""

from kogniterm.ui.terminal_ui import *  # noqa: F401, F403
from kogniterm.ui.terminal_ui import TerminalUI  # exportación explícita
