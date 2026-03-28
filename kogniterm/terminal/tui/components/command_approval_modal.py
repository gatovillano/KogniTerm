"""
CommandApprovalModal - Modal de aprobación de comandos/cambios para KogniTerm TUI.

Muestra un diff coloreado (estilo editor de código) cuando se tienen cambios de archivo,
o un mensaje de texto simple para confirmaciones de comandos bash.
"""

from __future__ import annotations

from typing import Optional, List
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Label, Button, Static
from textual import events
from textual.reactive import reactive
from rich.text import Text

from kogniterm.terminal.themes import ColorPalette


# ─── Parsing del diff ────────────────────────────────────────────────────────

@dataclass
class _DiffLine:
    kind: str          # 'add' | 'del' | 'context' | 'hunk'
    content: str
    old_lineno: Optional[int] = None
    new_lineno: Optional[int] = None


def _parse_unified_diff(diff_string: str) -> List[_DiffLine]:
    """Parsea un diff unificado y devuelve una lista de _DiffLine."""
    lines: List[_DiffLine] = []
    old_n = 0
    new_n = 0

    for raw in diff_string.splitlines():
        if raw.startswith("---") or raw.startswith("+++"):
            lines.append(_DiffLine(kind="hunk", content=raw))
            continue

        if raw.startswith("@@"):
            # @@ -old_start,old_len +new_start,new_len @@
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
            lines.append(_DiffLine(
                kind="context",
                content=raw[1:] if raw else "",
                old_lineno=old_n,
                new_lineno=new_n,
            ))

    return lines


# ─── Widget de una línea de diff ─────────────────────────────────────────────

class _DiffLineWidget(Static):
    """Renderiza una línea individual del diff con colour y número de línea."""

    DEFAULT_CSS = """
    _DiffLineWidget {
        width: 100%;
        height: 1;
        layout: horizontal;
    }
    """

    def __init__(self, diff_line: _DiffLine, **kwargs):
        super().__init__("", **kwargs)
        self._diff_line = diff_line

    def on_mount(self) -> None:
        dl = self._diff_line

        if dl.kind == "hunk":
            self.update(Text(dl.content, style=f"dim {ColorPalette.SECONDARY}"))
            return

        # Números de línea (4 chars cada uno)
        old_str = f"{dl.old_lineno:>4}" if dl.old_lineno is not None else "    "
        new_str = f"{dl.new_lineno:>4}" if dl.new_lineno is not None else "    "

        if dl.kind == "add":
            sym = "+"
            sym_style = f"bold {ColorPalette.SUCCESS}"
            bg = "on #1a3a1a"   # verde oscuro
            txt_style = f"#b9f0b9 {bg}"
            ln_style  = f"dim {ColorPalette.SUCCESS}"
        elif dl.kind == "del":
            sym = "-"
            sym_style = f"bold {ColorPalette.ERROR}"
            bg = "on #3a1a1a"   # rojo oscuro
            txt_style = f"#f0b9b9 {bg}"
            ln_style  = f"dim {ColorPalette.ERROR}"
        else:
            sym = " "
            sym_style = "dim"
            txt_style = f"dim {ColorPalette.TEXT_SECONDARY}"
            ln_style  = "dim #4b5563"

        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(old_str, style=ln_style)
        t.append(" ")
        t.append(new_str, style=ln_style)
        t.append(f" {sym} ", style=sym_style)
        t.append(dl.content, style=txt_style)

        self.update(t)


# ─── Modal principal ──────────────────────────────────────────────────────────

class CommandApprovalModal(ModalScreen[bool]):
    """
    Modal de aprobación de comandos/cambios.

    - Si se provee *diff_content*, muestra el diff coloreado junto con el header del archivo.
    - Si no hay diff, muestra el *message* en texto plano.

    Teclas:
        s / y / enter  → aprobar
        n / escape     → rechazar
    """

    CSS = """
    CommandApprovalModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.80);
    }

    /* ── Contenedor principal ── */
    #modal-shell {
        width: 90%;
        max-width: 110;
        height: auto;
        max-height: 85%;
        background: #111827;
        border: solid #374151;
    }

    /* ── Header con título ── */
    #modal-header {
        width: 100%;
        height: 2;
        background: #1f2937;
        padding: 0 2;
        border-bottom: solid #374151;
        content-align: left middle;
    }
    #modal-title {
        width: 1fr;
        text-style: bold;
        color: #f9fafb;
    }
    #modal-cost {
        color: #9ca3af;
        content-align: right middle;
    }

    /* ── Subheader "Edit <archivo>" ── */
    #modal-file-header {
        width: 100%;
        height: 1;
        background: #1a2332;
        padding: 0 2;
        color: #9ca3af;
        border-bottom: solid #1e3a5f;
    }

    /* ── Área de diff scrollable ── */
    #diff-scroll {
        width: 100%;
        height: auto;
        max-height: 35;
        background: #0d1117;
        border-bottom: solid #374151;
    }
    #diff-container {
        width: 100%;
        height: auto;
        padding: 0;
        background: #0d1117;
    }

    /* ── Mensaje de texto simple (sin diff) ── */
    #message-body {
        width: 100%;
        height: auto;
        padding: 1 2;
        background: #111827;
        border-bottom: solid #374151;
    }
    #message-label {
        width: 100%;
        color: #e5e7eb;
    }

    /* ── Barra de estado inferior ("Build ...") ── */
    #modal-status-bar {
        width: 100%;
        height: 1;
        background: #1f2937;
        padding: 0 2;
        color: #6b7280;
        border-bottom: solid #374151;
    }

    /* ── Footer con botones / atajos ── */
    #modal-footer {
        width: 100%;
        height: 2;
        background: #1f2937;
        padding: 0 2;
        align: left middle;
        layout: horizontal;
    }
    #footer-hint {
        width: 1fr;
        color: #6b7280;
        content-align: left middle;
    }
    #btn-yes {
        min-width: 10;
        margin: 0 1;
        height: 3;
        min-height: 3;
    }
    #btn-no {
        min-width: 10;
        margin: 0 1;
        height: 3;
        min-height: 3;
    }
    """

    def __init__(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.message = message
        self.title_text = title
        self.diff_content = diff_content
        self.file_path = file_path

    # ── Composición ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        has_diff = bool(self.diff_content and self.diff_content.strip())
        short_file = self.file_path.split("/")[-1] if self.file_path else ""

        with Vertical(id="modal-shell"):
            # Header principal
            with Horizontal(id="modal-header"):
                yield Label(f"⚠  {self.title_text}", id="modal-title", markup=True)
                if has_diff and self.file_path:
                    yield Label(
                        f"{self._count_diff_stats(self.diff_content)}",
                        id="modal-cost",
                        markup=False,
                    )

            # Subheader "← Edit archivo.ext"
            if has_diff and self.file_path:
                yield Label(
                    f"← Edit {self.file_path}",
                    id="modal-file-header",
                    markup=False,
                )

            # Área de contenido
            if has_diff:
                # Diff coloreado
                with ScrollableContainer(id="diff-scroll"):
                    with Vertical(id="diff-container"):
                        parsed = _parse_unified_diff(self.diff_content)
                        for dl in parsed:
                            yield _DiffLineWidget(dl)
            else:
                # Mensaje plano
                with Vertical(id="message-body"):
                    yield Label(self.message, id="message-label", markup=False)

            # Barra de estado estilo Kilo
            yield Label(
                "esc  interrumpir   tab  agentes   ctrl+p  comandos",
                id="modal-status-bar",
                markup=False,
            )

            # Footer con atajos y botones
            with Horizontal(id="modal-footer"):
                yield Label("s  aprobar   n  rechazar", id="footer-hint", markup=False)
                yield Button("Sí  [s]", id="btn-yes", variant="success")
                yield Button("No  [n]", id="btn-no", variant="error")

    # ── Eventos ──────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        elif event.button.id == "btn-no":
            self.dismiss(False)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("s", "y", "enter"):
            self.dismiss(True)
        elif event.key in ("n", "escape"):
            self.dismiss(False)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _count_diff_stats(diff_string: str) -> str:
        """Devuelve una cadena con el conteo de líneas añadidas y eliminadas."""
        added = sum(
            1 for l in diff_string.splitlines()
            if l.startswith("+") and not l.startswith("+++")
        )
        deleted = sum(
            1 for l in diff_string.splitlines()
            if l.startswith("-") and not l.startswith("---")
        )
        parts = []
        if added:
            parts.append(f"+{added}")
        if deleted:
            parts.append(f"-{deleted}")
        return "  ".join(parts)
