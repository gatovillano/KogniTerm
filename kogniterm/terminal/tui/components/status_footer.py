from textual.app import ComposeResult
from textual.widgets import Static, Input
from textual.containers import Horizontal, Vertical
from textual.suggester import Suggester
import os
import subprocess
import asyncio
import threading
from textual import events

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
        
        return [
            Static(left_text, id="footer_left", markup=True),
            Static(right_text, id="footer_right", markup=True)
        ]

class KogniTermSuggester(Suggester):
    """
    Suggester para autocompletado en Textual. Emula el comportamiento del FileCompleter.
    """
    def __init__(self):
        super().__init__()
        self._cached_files = None
        self._cached_containers = None
        
        self.MAGIC_COMMANDS = ["%help", "%models", "%provider", "%reset", "%undo", "%compress", "%theme", "%init", "%keys", "%session", "%salir"]
        self.SESSION_SUBCOMMANDS = ["list", "save", "load", "new", "delete"]
        
        # Iniciar carga de datos en 2do plano
        threading.Thread(target=self._load_files, daemon=True).start()
        threading.Thread(target=self._load_containers, daemon=True).start()

    def _load_files(self):
        try:
            from kogniterm.skills.bundled.file_operations.scripts.tool import _list_directory
            output = _list_directory(path=os.getcwd(), recursive=True)
            if isinstance(output, str):
                self._cached_files = [item.strip() for item in output.split('\n') if item.strip()]
        except Exception:
            pass

    def _load_containers(self):
        try:
            result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True)
            self._cached_containers = [c.strip() for c in result.stdout.split('\n') if c.strip()]
        except Exception:
            pass

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
            
        words = value.split()
        if not words:
            return None
            
        current_word = words[-1]
        
        # 1. Comandos Mágicos (%)
        if current_word.startswith('%'):
            if current_word == "%session" and value.endswith(' '):
                # Cannot suggest next word easily with inline suggester if it requires a space
                return None
            
            if current_word.startswith('%session') and len(words) > 1:
                subcmd = words[1]
                matches = [s for s in self.SESSION_SUBCOMMANDS if s.startswith(subcmd)]
                if matches:
                    return matches[0][len(subcmd):]
            else:
                matches = [c for c in self.MAGIC_COMMANDS if c.startswith(current_word)]
                if matches:
                    return matches[0][len(current_word):]
                    
        # 2. Archivos (@)
        if '@' in current_word:
            parts = current_word.split('@')
            search_path = parts[-1]
            if self._cached_files:
                matches = [f for f in self.cached_files_list if search_path.lower() in f.lower()]
                if matches:
                    # Encuentra el match más corto o el primero que empiece con search_path
                    best_match = next((m for m in matches if m.lower().startswith(search_path.lower())), matches[0])
                    # Extrar lo que falta por escribir
                    idx = best_match.lower().find(search_path.lower())
                    if idx == 0:
                        return best_match[len(search_path):]
                    else:
                        return best_match # If it doesn't start with it, suggesting the whole string might be confusing but it's the best we can do inline
                        
        # 3. Docker (:)
        if ':' in current_word:
            parts = current_word.split(':')
            search_container = parts[-1]
            if self._cached_containers:
                matches = [c for c in self._cached_containers if search_container.lower() in c.lower()]
                if matches:
                    best_match = next((m for m in matches if m.lower().startswith(search_container.lower())), matches[0])
                    if best_match.lower().startswith(search_container.lower()):
                        return best_match[len(search_container):]

        return None

    @property
    def cached_files_list(self):
        return self._cached_files or []

class ChatInput(Input):
    """
    Entrada de texto del usuario (reemplaza prompt_toolkit) con historial persistente.
    """
    def __init__(self, **kwargs):
        # Permitir id personalizado pero con default
        if "id" not in kwargs:
            kwargs["id"] = "chat_input"
        super().__init__(suggester=KogniTermSuggester(), **kwargs)
        
        # Usar historial persistente compartido
        self._history_manager = get_message_history()
        self._history = self._history_manager.get_history()
        self._history_index = -1
        self._temp_input = ""

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
        # Evitar interceptar flechas si el popup de comandos está abierto
        if hasattr(self.app, "command_popup") and self.app.command_popup.display:
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

        # Evitar interceptar flechas si la sugerencia está abierta (handled by textual input inherently if autocomplete is active)
        if event.key == "up":
            if self._history:
                # Si ya estamos al principio de la historia, podemos escrolear el chat arriba
                if self._history_index >= len(self._history) - 1:
                    if hasattr(self.app, "chat_log"):
                        self.app.chat_log.scroll_up(animate=False)
                        event.prevent_default()
                    return
                
                if self._history_index == -1:
                    self._temp_input = self.value
                
                self._history_index += 1
                self.value = self._history[self._history_index]
                self.cursor_position = len(self.value)
                event.prevent_default()
            else:
                # No hay historial, permitir scroll
                if hasattr(self.app, "chat_log"):
                    self.app.chat_log.scroll_up(animate=False)
                    event.prevent_default()
                
        elif event.key == "down":
            if self._history_index > 0:
                self._history_index -= 1
                self.value = self._history[self._history_index]
                self.cursor_position = len(self.value)
                event.prevent_default()
            elif self._history_index == 0:
                self._history_index = -1
                self.value = self._temp_input
                self.cursor_position = len(self.value)
                event.prevent_default()
            else:
                # Ya estamos abajo del todo en el historial (o no hay), permitir scroll abajo
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

    def _on_paste(self, event: events.Paste) -> None:
        """Override Textual's default paste to avoid truncating at the first newline."""
        if event.text:
            # Reemplazamos saltos de línea reales por un espacio o un literal '\n'
            # para que el LLM reciba el texto en una sola línea pero sin perder información.
            text = event.text.replace('\r\n', '\\n').replace('\n', '\\n')
            
            selection = getattr(self, "selection", None)
            if selection and not getattr(selection, "is_empty", True):
                self.replace(text, selection.start, selection.end)
            else:
                self.insert_text_at_cursor(text)
        event.stop()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp):
        if hasattr(self.app, "chat_log"):
            self.app.chat_log.scroll_up(animate=False)
            event.stop()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown):
        if hasattr(self.app, "chat_log"):
            self.app.chat_log.scroll_down(animate=False)
            event.stop()

