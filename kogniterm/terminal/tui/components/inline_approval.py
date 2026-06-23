"""
InlineApprovalWidget — Componente de aprobación inline para KogniTerm TUI.

Se incrusta directamente en el chat (no como modal), muestra el diff coloreado
estilo editor de código y ofrece tres acciones: Aceptar, Aceptar Todas, Cancelar.
"""

from __future__ import annotations

from typing import Optional, List, Callable
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Label, Button, Static
from textual import events
from textual.reactive import reactive
from rich.text import Text
from rich.syntax import Syntax
from textual.widget import Widget
from textual.message import Message

from kogniterm.terminal.themes import ColorPalette



# ─── Parsing de diff ──────────────────────────────────────────────────────────

@dataclass
class _DiffLine:
    kind: str          # 'add' | 'del' | 'context' | 'hunk'
    content: str
    old_lineno: Optional[int] = None
    new_lineno: Optional[int] = None


def _parse_diff(diff_string: str) -> List[_DiffLine]:
    lines: List[_DiffLine] = []
    old_n, new_n = 0, 0
    raw_lines = diff_string.splitlines()
    
    # Heurística simple: si no hay hunks ni headers, tratamos todo como contexto simple
    is_real_diff = any(l.startswith(("@@", "--- ", "+++ ")) for l in raw_lines)

    MAX_LINES = 500
    if len(raw_lines) > MAX_LINES:
        truncated_lines = raw_lines[:MAX_LINES]
        has_truncation = True
    else:
        truncated_lines = raw_lines
        has_truncation = False

    for raw in truncated_lines:
        if not is_real_diff:
            new_n += 1
            lines.append(_DiffLine(kind="context", content=raw, new_lineno=new_n))
            continue

        if raw.startswith("---") or raw.startswith("+++"):
            lines.append(_DiffLine(kind="hunk", content=raw))
            continue
        if raw.startswith("@@"):
            try:
                parts = raw.split(" ")
                old_n = int(parts[1].split(",")[0].replace("-", "")) - 1
                new_n = int(parts[2].split(",")[0].replace("+", "")) - 1
            except (ValueError, IndexError):
                pass
            lines.append(_DiffLine(kind="hunk", content=raw))
            continue
        
        if raw.startswith("+") and not raw.startswith("+++"):
            new_n += 1
            lines.append(_DiffLine(kind="add", content=raw[1:], new_lineno=new_n))
        elif raw.startswith("-") and not raw.startswith("---"):
            old_n += 1
            lines.append(_DiffLine(kind="del", content=raw[1:], old_lineno=old_n))
        else:
            old_n += 1
            new_n += 1
            # Solo quitamos el primer char si es un espacio (estándar de diff)
            content = raw[1:] if raw.startswith(" ") else raw
            lines.append(_DiffLine(
                kind="context",
                content=content,
                old_lineno=old_n,
                new_lineno=new_n,
            ))
    
    if has_truncation:
        lines.append(_DiffLine(kind="hunk", content=f"... [truncado, {len(raw_lines) - MAX_LINES} líneas adicionales] ..."))
        
    return lines


# ─── Widget de una sola línea del diff ────────────────────────────────────────

class _DiffLineWidget(Static):
    DEFAULT_CSS = """
    _DiffLineWidget {
        width: 100%;
        height: 1;
    }
    """

    def __init__(self, diff_line: _DiffLine, **kwargs):
        super().__init__("", **kwargs)
        self._dl = diff_line

    def on_mount(self) -> None:
        dl = self._dl
        if dl.kind == "hunk":
            self.update(Text(dl.content, style="dim #7c8fa6"))
            return

        old_str = f"{dl.old_lineno:>4}" if dl.old_lineno is not None else "    "
        new_str = f"{dl.new_lineno:>4}" if dl.new_lineno is not None else "    "

        if dl.kind == "add":
            sym, sym_style = "+", "bold #22c55e"
            bg, txt_style, ln_style = "on #0d2818", "#86efac on #0d2818", "dim #22c55e"
        elif dl.kind == "del":
            sym, sym_style = "-", "bold #ef4444"
            bg, txt_style, ln_style = "on #2a0d0d", "#fca5a5 on #2a0d0d", "dim #ef4444"
        else:
            sym, sym_style = " ", "dim"
            txt_style, ln_style = "dim #9ca3af", "dim #4b5563"

        t = Text(no_wrap=True, overflow="ellipsis")
        # Mostrar solo el número de línea nuevo si es contexto simple o add
        # Si es un diff real con old/new, mostramos ambos
        if dl.old_lineno and dl.new_lineno and dl.old_lineno != dl.new_lineno:
            t.append(old_str, style=ln_style)
            t.append(" ")
            t.append(new_str, style=ln_style)
        else:
            # Para comandos u otros, solo un número de línea
            t.append(new_str if dl.new_lineno else old_str, style=ln_style)
        
        t.append(f" {sym} " if sym != " " else "   ", style=sym_style)
        t.append(dl.content, style=txt_style)
        self.update(t)


# ─── Widget inline principal ──────────────────────────────────────────────────

# Resultado posible: "accept" | "accept_all" | "cancel"
ApprovalResult = str


class InlineApprovalWidget(Widget):
    """
    Widget de aprobación inline incrustado en el chat log.

    Emite un mensaje InlineApprovalWidget.Decided cuando el usuario elige
    una de las tres opciones.

    Parámetros
    ----------
    message:        Texto descriptivo de la acción a confirmar.
    title:          Título del panel (p.ej. "Confirmación de Comando").
    diff_content:   Diff unificado para renderizar coloreado. Puede ser None.
    file_path:      Ruta del archivo (mostrada en el subheader). Puede ser None.
    callback:       Función síncrona llamada con el resultado ("accept" | "accept_all" | "cancel").
    """
    can_focus = True

    # ── Mensaje de decisión ──────────────────────────────────────────────────
    class Decided(Message):
        def __init__(self, widget: "InlineApprovalWidget", result: ApprovalResult) -> None:
            super().__init__()
            self.widget = widget
            self.result = result

    # ── CSS ──────────────────────────────────────────────────────────────────
    def on_mount(self):
        """Aplicar colores dinámicos del tema al montar el widget."""
        p = ColorPalette
        # Fondo del contenedor principal
        self.styles.background = p.GRAY_800
        self.styles.border = None # Sin borde exterior
        
        try:
            title = self.query_one("#ia-title-label")
            title.styles.color = p.TEXT_PRIMARY
        except: pass
        
        try:
            scroll = self.query_one("#ia-diff-scroll")
            # El área de código/diff es un poco más oscura o contrastada
            scroll.styles.background = "black" if p.CURRENT_THEME != "light" else "#eeeeee"
        except: pass

        try:
            msg = self.query_one("#ia-message")
            msg.styles.color = p.TEXT_SECONDARY
        except: pass
        
        # Botones - Semántica consistente
        try:
            self.query_one("#ia-btn-accept").styles.background = p.SUCCESS
            self.query_one("#ia-btn-accept-all").styles.background = p.INFO
            self.query_one("#ia-btn-cancel").styles.background = p.ERROR
        except: pass

    DEFAULT_CSS = """
    InlineApprovalWidget {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: auto;
        margin: 1 0;
        padding: 1 2;
    }

    /* Título / Petición */
    #ia-title-label {
        width: 100%;
        text-style: bold;
        padding-bottom: 1;
    }

    /* Diff area */
    #ia-diff-scroll {
        width: 100%;
        height: auto;
        max-height: 20;
        margin-bottom: 1;
        border: none;
    }
    #ia-diff-container {
        width: 100%;
        height: auto;
        padding: 0;
        background: transparent;
    }
    #ia-bash-syntax {
        padding: 1 2;
    }

    /* Mensaje sin diff */
    #ia-message {
        width: 100%;
        height: auto;
        padding: 0 0 1 0;
        background: transparent;
    }

    /* Footer con botones */
    #ia-footer {
        width: 100%;
        height: 3;
        background: transparent;
        layout: horizontal;
    }
    #ia-btn-accept {
        color: #ffffff;
        border: none;
        margin-right: 1;
        width: 16;
        height: 3;
        min-height: 3;
    }
    #ia-btn-accept-all {
        color: #ffffff;
        border: none;
        margin-right: 1;
        width: 16;
        height: 3;
        min-height: 3;
    }
    #ia-btn-cancel {
        color: #ffffff;
        border: none;
        width: 16;
        height: 3;
        min-height: 3;
    }
    """

    def __init__(
        self,
        message: str,
        title: str = "⚠  Aprobación Requerida",
        diff_content: Optional[str] = None,
        file_path: Optional[str] = None,
        callback: Optional[Callable[[ApprovalResult], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._message = message
        self._title = title
        self._diff_content = diff_content
        self._file_path = file_path
        self._callback = callback

    # ── Composición ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        is_bash = (self._file_path == "bash")
        has_diff = bool(self._diff_content and self._diff_content.strip())

        # Título / Petición
        icon = "🐚" if is_bash else "📄"
        header_text = f"{icon} {self._title}"
        if self._file_path and not is_bash:
            header_text += f" [dim]({self._file_path})[/dim]"
        
        yield Label(header_text, id="ia-title-label", markup=True)

        # Contenido (Diff, Syntax o Mensaje)
        if is_bash and has_diff:
            # Para comandos, mostramos syntax highlighting directo
            # Asegurarse de que el color de fondo de la sintaxis sea negro o transparente
            with ScrollableContainer(id="ia-diff-scroll"):
                 # Usar tema monokai pero con fondo predeterminado (negro/oscuro)
                 yield Static(Syntax(self._diff_content, "bash", theme="monokai", background_color="default"), id="ia-bash-syntax")
        elif has_diff:
            # Diff de archivos real
            with ScrollableContainer(id="ia-diff-scroll"):
                with Vertical(id="ia-diff-container"):
                    for dl in _parse_diff(self._diff_content):
                        yield _DiffLineWidget(dl)
        else:
            yield Label(self._message, id="ia-message", markup=False)

        # Footer con botones
        with Horizontal(id="ia-footer"):
            yield Button("✓ Aceptar", id="ia-btn-accept", variant="success")
            yield Button("⚡ Siempre", id="ia-btn-accept-all", variant="primary")
            yield Button("✕ Cancelar", id="ia-btn-cancel", variant="error")

    # ── Eventos ──────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        id_map = {
            "ia-btn-accept":     "accept",
            "ia-btn-accept-all": "accept_all",
            "ia-btn-cancel":     "cancel",
        }
        result = id_map.get(event.button.id)
        if result:
            self._resolve(result)
            event.stop()

    def on_key(self, event: events.Key) -> None:
        key_map = {
            "s": "accept",
            "y": "accept",
            "enter": "accept",
            "a": "accept_all",
            "n": "cancel",
            "escape": "cancel",
        }
        result = key_map.get(event.key)
        if result:
            self._resolve(result)
            event.stop()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _resolve(self, result: ApprovalResult) -> None:
        """Llama al callback y elimina el widget del chat."""
        if self._callback:
            self._callback(result)
        self.post_message(self.Decided(self, result))
        # Auto-remover del DOM una vez decidido
        self.remove()

    def _diff_stats(self) -> str:
        if not self._diff_content:
            return ""
        lines = self._diff_content.splitlines()
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        deleted = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        parts = []
        if added:
            parts.append(f"+{added}")
        if deleted:
            parts.append(f"-{deleted}")
        return "  ".join(parts)
