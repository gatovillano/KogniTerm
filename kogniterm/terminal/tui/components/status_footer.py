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
        
    def _get_current_dir(self):
        return os.path.basename(os.getcwd())

    def _get_repo_name(self):
        # Intentar buscar nombre de git repo, o usar nombre de carpeta padre
        try:
            import subprocess
            result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True)
            return os.path.basename(result.stdout.strip())
        except Exception:
            return self._get_current_dir()
            
    def compose(self) -> ComposeResult:
        current_dir = self._get_current_dir()
        repo_name = self._get_repo_name()
        
        # Siempre mostrarlos para evitar confusión de que no está
        left_text = f"📦 {repo_name}  🗂️ {current_dir}"
            
        display_model = self.model_name.split("/")[-1]
        right_text = f"{display_model} 🤖"
        
        yield Static(left_text, id="footer_left", markup=True)
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
        self.cursor_line_style = "" # Intentar con cadena vacía para desactivar resaltado

        self.styles.background = None
        self.soft_wrap = True
        self.tab_behavior = "focus"  # Tab cambia el foco
        
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
        self.text = val

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
            exclude = {
                'build', 'venv', '.git', '__pycache__', 'node_modules', 
                'dist', 'out', 'coverage', '.mypy_cache', '.pytest_cache',
                '.gemini', '.antigravity'
            }
            exclude_extensions = {'.pyc', '.tmp', '.log', '.swp', '.bak', '.old'}
            
            items = []
            for root, dirs, files in os.walk(self.workspace_directory):
                # Filtrar directorios in-situ
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in exclude]
                
                rel_root = os.path.relpath(root, self.workspace_directory)
                if rel_root == ".": rel_root = ""
                
                for f in files:
                    if f.startswith('.') or any(f.endswith(ext) for ext in exclude_extensions):
                        continue
                    
                    rel_path = os.path.join(rel_root, f) if rel_root else f
                    items.append(rel_path)
                    if len(items) > 1000: # Límite razonable
                        break
                if len(items) > 1000: break
                
            with self._lock:
                self.cached_files_list = items
        except Exception:
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

