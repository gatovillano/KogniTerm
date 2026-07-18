"""
Ask Question Tool - Permite al agente consultar algo al usuario con un panel
interactivo de opciones seleccionables.

El agente puede presentar una pregunta con múltiples alternativas para que el
usuario elija, o escribir una respuesta personalizada.
"""

from typing import Optional, List, Any

# Metadata de la herramienta
name = "ask_question"
description = (
    "Muestra un panel interactivo al usuario con una pregunta y opciones seleccionables. "
    "Úsalo cuando necesites la opinión, preferencia o confirmación del usuario antes de continuar."
)

parameters_schema = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "La pregunta clara y concisa a hacer al usuario."
        },
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lista de 2 a 10 opciones predefinidas que el usuario puede seleccionar.",
            "minItems": 2,
            "maxItems": 10
        },
        "title": {
            "type": "string",
            "description": "Título del panel (default: 'Consulta del Agente')."
        },
        "allow_freeform": {
            "type": "boolean",
            "description": "Permite al usuario escribir una respuesta libre además de las opciones (default: true)."
        }
    },
    "required": ["question", "options"]
}


def get_action_description(args: dict) -> str:
    """Retorna una descripción legible de la acción para notificaciones UI."""
    question = args.get("question", "")
    short = question[:60] + ("…" if len(question) > 60 else "")
    return f"Preguntando al usuario: {short}"


def ask_question(
    question: str,
    options: List[str],
    title: str = "Consulta del Agente",
    allow_freeform: bool = True,
    terminal_ui: Optional[Any] = None,
) -> str:
    """
    Muestra al usuario un panel interactivo con una pregunta y opciones numeradas.
    El usuario puede seleccionar por número o escribir una respuesta libre.

    Args:
        question: La pregunta a mostrar al usuario.
        options: Lista de opciones predefinidas (2-10 elementos).
        title: Título del panel de pregunta.
        allow_freeform: Si es True, permite al usuario escribir una respuesta libre.
        terminal_ui: Inyectado automáticamente por KogniTerm.

    Returns:
        La respuesta del usuario como texto.
    """
    if not options or len(options) < 2:
        raise ValueError("Se requieren al menos 2 opciones.")
    if len(options) > 10:
        raise ValueError("Se permiten máximo 10 opciones.")

    # Usar Rich para el renderizado visual si está disponible
    try:
        from rich.console import Console, Group
        from rich.panel import Panel
        from rich.text import Text
        from rich.padding import Padding
        from rich import box

        console = getattr(terminal_ui, "console", None) if terminal_ui else None
        if console is None:
            console = Console()

        # ── Construir contenido del panel ────────────────────────────────────
        content_lines = Text()
        content_lines.append(f"{question}\n\n", style="bold white")

        option_colors = [
            "#7C3AED", "#2563EB", "#0891B2", "#059669",
            "#D97706", "#DC2626", "#7C3AED", "#BE185D",
            "#6D28D9", "#1D4ED8"
        ]

        for i, opt in enumerate(options, start=1):
            color = option_colors[(i - 1) % len(option_colors)]
            content_lines.append(f"  {i}. ", style=f"bold {color}")
            content_lines.append(f"{opt}\n", style="white")

        if allow_freeform:
            content_lines.append("\n  O escribe tu respuesta personalizada.", style="dim italic")

        # ── Renderizar panel ─────────────────────────────────────────────────
        panel = Panel(
            Padding(content_lines, (1, 2)),
            title=f"[bold #A78BFA]❓ {title}[/bold #A78BFA]",
            border_style="#7C3AED",
            box=box.ROUNDED,
            expand=False,
            width=min(console.width - 4, 90),
        )
        console.print()
        console.print(Padding(panel, (0, 2)))
        console.print()

        # ── Prompt de respuesta ──────────────────────────────────────────────
        valid_range = f"1-{len(options)}"
        freeform_hint = " (o escribe tu respuesta)" if allow_freeform else ""
        prompt_text = f"  Selecciona [{valid_range}]{freeform_hint}: "

        _print_prompt(console, prompt_text)

    except ImportError:
        # Fallback sin Rich
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
        print(f"\n  {question}\n")
        for i, opt in enumerate(options, start=1):
            print(f"  {i}. {opt}")
        if allow_freeform:
            print("\n  (o escribe tu respuesta personalizada)")
        prompt_text = f"Selecciona [1-{len(options)}]: "

    # ── Bucle de lectura de respuesta ────────────────────────────────────────
    while True:
        try:
            raw = _read_input(terminal_ui)
        except (EOFError, KeyboardInterrupt):
            return "Cancelado por el usuario."

        raw = (raw or "").strip()
        if not raw:
            continue

        # Intentar interpretar como número
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                selected = options[idx - 1]
                _print_selection(terminal_ui, selected)
                return selected
            else:
                _print_error(terminal_ui, f"Por favor elige un número entre 1 y {len(options)}.")
                continue

        # Respuesta libre
        if allow_freeform:
            _print_selection(terminal_ui, raw)
            return raw

        _print_error(terminal_ui, f"Por favor ingresa un número entre 1 y {len(options)}.")


# ── Helpers de I/O ────────────────────────────────────────────────────────────

def _print_prompt(console, text: str):
    """Imprime el prompt de selección."""
    try:
        from rich.text import Text
        console.print(Text(text, style="bold #A78BFA"), end="")
    except Exception:
        print(text, end="", flush=True)


def _read_input(terminal_ui) -> str:
    """Lee input del usuario, usando prompt_toolkit si está disponible."""
    # Intentar prompt_toolkit (usado por KogniTerm en modo CLI)
    if terminal_ui and hasattr(terminal_ui, "prompt_session"):
        try:
            import asyncio
            session = terminal_ui.prompt_session
            # Intentar prompt síncrono
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Estamos en el hilo worker del agente: usar input() directamente
                    return input("")
                else:
                    return loop.run_until_complete(session.prompt_async(""))
            except RuntimeError:
                return input("")
        except Exception:
            pass
    return input("")


def _print_selection(terminal_ui, text: str):
    """Muestra confirmación de la selección."""
    try:
        from rich.console import Console
        from rich.text import Text
        from rich.padding import Padding

        console = getattr(terminal_ui, "console", None) if terminal_ui else None
        if console is None:
            console = Console()

        msg = Text()
        msg.append("  ✓ Seleccionado: ", style="bold #10B981")
        msg.append(text, style="white bold")
        console.print(Padding(msg, (0, 2)))
        console.print()
    except Exception:
        print(f"\n  ✓ Seleccionado: {text}\n")


def _print_error(terminal_ui, text: str):
    """Muestra un error de validación."""
    try:
        from rich.console import Console
        from rich.text import Text
        from rich.padding import Padding

        console = getattr(terminal_ui, "console", None) if terminal_ui else None
        if console is None:
            console = Console()

        msg = Text(f"  ⚠ {text}", style="bold #F59E0B")
        console.print(Padding(msg, (0, 2)))
    except Exception:
        print(f"  ⚠ {text}")
