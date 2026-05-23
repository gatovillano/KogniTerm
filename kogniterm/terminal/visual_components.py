"""
SHIM DE COMPATIBILIDAD — kogniterm.terminal.visual_components

Este módulo re-exporta todo desde kogniterm.ui.visual_components para
mantener compatibilidad retroactiva con el código existente durante
la migración a la arquitectura cliente-servidor.

La implementación canónica ahora vive en: kogniterm/ui/visual_components.py
"""

from kogniterm.ui.visual_components import *  # noqa: F401, F403
from kogniterm.ui.visual_components import (  # exportaciones explícitas
    create_animated_spinner,
    create_thinking_spinner,
    create_processing_spinner,
    create_progress_bar,
    create_info_panel,
    create_thought_bubble,
    create_gradient_panel,
    create_success_box,
    create_error_box,
    create_warning_box,
    create_tool_output_panel,
    create_terminal_output_panel,
    create_separator,
    create_status_message,
    create_welcome_banner,
    create_section_title,
    create_info_table,
    create_gradient_text,
    get_random_motivational_message,
    get_kogniterm_theme,
    format_command,
    format_file_path,
    format_time_elapsed,
)
