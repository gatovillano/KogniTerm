import json
import os
import uuid
from typing import List, Union, Callable, Any, Optional, Dict, Set
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage
import sys
import tiktoken
import time
import threading
from contextlib import contextmanager


class AutoSavingMessageList(list):
    """Lista que persiste automáticamente el historial tras cada mutación con debounce."""

    def __init__(self, iterable=None, on_change=None, debounce_seconds=1.0):
        super().__init__(iterable or [])
        self._on_change = on_change
        self._autosave_suspended = 0
        self._debounce_seconds = debounce_seconds
        self._debounce_timer = None
        self._debounce_lock = threading.RLock()
        self._pending = False

    def set_on_change(self, callback):
        self._on_change = callback

    @contextmanager
    def suspend_autosave(self):
        self._autosave_suspended += 1
        try:
            yield self
        finally:
            self._autosave_suspended = max(0, self._autosave_suspended - 1)
            if self._autosave_suspended == 0 and self._pending:
                self._schedule_save()

    def _schedule_save(self):
        """Programa un guardado con debounce. Cancela el timer anterior si existe."""
        if self._autosave_suspended != 0:
            self._pending = True
            return
        if not self._on_change:
            return

        with self._debounce_lock:
            self._pending = True
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                self._debounce_seconds,
                self._flush
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _flush(self):
        """Fuerza la notificación inmediata al callback sin bloquear el lock durante la ejecución."""
        callback = None
        items_copy = None
        
        with self._debounce_lock:
            self._debounce_timer = None
            if self._pending and self._on_change and self._autosave_suspended == 0:
                self._pending = False
                callback = self._on_change
                items_copy = list(self)  # Copia defensiva mientras se tiene el lock
                
        # Ejecutar el callback FUERA del lock para evitar deadlocks
        if callback and items_copy is not None:
            try:
                callback(items_copy)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Error en callback de historial: {e}", exc_info=True
                )

    def force_flush(self):
        """Fuerza guardado inmediato. Útil al cerrar sesión o antes de operaciones críticas."""
        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None
        self._flush()

    def cancel_pending(self):
        """Cancela cualquier guardado pendiente sin ejecutarlo."""
        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None
            self._pending = False

    def append(self, item):
        super().append(item)
        self._schedule_save()

    def extend(self, items):
        super().extend(items)
        self._schedule_save()

    def insert(self, index, item):
        super().insert(index, item)
        self._schedule_save()

    def clear(self):
        super().clear()
        self._schedule_save()

    def pop(self, index=-1):
        value = super().pop(index)
        self._schedule_save()
        return value

    def remove(self, value):
        super().remove(value)
        self._schedule_save()

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self._schedule_save()

    def __delitem__(self, index):
        super().__delitem__(index)
        self._schedule_save()

    def __iadd__(self, other):
        result = super().__iadd__(other)
        self._schedule_save()
        return result

    def __imul__(self, value):
        result = super().__imul__(value)
        self._schedule_save()
        return result

    def sort(self, *args, **kwargs):
        super().sort(*args, **kwargs)
        self._schedule_save()

    def reverse(self):
        super().reverse()
        self._schedule_save()

class HistoryManager:
    """
    Gestiona el historial de conversación con optimizaciones de rendimiento y mantenibilidad.
    
    Características:
    - Caché de longitud de mensajes para evitar cálculos redundantes
    - Métodos especializados para cada operación (filtrado, resumen, truncamiento)
    - Validación de integridad de pares AIMessage-ToolMessage
    - Manejo robusto de errores
    """
    
    # Constantes de configuración
    MIN_MESSAGES_TO_KEEP = 10 # Aumentado para mantener más contexto
    MAX_SUMMARY_LENGTH_RATIO = 0.25  # 25% del max_history_chars
    DEFAULT_MAX_SUMMARY_LENGTH = 5500
    SUMMARY_TRUNCATION_SUFFIX = "... [Resumen truncado para evitar bucles]"
    MAX_TOOL_MESSAGE_CONTENT_LENGTH_ASSUMED = 100000
    # Marcador canónico para historiales comprimidos. TODOS los flujos
    # (/compress terminal, /compact servidor, auto-resumen) deben usarlo para
    # que los resúmenes previos se detecten y consoliden en cadena en lugar de
    # tratarse como texto genérico y perder el hilo.
    SUMMARY_MARKER = "📌 RESUMEN DE CONVERSACIÓN PREVIA (historial comprimido):"
    # Marcadores heredados que también deben reconocerse (compatibilidad).
    LEGACY_SUMMARY_MARKERS = (
        "resumen de la conversación",
        "resumen forzado",
        "resumen de conversación previa",
        "previous conversation summary",
        "compressed history summary",
        "compressed history",
    )
    # Compactación por antigüedad de ToolMessages (anti-RateLimit por terminal).
    # Los últimos KEEP_FULL outputs se envían íntegros; los anteriores se colapsan
    # de forma determinística (sin LLM) para que N comandos no multipliquen tokens.
    KEEP_FULL_TOOL_OUTPUTS = int(os.getenv("KOGNITERM_KEEP_FULL_TOOL_OUTPUTS", "3"))
    AGED_TOOL_MAX_CHARS = int(os.getenv("KOGNITERM_AGED_TOOL_CHARS", "1500"))
    ARCHIVED_TOOL_MAX_CHARS = int(os.getenv("KOGNITERM_ARCHIVED_TOOL_CHARS", "400"))
    
    def __init__(self, history_file_path: str, max_history_messages: int = 100, max_history_chars: int = 150000, auto_save_interval: Optional[float] = None, thread_manager: Optional[Any] = None, llm_service: Optional[Any] = None):
        self.history_file_path = history_file_path
        self.max_history_messages = max_history_messages
        self.max_history_chars = max_history_chars
        self._save_lock = threading.RLock()
        self._conversation_history = AutoSavingMessageList()
        self.conversation_history = self._load_history() or []
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self._tokenizer = self.tokenizer
        self._message_length_cache: Dict[int, int] = {}
        
        # El sistema de persistencia ahora es gestionado por ThreadManager.
        self.autosave_manager = None
        self._thread_manager = thread_manager
        self._llm_service = llm_service
        self._logger = __import__('logging').getLogger(__name__)
        
        # Autoguardado periódico
        self.auto_save_interval = auto_save_interval
        self._stop_auto_save = threading.Event()
        self._auto_save_thread = None
        if self.auto_save_interval:
            self._start_auto_save()

    @property
    def conversation_history(self) -> AutoSavingMessageList:
        return self._conversation_history

    @conversation_history.setter
    def conversation_history(self, value: Optional[List[BaseMessage]]):
        if isinstance(value, AutoSavingMessageList):
            value.set_on_change(self._handle_history_mutation)
            self._conversation_history = value
            return

        self._conversation_history = AutoSavingMessageList(value or [], self._handle_history_mutation)

    def set_thread_manager(self, thread_manager) -> None:
        """Inyecta (o reemplaza) el ThreadManager en tiempo de ejecución."""
        self._thread_manager = thread_manager

    def set_llm_service(self, llm_service) -> None:
        """Inyecta (o reemplaza) el LLMService en tiempo de ejecución para generación de títulos."""
        self._llm_service = llm_service

    def _save_to_active_thread(self, history: List[BaseMessage]) -> None:
        """Persiste el historial en el hilo activo del ThreadManager, si existe."""
        if not self._thread_manager:
            return
        thread_id = self._thread_manager.get_current_thread_id()
        if not thread_id:
            return
        try:
            self._thread_manager.save_thread_messages(thread_id, history, llm_service=self._llm_service)
        except Exception as exc:
            self._logger.error("Error persistiendo historial en hilo %s: %s", thread_id, exc)

    def _handle_history_mutation(self, history: List[BaseMessage]):
        """Maneja mutaciones del historial guardando en disco y en el hilo activo."""
        self._save_history(history)
        self._save_to_active_thread(history)

    def _start_auto_save(self):
        """Inicia el hilo de autoguardado."""
        if self._auto_save_thread and self._auto_save_thread.is_alive():
            return  # Ya está corriendo
        
        self._stop_auto_save.clear()
        self._auto_save_thread = threading.Thread(target=self._auto_save_loop, daemon=True)
        self._auto_save_thread.start()

    def _auto_save_loop(self):
        """Loop del hilo de autoguardado."""
        while not self._stop_auto_save.is_set():
            self._stop_auto_save.wait(self.auto_save_interval)
            if not self._stop_auto_save.is_set():
                try:
                    self._save_history(self.conversation_history)
                except Exception as e:
                    print(f"Error en autoguardado: {e}", file=sys.stderr)

    def stop_auto_save(self):
        """Detiene el autoguardado."""
        if self._auto_save_thread:
            self._stop_auto_save.set()
            self._auto_save_thread.join(timeout=5)  # Esperar hasta 5 segundos

    def _get_token_count(self, text: str) -> int:
        """Calcula el número de tokens en un texto."""
        return len(self.tokenizer.encode(text))

    def _get_message_hash(self, message: BaseMessage) -> int:
        """Genera un hash único para un mensaje basado en su contenido."""
        content_str = str(message.content)
        tool_calls_str = str(getattr(message, 'tool_calls', []))
        return hash(content_str + tool_calls_str)

    def _get_message_length(self, message: BaseMessage) -> int:
        """
        Calcula la longitud de un mensaje en tokens usando el tokenizador del modelo.
        """
        cached_len = getattr(message, "_cached_token_len", None)
        if cached_len is not None:
            return cached_len

        msg_hash = self._get_message_hash(message)
        if msg_hash not in self._message_length_cache:
            try:
                msg_litellm = self._to_litellm_message_for_len_calc(message)
                # Los tokens estimados de imágenes van aparte (no en el JSON).
                image_tokens = 0
                if isinstance(msg_litellm, dict) and "_image_tokens" in msg_litellm:
                    image_tokens = int(msg_litellm.pop("_image_tokens") or 0)
                text = json.dumps(msg_litellm, ensure_ascii=False)
                if getattr(self, "_tokenizer", None) is not None:
                    tokens = self._tokenizer.encode(text)
                    self._message_length_cache[msg_hash] = len(tokens) + image_tokens
                else:
                    # Fallback robusto: 1 token por cada ~3.5 caracteres
                    self._message_length_cache[msg_hash] = max(1, int(len(text) / 3.5)) + image_tokens
            except Exception:
                msg_litellm = self._to_litellm_message_for_len_calc(message)
                if isinstance(msg_litellm, dict):
                    msg_litellm.pop("_image_tokens", None)
                text = json.dumps(msg_litellm, ensure_ascii=False)
                self._message_length_cache[msg_hash] = max(1, int(len(text) / 3.5))

        calc_len = self._message_length_cache[msg_hash]
        try:
            message._cached_token_len = calc_len
        except Exception:
            pass
        return calc_len

    def _load_history(self) -> List[BaseMessage]:
        """Carga el historial desde el archivo JSON."""
        if not self.history_file_path:
            return []

        if not os.path.exists(self.history_file_path):
            return []

        try:
            with open(self.history_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
                if not file_content.strip():
                    return []
                serializable_history = json.loads(file_content)
            
            loaded_history = []
            for item in serializable_history:
                if item['type'] == 'human':
                    loaded_history.append(HumanMessage(content=item['content']))
                elif item['type'] == 'ai':
                    tool_calls = item.get('tool_calls', [])
                    reasoning = item.get('reasoning_content') or item.get('reasoning')
                    thought_sigs = item.get('thought_signatures')
                    additional_kwargs = {}
                    if reasoning:
                        additional_kwargs["reasoning_content"] = reasoning
                    if thought_sigs:
                        additional_kwargs["thought_signatures"] = thought_sigs
                    if tool_calls:
                        formatted_tool_calls = []
                        for tc in tool_calls:
                            # Asegurarse de que 'args' sea un diccionario
                            if isinstance(tc.get('args'), dict):
                                formatted_tool_calls.append({
                                    'name': tc['name'], 
                                    'args': tc['args'], 
                                    'id': tc.get('id')
                                })
                            else:
                                try:
                                    # Intentar parsear 'args' si es un string JSON
                                    parsed_args = json.loads(tc.get('args', '{}'))
                                    formatted_tool_calls.append({
                                        'name': tc['name'], 
                                        'args': parsed_args, 
                                        'id': tc.get('id')
                                    })
                                except (json.JSONDecodeError, TypeError):
                                    # Fallback si no es un JSON válido o tipo incorrecto
                                    print(f"Advertencia: No se pudieron parsear los argumentos de la herramienta al cargar: {tc.get('args')}", file=sys.stderr)
                                    formatted_tool_calls.append({
                                        'name': tc['name'], 
                                        'args': {}, 
                                        'id': tc.get('id')
                                    })
                        # Incluir additional_kwargs (razonamiento) si existe
                        if additional_kwargs:
                            loaded_history.append(AIMessage(content=item['content'], tool_calls=formatted_tool_calls, additional_kwargs=additional_kwargs))
                        else:
                            loaded_history.append(AIMessage(content=item['content'], tool_calls=formatted_tool_calls))
                    else:
                        if additional_kwargs:
                            loaded_history.append(AIMessage(content=item['content'], additional_kwargs=additional_kwargs))
                        else:
                            loaded_history.append(AIMessage(content=item['content']))
                elif item['type'] == 'tool':
                    loaded_history.append(ToolMessage(content=item['content'], tool_call_id=item['tool_call_id']))
                elif item['type'] == 'system':
                    loaded_history.append(SystemMessage(content=item['content']))
            
            return loaded_history
        except json.JSONDecodeError as e:
            print(f"Error al decodificar el historial JSON desde {self.history_file_path}: {e}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error inesperado al cargar el historial desde {self.history_file_path}: {e}", file=sys.stderr)
            return []

    def _save_history(self, history: List[BaseMessage]):
        """Guarda el historial en el archivo JSON (operación pura de serialización y escritura)."""
        with self._save_lock:
            if history is None:
                history = []
            if not self.history_file_path:
                return

            history_dir = os.path.dirname(self.history_file_path)
            os.makedirs(history_dir, exist_ok=True)

            serializable_history = []
            for message in history:
                if isinstance(message, HumanMessage):
                    serializable_history.append({'type': 'human', 'content': message.content})
                elif isinstance(message, AIMessage):
                    # Extraer razonamiento si existe en additional_kwargs o como atributo directo
                    reasoning = None
                    if getattr(message, 'additional_kwargs', None):
                        reasoning = message.additional_kwargs.get('reasoning_content')
                    if not reasoning and getattr(message, 'reasoning_content', None):
                        reasoning = getattr(message, 'reasoning_content')

                    if message.tool_calls:
                        # Asegurarse de que los args se guarden como diccionario
                        tool_calls_for_save = []
                        for tc in message.tool_calls:
                            args = tc.get('args', {})
                            # Si args es un string, intentar parsearlo
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    args = {}
                            tool_calls_for_save.append({
                                'name': tc['name'], 
                                'args': args, 
                                'id': tc.get('id')
                            })
                        entry = {
                            'type': 'ai', 
                            'content': message.content, 
                            'tool_calls': tool_calls_for_save
                        }
                        if reasoning:
                            entry['reasoning_content'] = reasoning
                        if getattr(message, 'additional_kwargs', None) and 'thought_signatures' in message.additional_kwargs:
                            entry['thought_signatures'] = message.additional_kwargs['thought_signatures']
                        serializable_history.append(entry)
                    else:
                        entry = {'type': 'ai', 'content': message.content}
                        if reasoning:
                            entry['reasoning_content'] = reasoning
                        if getattr(message, 'additional_kwargs', None) and 'thought_signatures' in message.additional_kwargs:
                            entry['thought_signatures'] = message.additional_kwargs['thought_signatures']
                        serializable_history.append(entry)
                elif isinstance(message, ToolMessage):
                    content = message.content
                    # No persistir data URLs gigantes en history.json: ocupan MB
                    # y ralentizan cada carga. Se guarda un marcador.
                    if isinstance(content, list):
                        safe_parts = []
                        for p in content:
                            if isinstance(p, dict) and p.get("type") == "image_url":
                                safe_parts.append({"type": "image_url", "image_url": {"url": "[imagen de sesión anterior: rehaz el screenshot si la necesitas]"}})
                            else:
                                safe_parts.append(p)
                        content = safe_parts
                    elif isinstance(content, str) and len(content) > 20000:
                        content = content[:20000] + "\n\n[... truncado al persistir ...]"
                    serializable_history.append({
                        'type': 'tool',
                        'content': content,
                        'tool_call_id': message.tool_call_id
                    })
                elif isinstance(message, SystemMessage):
                    serializable_history.append({'type': 'system', 'content': message.content})

            # Persistencia atómica y síncrona (Immediate Persistence)
            temp_path = self.history_file_path + ".tmp"
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    # Optimización: Eliminar indentación para reducir tamaño de archivo y tiempo de I/O
                    json.dump(serializable_history, f, ensure_ascii=False, separators=(',', ':'))
                    f.flush()
                    os.fsync(f.fileno()) # Asegurar que los datos lleguen al disco físicamente
                
                # Reemplazo atómico
                os.replace(temp_path, self.history_file_path)
            except Exception as e:
                if os.path.exists(temp_path):
                    try: os.remove(temp_path)
                    except: pass
                raise e

    def add_message(self, message: BaseMessage):
        """Agrega un mensaje al historial y lo guarda."""
        self.conversation_history.append(message)

    def get_history(self) -> List[BaseMessage]:
        """Retorna una copia del historial de conversación."""
        return self.conversation_history.copy()

    def clear_history(self):
        """Limpia el historial de conversación."""
        self.conversation_history.clear()
        self._message_length_cache.clear()

    # ==================== Métodos de Acceso a Hilos ====================
    
    def get_thread_versions(self) -> List[Dict]:
        """
        Obtiene los hilos disponibles desde ThreadManager cuando está disponible.
        
        Returns:
            Lista de diccionarios con información de hilos
        """
        if self._thread_manager:
            return self._thread_manager.list_threads()
        return []
    
    def load_thread(self, thread_id: str) -> Optional[List[BaseMessage]]:
        """
        Carga un hilo específico desde ThreadManager.
        
        Args:
            thread_id: ID del hilo a carrar
            
        Returns:
            Lista de mensajes o None si hay error
        """
        if not self._thread_manager:
            return None
        
        thread = self._thread_manager.get_thread(thread_id)
        return list(thread.messages) if thread else None
    
    def get_thread_statistics(self) -> Dict:
        """
        Obtiene estadísticas del sistema de hilos.
        
        Returns:
            Diccionario con estadísticas
        """
        if not self._thread_manager:
            return {}
        
        threads = self._thread_manager.list_threads()
        return {
            "total_threads": len(threads),
            "threads": threads,
        }

    def _remove_orphan_tool_messages(self, history: List[BaseMessage]) -> List[BaseMessage]:
        """
        Elimina ToolMessages que no tienen un AIMessage correspondiente.
        
        Args:
            history: Historial en formato LangChain
            
        Returns:
            Historial sin ToolMessages huérfanos
        """
        valid_tool_call_ids: Set[str] = set()
        for msg in history:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    if 'id' in tc and tc['id']:
                        valid_tool_call_ids.add(tc['id'])
        
        filtered_history = []
        for i, msg in enumerate(history):
            if isinstance(msg, ToolMessage):
                if not msg.tool_call_id:
                     if i > 0 and isinstance(history[i-1], AIMessage) and history[i-1].tool_calls:
                         filtered_history.append(msg)
                         continue
                
                if msg.tool_call_id and msg.tool_call_id not in valid_tool_call_ids:
                    continue
            filtered_history.append(msg)
        
        return filtered_history

    def _ensure_tool_message_pairs(self, history: List[BaseMessage]) -> List[BaseMessage]:
        """
        Asegura que cada ToolMessage tenga su AIMessage correspondiente.
        Elimina ToolMessages huérfanos al final del historial.

        Args:
            history: Historial en formato LangChain

        Returns:
            Historial con pares de mensajes válidos
        """
        if not history:
            return history
        
        if isinstance(history[-1], ToolMessage):
            last_tool_msg = history[-1]
            tool_call_id = last_tool_msg.tool_call_id
            found_ai_message = False
            
            if not tool_call_id:
                 if len(history) > 1 and isinstance(history[-2], AIMessage) and history[-2].tool_calls:
                     found_ai_message = True
            else:
                for msg in reversed(history[:-1]):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for tc in msg.tool_calls:
                            if tc.get('id') == tool_call_id:
                                found_ai_message = True
                                break
                    if found_ai_message:
                        break
            
            if not found_ai_message:
                history = history[:-1]
        
        if history and isinstance(history[-1], AIMessage):
            if not history[-1].content and not history[-1].tool_calls:
                history = history[:-1]
        
        return history

    def compact_aging_tool_outputs(self, history: List[BaseMessage]) -> List[BaseMessage]:
        """Colapsa ToolMessages antiguos de forma determinística (sin LLM).

        Estrategia anti `RateLimitError: input token limit exceeded` cuando el
        agente ejecutó muchos comandos de terminal:
        - Los últimos KEEP_FULL_TOOL_OUTPUTS ToolMessages se conservan íntegros.
        - Los anteriores se reducen a AGED_TOOL_MAX_CHARS (head+tail+errores).
        - Los más antiguos (más allá de max_history_messages) se archivan a
          ARCHIVED_TOOL_MAX_CHARS como una línea resumen.
        Preserva tool_call_id para no romper pares AIMessage-ToolMessage.
        """
        if not history:
            return history
        try:
            from kogniterm.core.utils.output_pruner import collapse_aged_tool_output
        except Exception:
            return history

        tool_indices = [i for i, m in enumerate(history) if isinstance(m, ToolMessage)]
        if len(tool_indices) <= self.KEEP_FULL_TOOL_OUTPUTS:
            return history

        keep_full = self.KEEP_FULL_TOOL_OUTPUTS
        aged_zone = tool_indices[:-keep_full] if keep_full > 0 else tool_indices
        # Los más antiguos dentro de la zona aged -> minimal; resto -> reduced
        minimal_cutoff = max(0, len(aged_zone) - self.max_history_messages)
        result = list(history)
        for rank, idx in enumerate(aged_zone):
            msg = result[idx]
            content = str(msg.content or "")
            if rank < minimal_cutoff:
                if len(content) > self.ARCHIVED_TOOL_MAX_CHARS:
                    result[idx] = ToolMessage(
                        content=collapse_aged_tool_output(content, level="minimal"),
                        tool_call_id=msg.tool_call_id,
                    )
                    self._message_length_cache.pop(self._get_message_hash(msg), None)
            else:
                if len(content) > self.AGED_TOOL_MAX_CHARS:
                    result[idx] = ToolMessage(
                        content=collapse_aged_tool_output(content, level="reduced"),
                        tool_call_id=msg.tool_call_id,
                    )
                    self._message_length_cache.pop(self._get_message_hash(msg), None)
        return result

    def extractive_fallback_summary(self, history: List[BaseMessage], max_chars: int = 4000) -> str:
        """Resumen extractivo local sin LLM (funciona bajo RateLimit).

        Lista objetivo inicial, herramientas ejecutadas y errores visibles.
        Se usa cuando summarize_conversation_history devuelve "" por fallo
        del proveedor, para poder comprimir igual y no reenviar el historial
        completo que causó el RateLimit.
        """
        if not history:
            return ""
        initial_goal = ""
        for m in history:
            if isinstance(m, HumanMessage) and m.content:
                initial_goal = str(m.content)[:500]
                break
        tool_lines: List[str] = []
        errors: List[str] = []
        for m in history:
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    try:
                        args = tc.get("args", {})
                        cmd = args.get("command", "") if isinstance(args, dict) else ""
                        cmd = str(cmd)[:120]
                    except Exception:
                        cmd = ""
                    tool_lines.append(f"- {tc.get('name', '?')}: {cmd}")
            elif isinstance(m, ToolMessage) and m.content:
                for ln in str(m.content).splitlines():
                    low = ln.lower()
                    if any(k in low for k in ("error", "exception", "traceback", "failed", "fatal", "denied")):
                        errors.append(ln.strip()[:160])
                        if len(errors) >= 8:
                            break
        parts = []
        if initial_goal:
            parts.append(f"🎯 OBJETIVO INICIAL: {initial_goal}")
        if tool_lines:
            seen: Set[str] = set()
            uniq = [t for t in tool_lines if not (t in seen or seen.add(t))]
            parts.append(f"✅ HERRAMIENTAS EJECUTADAS ({len(uniq)}):\n" + "\n".join(uniq[-30:]))
        # Últimas respuestas del asistente como estado actual
        ai_texts = [str(m.content)[:300] for m in history if isinstance(m, AIMessage) and m.content]
        if ai_texts:
            parts.append(f"📌 ÚLTIMO ESTADO: {ai_texts[-1]}")
        if errors:
            parts.append("⚠️ ERRORES VISIBLES:\n" + "\n".join(errors[:8]))
        summary = "\n\n".join(parts)
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "\n\n" + self.SUMMARY_TRUNCATION_SUFFIX
        return summary or "Historial con múltiples comandos de terminal ejecutados."

    @classmethod
    def is_summary_message(cls, message: BaseMessage) -> Optional[str]:
        """Detecta si un mensaje es un resumen previo (canónico o heredado).

        Comparación insensible a mayúsculas para no depender del formato exacto.
        Returns:
            Contenido limpio del resumen o None si no es un resumen.
        """
        if not isinstance(message, SystemMessage):
            return None
        content = str(message.content or "")
        low = content.lower()
        if cls.SUMMARY_MARKER.lower() not in low and not any(
            m in low for m in cls.LEGACY_SUMMARY_MARKERS
        ):
            return None
        # Extraer el cuerpo tras el primer ':' si hay encabezado
        for marker in (cls.SUMMARY_MARKER,) + tuple(cls.LEGACY_SUMMARY_MARKERS):
            idx = low.find(marker)
            if idx != -1:
                body = content[idx + len(marker):].strip().lstrip(":").strip()
                return body or content
        return content

    def build_compressed_history(
        self,
        full_history: List[BaseMessage],
        summary: str,
        keep_recent: int = 20,
        base_system_message: Optional[BaseMessage] = None,
    ) -> List[BaseMessage]:
        """Ensambla [base?, resumen canónico, objetivo inicial?, recents seguros].

        - Conserva el primer HumanMessage (objetivo) aunque sea antiguo.
        - Los recents nunca empiezan a mitad de un par AI(tool_calls)+Tool:
          retrocede hasta un HumanMessage o un AI sin tool_calls pendiente.
        - Elimina duplicados del objetivo si ya está en recents.
        """
        history = list(full_history or [])
        if not history:
            return [base_system_message] if base_system_message else []

        summary_msg = SystemMessage(content=f"{self.SUMMARY_MARKER}\n\n{summary}")

        # Objetivo inicial: primer HumanMessage con contenido
        initial_goal = None
        for m in history:
            if isinstance(m, HumanMessage) and str(m.content or "").strip():
                initial_goal = m
                break

        # Ventana reciente segura por pares (máx. keep_recent mensajes)
        recents: List[BaseMessage] = []
        for m in reversed(history):
            if isinstance(m, SystemMessage) and self.is_summary_message(m) is not None:
                continue  # los resúmenes viejos ya están consolidados en `summary`
            recents.append(m)
            if len(recents) >= keep_recent:
                break
        recents.reverse()
        # No empezar a mitad de par: si el primero es Tool huérfano o AI con
        # tool_calls sin sus Tools a continuación, avanzar al siguiente turno.
        while recents and isinstance(recents[0], ToolMessage):
            recents.pop(0)
        if recents and isinstance(recents[0], AIMessage) and recents[0].tool_calls:
            expected = {tc.get("id") for tc in recents[0].tool_calls if tc.get("id")}
            following_tools = {
                m.tool_call_id for m in recents[1:] if isinstance(m, ToolMessage)
            }
            if expected and not (expected & following_tools):
                recents.pop(0)
                while recents and isinstance(recents[0], ToolMessage):
                    recents.pop(0)

        new_history: List[BaseMessage] = []
        if base_system_message is not None:
            new_history.append(base_system_message)
        new_history.append(summary_msg)
        if initial_goal is not None and initial_goal not in recents:
            new_history.append(initial_goal)
        new_history.extend(recents)
        return new_history

    def _truncate_history(self, history: List[BaseMessage], max_messages: int, max_tokens: int) -> List[BaseMessage]:
        """
        Trunca el historial según límites de mensajes y tokens.
        Protege los pares AIMessage-ToolMessage y trunca el contenido de ToolMessages grandes.
        
        Args:
            history: Historial en formato LangChain
            max_messages: Número máximo de mensajes conversacionales
            max_tokens: Número máximo de tokens totales
            
        Returns:
            Historial truncado
        """
        system_messages = [msg for msg in history if isinstance(msg, SystemMessage)]
        conversational_messages = [msg for msg in history if not isinstance(msg, SystemMessage)]
        
        message_units = []
        i = 0
        while i < len(conversational_messages):
            msg = conversational_messages[i]
            if isinstance(msg, AIMessage) and msg.tool_calls:
                current_unit = [msg]
                expected_tool_ids = set()
                for tc in msg.tool_calls:
                    if tc.get('id'):
                        expected_tool_ids.add(tc.get('id'))
                
                next_idx = i + 1
                while next_idx < len(conversational_messages):
                    next_msg = conversational_messages[next_idx]
                    if isinstance(next_msg, ToolMessage):
                        if (next_msg.tool_call_id and next_msg.tool_call_id in expected_tool_ids) or \
                           (not next_msg.tool_call_id):
                            current_unit.append(next_msg)
                            next_idx += 1
                        else:
                            break
                    else:
                        break
                
                message_units.append(current_unit)
                i = next_idx - 1 
            else:
                message_units.append([msg])
            i += 1
        
        # PASO A: Truncamiento de contenido preventivo en mensajes individuales desproporcionados
        processed_units = []
        for unit in message_units:
            new_unit = []
            for msg in unit:
                msg_len = self._get_message_length(msg)
                if isinstance(msg, ToolMessage) and (msg_len > 2000 or len(str(msg.content)) > 4000):
                    try:
                        max_chars = 4000
                        if isinstance(msg.content, str) and len(msg.content) > max_chars:
                            truncated_content = msg.content[:max_chars] + "\n\n[Contenido truncado por límite de contexto]"
                            msg = ToolMessage(content=truncated_content, tool_call_id=msg.tool_call_id)
                            # Invalidar caché para este mensaje
                            msg_hash = self._get_message_hash(msg)
                            self._message_length_cache.pop(msg_hash, None)
                    except Exception:
                        pass
                elif isinstance(msg, (HumanMessage, AIMessage)) and (msg_len > 8000 or len(str(msg.content)) > 16000):
                    try:
                        if isinstance(msg.content, str) and len(msg.content) > 16000:
                            truncated_content = msg.content[:16000] + "\n\n[Mensaje truncado por límite de contexto]"
                            if isinstance(msg, HumanMessage):
                                msg = HumanMessage(content=truncated_content)
                            else:
                                msg = AIMessage(content=truncated_content, tool_calls=getattr(msg, 'tool_calls', []))
                            msg_hash = self._get_message_hash(msg)
                            self._message_length_cache.pop(msg_hash, None)
                    except Exception:
                        pass
                new_unit.append(msg)
            processed_units.append(new_unit)
        
        message_units = processed_units

        def get_unit_length(unit: List[BaseMessage]) -> int:
            return sum(self._get_message_length(m) for m in unit)
            
        total_length = sum(get_unit_length(u) for u in message_units)
        
        # Identificar si la primera unidad representa el objetivo/prompt inicial del usuario
        has_pinned_initial_unit = (
            len(message_units) > 1
            and len(message_units[0]) > 0
            and isinstance(message_units[0][0], (HumanMessage, SystemMessage))
        )

        # PASO B: Eliminar mensajes antiguos si exceden la cantidad máxima de mensajes
        while len(message_units) > max_messages:
            if len(message_units) > self.MIN_MESSAGES_TO_KEEP:
                pop_idx = 1 if (has_pinned_initial_unit and len(message_units) > 2) else 0
                removed_unit = message_units.pop(pop_idx)
                total_length -= get_unit_length(removed_unit)
            else:
                break
                
        # PASO C: Eliminar mensajes antiguos si el total de tokens aún excede el límite
        if total_length > max_tokens:
            while total_length > max_tokens and len(message_units) > 1:
                pop_idx = 1 if (has_pinned_initial_unit and len(message_units) > 2) else 0
                removed_unit = message_units.pop(pop_idx)
                total_length -= get_unit_length(removed_unit)
            
        final_conversational_messages = []
        for unit in message_units:
            for msg in unit:
                final_conversational_messages.append(msg)
        
        return system_messages + final_conversational_messages

    def _convert_litellm_to_langchain(self, messages_litellm: List[Dict[str, Any]]) -> List[BaseMessage]:
        """Convierte mensajes de formato LiteLLM a formato LangChain."""
        langchain_messages = []
        for msg_litellm in messages_litellm:
            role = msg_litellm.get("role")
            if role == "user":
                langchain_messages.append(HumanMessage(content=msg_litellm.get("content", "")))
            elif role == "assistant":
                tool_calls_data = msg_litellm.get("tool_calls")
                if tool_calls_data:
                    tool_calls = []
                    for tc in tool_calls_data:
                        tool_calls.append({
                            "id": tc.get("id", str(uuid.uuid4())),
                            "name": tc["function"].get("name", ""),
                            "args": json.loads(tc["function"].get("arguments", "{}"))
                        })
                    langchain_messages.append(AIMessage(
                        content=msg_litellm.get("content", ""), 
                        tool_calls=tool_calls
                    ))
                else:
                    langchain_messages.append(AIMessage(content=msg_litellm.get("content", "")))
            elif role == "tool":
                langchain_messages.append(ToolMessage(
                    content=msg_litellm.get("content", ""), 
                    tool_call_id=msg_litellm.get("tool_call_id", "")
                ))
            elif role == "system":
                langchain_messages.append(SystemMessage(content=msg_litellm.get("content", "")))
        return langchain_messages
    def _ensure_ai_message_for_tool(self, 
                                   tool_msg: ToolMessage, 
                                   final_messages: List[BaseMessage],
                                   all_messages: List[BaseMessage]) -> int:
        """Asegura que un ToolMessage tenga su AIMessage correspondiente."""
        tool_call_id = tool_msg.tool_call_id
        additional_length = 0
        found_ai_message = False
        for prev_msg in final_messages[:-1]:
            if isinstance(prev_msg, AIMessage) and prev_msg.tool_calls:
                for tc in prev_msg.tool_calls:
                    if tc.get('id') == tool_call_id:
                        found_ai_message = True
                        break
            if found_ai_message:
                break
        
        if not found_ai_message:
            for original_msg in all_messages:
                if isinstance(original_msg, AIMessage) and original_msg.tool_calls:
                    for tc in original_msg.tool_calls:
                        if tc.get('id') == tool_call_id:
                            final_messages.insert(0, original_msg)
                            additional_length = self._get_message_length(original_msg)
                            break
                    if additional_length > 0:
                        break
        return additional_length

    def _summarize_and_compress(self, 
                               history: List[BaseMessage],
                               summarize_method: Callable[[List[BaseMessage]], str],
                               console: Any) -> List[BaseMessage]:
        """Genera un resumen de los mensajes antiguos y mantiene los recientes."""
        if console:
            console.print("[yellow]El historial de conversación es demasiado largo. Resumiendo mensajes antiguos...[/yellow]")
        
        keep_count = max(self.MIN_MESSAGES_TO_KEEP, int(self.max_history_messages * 0.7))
        if len(history) <= keep_count:
            return history

        split_index = len(history) - keep_count
        while split_index > 0 and split_index < len(history):
            msg = history[split_index]
            if isinstance(msg, ToolMessage):
                split_index -= 1
                keep_count += 1
            else:
                break
        
        messages_to_keep = history[-keep_count:]
        messages_to_summarize = history[:-keep_count]
        
        summary = summarize_method(messages_to_summarize)
        
        try:
            max_summary_chars = int(min(self.DEFAULT_MAX_SUMMARY_LENGTH, int(self.max_history_chars * self.MAX_SUMMARY_LENGTH_RATIO)))
        except Exception:
            max_summary_chars = self.DEFAULT_MAX_SUMMARY_LENGTH

        if summary and len(summary) > max_summary_chars:
            if console:
                console.print(f"[yellow]Resumen demasiado largo ({len(summary)} chars). Truncando a {max_summary_chars} chars.[/yellow]")
            summary = summary[:max_summary_chars] + "\n\n" + self.SUMMARY_TRUNCATION_SUFFIX

        if not summary:
            if console:
                console.print("[red]No se pudo resumir el historial. Se procederá con el truncamiento estándar.[/red]")
            # Fallback determinístico: resumen extractivo local (funciona bajo
            # RateLimit) para no devolver el historial íntegro que causó el exceso.
            try:
                summary = self.extractive_fallback_summary(messages_to_summarize)
            except Exception:
                summary = ""
            if not summary:
                return history
            
        # Preservar el prompt u objetivo inicial del usuario si existe
        initial_user_msg = None
        for m in history:
            if isinstance(m, HumanMessage):
                initial_user_msg = m
                break

        summary_message = SystemMessage(content=f"{self.SUMMARY_MARKER}\n{summary}")
        
        if initial_user_msg and initial_user_msg not in messages_to_keep:
            new_history = [initial_user_msg, summary_message] + messages_to_keep
        else:
            new_history = [summary_message] + messages_to_keep
        
        if console:
            console.print(f"[green]Historial resumido. {len(messages_to_summarize)} mensajes condensados en un resumen manteniendo el objetivo inicial.[/green]")
        return new_history

    def get_processed_history_for_llm(self, 
                                     llm_service_summarize_method: Callable[[List[BaseMessage]], str],
                                     max_history_messages: int = 100,
                                     max_history_tokens: Optional[int] = None,
                                     console: Any = None,
                                     save_history: bool = True,
                                     history: Optional[List[BaseMessage]] = None,
                                     max_history_chars: Optional[int] = None,
                                     **kwargs) -> List[BaseMessage]:
        """Procesa el historial aplicando filtrado, resumen y truncamiento."""
        self.max_history_messages = max_history_messages
        resolved_tokens = max_history_tokens
        if resolved_tokens is None:
            resolved_tokens = max_history_chars
        if resolved_tokens is None:
            resolved_tokens = kwargs.get("max_history_tokens", kwargs.get("max_history_chars", 100000))
        self.max_history_tokens = resolved_tokens

        target_history = history if history is not None else self.conversation_history
        if not target_history:
            return []
            
        if not isinstance(target_history, list):
            target_history = list(target_history)

        # Paso 0 (nuevo): compactación por antigüedad de outputs de terminal.
        # Barata y determinística: evita que N comandos × 8KB saturen el input.
        try:
            target_history = self.compact_aging_tool_outputs(list(target_history))
        except Exception:
            pass

        valid_tool_call_ids: Set[str] = {
            tc['id'] for msg in target_history 
            if isinstance(msg, AIMessage) and msg.tool_calls 
            for tc in msg.tool_calls if tc.get('id')
        }
        
        cleaned_history = []
        for i, msg in enumerate(target_history):
            if isinstance(msg, ToolMessage):
                if msg.tool_call_id in valid_tool_call_ids:
                    cleaned_history.append(msg)
                elif msg.tool_call_id == 'execute_command' or not msg.tool_call_id:
                    has_recent_ai_call = False
                    for prev_msg in reversed(target_history[:i]):
                        if isinstance(prev_msg, AIMessage) and prev_msg.tool_calls:
                            has_recent_ai_call = True
                            break
                        if isinstance(prev_msg, HumanMessage):
                            break
                    if has_recent_ai_call:
                        cleaned_history.append(msg)
                continue
            
            if i == len(target_history) - 1 and isinstance(msg, AIMessage) and not msg.content and not msg.tool_calls:
                continue
                
            cleaned_history.append(msg)

        total_length = sum(self._get_message_length(msg) for msg in cleaned_history)
        if (len(cleaned_history) > self.max_history_messages or total_length > self.max_history_tokens) and \
           len(cleaned_history) > self.MIN_MESSAGES_TO_KEEP:
            
            cleaned_history = self._summarize_and_compress(
                cleaned_history,
                llm_service_summarize_method,
                console
            )
            
            cleaned_history = self._remove_orphan_tool_messages(cleaned_history)
            cleaned_history = self._truncate_history(
                cleaned_history,
                self.max_history_messages,
                self.max_history_tokens
            )
            cleaned_history = self._ensure_tool_message_pairs(cleaned_history)

        if save_history:
            if cleaned_history is not self.conversation_history:
                self.conversation_history[:] = cleaned_history
            self._save_history(self.conversation_history)
        
        return cleaned_history
    def _filter_empty_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtra mensajes de asistente vacíos sin tool_calls.
        
        Args:
            messages: Lista de mensajes en formato LiteLLM
            
        Returns:
            Lista filtrada de mensajes
        """
        filtered = []
        for msg in messages:
            if msg.get('type') == 'ai':
                content = msg.get('content', '').strip()
                tool_calls = msg.get('tool_calls', [])
                if not content and not tool_calls:
                    continue
            filtered.append(msg)
        return filtered

    def _to_litellm_message_for_len_calc(self, message: BaseMessage) -> Dict[str, Any]:
        """Convierte un mensaje de LangChain a formato LiteLLM para cálculo de longitud.

        Los bloques image_url van sin el base64: contar esos bytes como texto
        inflaba el presupuesto a millones de tokens y provocaba que la purga
        eliminara el turno con la imagen (el modelo respondía a ciegas).
        """
        try:
            from kogniterm.core.llm.message_converter import content_for_token_count
        except Exception:
            content_for_token_count = lambda c: c  # noqa: E731
        if isinstance(message, HumanMessage):
            content = content_for_token_count(message.content)
            if isinstance(message.content, list) and isinstance(content, list):
                extra = sum(
                    1500 for p in message.content
                    if isinstance(p, dict) and p.get("type") == "image_url"
                )
                if extra:
                    return {"role": "user", "content": content, "_image_tokens": extra}
            return {"role": "user", "content": content}
        elif isinstance(message, AIMessage):
            msg = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                msg["tool_calls"] = message.tool_calls
            return msg
        elif isinstance(message, ToolMessage):
            content = message.content
            # Contenido multimodal (screenshot): no contar el base64 como texto
            # (inflaría a millones de tokens y dispararía resúmenes/purgas).
            if isinstance(content, list):
                try:
                    from kogniterm.core.llm.message_converter import content_for_token_count
                    safe = content_for_token_count(content)
                except Exception:
                    safe = [{"type": p.get("type", "?")} if isinstance(p, dict) else p for p in content]
                extra = sum(
                    1500 for p in content
                    if isinstance(p, dict) and p.get("type") == "image_url"
                )
                if extra:
                    return {"role": "tool", "content": safe, "_image_tokens": extra,
                            "tool_call_id": message.tool_call_id}
                return {"role": "tool", "content": safe, "tool_call_id": message.tool_call_id}
            return {"role": "tool", "content": content, "tool_call_id": message.tool_call_id}
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        return {"role": "user", "content": str(message.content)}
