"""
Temas de color y estilos para KogniTerm.

Este módulo define paletas de colores, estilos de texto y configuraciones
de tema para mantener una apariencia visual consistente en toda la aplicación.
"""

from typing import Dict
from rich.theme import Theme
from rich.style import Style


# ============================================================================
# DEFINICIONES DE TEMAS
# ============================================================================

_THEMES = {
    "default": {
        "PRIMARY_LIGHTEST": "#e9d5ff",
        "PRIMARY_LIGHTER": "#d8b4fe",
        "PRIMARY_LIGHT": "#c084fc",
        "PRIMARY": "#a855f7",
        "PRIMARY_DARK": "#9333ea",
        "PRIMARY_DARKER": "#7e22ce",
        "SECONDARY_LIGHT": "#67e8f9",
        "SECONDARY": "#06b6d4",
        "SECONDARY_DARK": "#0891b2",
        "ACCENT_PINK": "#f472b6",
        "ACCENT_BLUE": "#60a5fa",
        "ACCENT_GREEN": "#4ade80",
        "SUCCESS": "#10b981",
        "SUCCESS_LIGHT": "#34d399",
        "WARNING": "#f59e0b",
        "WARNING_LIGHT": "#fbbf24",
        "ERROR": "#ef4444",
        "ERROR_LIGHT": "#f87171",
        "INFO": "#3b82f6",
        "INFO_LIGHT": "#60a5fa",
        "GRAY_50": "#f9fafb",
        "GRAY_100": "#f3f4f6",
        "GRAY_200": "#e5e7eb",
        "GRAY_300": "#d1d5db",
        "GRAY_400": "#9ca3af",
        "GRAY_500": "#6b7280",
        "GRAY_600": "#4b5563",
        "GRAY_700": "#374151",
        "GRAY_800": "#1f2937",
        "GRAY_900": "#111827",
        "TEXT_PRIMARY": "#f9fafb",
        "TEXT_SECONDARY": "#d1d5db",
        "TEXT_MUTED": "#9ca3af",
        "TEXT_DIM": "#6b7280",
    },
    "ocean": {
        "PRIMARY_LIGHTEST": "#cffafe",
        "PRIMARY_LIGHTER": "#a5f3fc",
        "PRIMARY_LIGHT": "#67e8f9",
        "PRIMARY": "#06b6d4",
        "PRIMARY_DARK": "#0891b2",
        "PRIMARY_DARKER": "#0e7490",
        "SECONDARY_LIGHT": "#bae6fd",
        "SECONDARY": "#3b82f6",
        "SECONDARY_DARK": "#1d4ed8",
        "ACCENT_PINK": "#f472b6",
        "ACCENT_BLUE": "#60a5fa",
        "ACCENT_GREEN": "#4ade80",
        "SUCCESS": "#10b981",
        "SUCCESS_LIGHT": "#34d399",
        "WARNING": "#f59e0b",
        "WARNING_LIGHT": "#fbbf24",
        "ERROR": "#ef4444",
        "ERROR_LIGHT": "#f87171",
        "INFO": "#3b82f6",
        "INFO_LIGHT": "#60a5fa",
        "GRAY_50": "#f0f9ff",
        "GRAY_100": "#e0f2fe",
        "GRAY_200": "#bae6fd",
        "GRAY_300": "#7dd3fc",
        "GRAY_400": "#38bdf8",
        "GRAY_500": "#0ea5e9",
        "GRAY_600": "#0284c7",
        "GRAY_700": "#0369a1",
        "GRAY_800": "#075985",
        "GRAY_900": "#0c4a6e",
        "TEXT_PRIMARY": "#f0f9ff",
        "TEXT_SECONDARY": "#bae6fd",
        "TEXT_MUTED": "#7dd3fc",
        "TEXT_DIM": "#38bdf8",
    },
    "matrix": {
        "PRIMARY_LIGHTEST": "#d1fae5",
        "PRIMARY_LIGHTER": "#a7f3d0",
        "PRIMARY_LIGHT": "#6ee7b7",
        "PRIMARY": "#10b981",
        "PRIMARY_DARK": "#059669",
        "PRIMARY_DARKER": "#047857",
        "SECONDARY_LIGHT": "#a3e635",
        "SECONDARY": "#84cc16",
        "SECONDARY_DARK": "#4d7c0f",
        "ACCENT_PINK": "#f472b6",
        "ACCENT_BLUE": "#60a5fa",
        "ACCENT_GREEN": "#4ade80",
        "SUCCESS": "#10b981",
        "SUCCESS_LIGHT": "#34d399",
        "WARNING": "#f59e0b",
        "WARNING_LIGHT": "#fbbf24",
        "ERROR": "#ef4444",
        "ERROR_LIGHT": "#f87171",
        "INFO": "#3b82f6",
        "INFO_LIGHT": "#60a5fa",
        "GRAY_50": "#f0fdf4",
        "GRAY_100": "#dcfce7",
        "GRAY_200": "#bbf7d0",
        "GRAY_300": "#86efac",
        "GRAY_400": "#4ade80",
        "GRAY_500": "#22c55e",
        "GRAY_600": "#16a34a",
        "GRAY_700": "#15803d",
        "GRAY_800": "#166534",
        "GRAY_900": "#14532d",
        "TEXT_PRIMARY": "#f0fdf4",
        "TEXT_SECONDARY": "#bbf7d0",
        "TEXT_MUTED": "#86efac",
        "TEXT_DIM": "#4ade80",
    },
    "sunset": {
        "PRIMARY_LIGHTEST": "#fef3c7",
        "PRIMARY_LIGHTER": "#fde68a",
        "PRIMARY_LIGHT": "#fcd34d",
        "PRIMARY": "#f59e0b",
        "PRIMARY_DARK": "#d97706",
        "PRIMARY_DARKER": "#b45309",
        "SECONDARY_LIGHT": "#fed7aa",
        "SECONDARY": "#f97316",
        "SECONDARY_DARK": "#c2410c",
        "ACCENT_PINK": "#f472b6",
        "ACCENT_BLUE": "#60a5fa",
        "ACCENT_GREEN": "#4ade80",
        "SUCCESS": "#10b981",
        "SUCCESS_LIGHT": "#34d399",
        "WARNING": "#f59e0b",
        "WARNING_LIGHT": "#fbbf24",
        "ERROR": "#ef4444",
        "ERROR_LIGHT": "#f87171",
        "INFO": "#3b82f6",
        "INFO_LIGHT": "#60a5fa",
        "GRAY_50": "#fff7ed",
        "GRAY_100": "#ffedd5",
        "GRAY_200": "#fed7aa",
        "GRAY_300": "#fdba74",
        "GRAY_400": "#fb923c",
        "GRAY_500": "#f97316",
        "GRAY_600": "#ea580c",
        "GRAY_700": "#c2410c",
        "GRAY_800": "#9a3412",
        "GRAY_900": "#7c2d12",
        "TEXT_PRIMARY": "#fff7ed",
        "TEXT_SECONDARY": "#fed7aa",
        "TEXT_MUTED": "#fdba74",
        "TEXT_DIM": "#fb923c",
    }
}


# ============================================================================
# PALETA DE COLORES PRINCIPAL
# ============================================================================

class ColorPalette:
    """Paleta de colores principal de KogniTerm."""
    
    # Inicializar con el tema por defecto
    _current_theme = _THEMES["default"]

    # Colores primarios
    PRIMARY_LIGHTEST = _current_theme["PRIMARY_LIGHTEST"]
    PRIMARY_LIGHTER = _current_theme["PRIMARY_LIGHTER"]
    PRIMARY_LIGHT = _current_theme["PRIMARY_LIGHT"]
    PRIMARY = _current_theme["PRIMARY"]
    PRIMARY_DARK = _current_theme["PRIMARY_DARK"]
    PRIMARY_DARKER = _current_theme["PRIMARY_DARKER"]
    
    # Colores secundarios
    SECONDARY_LIGHT = _current_theme["SECONDARY_LIGHT"]
    SECONDARY = _current_theme["SECONDARY"]
    SECONDARY_DARK = _current_theme["SECONDARY_DARK"]
    
    # Colores de acento
    ACCENT_PINK = _current_theme["ACCENT_PINK"]
    ACCENT_BLUE = _current_theme["ACCENT_BLUE"]
    ACCENT_GREEN = _current_theme["ACCENT_GREEN"]
    
    # Colores semánticos
    SUCCESS = _current_theme["SUCCESS"]
    SUCCESS_LIGHT = _current_theme["SUCCESS_LIGHT"]
    WARNING = _current_theme["WARNING"]
    WARNING_LIGHT = _current_theme["WARNING_LIGHT"]
    ERROR = _current_theme["ERROR"]
    ERROR_LIGHT = _current_theme["ERROR_LIGHT"]
    INFO = _current_theme["INFO"]
    INFO_LIGHT = _current_theme["INFO_LIGHT"]
    
    # Colores neutros
    GRAY_50 = _current_theme["GRAY_50"]
    GRAY_100 = _current_theme["GRAY_100"]
    GRAY_200 = _current_theme["GRAY_200"]
    GRAY_300 = _current_theme["GRAY_300"]
    GRAY_400 = _current_theme["GRAY_400"]
    GRAY_500 = _current_theme["GRAY_500"]
    GRAY_600 = _current_theme["GRAY_600"]
    GRAY_700 = _current_theme["GRAY_700"]
    GRAY_800 = _current_theme["GRAY_800"]
    GRAY_900 = _current_theme["GRAY_900"]
    
    # Colores de texto
    TEXT_PRIMARY = _current_theme["TEXT_PRIMARY"]
    TEXT_SECONDARY = _current_theme["TEXT_SECONDARY"]
    TEXT_MUTED = _current_theme["TEXT_MUTED"]
    TEXT_DIM = _current_theme["TEXT_DIM"]

    @classmethod
    def set_theme(cls, theme_name: str):
        """Cambia el tema actual."""
        if theme_name not in _THEMES:
            raise ValueError(f"Tema '{theme_name}' no encontrado.")
        
        theme = _THEMES[theme_name]
        cls._current_theme = theme
        
        # Actualizar atributos de la clase
        for key, value in theme.items():
            setattr(cls, key, value)


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

def get_available_themes() -> list:
    """Retorna una lista de los temas disponibles."""
    return list(_THEMES.keys())

def set_kogniterm_theme(theme_name: str):
    """
    Establece el tema global de KogniTerm.
    
    Args:
        theme_name: Nombre del tema a aplicar.
    """
    ColorPalette.set_theme(theme_name)
