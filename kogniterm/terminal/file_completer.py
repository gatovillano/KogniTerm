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
        "build/", "venv/", ".git/", "__pycache__/", "kogniterm.egg-info/",
        "*/build/*", "*/venv/*", "*/.git/*", "*/__pycache__/*", "*/kogniterm.egg-info/*",
        ".*/", "*/.*/",
        "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store", "*.swp", "*.bak", "*.old", "*.fuse_hidden*",
        "node_modules/", "dist/", "out/", "coverage/", ".mypy_cache/", ".pytest_cache/",
    ]

    MAGIC_COMMANDS = [
        ("/help", "Mostrar menú de ayuda interactivo"),
        ("/models", "Cambiar modelo de IA"),
        ("/provider", "Cambiar proveedor de LLM"),
        ("/agy-login", "Iniciar/Cerrar sesión de Google Antigravity"),
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
                dirs[:] = [d for d in dirs if not is_ignored_path(d)]
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
        idx = -1
        for i in range(len(text_before_cursor) - 1, -1, -1):
            if text_before_cursor[i] == '@':
                if i == 0:
                    idx = i
                    break
                prev_char = text_before_cursor[i - 1]
                if prev_char.isspace() or prev_char in ('=', '(', '[', '{', ',', '"', "'", '!', '&', '|', ';', '<', '>', '@'):
                    idx = i
                    break

        if idx != -1:
            current_input_part = text_before_cursor[idx + 1:]
            with self.cache_lock:
                cached_files = self._cached_files
            if cached_files is None:
                if self._loading_future is None or self._loading_future.done():
                    self._start_background_load_files()
                if self.show_indicator:
                    yield Completion("(Cargando archivos...)", start_position=-len(current_input_part))
                return

            results = fuzzy_match_files(current_input_part, cached_files, self.workspace_directory, max_results=100)
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


def fuzzy_match_files(query: str, files: List[str], workspace_directory: Optional[str] = None, max_results: int = 20) -> List[tuple]:
    """
    Realiza una búsqueda difusa (fuzzy character matching) sobre una lista de archivos relativos.

    Retorna una lista de tuplas: (score, relative_path, meta_tag) ordenada por score descendente.
    """
    if not files:
        return []

    query_strip = query.strip()
    if not query_strip:
        scored_root = []
        for rel_path in files:
            is_dir = rel_path.endswith('/') or (workspace_directory and os.path.isdir(os.path.join(workspace_directory, rel_path)))
            display_item = rel_path + ('/' if is_dir and not rel_path.endswith('/') else '')
            depth = display_item.count('/')
            if (is_dir and depth == 1) or (not is_dir and depth == 0):
                ext = os.path.splitext(display_item)[1]
                meta = "📁 dir" if is_dir else _get_file_meta_icon(ext)
                scored_root.append((1.0, display_item, meta))
        scored_root.sort(key=lambda x: x[1])
        return scored_root[:max_results]

    query_lower = query_strip.lower().replace('\\', '/')
    terms = query_lower.split()

    scored_matches = []
    for rel_path in files:
        if is_ignored_path(rel_path):
            continue
        display_item = rel_path
        is_dir = rel_path.endswith('/') or (workspace_directory and os.path.isdir(os.path.join(workspace_directory, rel_path)))
        if is_dir and not display_item.endswith('/'):
            display_item += '/'

        display_lower = display_item.lower().replace('\\', '/')
        basename = os.path.basename(display_item.rstrip('/')).lower()
        basename_no_ext = os.path.splitext(basename)[0]

        matched_all = True
        total_score = 0.0

        for term in terms:
            term_score = 0.0
            p_idx = 0
            has_seq = True
            for char in term:
                p_idx = display_lower.find(char, p_idx)
                if p_idx == -1:
                    has_seq = False
                    break
                p_idx += 1

            if not has_seq:
                matched_all = False
                break

            exact_base = (basename == term)
            exact_base_no_ext = (basename_no_ext == term)
            exact_in_base = (term in basename)
            exact_in_path = (term in display_lower)

            if exact_base:
                term_score += 2000.0
            elif exact_base_no_ext:
                term_score += 1500.0
            elif exact_in_base:
                term_score += 1000.0
                if basename.startswith(term):
                    term_score += 300.0
            elif exact_in_path:
                term_score += 600.0
                exact_pos = display_lower.find(term)
                if exact_pos == 0 or (exact_pos > 0 and display_lower[exact_pos - 1] in ('/', '_', '-', '.')):
                    term_score += 300.0

            seq_score = 0.0
            last_pos = -1
            consec_count = 0
            for char in term:
                next_pos = display_lower.find(char, last_pos + 1)
                if next_pos != -1:
                    seq_score += 100.0
                    if last_pos != -1 and next_pos == last_pos + 1:
                        consec_count += 1
                        seq_score += 50.0 + min(consec_count * 10, 50)
                    else:
                        consec_count = 0
                        gap = next_pos - last_pos - 1 if last_pos != -1 else 0
                        seq_score -= min(gap * 10.0, 50.0)

                    if next_pos == 0 or display_lower[next_pos - 1] in ('/', '_', '-', '.'):
                        seq_score += 100.0
                    last_pos = next_pos

            term_score += seq_score
            total_score += term_score

        if matched_all:
            depth = display_item.count('/')
            total_score -= depth * 20.0
            total_score -= len(display_lower) * 0.1

            ext = os.path.splitext(display_item)[1]
            meta = "📁 dir" if is_dir else _get_file_meta_icon(ext)

            scored_matches.append((total_score, display_item, meta))

    scored_matches.sort(key=lambda x: -x[0])
    return scored_matches[:max_results]


def is_ignored_path(path_str: str) -> bool:
    """Verifica si la ruta pertenece a una carpeta virtualenv u otra carpeta ignorada."""
    parts = path_str.lower().replace('\\', '/').split('/')
    for part in parts:
        if not part:
            continue
        if part in ('venv', '.venv', 'env', '.env', 'virtualenv', '.virtualenv',
                    'site-packages', 'node_modules', '__pycache__', 'build',
                    'dist', 'out', 'coverage', '.mypy_cache', '.pytest_cache',
                    'kogniterm.egg-info', '.git', '.gemini', '.antigravity', '.pyfly'):
            return True
        if 'venv' in part or 'virtualenv' in part or 'site-packages' in part:
            return True
    return False


def _get_file_meta_icon(ext: str) -> str:
    if ext in ('.py',):
        return "🐍 python"
    elif ext in ('.md', '.rst', '.txt'):
        return "📝 texto"
    elif ext in ('.json', '.yaml', '.yml', '.toml', '.ini', '.env'):
        return "⚙️ config"
    elif ext in ('.js', '.ts', '.jsx', '.tsx'):
        return "🌐 js/ts"
    elif ext in ('.sh', '.bash'):
        return "🖥️ shell"
    elif ext in ('.html', '.css'):
        return "🎨 web"
    else:
        return ext if ext else "📄 archivo"

