"""
Widget de tareas para KogniTerm: panel replegable anclado sobre el input.

Comportamiento:
- Replegado (por defecto): una sola línea indicadora con el progreso
  global (p.ej. "▸ ☰ Tareas 1/3 · 🔄 <tarea actual>"). Ocupa 1 línea
  sobre el input y no invade el flujo del chat.
- Desplegado: muestra el detalle por agente con estados
  (⏳ pendiente / 🔄 en curso / ✅ hecha). Al presionar el indicador
  (click o Enter/Espacio con foco, o la acción `toggle-task-tracker`
  / Ctrl+K de la app) se alterna entre ambos estados.

La API pública se mantiene compatible con el widget anterior:
`update_tasks(agent_plans)`, `tasks_data`, `display` y `panel_title`.
"""
from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import events
from textual.reactive import reactive
from textual.widgets import Static

from kogniterm.terminal.themes import ColorPalette


class TaskTrackerPanelWidget(Static):
    """Panel replegable de tareas anclado sobre el input."""

    tasks_data = reactive({})
    expanded = reactive(False)

    def __init__(self, panel_title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.tasks_data = {}
        self.panel_title = panel_title
        self.display = False  # Oculto hasta que haya tareas visibles
        self.expanded = False  # Replegado por defecto
        self.can_focus = True

    # ── API pública ──────────────────────────────────────────────
    def watch_tasks_data(self, new_value):
        """Reacciona al cambio en los datos de tareas."""
        self.update_display()

    def watch_expanded(self, new_value):
        """Re-renderiza al plegar/desplegar."""
        self.update_display()

    def update_tasks(self, agent_plans: dict):
        """Actualiza el panel con los datos de las tareas."""
        self.tasks_data = agent_plans or {}
        self.update_display()

    def toggle(self):
        """Alterna entre vista replegada y desplegada."""
        if not self._visible_tasks():
            return
        self.expanded = not self.expanded

    def expand(self):
        if self._visible_tasks():
            self.expanded = True

    def collapse(self):
        self.expanded = False

    @property
    def is_expanded(self) -> bool:
        return bool(self.expanded)

    # ── Interacción: click o Enter/Espacio ───────────────────────
    async def on_click(self, event: events.Click) -> None:
        self.toggle()
        event.stop()

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("enter", "space"):
            self.toggle()
            event.prevent_default()
            event.stop()

    # ── Cómputo ──────────────────────────────────────────────────
    def _visible_tasks(self) -> dict:
        """Filtra agentes sin tareas o con todo en 'done'."""
        visible = {}
        for agent_name, tasks in (self.tasks_data or {}).items():
            if not tasks:
                continue
            pending = [t for t in tasks if t.get("status") != "done"]
            if pending:
                visible[agent_name] = tasks
        return visible

    def get_summary(self) -> dict:
        """Resumen {total, done, pending, in_progress, current} para tests/footer."""
        total = done = 0
        current = ""
        for tasks in (self.tasks_data or {}).values():
            for task in tasks or []:
                total += 1
                if task.get("status") == "done":
                    done += 1
                elif task.get("status") == "in-progress" and not current:
                    current = task.get("task", "")
        if not current:
            for tasks in (self.tasks_data or {}).values():
                for task in tasks or []:
                    if task.get("status") != "done":
                        current = task.get("task", "")
                        break
                if current:
                    break
        return {
            "total": total,
            "done": done,
            "pending": total - done,
            "current": current,
        }

    def _summary_line(self) -> Text:
        s = self.get_summary()
        if s["total"] and s["done"] >= s["total"]:
            icon, label = "✅", "Tareas completadas"
        elif any(
            t.get("status") == "in-progress"
            for tasks in (self.tasks_data or {}).values()
            for t in (tasks or [])
        ):
            icon, label = "🔄", "Tareas"
        else:
            icon, label = "⏳", "Tareas"
        arrow = "▾" if self.expanded else "▸"
        text = Text()
        text.append(f"{arrow} ☰ {label} {s['done']}/{s['total']}", style=f"bold {ColorPalette.SECONDARY}")
        if s["current"] and not self.expanded:
            short = s["current"] if len(s["current"]) <= 60 else s["current"][:57] + "…"
            text.append(f"  ·  {icon} {short}", style=ColorPalette.TEXT_MUTED)
        text.append("  (click o Enter para desplegar)" if not self.expanded else "  (click para replegar)", style="dim")
        return text

    # ── Render ───────────────────────────────────────────────────
    def update_display(self):
        """Renderiza según haya tareas y el estado plegado/desplegado."""
        visible = self._visible_tasks()
        if not visible:
            self.display = False
            try:
                self.update("")
            except Exception:
                pass
            return

        self.display = True
        if not self.expanded:
            try:
                self.update(self._summary_line())
            except Exception:
                pass
            return

        blocks = [self._summary_line()]
        for agent_name, tasks in visible.items():
            header = Text.from_markup(
                f"[bold {ColorPalette.SECONDARY}]● {self.panel_title or agent_name}[/bold {ColorPalette.SECONDARY}]"
            )
            table = Table(
                expand=True,
                box=None,
                show_header=False,
                padding=(0, 1),
                title=None,
            )
            table.add_column("Status")
            table.add_column("Task")

            for task in tasks:
                status = task.get("status", "pending")
                task_text = task.get("task", "")

                if status == "done":
                    style = "strike #525252"
                    status_icon = "✅"
                elif status == "in-progress":
                    style = "bold cyan"
                    status_icon = "🔄"
                else:
                    style = ColorPalette.TEXT_PRIMARY
                    status_icon = "⏳"

                table.add_row(status_icon, f"[{style}]{task_text}[/]")

            blocks.append(Group(header, table))

        try:
            self.update(Group(*blocks))
        except Exception:
            pass
