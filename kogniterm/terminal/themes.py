"""
Temas de color y estilos para KogniTerm.

Este módulo define paletas de colores, estilos de texto y configuraciones
de tema para mantener una apariencia visual consistente en toda la aplicación.
"""

from typing import Dict
from rich.theme import Theme
from rich.style import Style


# ============================================================================
# PALETA DE COLORES PRINCIPAL
# ============================================================================

class ColorPalette:
    """Paleta de colores principal de KogniTerm."""
    
    # Colores primarios (morados y lilas)
    PRIMARY_LIGHTEST = "#e9d5ff"  # Lila muy claro
    PRIMARY_LIGHTER = "#d8b4fe"   # Lila claro
    PRIMARY_LIGHT = "#c084fc"     # Morado claro
    PRIMARY = "#a855f7"           # Morado principal
    PRIMARY_DARK = "#9333ea"      # Morado oscuro
    PRIMARY_DARKER = "#7e22ce"    # Morado muy oscuro
    
    # Colores secundarios (cian y azul)
    SECONDARY_LIGHT = "#67e8f9"   # Cian claro
    SECONDARY = "#06b6d4"         # Cian
    SECONDARY_DARK = "#0891b2"    # Cian oscuro
    
    # Colores de acento
    ACCENT_PINK = "#f472b6"       # Rosa
    ACCENT_BLUE = "#60a5fa"       # Azul
    ACCENT_GREEN = "#4ade80"      # Verde
    
    # Colores semánticos
    SUCCESS = "#10b981"           # Verde éxito
    SUCCESS_LIGHT = "#34d399"     # Verde éxito claro
    WARNING = "#f59e0b"           # Naranja advertencia
    WARNING_LIGHT = "#fbbf24"     # Naranja advertencia claro
    ERROR = "#ef4444"             # Rojo error
    ERROR_LIGHT = "#f87171"       # Rojo error claro
    INFO = "#3b82f6"              # Azul info
    INFO_LIGHT = "#60a5fa"        # Azul info claro
    
    # Colores neutros
    GRAY_50 = "#f9fafb"
    GRAY_100 = "#f3f4f6"
    GRAY_200 = "#e5e7eb"
    GRAY_300 = "#d1d5db"
    GRAY_400 = "#9ca3af"
    GRAY_500 = "#6b7280"
    GRAY_600 = "#4b5563"
    GRAY_700 = "#374151"
    GRAY_800 = "#1f2937"
    GRAY_900 = "#111827"
    
    # Colores de texto
    TEXT_PRIMARY = "#f9fafb"      # Texto principal (claro)
    TEXT_SECONDARY = "#d1d5db"    # Texto secundario
    TEXT_MUTED = "#9ca3af"        # Texto apagado
    TEXT_DIM = "#6b7280"          # Texto muy apagado


# ============================================================================
# ESTILOS DE TEXTO
# ============================================================================

class TextStyles:
    """Estilos de texto predefinidos."""
    
    # Títulos
    TITLE = Style(color=ColorPalette.PRIMARY_LIGHT, bold=True)
    SUBTITLE = Style(color=ColorPalette.SECONDARY_LIGHT, bold=True)
    HEADING = Style(color=ColorPalette.PRIMARY, bold=True)
    
    # Texto general
    NORMAL = Style(color=ColorPalette.TEXT_PRIMARY)
    MUTED = Style(color=ColorPalette.TEXT_MUTED)
    DIM = Style(color=ColorPalette.TEXT_DIM, dim=True)
    BOLD = Style(bold=True)
    ITALIC = Style(italic=True)
    
    # Código
    CODE = Style(color=ColorPalette.ACCENT_BLUE, bgcolor=ColorPalette.GRAY_800)
    CODE_INLINE = Style(color=ColorPalette.SECONDARY_LIGHT)
    
    # Estados
    SUCCESS = Style(color=ColorPalette.SUCCESS, bold=True)
    SUCCESS_LIGHT = Style(color=ColorPalette.SUCCESS_LIGHT)
    WARNING = Style(color=ColorPalette.WARNING, bold=True)
    WARNING_LIGHT = Style(color=ColorPalette.WARNING_LIGHT)
    ERROR = Style(color=ColorPalette.ERROR, bold=True)
    ERROR_LIGHT = Style(color=ColorPalette.ERROR_LIGHT)
    INFO = Style(color=ColorPalette.INFO, bold=True)
    INFO_LIGHT = Style(color=ColorPalette.INFO_LIGHT)
    
    # Prompt
    PROMPT = Style(color=ColorPalette.PRIMARY_LIGHT, bold=True)
    PROMPT_SYMBOL = Style(color=ColorPalette.SECONDARY, bold=True)
    
    # Bordes y decoraciones
    BORDER_PRIMARY = Style(color=ColorPalette.PRIMARY)
    BORDER_SECONDARY = Style(color=ColorPalette.SECONDARY)
    BORDER_SUCCESS = Style(color=ColorPalette.SUCCESS)
    BORDER_WARNING = Style(color=ColorPalette.WARNING)
    BORDER_ERROR = Style(color=ColorPalette.ERROR)
    BORDER_INFO = Style(color=ColorPalette.INFO)


# ============================================================================
# ICONOS
# ============================================================================

class Icons:
    """Iconos Unicode para diferentes estados y acciones."""
    
    # Estados
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    QUESTION = "❓"
    
    # Acciones
    PROCESSING = "🔄"
    THINKING = "🤔"
    ROBOT = "🤖"
    SPARKLES = "✨"
    ROCKET = "🚀"
    FIRE = "🔥"
    STAR = "⭐"
    
    # Herramientas
    TOOL = "🛠️"
    WRENCH = "🔧"
    HAMMER = "🔨"
    GEAR = "⚙️"
    
    # Archivos y carpetas
    FILE = "📄"
    FOLDER = "📁"
    DOCUMENT = "📝"
    CODE = "💻"
    
    # Comunicación
    SPEECH = "💬"
    MEGAPHONE = "📢"
    BELL = "🔔"
    
    # Tiempo
    CLOCK = "🕐"
    HOURGLASS = "⏳"
    STOPWATCH = "⏱️"
    
    # Direcciones
    ARROW_RIGHT = "→"
    ARROW_LEFT = "←"
    ARROW_UP = "↑"
    ARROW_DOWN = "↓"
    
    # Otros
    CHECKMARK = "✓"
    CROSS = "✗"
    BULLET = "•"
    SEPARATOR = "─"


# ============================================================================
# TEMA RICH
# ============================================================================

def get_kogniterm_theme() -> Theme:
    """
    Retorna el tema Rich personalizado para KogniTerm.
    
    Returns:
        Theme: Tema Rich configurado con los estilos de KogniTerm
    """
    return Theme({
        # Estilos básicos
        "info": f"bold {ColorPalette.INFO}",
        "warning": f"bold {ColorPalette.WARNING}",
        "error": f"bold {ColorPalette.ERROR}",
        "success": f"bold {ColorPalette.SUCCESS}",
        
        # Estilos de texto
        "title": f"bold {ColorPalette.PRIMARY_LIGHT}",
        "subtitle": f"bold {ColorPalette.SECONDARY_LIGHT}",
        "heading": f"bold {ColorPalette.PRIMARY}",
        "muted": ColorPalette.TEXT_MUTED,
        "dim": f"dim {ColorPalette.TEXT_DIM}",
        
        # Código
        "code": f"{ColorPalette.ACCENT_BLUE} on {ColorPalette.GRAY_800}",
        "code.inline": ColorPalette.SECONDARY_LIGHT,
        
        # Prompt
        "prompt": f"bold {ColorPalette.PRIMARY_LIGHT}",
        "prompt.symbol": f"bold {ColorPalette.SECONDARY}",
        
        # Bordes
        "border.primary": ColorPalette.PRIMARY,
        "border.secondary": ColorPalette.SECONDARY,
        "border.success": ColorPalette.SUCCESS,
        "border.warning": ColorPalette.WARNING,
        "border.error": ColorPalette.ERROR,
        "border.info": ColorPalette.INFO,
    })


# ============================================================================
# GRADIENTES
# ============================================================================

class Gradients:
    """Definiciones de gradientes de color para texto."""
    
    # Gradiente original con pasos intermedios (tonos de morado y lila)
    PRIMARY = [
        "#d1c4e9",  # Light Lilac (original)
        "#cebee7",  # Intermedio
        "#cbb8e5",  # Intermedio
        "#c5b7e0",  # Original
        "#c0b1dc",  # Intermedio
        "#bcabda",  # Intermedio
        "#b9aad7",  # Original
        "#b5a4d4",  # Intermedio
        "#b19fd1",  # Intermedio
        "#ad9dce",  # Original
        "#aa97cb",  # Intermedio
        "#a694c8",  # Intermedio
        "#a190c5",  # Original
        "#9e8ac1",  # Intermedio
        "#9a87bf",  # Intermedio
        "#9583bc",  # Original (final)
    ]
    
    # Gradiente de éxito (verde)
    SUCCESS = [
        "#d1fae5",
        "#a7f3d0",
        "#6ee7b7",
        "#34d399",
        "#10b981",
        "#059669",
    ]
    
    # Gradiente de advertencia (naranja)
    WARNING = [
        "#fef3c7",
        "#fde68a",
        "#fcd34d",
        "#fbbf24",
        "#f59e0b",
        "#d97706",
    ]
    
    # Gradiente de error (rojo)
    ERROR = [
        "#fee2e2",
        "#fecaca",
        "#fca5a5",
        "#f87171",
        "#ef4444",
        "#dc2626",
    ]
    
    # Gradiente arcoíris
    RAINBOW = [
        "#ef4444",  # Rojo
        "#f59e0b",  # Naranja
        "#eab308",  # Amarillo
        "#10b981",  # Verde
        "#06b6d4",  # Cian
        "#3b82f6",  # Azul
        "#a855f7",  # Morado
    ]


# ============================================================================
# UTILIDADES
# ============================================================================

def get_status_color(status: str) -> str:
    """
    Retorna el color apropiado para un estado dado.
    
    Args:
        status: El estado ('success', 'error', 'warning', 'info')
        
    Returns:
        str: Color hexadecimal
    """
    status_colors = {
        "success": ColorPalette.SUCCESS,
        "error": ColorPalette.ERROR,
        "warning": ColorPalette.WARNING,
        "info": ColorPalette.INFO,
    }
    return status_colors.get(status.lower(), ColorPalette.INFO)


def get_status_icon(status: str) -> str:
    """
    Retorna el icono apropiado para un estado dado.
    
    Args:
        status: El estado ('success', 'error', 'warning', 'info')
        
    Returns:
        str: Icono Unicode
    """
    status_icons = {
        "success": Icons.SUCCESS,
        "error": Icons.ERROR,
        "warning": Icons.WARNING,
        "info": Icons.INFO,
    }
    return status_icons.get(status.lower(), Icons.INFO)
