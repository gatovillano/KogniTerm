"""
SHIM DE COMPATIBILIDAD — kogniterm.terminal.themes

Este módulo re-exporta todo desde kogniterm.ui.themes para
mantener compatibilidad retroactiva con el código existente durante
la migración a la arquitectura cliente-servidor.

La implementación canónica ahora vive en: kogniterm/ui/themes.py
"""

from kogniterm.ui.themes import *  # noqa: F401, F403
from kogniterm.ui.themes import (  # exportaciones explícitas
    ColorPalette,
    TextStyles,
    Icons,
    Gradients,
    _THEMES,
    get_kogniterm_theme,
    get_available_themes,
    get_status_color,
    get_status_icon,
    set_kogniterm_theme,
    detect_terminal_theme,
)
