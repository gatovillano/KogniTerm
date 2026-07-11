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
    
    def __init__(self, history_file_path: str, max_history_messages: int = 100, max_history_chars: int = 150000, auto_save_interval: Optional[float] = None, thread_manager: Optional[Any] = None):
        self.history_file_path = history_file_path
        self.max_history_messages = max_history_messages
        self.max_history_chars = max_history_chars
        self._save_lock = threading.RLock()
        self._conversation_history = AutoSavingMessageList()
        self.conversation_history = self._load_history() or []
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self._message_length_cache: Dict[int, int] = {}
        
        # El sistema de persistencia ahora es gestionado por ThreadManager.
        self.autosave_manager = None
        self._thread_manager = thread_manager
        
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

    def _handle_history_mutation(self, history: List[BaseMessage]):
        """Maneja mutaciones del historial guardando en disco."""
        self._save_history(history)

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
        Calcula la longitud de un mensaje con caché para optimización.
        
        Args:
            message: Mensaje en formato LangChain
            
        Returns:
            Longitud del mensaje en caracteres (formato JSON)
        """
        msg_hash = self._get_message_hash(message)
        if msg_hash not in self._message_length_cache:
            msg_litellm = self._to_litellm_message_for_len_calc(message)
            self._message_length_cache[msg_hash] = len(json.dumps(msg_litellm, ensure_ascii=False))
        return self._message_length_cache[msg_hash]

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
        """Guarda el historial en el archivo JSON."""
        with self._save_lock:
            if history is None:
                history = []
            if not self.history_file_path:
                return

            if self.conversation_history is None:
                self.conversation_history = []

            if history is not self.conversation_history:
                self.conversation_history = history
                history = self.conversation_history

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
                    serializable_history.append({
                        'type': 'tool', 
                        'content': message.content, 
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
        """Convierte un mensaje de LangChain a formato LiteLLM para cálculo de longitud."""
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            msg = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                msg["tool_calls"] = message.tool_calls
            return msg
        elif isinstance(message, ToolMessage):
            return {"role": "tool", "content": message.content, "tool_call_id": message.tool_call_id}
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        return {"role": "user", "content": str(message.content)}
