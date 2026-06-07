"""
file_completer.py — Autocompletado de archivos, comandos mágicos y contenedores Docker
para la interfaz de prompt_toolkit (kogniterm legacy CLI).

Extraído de kogniterm_app.py para permitir su reutilización sin depender
del monolito KogniTermApp.
"""

import os
import sys
import subprocess
import threading
import concurrent.futures
import asyncio
import fnmatch
import logging
from typing import Optional, List

from prompt_toolkit.completion import Completer, Completion

logger = logging.getLogger(__name__)


class FileCompleter(Completer):
    """
    Autocompletado inteligente para prompt_toolkit con soporte para:
      - Comandos mágicos (/)
      - Archivos del workspace (@)
      - Contenedores Docker (:)

    La carga de archivos y contenedores se hace en background para no bloquear
    el hilo principal.
    """

    EXCLUDE_PATTERNS = [
        "build/", "venv/", ".git/", "__pycache__/", "kogniterm.egg-info/", "src/",
        "*/build/*", "*/venv/*", "*/.git/*", "*/__pycache__/*", "*/kogniterm.egg-info/*", "*/src/*",
        ".*/", "*/.*/",
        "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store", "*.swp", "*.bak", "*.old", "*.fuse_hidden*",
        "node_modules/", "dist/", "out/", "coverage/", ".mypy_cache/", ".pytest_cache/",
    ]

    MAGIC_COMMANDS = [
        ("/help", "Mostrar menú de ayuda interactivo"),
        ("/models", "Cambiar modelo de IA"),
        ("/provider", "Cambiar proveedor de LLM"),
        ("/reset", "Reiniciar conversación"),
        ("/undo", "Deshacer última acción"),
        ("/compress", "Resumir historial"),
        ("/theme", "Cambiar tema de colores"),
        ("/tema", "Cambiar tema de colores (alias)"),
        ("/init", "Inicializar contexto"),
        ("/keys", "Gestionar API Keys"),
        ("/session", "Gestión de sesiones"),
        ("/instructions", "Instrucciones del agente (global/workspace)"),
        ("/instruct", "Instrucciones del agente (alias)"),
        ("/resume", "Reanudar sesión guardada"),
        ("/skills", "Listar todas las skills disponibles"),
        ("/salir", "Salir de KogniTerm"),
        ("/mouse", "Alternar ratón"),
        ("/summarize", "Resumir historial para mejorar contexto"),
        ("/reasoning", "Ajustar nivel de razonamiento"),
        ("/summarymodel", "Cambiar modelo de resumen"),
        ("/embeddings", "Configurar embeddings"),
        ("/insights", "Analítica de uso"),
    ]

    SESSION_SUBCOMMANDS = [
        ("list", "Listar sesiones guardadas"),
        ("save", "Guardar sesión actual"),
        ("load", "Cargar una sesión"),
        ("new", "Crear nueva sesión"),
        ("delete", "Eliminar una sesión"),
    ]

    def __init__(self, skill_manager, workspace_directory: str, show_indicator: bool = True):
        self.skill_manager = skill_manager
        self.workspace_directory = workspace_directory
        self.show_indicator = show_indicator
        self._cached_files: Optional[List[str]] = None
        self._cached_containers: Optional[List[str]] = None
        self.cache_lock = threading.Lock()
        self._loading_future: Optional[concurrent.futures.Future] = None
        self._loading_containers_future: Optional[concurrent.futures.Future] = None
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.warning("FileCompleter: No hay un bucle de eventos de asyncio corriendo.")
            self._loop = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        self._start_background_load_files()
        self._start_background_load_containers()

    # ── Caché de archivos ──────────────────────────────────────────────────────

    def invalidate_cache(self):
        """Invalida la caché de archivos, forzando una recarga la próxima vez."""
        with self.cache_lock:
            self._cached_files = None
        if self._loading_future is None or self._loading_future.done():
            self._start_background_load_files()

    def _start_background_load_files(self):
        with self.cache_lock:
            if self._loading_future is not None and not self._loading_future.done():
                return
            if self._loop is None:
                logger.error("FileCompleter: No se puede iniciar la carga en segundo plano, no hay bucle de eventos.")
                return
            self._loading_future = self._loop.run_in_executor(self._executor, self._do_load_files)

    def _do_load_files(self) -> List[str]:
        try:
            all_relative_items = []
            for root, dirs, files in os.walk(self.workspace_directory):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in (
                    'venv', '__pycache__', 'node_modules', 'build', 'dist',
                    'out', 'coverage', '.mypy_cache', '.pytest_cache',
                    'kogniterm.egg-info', '.git',
                )]
                rel_root = os.path.relpath(root, self.workspace_directory)
                if rel_root == ".":
                    rel_root = ""
                for d in dirs:
                    rel_path = os.path.join(rel_root, d) + os.sep if rel_root else d + os.sep
                    if not any(fnmatch.fnmatch(rel_path, pattern) for pattern in self.EXCLUDE_PATTERNS):
                        all_relative_items.append(rel_path)
                for f in files:
                    rel_path = os.path.join(rel_root, f) if rel_root else f
                    if not f.startswith('.') and not any(
                        f.endswith(ext) for ext in ('.pyc', '.tmp', '.log', '.swp', '.bak', '.old')
                    ):
                        if not any(fnmatch.fnmatch(rel_path, pattern) for pattern in self.EXCLUDE_PATTERNS):
                            all_relative_items.append(rel_path)

            with self.cache_lock:
                self._cached_files = all_relative_items
            return all_relative_items
        except Exception as e:
            logger.error(f"FileCompleter: Error al cargar archivos en segundo plano: {e}", exc_info=True)
            with self.cache_lock:
                self._cached_files = []
            return []

    # ── Caché de contenedores Docker ───────────────────────────────────────────

    def _start_background_load_containers(self):
        with self.cache_lock:
            if self._loading_containers_future is not None and not self._loading_containers_future.done():
                return
            if self._loop is None:
                return
            self._loading_containers_future = self._loop.run_in_executor(self._executor, self._do_load_containers)

    def _do_load_containers(self) -> List[str]:
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            containers = [c.strip() for c in result.stdout.split('\n') if c.strip()]
            with self.cache_lock:
                self._cached_containers = containers
            return containers
        except Exception as e:
            logger.error(f"FileCompleter: Error al cargar contenedores Docker: {e}")
            with self.cache_lock:
                self._cached_containers = []
            return []

    # ── Motor de completado ────────────────────────────────────────────────────

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        word_before_cursor = document.get_word_before_cursor(WORD=True)

        # 1. Comandos mágicos (/)
        if text_before_cursor.lstrip().startswith('/') or word_before_cursor.startswith('/'):
            stripped_text = text_before_cursor.lstrip()

            # Subcomandos de /session
            if stripped_text.startswith('/session '):
                parts = stripped_text.split()
                if len(parts) == 2 and not stripped_text.endswith(' '):
                    current_subcmd = parts[1]
                    for subcmd, desc in self.SESSION_SUBCOMMANDS:
                        if subcmd.startswith(current_subcmd):
                            yield Completion(subcmd, start_position=-len(current_subcmd), display_meta=desc)
                    return
                elif len(parts) == 1 and stripped_text.endswith(' '):
                    for subcmd, desc in self.SESSION_SUBCOMMANDS:
                        yield Completion(subcmd, start_position=0, display_meta=desc)
                    return

            # Nombres de sesiones para /resume
            if stripped_text.startswith('/resume '):
                parts = stripped_text.split()
                try:
                    from kogniterm.core.session_manager import SessionManager
                    session_manager = SessionManager(self.workspace_directory or os.getcwd())
                    names = [session["name"] for session in session_manager.list_sessions()]
                except Exception:
                    names = []
                if len(parts) == 2 and not stripped_text.endswith(' '):
                    current_name = parts[1]
                    for name in names:
                        if name.startswith(current_name):
                            yield Completion(name, start_position=-len(current_name), display_meta='Sesión guardada')
                    return
                if len(parts) == 1 and stripped_text.endswith(' '):
                    for name in names:
                        yield Completion(name, start_position=0, display_meta='Sesión guardada')
                    return

            # Comando principal
            if ' ' not in stripped_text:
                current_input = stripped_text
                all_commands = list(self.MAGIC_COMMANDS)
                if self.skill_manager:
                    try:
                        for skill_info in self.skill_manager.list_skills():
                            s_name = skill_info['name']
                            s_desc = skill_info.get('description', '')
                            s_loaded = skill_info.get('loaded', False)
                            icon = "✅" if s_loaded else "⏸"
                            entry = (f"/{s_name}", f"{icon} Skill: {s_desc[:40]}")
                            if not any(cmd == entry[0] for cmd, _ in all_commands):
                                all_commands.append(entry)
                    except Exception:
                        pass

                matches = [cmd for cmd, desc in all_commands if cmd.startswith(current_input)]
                if len(matches) == 1 and matches[0] == current_input:
                    return
                for cmd, desc in all_commands:
                    if cmd.startswith(current_input):
                        yield Completion(cmd, start_position=-len(current_input), display_meta=desc)
                return

        # 2. Archivos (@)
        if '@' in text_before_cursor:
            current_input_part = text_before_cursor.split('@')[-1]
            with self.cache_lock:
                cached_files = self._cached_files
            if cached_files is None:
                if self._loading_future is None or self._loading_future.done():
                    self._start_background_load_files()
                if self.show_indicator:
                    yield Completion("(Cargando archivos...)", start_position=-len(current_input_part))
                return

            query = current_input_part.lower()
            path_prefix = ""
            basename_query = query
            if '/' in query:
                path_prefix = query.rsplit('/', 1)[0] + '/'
                basename_query = query.rsplit('/', 1)[1]

            scored: List[tuple] = []
            for relative_item_path in cached_files:
                absolute_item_path = os.path.join(self.workspace_directory, relative_item_path)
                is_dir = os.path.isdir(absolute_item_path)
                display_item = relative_item_path
                if is_dir and not display_item.endswith('/'):
                    display_item += '/'
                display_lower = display_item.lower()
                if path_prefix and not display_lower.startswith(path_prefix):
                    continue
                segment = display_lower[len(path_prefix):] if path_prefix else display_lower
                base_name = os.path.basename(display_item.rstrip('/')).lower()

                if not basename_query:
                    score = 100 if is_dir else 50
                elif base_name == basename_query or base_name.rstrip('/') == basename_query.rstrip('/'):
                    score = 200
                elif base_name.startswith(basename_query):
                    score = 150
                elif basename_query in base_name:
                    score = 100
                elif basename_query in segment:
                    score = 60
                else:
                    # Fuzzy matching: verificar si todos los caracteres de la query aparecen
                    # consecutivamente en el segmento
                    target = basename_query
                    source = base_name
                    match_idx = 0
                    for ch in source:
                        if match_idx < len(target) and ch == target[match_idx]:
                            match_idx += 1
                    if match_idx == len(target):
                        score = 40
                    else:
                        continue

                if is_dir:
                    score += 10
                depth = display_item.count('/')
                # Penalizar menos la profundidad para permitir archivos anidados
                score -= min(depth, 3) * 2

                ext = os.path.splitext(display_item)[1]
                if is_dir:
                    meta = "📁 dir"
                elif ext in ('.py',):
                    meta = "🐍 python"
                elif ext in ('.md', '.rst', '.txt'):
                    meta = "📝 texto"
                elif ext in ('.json', '.yaml', '.yml', '.toml', '.ini', '.env'):
                    meta = "⚙️ config"
                elif ext in ('.js', '.ts', '.jsx', '.tsx'):
                    meta = "🌐 js/ts"
                elif ext in ('.sh', '.bash'):
                    meta = "🖥️ shell"
                elif ext in ('.html', '.css'):
                    meta = "🎨 web"
                else:
                    meta = ext if ext else "📄 archivo"

                scored.append((-score, display_item, meta))

            scored.sort(key=lambda x: (x[0], x[1]))
            results = scored[:100]  # Aumentado de 30 a 100 resultados
            if len(results) == 1:
                only = results[0][1]
                if only == current_input_part or only.rstrip('/') == current_input_part.rstrip('/'):
                    return
            for _, suggestion, meta in results:
                yield Completion(suggestion, start_position=-len(current_input_part), display_meta=meta)

        # 3. Contenedores Docker (:)
        if ':' in text_before_cursor:
            parts = text_before_cursor.split(':')
            current_input_part = parts[-1]
            if len(parts) > 1 and text_before_cursor.endswith(':' + current_input_part):
                with self.cache_lock:
                    cached_containers = self._cached_containers
                if cached_containers is None:
                    if self._loading_containers_future is None or self._loading_containers_future.done():
                        self._start_background_load_containers()
                    return
                matches = [c for c in cached_containers if current_input_part.lower() in c.lower()]
                if len(matches) == 1 and matches[0].lower() == current_input_part.lower():
                    return
                for container in matches:
                    yield Completion(container, start_position=-len(current_input_part), display_meta="Docker Container")

    def dispose(self):
        """Libera el ThreadPoolExecutor cuando la aplicación se cierra."""
        if self._executor:
            if sys.version_info >= (3, 9):
                self._executor.shutdown(wait=False, cancel_futures=True)
            else:
                self._executor.shutdown(wait=False)
