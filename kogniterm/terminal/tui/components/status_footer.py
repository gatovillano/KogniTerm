from textual.app import ComposeResult
from textual.widgets import Static, TextArea
from textual.containers import Horizontal, Vertical
from textual.message import Message
import os
import subprocess
import asyncio
import threading
import fnmatch
from textual import events
from typing import List, Optional

from kogniterm.terminal.message_history import get_message_history

class StatusFooter(Static):
    """
    Muestra información del entorno de trabajo, repo, y modelo en la parte inferior.
    """
    def __init__(self, model_name: str, **kwargs):
        super().__init__(**kwargs)
        self.model_name = model_name
        self._auto_approve_active = False  # Estado de auto-aceptación
        
    def _get_current_dir(self):
        return os.path.basename(os.getcwd())

    def _get_git_branch(self):
        # Obtener el branch actual de git, o indicar si no hay repo
        try:
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return None
            
    def compose(self) -> ComposeResult:
        current_dir = self._get_current_dir()
        branch = self._get_git_branch()
        
        # Mostrar branch si hay repo git, si no solo el directorio
        if branch:
            left_text = f" {branch}  🗂️ {current_dir}"
        else:
            left_text = f"🗂️ {current_dir}"
            
        display_model = self.model_name.split("/")[-1]
        right_text = f"{display_model} 🤖"
        
        yield Static(left_text, id="footer_left", markup=True)
        yield Static("[dim]Ctrl+O:[/dim] Herramientas  [dim]Ctrl+B:[/dim] Tareas", id="footer_middle", markup=True)
        yield Static(right_text, id="footer_right", markup=True)

    def update_model(self, new_model: str):
        """Actualiza el nombre del modelo mostrado en el footer."""
        self.model_name = new_model
        display_model = new_model.split("/")[-1]
        right_text = f"{display_model} 🤖"
        try:
            self.query_one("#footer_right", Static).update(right_text)
        except Exception:
            pass

    def set_auto_approve(self, active: bool):
        """Actualiza el estado de auto-aceptación y refresca el footer."""
        self._auto_approve_active = active
        self._update_auto_approve_indicator()
    
    def _update_auto_approve_indicator(self):
        """Actualiza el indicador visual de auto-aceptación en el footer."""
        try:
            from kogniterm.terminal.themes import ColorPalette
            if self._auto_approve_active:
                indicator = f" [bold {ColorPalette.SUCCESS}]⇥ Auto-aceptación ON[/]"
            else:
                indicator = f" [dim]⇥ Shift+Tab para auto-aceptar[/dim]"
            # Actualizar el footer derecho con el indicador
            footer_right = self.query_one("#footer_right", Static)
            display_model = self.model_name.split("/")[-1]
            footer_right.update(f"{display_model} 🤖{indicator}")
        except Exception:
            pass

class ChatInput(TextArea):
    """
    Entrada de texto del usuario multi-línea con historial persistente.
    """
    class Submitted(Message):
        """Mensaje emitido cuando se envía el contenido."""
        def __init__(self, value: str, input_widget: "ChatInput"):
            super().__init__()
            self.value = value
            self.input = input_widget

    def __init__(self, **kwargs):
        # Permitir id personalizado pero con default
        if "id" not in kwargs:
            kwargs["id"] = "chat_input"
        
        super().__init__(**kwargs)
        
        # Configuración básica de TextArea para que parezca un input
        self.show_line_numbers = False
        self.show_cursor_line = False
        self.cursor_line_style = "" 

        self.styles.background = "transparent"
        self.soft_wrap = True
        self.tab_behavior = "focus"
        # Desactivar explícitamente el scrollbar horizontal si aparece
        self.styles.overflow_x = "hidden"
        self.styles.overflow_y = "hidden"
        
        # Forzar altura inicial y permitir expansión
        self.styles.height = 1
        self.styles.min_height = 1
        self.styles.max_height = 20
        
        # Usar historial persistente compartido
        self._history_manager = get_message_history()
        self._history = self._history_manager.get_history()
        self._history_index = -1
        self._temp_input = ""
        
        # Inicializar suggester para autocompletado de archivos y contenedores
        try:
            from textual.app import App
            # Intentar obtener el workspace si la app lo tiene
            workspace = getattr(self.app, "workspace_directory", None)
            self.suggester = KogniTermSuggester(workspace)
        except Exception:
            self.suggester = KogniTermSuggester()

    def refresh_history(self):
        """Recarga el historial desde el almacenamiento persistente."""
        self._history = self._history_manager.get_history()
        self._history_index = -1

    def add_to_history(self, text: str):
        if text.strip() and (not self._history or self._history[0] != text):
            # Insertar al inicio local
            self._history.insert(0, text.strip())
            # Guardar en almacenamiento persistente
            self._history_manager.add_message(text.strip())
        self._history_index = -1
        self._temp_input = ""

    def on_key(self, event: events.Key):
        # Evitar que el editor procese teclas de navegación/selección si el popup está abierto
        if hasattr(self.app, "command_popup") and self.app.command_popup.display:
            if event.key in ("up", "down", "enter", "escape"):
                # Dejar que burbujee a TUIApp pero evitar comportamiento local (ej: nuevas líneas en TextArea)
                event.prevent_default()
                return

        # Atajos de scroll directo con Ctrl
        if event.key == "ctrl+up":
            if hasattr(self.app, "chat_log"):
                self.app.chat_log.scroll_up(animate=False)
                event.prevent_default()
            return
        elif event.key == "ctrl+down":
            if hasattr(self.app, "chat_log"):
                self.app.chat_log.scroll_down(animate=False)
                event.prevent_default()
            return

        # Manejo de Enter para submit
        if event.key == "enter":
            text = self.text
            if text.strip():
                self.post_message(self.Submitted(text, self))
                event.stop()
                event.prevent_default()
            return

        # Teclas para forzar nueva línea (añadir salto de línea hacia abajo)
        if event.key in ("ctrl+j", "ctrl+enter", "alt+enter", "shift+enter"): 
            self.insert("\n")
            event.stop()
            event.prevent_default()
            return

        if event.key == "up":
            # Navegación de historial solo si estamos en la primera línea
            if self.cursor_location[0] == 0:
                if self._history:
                    if self._history_index >= len(self._history) - 1:
                        if hasattr(self.app, "chat_log"):
                            self.app.chat_log.scroll_up(animate=False)
                            event.prevent_default()
                        return
                    
                    if self._history_index == -1:
                        self._temp_input = self.text
                    
                    self._history_index += 1
                    self.text = self._history[self._history_index]
                    # Mover cursor al final del texto cargado
                    last_line = len(self.document.lines) - 1
                    last_col = len(self.document.lines[last_line])
                    self.cursor_location = (last_line, last_col)
                    event.prevent_default()
                    event.stop()
                else:
                    if hasattr(self.app, "chat_log"):
                        self.app.chat_log.scroll_up(animate=False)
                        event.prevent_default()
            
        elif event.key == "down":
            # Navegación de historial solo si estamos en la última línea
            last_line_idx = len(self.document.lines) - 1
            if self.cursor_location[0] == last_line_idx:
                if self._history_index > 0:
                    self._history_index -= 1
                    self.text = self._history[self._history_index]
                    last_line = len(self.document.lines) - 1
                    last_col = len(self.document.lines[last_line])
                    self.cursor_location = (last_line, last_col)
                    event.prevent_default()
                    event.stop()
                elif self._history_index == 0:
                    self._history_index = -1
                    self.text = self._temp_input
                    last_line = len(self.document.lines) - 1
                    last_col = len(self.document.lines[last_line])
                    self.cursor_location = (last_line, last_col)
                    event.prevent_default()
                    event.stop()
                else:
                    if hasattr(self.app, "chat_log"):
                        self.app.chat_log.scroll_down(animate=False)
                        event.prevent_default()

        elif event.key == "pageup":
            if hasattr(self.app, "chat_log"):
                self.app.chat_log.scroll_page_up(animate=False)
                event.prevent_default()

        elif event.key == "pagedown":
            if hasattr(self.app, "chat_log"):
                self.app.chat_log.scroll_page_down(animate=False)
                event.prevent_default()
        

    def on_mouse_scroll_up(self, event: events.MouseScrollUp):
        # Si el ratón está sobre el input pero ya no puede subir más, subir el chat log
        if self.cursor_location[0] == 0:
            if hasattr(self.app, "chat_log"):
                self.app.chat_log.scroll_up(animate=False)
                event.stop()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown):
        last_line_idx = len(self.document.lines) - 1
        if self.cursor_location[0] == last_line_idx:
            if hasattr(self.app, "chat_log"):
                self.app.chat_log.scroll_down(animate=False)
                event.stop()

    @property
    def value(self) -> str:
        """Compatibilidad con el código que espera .value"""
        return self.text

    @value.setter
    def value(self, val: str):
        if not val:
            if hasattr(self, "clear"):
                self.clear()
            else:
                self.text = ""
        else:
            self.text = val
        self.cursor_location = (0, 0)
        self._adjust_height()

    def _adjust_height(self):
        """Ajusta manualmente la altura basada en el número de líneas para corregir bug de Textual."""
        line_count = self.document.line_count
        # Altura mínima 1, máxima 20
        target_height = max(1, min(20, line_count))
        self.styles.height = target_height
        
        # Solo ajustamos nuestra propia altura. El contenedor (input_container) 
        # tiene height: auto en CSS y se ajustará solo gracias al padding.
        # Eliminamos el refresh(layout=True) para evitar parpadeos y pérdida de foco.
        pass

    def _on_text_area_changed(self, event: TextArea.Changed):
        """Ajustar altura mientras se escribe."""
        self._adjust_height()


    def on_mount(self):
        # Actualizar workspace del suggester si no se conocía en __init__
        if hasattr(self, "suggester") and self.suggester.workspace_directory is None:
            try:
                workspace = getattr(self.app, "workspace_directory", None)
                if workspace:
                    self.suggester.workspace_directory = workspace
            except Exception:
                pass
        # Iniciar el suggester cuando se monte
        if hasattr(self, "suggester"):
            self.suggester.start()
            # Forzar actualización inmediata de archivos para que esté lista para el primer @
            self.suggester.update_files_now()

    def on_unmount(self):
        # Limpiar el suggester al desmontar
        if hasattr(self, "suggester"):
            self.suggester.stop()


class KogniTermSuggester:
    """
    Proporciona sugerencias para autocompletado de archivos (@) y contenedores (:).
    """
    def __init__(self, workspace_directory: str = None):
        self.workspace_directory = workspace_directory or os.getcwd()
        self.cached_files_list: List[str] = []
        self._cached_containers: List[dict] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def update_files_now(self):
        """Fuerza actualización inmediata de archivos (sin esperar al worker)."""
        self._update_files()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _worker(self):
        """Hilo de segundo plano para actualizar caches periódicamente."""
        # Primera actualización inmediata, sin esperar
        self._update_files()
        self._update_containers()

        # Luego dormir entre actualizaciones completas
        while not self._stop_event.is_set():
            # Dormir 30 segundos antes de la próxima actualización completa
            # pero revisar el stop_event frecuentemente
            for _ in range(30):
                if self._stop_event.is_set():
                    break
                import time
                time.sleep(1)

    def _update_files(self):
        """Escanea el workspace en busca de archivos."""
        try:
            if not self.workspace_directory or not os.path.exists(self.workspace_directory):
                return

            exclude = {
                'build', 'venv', '.git', '__pycache__', 'node_modules', 
                'dist', 'out', 'coverage', '.mypy_cache', '.pytest_cache',
                '.gemini', '.antigravity', '.pyfly'
            }
            exclude_extensions = {'.pyc', '.tmp', '.log', '.swp', '.bak', '.old', '.pyfly'}
            
            items = []
            # Usar una lista temporal para evitar bloqueos largos del lock
            for root, dirs, files in os.walk(self.workspace_directory):
                # Filtrar directorios in-situ para no descender en ellos
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in exclude]
                
                try:
                    rel_root = os.path.relpath(root, self.workspace_directory)
                except ValueError:
                    continue
                    
                if rel_root == ".": rel_root = ""
                
                for f in files:
                    if f.startswith('.') or any(f.endswith(ext) for ext in exclude_extensions):
                        continue
                    
                    rel_path = os.path.join(rel_root, f) if rel_root else f
                    items.append(rel_path)
                    
                    if len(items) > 5000: # Aumentado el límite para mejor cobertura
                        break
                if len(items) > 5000: break
                
            with self._lock:
                self.cached_files_list = items
        except Exception as e:
            # Registrar error si es posible (aunque aquí suele ser silencioso)
            pass

    def _update_containers(self):
        """Obtiene lista de contenedores Docker activos."""
        try:
            # Solo intentar si docker está disponible
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.Image}}"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if not line: continue
                    parts = line.split('|')
                    if len(parts) >= 3:
                        containers.append({
                            'name': parts[0],
                            'status': parts[1],
                            'image': parts[2]
                        })
                with self._lock:
                    self._cached_containers = containers
        except Exception:
            pass
