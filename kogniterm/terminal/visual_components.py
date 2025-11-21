"""
Componentes visuales reutilizables para KogniTerm.

Este módulo proporciona funciones y clases para crear elementos visuales
consistentes y atractivos en la terminal usando Rich.
"""

from typing import Optional, List, Union
from rich.console import Console, Group, RenderableType
from rich.text import Text
from rich.panel import Panel
from rich.spinner import Spinner
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich.padding import Padding
from rich.align import Align
from rich.rule import Rule
from rich.markdown import Markdown
import random

from .themes import ColorPalette, Icons, Gradients, TextStyles


# ============================================================================
# TEXTO CON GRADIENTE
# ============================================================================

def create_gradient_text(text: str, gradient: List[str] = None, bold: bool = False) -> Text:
    """
    Crea texto con un degradado de colores.
    
    Args:
        text: El texto a colorear
        gradient: Lista de colores hexadecimales para el degradado
        bold: Si el texto debe ser negrita
        
    Returns:
        Text: Objeto Text de Rich con el degradado aplicado
    """
    if gradient is None:
        gradient = Gradients.PRIMARY
    
    if len(text) == 0:
        return Text("")
    
    result = Text()
    gradient_length = len(gradient)
    text_length = len(text)
    
    for i, char in enumerate(text):
        # Calcular el índice del color en el gradiente
        color_index = int((i / text_length) * (gradient_length - 1))
        color = gradient[color_index]
        
        # Añadir el carácter con su color
        result.append(char, style=f"bold {color}" if bold else color)
    
    return result


# ============================================================================
# SPINNERS PERSONALIZADOS
# ============================================================================

def create_animated_spinner(text: str = "Procesando", style: str = "dots") -> Spinner:
    """
    Crea un spinner animado con texto personalizado.
    
    Args:
        text: Texto a mostrar junto al spinner
        style: Estilo del spinner ('dots', 'line', 'arc', 'arrow', etc.)
        
    Returns:
        Spinner: Objeto Spinner de Rich
    """
    spinner_text = Text(f" {text}...", style=TextStyles.INFO_LIGHT)
    return Spinner(style, text=spinner_text, style=ColorPalette.SECONDARY)


def create_thinking_spinner() -> Spinner:
    """Crea un spinner específico para indicar que el agente está pensando."""
    text = Text(f"{Icons.THINKING} Pensando...", style=TextStyles.INFO_LIGHT)
    return Spinner("dots", text=text, style=ColorPalette.PRIMARY_LIGHT)


def create_processing_spinner() -> Spinner:
    """Crea un spinner específico para procesamiento general."""
    text = Text(f"{Icons.ROBOT} Procesando respuesta...", style=TextStyles.INFO_LIGHT)
    return Spinner("dots", text=text, style=ColorPalette.SECONDARY)


# ============================================================================
# BARRAS DE PROGRESO
# ============================================================================

def create_progress_bar(description: str = "Progreso") -> Progress:
    """
    Crea una barra de progreso personalizada.
    
    Args:
        description: Descripción de la tarea
        
    Returns:
        Progress: Objeto Progress de Rich
    """
    return Progress(
        SpinnerColumn(style=ColorPalette.SECONDARY),
        TextColumn("[bold]{task.description}"),
        BarColumn(
            complete_style=ColorPalette.SUCCESS,
            finished_style=ColorPalette.SUCCESS_LIGHT,
            pulse_style=ColorPalette.PRIMARY_LIGHT
        ),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        expand=False
    )


# ============================================================================
# PANELES INFORMATIVOS
# ============================================================================

def create_info_panel(
    content: Union[str, RenderableType],
    title: Optional[str] = None,
    status: str = "info",
    icon: Optional[str] = None,
    expand: bool = False,
    padding: tuple = (1, 2)
) -> Padding:
    """
    Crea un panel informativo con estilo consistente.
    
    Args:
        content: Contenido del panel (puede ser str, Markdown, Text, etc.)
        title: Título del panel
        status: Tipo de panel ('info', 'success', 'warning', 'error')
        icon: Icono personalizado (si no se proporciona, se usa el del status)
        expand: Si el panel debe expandirse al ancho completo
        padding: Padding exterior del panel
        
    Returns:
        Padding: Panel envuelto en Padding
    """
    # Determinar el color del borde según el status
    border_colors = {
        "info": ColorPalette.INFO,
        "success": ColorPalette.SUCCESS,
        "warning": ColorPalette.WARNING,
        "error": ColorPalette.ERROR,
    }
    border_color = border_colors.get(status.lower(), ColorPalette.INFO)
    
    # Determinar el icono
    if icon is None:
        status_icons = {
            "info": Icons.INFO,
            "success": Icons.SUCCESS,
            "warning": Icons.WARNING,
            "error": Icons.ERROR,
        }
        icon = status_icons.get(status.lower(), Icons.INFO)
    
    # Crear el título con icono si se proporciona
    panel_title = None
    if title:
        panel_title = f"{icon} {title}"
    
    # Convertir contenido a Markdown si es string
    if isinstance(content, str):
        content = Markdown(content)
    
    # Crear el panel
    panel = Panel(
        content,
        title=panel_title,
        border_style=border_color,
        expand=expand,
        padding=(1, 2)
    )
    
    return Padding(panel, padding)


def create_success_box(message: str, title: str = "Éxito") -> Padding:
    """Crea un panel de éxito."""
    return create_info_panel(message, title=title, status="success")


def create_error_box(message: str, title: str = "Error") -> Padding:
    """Crea un panel de error."""
    return create_info_panel(message, title=title, status="error")


def create_warning_box(message: str, title: str = "Advertencia") -> Padding:
    """Crea un panel de advertencia."""
    return create_info_panel(message, title=title, status="warning")


# ============================================================================
# SEPARADORES
# ============================================================================

def create_separator(
    text: Optional[str] = None,
    style: str = "primary",
    align: str = "center"
) -> Rule:
    """
    Crea un separador visual elegante.
    
    Args:
        text: Texto opcional para el separador
        style: Estilo del separador ('primary', 'secondary', 'muted')
        align: Alineación del texto ('left', 'center', 'right')
        
    Returns:
        Rule: Objeto Rule de Rich
    """
    style_colors = {
        "primary": ColorPalette.PRIMARY,
        "secondary": ColorPalette.SECONDARY,
        "muted": ColorPalette.GRAY_600,
    }
    color = style_colors.get(style, ColorPalette.PRIMARY)
    
    return Rule(text, style=color, align=align)


# ============================================================================
# MENSAJES ESTILIZADOS
# ============================================================================

def create_status_message(message: str, status: str = "info") -> Text:
    """
    Crea un mensaje de estado con icono y color apropiados.
    
    Args:
        message: El mensaje a mostrar
        status: Tipo de estado ('info', 'success', 'warning', 'error')
        
    Returns:
        Text: Mensaje formateado
    """
    status_icons = {
        "info": Icons.INFO,
        "success": Icons.SUCCESS,
        "warning": Icons.WARNING,
        "error": Icons.ERROR,
    }
    
    status_styles = {
        "info": TextStyles.INFO,
        "success": TextStyles.SUCCESS,
        "warning": TextStyles.WARNING,
        "error": TextStyles.ERROR,
    }
    
    icon = status_icons.get(status.lower(), Icons.INFO)
    style = status_styles.get(status.lower(), TextStyles.INFO)
    
    return Text(f"{icon} {message}", style=style)


# ============================================================================
# BANNER Y TÍTULOS
# ============================================================================

def create_welcome_banner(
    ascii_art: str,
    subtitle: Optional[str] = None,
    gradient: List[str] = None
) -> Group:
    """
    Crea un banner de bienvenida con arte ASCII y degradado suave carácter por carácter.
    
    Args:
        ascii_art: Arte ASCII para el banner
        subtitle: Subtítulo opcional
        gradient: Gradiente de colores personalizado
        
    Returns:
        Group: Grupo de renderables para el banner
    """
    if gradient is None:
        gradient = Gradients.PRIMARY
    
    # Dividir el arte ASCII en líneas
    lines = ascii_art.strip().split('\n')
    
    # Calcular el total de caracteres en todas las líneas para el degradado
    total_chars = sum(len(line) for line in lines)
    
    # Crear líneas con degradado suave aplicado carácter por carácter
    banner_lines = []
    char_count = 0
    
    for line in lines:
        line_text = Text()
        for char in line:
            # Calcular la posición de este carácter en el degradado total (0.0 a 1.0)
            position = char_count / max(total_chars - 1, 1)
            
            # Interpolar el color para este carácter
            color = _interpolate_gradient_color(gradient, position)
            
            # Añadir el carácter con su color interpolado
            line_text.append(char, style=color)
            char_count += 1
        
        line_text.justify = "center"
        banner_lines.append(line_text)
    
    # Crear el grupo de renderables
    renderables = [Text("")]  # Línea en blanco superior
    renderables.extend(banner_lines)
    
    if subtitle:
        renderables.append(Text(""))  # Línea en blanco
        renderables.append(Text(subtitle, style=TextStyles.SUBTITLE, justify="center"))
    
    renderables.append(Text(""))  # Línea en blanco inferior
    
    return Group(*renderables)


def _interpolate_gradient_color(gradient: List[str], position: float) -> str:
    """
    Interpola un color en una posición específica del gradiente.
    
    Args:
        gradient: Lista de colores hexadecimales
        position: Posición en el gradiente (0.0 a 1.0)
        
    Returns:
        str: Color hexadecimal interpolado
    """
    if len(gradient) == 0:
        return "#ffffff"
    if len(gradient) == 1:
        return gradient[0]
    
    # Calcular entre qué dos colores interpolar
    segment_size = 1.0 / (len(gradient) - 1)
    segment_index = int(position / segment_size)
    
    # Asegurar que no nos salgamos del rango
    if segment_index >= len(gradient) - 1:
        return gradient[-1]
    
    # Calcular la posición dentro del segmento (0.0 a 1.0)
    segment_position = (position - segment_index * segment_size) / segment_size
    
    # Interpolar entre los dos colores
    color1 = gradient[segment_index]
    color2 = gradient[segment_index + 1]
    
    return _interpolate_hex_colors(color1, color2, segment_position)


def _interpolate_hex_colors(color1: str, color2: str, t: float) -> str:
    """
    Interpola entre dos colores hexadecimales.
    
    Args:
        color1: Color hexadecimal inicial
        color2: Color hexadecimal final
        t: Factor de interpolación (0.0 a 1.0)
        
    Returns:
        str: Color hexadecimal interpolado
    """
    # Convertir hex a RGB
    c1 = color1.lstrip('#')
    c2 = color2.lstrip('#')
    
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    
    # Interpolar cada componente
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    
    # Convertir de vuelta a hex
    return f"#{r:02x}{g:02x}{b:02x}"


def create_section_title(title: str, icon: Optional[str] = None) -> Text:
    """
    Crea un título de sección estilizado.
    
    Args:
        title: Texto del título
        icon: Icono opcional
        
    Returns:
        Text: Título formateado
    """
    if icon:
        title = f"{icon} {title}"
    return Text(title, style=TextStyles.TITLE)


# ============================================================================
# TABLAS
# ============================================================================

def create_info_table(data: dict, title: Optional[str] = None) -> Table:
    """
    Crea una tabla informativa con pares clave-valor.
    
    Args:
        data: Diccionario con los datos a mostrar
        title: Título opcional de la tabla
        
    Returns:
        Table: Tabla formateada
    """
    table = Table(
        title=title,
        border_style=ColorPalette.PRIMARY,
        header_style=TextStyles.HEADING,
        show_header=False,
        padding=(0, 1)
    )
    
    table.add_column("Key", style=TextStyles.BOLD)
    table.add_column("Value", style=TextStyles.NORMAL)
    
    for key, value in data.items():
        table.add_row(key, str(value))
    
    return table


# ============================================================================
# MENSAJES MOTIVACIONALES
# ============================================================================

MOTIVATIONAL_MESSAGES = [
    "¡Listo para ayudarte a conquistar la terminal! 🚀",
    "¡Hagamos que el código cobre vida! ✨",
    "Tu asistente de terminal favorito está aquí 💜",
    "¡Preparado para automatizar todo! ⚡",
    "¡Vamos a hacer magia con código! 🎩",
    "Tu copiloto de terminal está listo 🛸",
    "¡A programar se ha dicho! 💻",
    "¡Transformemos ideas en realidad! 🌟",
]


def get_random_motivational_message() -> str:
    """Retorna un mensaje motivacional aleatorio."""
    return random.choice(MOTIVATIONAL_MESSAGES)


# ============================================================================
# UTILIDADES DE FORMATO
# ============================================================================

def format_command(command: str) -> Text:
    """
    Formatea un comando para mostrarlo de forma destacada.
    
    Args:
        command: El comando a formatear
        
    Returns:
        Text: Comando formateado
    """
    return Text(f"$ {command}", style=TextStyles.CODE_INLINE)


def format_file_path(path: str) -> Text:
    """
    Formatea una ruta de archivo para mostrarlo de forma destacada.
    
    Args:
        path: La ruta del archivo
        
    Returns:
        Text: Ruta formateada
    """
    return Text(f"{Icons.FILE} {path}", style=ColorPalette.ACCENT_BLUE)


def format_time_elapsed(seconds: float) -> str:
    """
    Formatea el tiempo transcurrido de forma legible.
    
    Args:
        seconds: Segundos transcurridos
        
    Returns:
        str: Tiempo formateado
    """
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}m {remaining_seconds}s"
