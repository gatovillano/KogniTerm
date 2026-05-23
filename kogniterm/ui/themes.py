"""
Temas de color y estilos para KogniTerm.

Este módulo define paletas de colores, estilos de texto y configuraciones
de tema para mantener una apariencia visual consistente en toda la aplicación.
"""

from typing import Dict, List
from rich.theme import Theme
from rich.style import Style


# ============================================================================
# DEFINICIONES DE TEMAS
# ============================================================================

_THEMES = {
    "default": {
        "PRIMARY_LIGHTEST": "#f9fafb",
        "PRIMARY_LIGHTER": "#f3f4f6",
        "PRIMARY_LIGHT": "#e5e7eb",
        "PRIMARY": "#9ca3af",
        "PRIMARY_DARK": "#4b5563",
        "PRIMARY_DARKER": "#374151",
        "PRIMARY_DARKEST": "#1f2937",
        "SECONDARY": "#9ca3af",
        "SECONDARY_LIGHT": "#d1d5db",
        "SECONDARY_DARK": "#374151",
        "ACCENT": "#6b7280",
        "ACCENT_PINK": "#9ca3af",
        "ACCENT_BLUE": "#d1d5db",
        "ACCENT_GREEN": "#6b7280",
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
        "GRADIENT_PRIMARY": [
            "#ffffff", "#fafafa", "#f5f5f5", "#f0f0f0", "#e5e5e5", "#d4d4d4", 
            "#a3a3a3", "#737373", "#525252", "#404040", "#262626", "#171717", "#0a0a0a"
        ]
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
        "PRIMARY_LIGHTEST": "#00ff41",
        "PRIMARY_LIGHTER": "#00e538",
        "PRIMARY_LIGHT": "#00cc32",
        "PRIMARY": "#00b32c",
        "PRIMARY_DARK": "#009926",
        "PRIMARY_DARKER": "#008020",
        "SECONDARY_LIGHT": "#39ff14",
        "SECONDARY": "#00ff41",
        "SECONDARY_DARK": "#007a1a",
        "ACCENT_PINK": "#00ff41",
        "ACCENT_BLUE": "#00cc32",
        "ACCENT_GREEN": "#39ff14",
        "SUCCESS": "#00ff41",
        "SUCCESS_LIGHT": "#39ff14",
        "WARNING": "#ccff00",
        "WARNING_LIGHT": "#ddff33",
        "ERROR": "#ff4444",
        "ERROR_LIGHT": "#ff6666",
        "INFO": "#00cc32",
        "INFO_LIGHT": "#00ff41",
        "GRAY_50":  "#0d1a0d",   # fondo oscuro con matiz verde
        "GRAY_100": "#0a140a",   # fondo muy oscuro
        "GRAY_200": "#071007",   # fondo casi negro
        "GRAY_300": "#1a4d1a",   # verde oscuro — visible como texto dim
        "GRAY_400": "#1f6b1f",   # verde medio oscuro
        "GRAY_500": "#267a26",   # verde legible (texto razonamiento dim)
        "GRAY_600": "#2d9e2d",   # verde medio — bordes visibles
        "GRAY_700": "#157a15",   # verde oscuro para bordes del panel
        "GRAY_800": "#050d05",   # fondo muy oscuro del panel de razonamiento
        "GRAY_900": "#000000",   # fondo base negro puro
        "TEXT_PRIMARY": "#00ff41",
        "TEXT_SECONDARY": "#00cc32",
        "TEXT_MUTED": "#009926",
        "TEXT_DIM": "#267a26",   # visible como texto atenuado sobre negro
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
    },
    "cyberpunk": {
        "PRIMARY_LIGHTEST": "#ff7edb",
        "PRIMARY_LIGHTER": "#ff49db",
        "PRIMARY_LIGHT": "#ff00ff",
        "PRIMARY": "#d300d3",
        "PRIMARY_DARK": "#a300a3",
        "PRIMARY_DARKER": "#730073",
        "SECONDARY_LIGHT": "#00ffff",
        "SECONDARY": "#00d3d3",
        "SECONDARY_DARK": "#00a3a3",
        "ACCENT_PINK": "#ff007f",
        "ACCENT_BLUE": "#007fff",
        "ACCENT_GREEN": "#39ff14",
        "SUCCESS": "#39ff14",
        "SUCCESS_LIGHT": "#bfff00",
        "WARNING": "#ffff00",
        "WARNING_LIGHT": "#fff000",
        "ERROR": "#ff0033",
        "ERROR_LIGHT": "#ff3366",
        "INFO": "#00ccff",
        "INFO_LIGHT": "#33ddff",
        "GRAY_50": "#1a1a1a",
        "GRAY_100": "#141414",
        "GRAY_200": "#0f0f0f",
        "GRAY_300": "#0a0a0a",
        "GRAY_400": "#050505",
        "GRAY_500": "#000000",
        "GRAY_600": "#121212",
        "GRAY_700": "#1e1e1e",
        "GRAY_800": "#2a2a2a",
        "GRAY_900": "#363636",
        "TEXT_PRIMARY": "#00ffff",
        "TEXT_SECONDARY": "#ff00ff",
        "TEXT_MUTED": "#39ff14",
        "TEXT_DIM": "#ffff00",
    },
    "nebula": {
        "PRIMARY_LIGHTEST": "#f3e5f5",
        "PRIMARY_LIGHTER": "#e1bee7",
        "PRIMARY_LIGHT": "#ce93d8",
        "PRIMARY": "#ba68c8",
        "PRIMARY_DARK": "#ab47bc",
        "PRIMARY_DARKER": "#9c27b0",
        "SECONDARY_LIGHT": "#e1f5fe",
        "SECONDARY": "#81d4fa",
        "SECONDARY_DARK": "#29b6f6",
        "ACCENT_PINK": "#f06292",
        "ACCENT_BLUE": "#64b5f6",
        "ACCENT_GREEN": "#81c784",
        "SUCCESS": "#4caf50",
        "SUCCESS_LIGHT": "#8bc34a",
        "WARNING": "#ffb74d",
        "WARNING_LIGHT": "#ffcc80",
        "ERROR": "#e57373",
        "ERROR_LIGHT": "#ef9a9a",
        "INFO": "#4fc3f7",
        "INFO_LIGHT": "#81d4fa",
        "GRAY_50": "#fafafa",
        "GRAY_100": "#f5f5f5",
        "GRAY_200": "#eeeeee",
        "GRAY_300": "#e0e0e0",
        "GRAY_400": "#bdbdbd",
        "GRAY_500": "#9e9e9e",
        "GRAY_600": "#757575",
        "GRAY_700": "#616161",
        "GRAY_800": "#424242",
        "GRAY_900": "#212121",
        "TEXT_PRIMARY": "#ffffff",
        "TEXT_SECONDARY": "#e1bee7",
        "TEXT_MUTED": "#ce93d8",
        "TEXT_DIM": "#b0bec5",
    },
    "dracula": {
        "PRIMARY_LIGHTEST": "#ff92df",
        "PRIMARY_LIGHTER": "#ff79c6",
        "PRIMARY_LIGHT": "#bd93f9",
        "PRIMARY": "#8be9fd",
        "PRIMARY_DARK": "#50fa7b",
        "PRIMARY_DARKER": "#f1fa8c",
        "SECONDARY_LIGHT": "#ffb86c",
        "SECONDARY": "#ff5555",
        "SECONDARY_DARK": "#6272a4",
        "ACCENT_PINK": "#ff79c6",
        "ACCENT_BLUE": "#8be9fd",
        "ACCENT_GREEN": "#50fa7b",
        "SUCCESS": "#50fa7b",
        "SUCCESS_LIGHT": "#f1fa8c",
        "WARNING": "#ffb86c",
        "WARNING_LIGHT": "#ffb86c",
        "ERROR": "#ff5555",
        "ERROR_LIGHT": "#ff5555",
        "INFO": "#8be9fd",
        "INFO_LIGHT": "#8be9fd",
        "GRAY_50": "#f8f8f2",
        "GRAY_100": "#f8f8f2",
        "GRAY_200": "#f8f8f2",
        "GRAY_300": "#f8f8f2",
        "GRAY_400": "#f8f8f2",
        "GRAY_500": "#6272a4",
        "GRAY_600": "#44475a",
        "GRAY_700": "#282a36",
        "GRAY_800": "#21222c",
        "GRAY_900": "#191a21",
        "TEXT_PRIMARY": "#f8f8f2",
        "TEXT_SECONDARY": "#bd93f9",
        "TEXT_MUTED": "#6272a4",
        "TEXT_DIM": "#44475a",
    },
    "light": {
        "PRIMARY_LIGHTEST": "#f5f9ff",
        "PRIMARY_LIGHTER": "#dbeafe",
        "PRIMARY_LIGHT": "#93c5fd",
        "PRIMARY": "#2563eb",
        "PRIMARY_DARK": "#1d4ed8",
        "PRIMARY_DARKER": "#1e3a8a",
        "PRIMARY_DARKEST": "#172554",
        "SECONDARY": "#0284c7",
        "SECONDARY_LIGHT": "#38bdf8",
        "SECONDARY_DARK": "#0369a1",
        "ACCENT": "#475569",
        "ACCENT_PINK": "#be185d",
        "ACCENT_BLUE": "#1d4ed8",
        "ACCENT_GREEN": "#15803d",
        "SUCCESS": "#059669",
        "SUCCESS_LIGHT": "#10b981",
        "WARNING": "#d97706",
        "WARNING_LIGHT": "#f59e0b",
        "ERROR": "#dc2626",
        "ERROR_LIGHT": "#ef4444",
        "INFO": "#2563eb",
        "INFO_LIGHT": "#3b82f6",
        "GRAY_50": "#ffffff",
        "GRAY_100": "#f8fafc",
        "GRAY_200": "#e2e8f0",
        "GRAY_300": "#cbd5e1",
        "GRAY_400": "#94a3b8",
        "GRAY_500": "#64748b",
        "GRAY_600": "#475569",
        "GRAY_700": "#334155",
        "GRAY_800": "#e2e8f0",
        "GRAY_900": "#f8fafc",
        "TEXT_PRIMARY": "#0b1324",
        "TEXT_SECONDARY": "#1e293b",
        "TEXT_MUTED": "#334155",
        "TEXT_DIM": "#475569",
    },
}


# ============================================================================
# PALETA DE COLORES PRINCIPAL
# ============================================================================

class ColorPalette:
    """Paleta de colores principal de KogniTerm."""
    
    # Inicializar con el tema por defecto
    _current_theme = _THEMES["default"]
    CURRENT_THEME = "default"

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
        # Soporte para detección automática del tema default
        if theme_name == "default":
            try:
                scheme = detect_terminal_theme()
                if scheme == "light":
                    theme_name = "light"
            except Exception:
                # Si falla la detección, permanecemos en default (dark)
                pass

        if theme_name not in _THEMES:
            # Fallback seguro
            if theme_name != "default":
                return cls.set_theme("default")
            raise ValueError(f"Tema '{theme_name}' no encontrado.")
        
        theme = _THEMES[theme_name]
        cls._current_theme = theme
        cls.CURRENT_THEME = theme_name
        
        # Actualizar atributos de la clase
        for key, value in theme.items():
            setattr(cls, key, value)


# ============================================================================
# ESTILOS DE TEXTO
# ============================================================================

class TextStyles:
    """Estilos de texto predefinidos que se actualizan dinámicamente con el tema."""
    
    @classmethod
    def _get_style(cls, color, bold=False, italic=False, dim=False, bgcolor=None):
        return Style(color=color, bold=bold, italic=italic, dim=dim, bgcolor=bgcolor)

    # Títulos
    @property
    def TITLE(self): return self._get_style(ColorPalette.PRIMARY_LIGHT, bold=True)
    @property
    def SUBTITLE(self): return self._get_style(ColorPalette.SECONDARY_LIGHT, bold=True)
    @property
    def HEADING(self): return self._get_style(ColorPalette.PRIMARY, bold=True)
    
    # Texto general
    @property
    def NORMAL(self): return self._get_style(ColorPalette.TEXT_PRIMARY)
    @property
    def MUTED(self): return self._get_style(ColorPalette.TEXT_MUTED)
    @property
    def DIM(self): return self._get_style(ColorPalette.TEXT_DIM, dim=True)
    @property
    def BOLD(self): return Style(bold=True)
    @property
    def ITALIC(self): return Style(italic=True)
    
    # Código
    @property
    def CODE(self): return self._get_style(ColorPalette.ACCENT_BLUE, bgcolor=ColorPalette.GRAY_800)
    @property
    def CODE_INLINE(self): return self._get_style(ColorPalette.SECONDARY_LIGHT)
    
    # Estados
    @property
    def SUCCESS(self): return self._get_style(ColorPalette.SUCCESS, bold=True)
    @property
    def SUCCESS_LIGHT(self): return self._get_style(ColorPalette.SUCCESS_LIGHT)
    @property
    def WARNING(self): return self._get_style(ColorPalette.WARNING, bold=True)
    @property
    def WARNING_LIGHT(self): return self._get_style(ColorPalette.WARNING_LIGHT)
    @property
    def ERROR(self): return self._get_style(ColorPalette.ERROR, bold=True)
    @property
    def ERROR_LIGHT(self): return self._get_style(ColorPalette.ERROR_LIGHT)
    @property
    def INFO(self): return self._get_style(ColorPalette.INFO, bold=True)
    @property
    def INFO_LIGHT(self): return self._get_style(ColorPalette.INFO_LIGHT)
    
    # Prompt
    @property
    def PROMPT(self): return self._get_style(ColorPalette.PRIMARY_LIGHT, bold=True)
    @property
    def PROMPT_SYMBOL(self): return self._get_style(ColorPalette.SECONDARY, bold=True)
    
    # Bordes y decoraciones
    @property
    def BORDER_PRIMARY(self): return self._get_style(ColorPalette.PRIMARY)
    @property
    def BORDER_SECONDARY(self): return self._get_style(ColorPalette.SECONDARY)
    @property
    def BORDER_SUCCESS(self): return self._get_style(ColorPalette.SUCCESS)
    @property
    def BORDER_WARNING(self): return self._get_style(ColorPalette.WARNING)
    @property
    def BORDER_ERROR(self): return self._get_style(ColorPalette.ERROR)
    @property
    def BORDER_INFO(self): return self._get_style(ColorPalette.INFO)

# Instancia global para acceso fácil
TextStyles = TextStyles()


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
    RESEARCH = "🔍"
    FOCO = "🎯"
    SPARKLES = "✨"
    ROCKET = "🚀"
    FIRE = "🔥"
    STAR = "⭐"
    
    # Herramientas
    TOOL = "🛠️"
    WRENCH = "🔧"
    HAMMER = "🔨"
    GEAR = "⚙️"
    TERMINAL = "🐚"
    
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
        "#f3f4f6", # Gray 100
        "#e5e7eb", # Gray 200
        "#d1d5db", # Gray 300
        "#9ca3af", # Gray 400
        "#6b7280", # Gray 500
        "#4b5563", # Gray 600
        "#374151", # Gray 700
        "#1f2937", # Gray 800
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

    # Gradientes para nuevos temas
    CYBERPUNK = [
        "#ff00ff", # Fucsia
        "#d300d3",
        "#00ffff", # Cian
        "#00d3d3",
        "#39ff14", # Lima
    ]

    OCEAN = [
        "#00d2ff", # Azul claro
        "#3a7bd5", # Azul medio
        "#004e92", # Azul oscuro
    ]

    LIGHT = [
        "#1d4ed8", # Azul intenso
        "#2563eb", # Azul primario
        "#3b82f6", # Azul medio
        "#60a5fa", # Azul claro
        "#93c5fd", # Azul suave
    ]

    MATRIX = [
        "#00ff00", # Verde brillante
        "#008f11", # Verde medio
        "#003b00", # Verde oscuro
    ]

    SUNSET = [
        "#ff512f", # Naranja quemado
        "#dd2476", # Rosa oscuro
        "#f09819", # Ámbar
        "#ff512f",
    ]


    NEBULA = [
        "#4a148c", # Morado oscuro
        "#7b1fa2",
        "#9c27b0",
        "#ba68c8",
        "#e1bee7",
        "#f06292", # Rosa
    ]

    DRACULA = [
        "#8be9fd", # Cian
        "#bd93f9", # Morado
        "#ff79c6", # Rosa
        "#ffb86c", # Naranja
        "#f1fa8c", # Amarillo
        "#50fa7b", # Verde
    ]

    @classmethod
    def get_current_gradient(cls) -> List[str]:
        """Retorna el degradado correspondiente al tema actual."""
        theme_name = ColorPalette.CURRENT_THEME
        
        mapping = {
            "default": cls.PRIMARY,
            "light": cls.LIGHT,
            "ocean": cls.OCEAN,
            "matrix": cls.MATRIX,
            "sunset": cls.SUNSET,
            "cyberpunk": cls.CYBERPUNK,
            "nebula": cls.NEBULA,
            "dracula": cls.DRACULA
        }
        
        return mapping.get(theme_name, cls.PRIMARY)


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

def detect_terminal_theme() -> str:
    """
    Detecta si la terminal está en modo claro u oscuro.
    
    Returns:
        str: 'light' o 'dark'
    """
    import os
    import sys
    import select
    
    # 1. Intentar por variables de entorno (rápido)
    colorfgbg = os.environ.get("COLORFGBG")
    if colorfgbg:
        try:
            parts = colorfgbg.split(";")
            if len(parts) >= 2:
                bg = int(parts[1])
                # Típicamente 0-7 son oscuros, 8-15 son claros en paletas de 16 colores
                if bg >= 7:
                    return "light"
                else:
                    return "dark"
        except (ValueError, IndexError):
            pass

    # 2. Intentar por secuencias de escape OSC 11 (preciso pero requiere TTY)
    if sys.stdin.isatty() and sys.stdout.isatty():
        import termios
        import tty
        
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                # Query background color
                sys.stdout.write("\x1b]11;?\x1b\\")
                sys.stdout.flush()
                
                # Leer respuesta con timeout corto
                response = ""
                while True:
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        char = sys.stdin.read(1)
                        response += char
                        if char in ("\x07", "\\"): # Terminadores OSC o ST
                            break
                        if len(response) > 50:
                            break
                    else:
                        break
                
                if "rgb:" in response:
                    rgb_part = response.split("rgb:")[1].split("\x1b")[0].split("\x07")[0]
                    r, g, b = [int(x, 16) for x in rgb_part.split("/")]
                    # Heurística de luminancia (0-65535)
                    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 65535
                    return "light" if luminance > 0.5 else "dark"
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass

    # Por defecto asumimos oscuro (estética original de KogniTerm)
    return "dark"
