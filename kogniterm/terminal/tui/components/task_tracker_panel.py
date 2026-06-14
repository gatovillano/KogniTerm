"""
Widget de panel de tareas para KogniTerm.
Muestra el progreso de las tareas en un panel lateral (sidebar).
"""
from rich.table import Table
from rich.text import Text
from textual.widgets import Static
from textual.reactive import reactive
from kogniterm.terminal.themes import ColorPalette


class TaskTrackerPanelWidget(Static):
    """Panel lateral que muestra el estado de las tareas."""
    
    # Reativo para actualizar cuando cambian las tareas
    tasks_data = reactive({})
    
    def __init__(self, panel_title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.tasks_data = {}
        self.panel_title = panel_title
        self.display = False  # Oculto por defecto hasta que hay tareas
        self.can_focus = False
        
    def watch_tasks_data(self, new_value):
        """Reacciona al cambio en los datos de tareas."""
        self.update_display()
        
    def update_tasks(self, agent_plans: dict):
        """Actualiza el panel con los datos de las tareas."""
        self.tasks_data = agent_plans
        self.update_display()
        
    def update_display(self):
        """Renderiza el panel con los datos actuales."""
        if not self.tasks_data:
            self.update("No hay tareas")
            self.display = False
            return
            
        from rich.console import Group
        
        # Crear una tabla por agente sin bordes internos
        blocks = []
        for agent_name, tasks in self.tasks_data.items():
            # Si todas las tareas del agente están completadas ("done") o no hay tareas,
            # su plan completo desaparece del panel.
            if not tasks or all(task.get("status") == "done" for task in tasks):
                continue
                
            header = Text.from_markup(
                f"[bold {ColorPalette.SECONDARY}]● {self.panel_title or agent_name}[/bold {ColorPalette.SECONDARY}]"
            )
            table = Table(
                expand=True, 
                box=None, 
                show_header=False, 
                padding=(0, 1),
                title=None
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
                    style = "white"
                    status_icon = "⏳"
                    
                table.add_row(status_icon, f"[{style}]{task_text}[/]")

            blocks.append(Group(header, table))

        if not blocks:
            self.update("No hay tareas")
            self.display = False
        else:
            self.update(Group(*blocks))
            self.display = True