import logging
import threading
from textual.widgets import Static
from textual.containers import VerticalScroll, Horizontal
from kogniterm.terminal.themes import ColorPalette

logger = logging.getLogger(__name__)

from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.align import Align
from rich.markdown import Markdown
from rich.console import Group
from rich import box

from .tool_output import ToolOutputWidget


def _is_empty_renderable(r) -> bool:
    """Detecta si un renderable de Rich no contiene contenido visible."""
    if r is None:
        return True
    if isinstance(r, str):
        return not r.strip()
    if isinstance(r, Text):
        return not r.plain.strip()
    if isinstance(r, Padding):
        return _is_empty_renderable(r.renderable)
    if isinstance(r, Group):
        return all(_is_empty_renderable(child) for child in r.renderables)
    return False


def _should_call_from_thread(widget) -> bool:
    """Determina si se debe usar call_from_thread según el hilo actual."""
    try:
        app = widget.app
    except Exception:
        return False
    if app is None or not getattr(app, "call_from_thread", None):
        return False
    app_thread_id = getattr(app, "_thread_id", None)
    if app_thread_id is None:
        return False
    return threading.get_ident() != app_thread_id


class MessageWidget(Static):
    """Widget para representar un mensaje individual en el chat."""
    def __init__(self, renderable, **kwargs):
        super().__init__(renderable, **kwargs)
        self.can_focus = False
        self._raw_renderable = renderable

    def update(self, renderable) -> None:
        self._raw_renderable = renderable
        super().update(renderable)

class AnimatedSpinnerWidget(Static):
    """Widget que representa un spinner animado en el chat log."""
    def __init__(self, text: str = "Procesando", **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_idx = 0
        self.can_focus = False

    def on_mount(self) -> None:
        self.set_interval(0.1, self.tick)

    def tick(self) -> None:
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        frame = self.frames[self.frame_idx]
        from rich.text import Text
        self.update(Text(f" {frame} {self.text}", style="bold cyan"))


def _reasoning_summary(text: str) -> tuple:
    """Replica opencode `reasoningSummary`: separa `**Titulo**\\n\\nbody`.

    OpenCode usa ese primer bloque en negrita como metadata del header
    para estilarlo independiente del cuerpo markdown.
    """
    import re as _re
    content = (text or "").strip()
    m = _re.match(r"^\*\*([^*\n]+)\*\*(?:\r?\n\r?\n|$)", content)
    if not m:
        return None, content
    title = m.group(1).strip()
    return title, content[m.end():].rstrip()


def _extract_thinking_text(r) -> str:
    """Desenvuelve Panel/Padding/Group hasta obtener el markdown en texto plano.

    Los agentes emiten `Panel(Markdown(thinking_text), title="💭 Pensando...")`
    (ver super_agent.py). Para el modo colapsado necesitamos el str,
    no el renderable expandido.
    """
    from rich.panel import Panel
    from rich.padding import Padding
    from rich.console import Group
    from rich.markdown import Markdown as RichMarkdown
    seen = 0
    while r is not None and seen < 8:
        seen += 1
        if isinstance(r, str):
            return r
        if isinstance(r, Text):
            return r.plain
        if isinstance(r, RichMarkdown):
            return r.markup or ""
        if isinstance(r, Panel):
            r = r.renderable
            continue
        if isinstance(r, Padding):
            r = r.renderable
            continue
        if isinstance(r, Group):
            parts = [_extract_thinking_text(sub) for sub in r.renderables]
            return "\n".join(p for p in parts if p)
        return str(r)
    return ""


class ThinkingWidget(Static):
    """Pensamiento del LLM colapsado por defecto, estilo OpenCode.

    Patrón tomado de `ReasoningPart` en
    `packages/tui/src/routes/session/index.tsx` (sst/opencode):
    - `thinking_mode` por defecto `hide` (colapsado): una sola línea,
      el layout nunca salta. Click para abrir el bloque markdown completo.
    - Header siempre visible: spinner `Thinking...` en streaming,
      `Thought` (+ título/duración) al finalizar.
    - Cuerpo solo renderizado/visible cuando se expande.

    Implementado con Textual `Collapsible` (collapsed=True) + `Markdown`
    interno actualizable en streaming. Click/Enter lo despliega (toggle
    nativo de Collapsible), igual que `onMouseUp={toggle}` en OpenCode.
    """

    DEFAULT_CSS = """
    ThinkingWidget {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        padding: 0 0 0 2;
        color: #9ca3af;
        background: transparent;
        border: none;
    }
    ThinkingWidget Collapsible {
        width: 100%;
        height: auto;
        color: #9ca3af;
        background: transparent;
        border: none;
    }
    ThinkingWidget Markdown {
        background: transparent;
        border: none;
        color: #9ca3af;
    }
    ThinkingWidget #thinking-body {
        width: 100%;
        height: auto;
        padding: 0 0 0 2;
        color: #9ca3af;
        background: transparent;
        border: none;
    }
    """

    _DOTS = [".", "..", "..."]

    def __init__(self, body: str = "", **kwargs):
        from textual.widgets import Collapsible, Markdown as MdWidget
        import time as _time
        self._body_text: str = body or ""
        self._started_at: float = _time.monotonic()
        self._is_done: bool = False
        self._title_text: str = ""
        self._dot_idx: int = 2
        self._dot_timer = None
        self._inner = MdWidget(self._body_text or "…")
        try:
            self._inner.styles.background = "transparent"
        except Exception:
            pass
        title = self._build_title()
        super().__init__(**kwargs)
        try:
            self.styles.background = "transparent"
        except Exception:
            pass
        self._collapsible = Collapsible(
            self._inner,
            title=title,
            collapsed=True,
            collapsed_symbol="▶",
            expanded_symbol="▼",
        )

    def compose(self):
        yield self._collapsible

    def on_mount(self) -> None:
        try:
            self._dot_timer = self.set_interval(0.4, self._tick_dots)
        except Exception:
            pass

    def on_unmount(self) -> None:
        try:
            if self._dot_timer is not None:
                self._dot_timer.stop()
        except Exception:
            pass

    def _tick_dots(self) -> None:
        if self._is_done:
            try:
                if self._dot_timer is not None:
                    self._dot_timer.stop()
            except Exception:
                pass
            return
        self._dot_idx = (self._dot_idx + 1) % len(self._DOTS)
        self._refresh_title()

    def _dots(self) -> str:
        try:
            return self._DOTS[self._dot_idx % len(self._DOTS)]
        except Exception:
            return "..."

    def _build_title(self) -> str:
        summary_title, _ = _reasoning_summary(self._body_text)
        if not self._is_done:
            base = f"💭 Thinking{self._dots()}"
            if summary_title:
                base = f"💭 Thinking: {summary_title}{self._dots()}"
            return base
        import time as _time
        elapsed = max(0.0, _time.monotonic() - self._started_at)
        dur = f" · {elapsed:.1f}s" if elapsed >= 0.5 else ""
        if summary_title:
            return f"💭 Thought: {summary_title}{dur}"
        return f"💭 Thought{dur}"

    def _refresh_title(self) -> None:
        try:
            self._collapsible.title = self._build_title()
        except Exception:
            pass

    def update_thinking(self, new_body: str, is_done: bool = False) -> None:
        """Actualiza el cuerpo markdown manteniendo colapsado (como OpenCode)."""
        self._body_text = new_body or ""
        try:
            self._inner.update(self._body_text or "…")
        except Exception:
            pass
        if is_done:
            self.finalize()
        else:
            self._refresh_title()

    def finalize(self) -> None:
        """Congela el header a `Thought` y fuerza colapsado."""
        self._is_done = True
        try:
            if self._dot_timer is not None:
                self._dot_timer.stop()
        except Exception:
            pass
        try:
            self._inner.update(self._body_text or "…")
        except Exception:
            pass
        try:
            self._collapsible.collapsed = True
        except Exception:
            pass
        self._refresh_title()

    @property
    def body_text(self) -> str:
        return self._body_text

class ChatLogWidget(VerticalScroll):
    """
    Widget para mostrar el historial del chat usando un contenedor vertical
    que permite modificar mensajes en tiempo real (streaming).
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_message_widget = None
        self._active_thinking_widget = None
        self._last_tracker_widget = None
        self.can_focus = True

    def _get_available_width(self):
        """Calcula el ancho disponible real dentro del widget."""
        try:
            w = self.size.width
            if w > 0:
                return max(w - 4, 40) # Margen para scrollbar y bordes
            
            # Fallback a dimensiones de la aplicación
            if hasattr(self, "app") and self.app.size.width > 0:
                # El chat log suele ocupar el 94% del ancho de la app
                return max(int(self.app.size.width * 0.94) - 4, 40)
                
            return 78
        except:
            return 78

    def _finalize_thinking(self):
        """Congela el thinking activo a 'Thought' colapsado sin eliminarlo."""
        w = self._active_thinking_widget
        if isinstance(w, ThinkingWidget):
            try:
                w.finalize()
            except Exception:
                pass

    def write(self, renderable):
        """Redirige a write_message para compatibilidad con RichLog."""
        return self.write_message(renderable)

    def write_message(self, renderable, style=None):
        """Escribe un elemento Rich al log."""
        if style and isinstance(renderable, str):
            renderable = Text(renderable, style=style)

        # Si es un simple string, lo envolvemos para padding
        if isinstance(renderable, str):
             renderable = Text(renderable)

        # Centrar el mensaje envolviéndolo en Align.center
        renderable = Align.center(renderable)

        def _mount_msg(r):
            try:
                widget = MessageWidget(Padding(r, (1, 0)))
                self.mount(widget)
                self.scroll_end(animate=False)
                return widget
            except Exception as e:
                logger.warning("ChatLogWidget.write_message: _mount_msg falló: %s", e)
                return None

        if _should_call_from_thread(self):
            try:
                self.app.call_from_thread(_mount_msg, renderable)
                return None
            except Exception as e:
                logger.warning("ChatLogWidget.write_message: call_from_thread falló, intentando mount directo: %s", e)

        return _mount_msg(renderable)

    def write_user_message(self, text: str):
        """Escribe un mensaje de usuario con línea vertical izquierda."""
        self._finalize_thinking()
        self._last_tracker_widget = None
        self._active_thinking_widget = None
        if self._active_message_widget:
            if isinstance(self._active_message_widget, AnimatedSpinnerWidget) or (
                isinstance(self._active_message_widget, MessageWidget)
                and _is_empty_renderable(getattr(self._active_message_widget, "_raw_renderable", None))
            ):
                try:
                    self._active_message_widget.remove()
                except Exception:
                    pass
            self._active_message_widget = None
        from rich.text import Text
        from rich.console import Console, Group
        
        text_color = ColorPalette.TEXT_PRIMARY
        pipe_color = ColorPalette.PRIMARY

        available_width = self._get_available_width()
        console = Console(width=available_width)

        input_lines = text.split('\n')
        wrapped_text_lines = []
        
        for input_line in input_lines:
            if not input_line.strip() and not input_line:
                wrapped_text_lines.append(Text(""))
                continue

            try:
                if "[" in input_line and "]" in input_line:
                    t = Text.from_markup(input_line, style=text_color)
                else:
                    t = Text(input_line, style=text_color)
            except Exception:
                t = Text(input_line, style=text_color)

            wrapped_sublines = list(t.wrap(console, available_width - 5)) # 5 = 0 margin + 1 pipe + 2 padding left + 2 padding right
            if not wrapped_sublines:
                wrapped_text_lines.append(Text(""))
            else:
                for subline in wrapped_sublines:
                    wrapped_text_lines.append(subline)

        def _mount_user_message():
            try:
                # Creamos el texto de los pipes para que coincida con el número de líneas + padding (1 arriba, 1 abajo)
                pipes_text = Text("\n".join(["┃"] * (len(wrapped_text_lines) + 2)), style=pipe_color)
                left = Static(pipes_text)
                left.styles.width = 1
                left.styles.height = "auto"
                left.styles.background = ColorPalette.GRAY_800 # El pipe ahora tiene el mismo fondo que el mensaje

                # El panel derecho con el texto y su fondo
                right = Static(Group(*wrapped_text_lines))
                right.styles.flex = 1
                right.styles.height = "auto"
                right.styles.background = ColorPalette.GRAY_800
                right.styles.padding = (1, 2) # Margen interno (padding) añadido

                row = Horizontal(left, right, classes="user-message-row")
                row.styles.height = "auto"
                row.styles.margin = (0, 0, 1, 0) # Eliminado el margen izquierdo para que esté al borde
                
                self.mount(row)
                self._active_message_widget = None
                self.scroll_end(animate=False)
            except Exception as e:
                import logging
                logging.error(f"Error mounting user message: {e}")
                pass

        if _should_call_from_thread(self):
            try:
                self.app.call_from_thread(_mount_user_message)
                return
            except Exception:
                pass

        _mount_user_message()

    def write_agent_message(self, text: str):
        """Escribe un mensaje de agente."""
        self._finalize_thinking()
        if text is None: text = ""
        
        if not isinstance(text, str):
            import json
            try: text = json.dumps(text, indent=2)
            except: text = str(text)
        
        markdown_content = Markdown(text)

        def _mount_agent(md):
            try:
                widget = MessageWidget(Padding(md, (1, 0, 1, 2)))
                self.mount(widget)
                self.scroll_end(animate=False)
            except Exception:
                try:
                    # Fallback simple
                    widget = MessageWidget(Padding(md, (1, 0)))
                    self.mount(widget)
                    self.scroll_end(animate=False)
                except Exception:
                    pass

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_agent, markdown_content)
                return
        except Exception:
            pass

        _mount_agent(markdown_content)
    def write_stream(self, content):
        """
        Escribe contenido de streaming al log. 
        Si hay un mensaje activo, lo actualiza. Si no, crea uno nuevo.
        """
        if not content:
            return
            
        renderable = content
        is_terminal = False
        is_spinner = False
        tool_name = "Terminal"
        
        # Detectar si recibimos la tupla especial de spinner especial ("__SPINNER__", text)
        if isinstance(content, tuple) and len(content) == 2 and content[0] == "__SPINNER__":
            is_spinner = True
            renderable = content[1]
            terminal_command = ""
        # Detectar si recibimos la tupla especial ("__TERMINAL__", tool_name, output) o ("__TERMINAL__", tool_name, output, command)
        elif isinstance(content, tuple) and len(content) >= 3 and content[0] == "__TERMINAL__":
            is_terminal = True
            tool_name = content[1]
            renderable = content[2]
            terminal_command = content[3] if len(content) >= 4 else tool_name
        else:
            # Detectar si es un panel de terminal (vía tui_app.update_terminal_output fallback)
            # El renderable puede venir envuelto en Padding o Group desde visual_components
            def _check_is_terminal(r):
                from rich.panel import Panel
                from rich.padding import Padding
                from rich.console import Group
                
                def _title_matches(t_str):
                    t = str(t_str or "").lower()
                    # Paneles de diff/edición de archivo NUNCA son salidas de terminal
                    if any(kw in t for kw in ["diff", "cambios aplicados", "diff aplicado"]):
                        return False
                    # Coincidencia explícita con títulos de terminales
                    if t.startswith("terminal") or "terminal |" in t or "terminal —" in t:
                        return True
                    return False

                if isinstance(r, Panel):
                    title = str(r.title or "")
                    if _title_matches(title):
                        return True, title.replace("TERMINAL | ", "")
                    # Si es un Panel estilizado de Rich (incluyendo diffs), NO es terminal
                    return False, "Terminal"
                
                if isinstance(r, Padding):
                    return _check_is_terminal(r.renderable)
                    
                if isinstance(r, Group):
                    for sub_r in r.renderables:
                        if isinstance(sub_r, Panel):
                            title = str(sub_r.title or "")
                            if _title_matches(title):
                                return True, "bash"
                        found, name = _check_is_terminal(sub_r)
                        if found: return True, name
                
                return False, "Terminal"

            is_terminal, tool_name = _check_is_terminal(content)
            
            if isinstance(content, str):
                if "\x1b" in content or "┃" in content or "╭" in content:
                    from rich.text import Text
                    renderable = Padding(Text.from_ansi(content), (1, 0, 1, 2))
                else:
                    from rich.markdown import Markdown
                    renderable = Padding(Markdown(content), (1, 0, 1, 2))
            else:
                renderable = content
            terminal_command = tool_name  # para el caso no-terminal, coincide con tool_name

        def _check_is_thinking(r):
            from rich.panel import Panel
            from rich.padding import Padding
            from rich.console import Group

            if isinstance(r, Panel):
                title = str(r.title or "").lower()
                if "pensando" in title or "thinking" in title:
                    return True

            if isinstance(r, Padding):
                return _check_is_thinking(r.renderable)

            if isinstance(r, Group):
                for sub_r in r.renderables:
                    if _check_is_thinking(sub_r):
                        return True

            return False

        def _mount_or_update(r, terminal_flag, spinner_flag, t_name, t_command=""):
            try:
                is_new_widget = False
                try:
                    was_at_bottom = self.scroll_y >= self.max_scroll_y - 1
                except Exception:
                    was_at_bottom = True
                is_thinking = _check_is_thinking(r)
                thinking_body = _extract_thinking_text(r) if is_thinking else ""

                if not is_thinking:
                    # Finalizar el pensamiento activo (estilo OpenCode: pasa de
                    # "Thinking..." a "Thought" colapsado) antes de soltarlo.
                    if self._active_thinking_widget is not None:
                        try:
                            if isinstance(self._active_thinking_widget, ThinkingWidget):
                                self._active_thinking_widget.finalize()
                        except Exception:
                            pass
                        self._active_thinking_widget = None
                        self._active_message_widget = None

                if is_thinking:
                    # Patrón OpenCode ReasoningPart: colapsado por defecto,
                    # una sola línea durante todo el streaming; click -> expandir.
                    active = self._active_thinking_widget
                    if isinstance(active, ThinkingWidget):
                        try:
                            active.update_thinking(thinking_body, is_done=False)
                        except Exception:
                            pass
                    else:
                        # Limpiar spinner vacío si lo hubiera antes del thinking
                        if self._active_message_widget is not None and isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                            try:
                                self._active_message_widget.remove()
                            except Exception:
                                pass
                        new_widget = ThinkingWidget(thinking_body)
                        self._active_thinking_widget = new_widget
                        self._active_message_widget = new_widget
                        try:
                            self.mount(new_widget)
                        except Exception:
                            pass
                        is_new_widget = True
                elif spinner_flag:
                    if self._active_message_widget is None or not isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                        if self._active_message_widget:
                            if isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                                self._active_message_widget.remove()
                            else:
                                self._active_message_widget = None
                        self._active_message_widget = AnimatedSpinnerWidget(r)
                        self.mount(self._active_message_widget)
                        is_new_widget = True
                    else:
                        if self._active_message_widget.text != r:
                            self._active_message_widget.text = r
                # Si es terminal, forzar el uso de ToolOutputWidget para interactividad y persistencia
                elif terminal_flag:
                    is_same_terminal = (
                        isinstance(self._active_message_widget, ToolOutputWidget)
                        and getattr(self._active_message_widget, "command", "") == t_command
                        and getattr(self._active_message_widget, "tool_name", "") == t_name
                    )
                    if not is_same_terminal:
                        if self._active_message_widget:
                            if isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                                self._active_message_widget.remove()
                            elif isinstance(self._active_message_widget, MessageWidget) and _is_empty_renderable(getattr(self._active_message_widget, "_raw_renderable", None)):
                                self._active_message_widget.remove()
                            else:
                                self._active_message_widget = None
                        
                        self._active_message_widget = ToolOutputWidget("", t_name, command=t_command)
                        self.mount(self._active_message_widget)
                        is_new_widget = True
                    
                    # ToolOutputWidget.update_content maneja la lógica de pyte
                    self._active_message_widget.update_content(r, command=t_command)
                else:
                    if self._active_message_widget is None or not isinstance(self._active_message_widget, MessageWidget):
                        if self._active_message_widget:
                            if isinstance(self._active_message_widget, AnimatedSpinnerWidget):
                                self._active_message_widget.remove()
                            else:
                                self._active_message_widget = None
                        new_widget = MessageWidget(r)
                        self._active_message_widget = new_widget
                        self.mount(new_widget)
                        is_new_widget = True
                    else:
                        self._active_message_widget.update(r)
                
                if is_new_widget or was_at_bottom:
                    self.scroll_end(animate=False)
            except Exception as e:
                import logging
                logging.exception("ChatLogWidget: Error in _mount_or_update for %s: %s", self.id, e)

        if _should_call_from_thread(self):
            try:
                self.app.call_from_thread(_mount_or_update, renderable, is_terminal, is_spinner, tool_name, terminal_command)
                return
            except Exception as e:
                import logging
                logging.exception("ChatLogWidget: Error calling call_from_thread in write_stream: %s", e)

        _mount_or_update(renderable, is_terminal, is_spinner, tool_name, terminal_command)

    def stop_stream(self):
        """Finaliza el streaming actual y elimina el spinner si estaba activo."""
        # El pensamiento NO se elimina: se finaliza a "Thought" colapsado (OpenCode).
        if isinstance(self._active_thinking_widget, ThinkingWidget):
            try:
                self._active_thinking_widget.finalize()
            except Exception:
                pass
        if self._active_message_widget:
            if isinstance(self._active_message_widget, AnimatedSpinnerWidget) or (
                isinstance(self._active_message_widget, MessageWidget)
                and _is_empty_renderable(getattr(self._active_message_widget, "_raw_renderable", None))
            ):
                try:
                    self._active_message_widget.remove()
                except Exception:
                    pass
        self._active_message_widget = None
        self._active_thinking_widget = None

    def write_tool_notification(self, tool_name: str, action_desc: str = "", skill_name: str = ""):
        """Escribe notificación de herramienta."""
        self._finalize_thinking()
        if self._active_message_widget:
            if isinstance(self._active_message_widget, AnimatedSpinnerWidget) or (
                isinstance(self._active_message_widget, MessageWidget)
                and _is_empty_renderable(getattr(self._active_message_widget, "_raw_renderable", None))
            ):
                try:
                    self._active_message_widget.remove()
                except Exception:
                    pass
        self._active_thinking_widget = None
        self._active_message_widget = None
        from rich.text import Text
        from kogniterm.terminal.themes import (
            ColorPalette,
            Icons,
            is_light_theme,
        )

        line1 = Text()
        line1.append(f"{Icons.TOOL} ", style=f"bold {ColorPalette.SECONDARY}")
        line1.append(tool_name, style=f"bold {ColorPalette.SECONDARY_LIGHT}")

        lines = [line1]
        if action_desc:
            line2 = Text()
            # Consciente del tema: `dim` sobre fondo claro queda casi invisible
            arrow_style = (
                ColorPalette.TEXT_MUTED
                if is_light_theme()
                else f"dim {ColorPalette.GRAY_600}"
            )
            line2.append("   ↳ ", style=arrow_style)
            line2.append("Acción: ", style=f"bold italic {ColorPalette.TEXT_SECONDARY}")
            line2.append(action_desc, style=f"italic {ColorPalette.TEXT_SECONDARY}")
            lines.append(line2)
        
        def _mount_tool_notify(lines_group):
            try:
                widget = MessageWidget(Padding(lines_group, (1, 0, 1, 2)))
                self.mount(widget)
                self.scroll_end(animate=False)
            except Exception:
                pass

        if _should_call_from_thread(self):
            try:
                self.app.call_from_thread(_mount_tool_notify, Group(*lines))
                return
            except Exception:
                pass

        _mount_tool_notify(Group(*lines))

    def write_tool_output(self, content: str, tool_name: str, language: str = None):
        """Escribe la salida de una herramienta usando el ToolOutputWidget."""
        self._finalize_thinking()
        if self._active_message_widget:
            if isinstance(self._active_message_widget, AnimatedSpinnerWidget) or (
                isinstance(self._active_message_widget, MessageWidget)
                and _is_empty_renderable(getattr(self._active_message_widget, "_raw_renderable", None))
            ):
                try:
                    self._active_message_widget.remove()
                except Exception:
                    pass
        self._active_thinking_widget = None
        self._active_message_widget = None
        def _mount_tool_output(c, tname, lang):
            try:
                widget = ToolOutputWidget(c, tname, language=lang)
                self.mount(widget)
                self.scroll_end(animate=False)
                return widget
            except Exception:
                return None

        if _should_call_from_thread(self):
            try:
                self.app.call_from_thread(_mount_tool_output, content, tool_name, language)
                return None
            except Exception:
                pass

        return _mount_tool_output(content, tool_name, language)

    def write_task_tracker(self, panel):
        """Escribe o actualiza el panel de seguimiento de tareas en el chat log."""
        def _mount_or_update():
            try:
                is_new = not (hasattr(self, "_last_tracker_widget") and self._last_tracker_widget and self._last_tracker_widget.parent)
                was_at_bottom = self.scroll_y >= self.max_scroll_y - 1

                if not is_new:
                    # Centrar el mensaje envolviéndolo en Align.center
                    self._last_tracker_widget.update(Padding(Align.center(panel), (1, 0)))
                else:
                    widget = MessageWidget(Padding(Align.center(panel), (1, 0)))
                    self._last_tracker_widget = widget
                    self.mount(widget)
                
                if is_new or was_at_bottom:
                    self.scroll_end(animate=False)
            except Exception as e:
                logger.warning("ChatLogWidget.write_task_tracker: _mount_or_update falló: %s", e)

        try:
            if hasattr(self, "app") and getattr(self.app, "call_from_thread", None):
                self.app.call_from_thread(_mount_or_update)
                return
        except Exception as e:
            logger.warning("ChatLogWidget.write_task_tracker: call_from_thread falló: %s", e)

        _mount_or_update()

    def clear(self):
        """Limpia el chat log."""
        # En VerticalScroll, para limpiar eliminamos los hijos
        for child in list(self.children):
            child.remove()
        self._active_message_widget = None
        self._active_thinking_widget = None
        self._last_tracker_widget = None
