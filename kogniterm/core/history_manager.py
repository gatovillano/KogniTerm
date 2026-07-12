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

    def _truncate_history(self, history: List[BaseMessage], max_messages: int, max_chars: int) -> List[BaseMessage]:
        """
        Trunca el historial según límites de mensajes y caracteres.
        Protege los pares AIMessage-ToolMessage y trunca el contenido de ToolMessages grandes.
        
        Args:
            history: Historial en formato LangChain
            max_messages: Número máximo de mensajes conversacionales
            max_chars: Número máximo de caracteres totales
            
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
        
        def get_unit_length(unit: List[BaseMessage]) -> int:
            return sum(self._get_message_length(m) for m in unit)
            
        total_length = sum(get_unit_length(u) for u in message_units)
        
        # Eliminar mensajes antiguos si exceden la cantidad de mensajes
        while len(message_units) > max_messages:
            if len(message_units) > self.MIN_MESSAGES_TO_KEEP:
                removed_unit = message_units.pop(0)
                total_length -= get_unit_length(removed_unit)
            else:
                break
                
        # Eliminar mensajes antiguos si exceden el límite de caracteres
        if total_length > max_chars:
            while total_length > max_chars:
                if len(message_units) > self.MIN_MESSAGES_TO_KEEP:
                    removed_unit = message_units.pop(0)
                    total_length -= get_unit_length(removed_unit)
                else:
                    break
            
            # Si todavía excedemos max_chars, truncar el contenido de los mensajes individuales
            if total_length > max_chars:
                target_msg_len = max(1000, max_chars // self.MIN_MESSAGES_TO_KEEP)
                for unit in message_units:
                    for msg in unit:
                        if isinstance(msg, SystemMessage):
                            continue
                        content = msg.content or ""
                        if isinstance(content, str) and len(content) > target_msg_len:
                            half = target_msg_len // 2
                            msg.content = content[:half] + f"\n\n... [Contenido truncado de {len(content)} a {target_msg_len} caracteres por límite de contexto] ...\n\n" + content[-half:]
            
        final_conversational_messages = []
        for unit in message_units:
            final_conversational_messages.extend(unit)
        
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
            return history
            
        summary_message = SystemMessage(content=f"Resumen de la conversación anterior: {summary}")
        new_history = [summary_message] + messages_to_keep
        
        if console:
            console.print(f"[green]Historial resumido. {len(messages_to_summarize)} mensajes condensados en un resumen.[/green]")
        return new_history

    def get_processed_history_for_llm(self, 
                                     llm_service_summarize_method: Callable[[List[BaseMessage]], str],
                                     max_history_messages: int,
                                     max_history_chars: int,
                                     console: Any,
                                     save_history: bool = True,
                                     history: Optional[List[BaseMessage]] = None) -> List[BaseMessage]:
        """Procesa el historial aplicando filtrado, resumen y truncamiento."""
        if max_history_messages >= 10:
            self.max_history_messages = max(max_history_messages, 30)
        else:
            self.max_history_messages = max_history_messages

        if max_history_chars >= 1000:
            self.max_history_chars = max(max_history_chars, 50000)
        else:
            self.max_history_chars = max_history_chars
        
        target_history = history if history is not None else self.conversation_history
        if not target_history:
            return []
            
        if not isinstance(target_history, list):
            target_history = list(target_history)

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
        if (len(cleaned_history) > self.max_history_messages or total_length > self.max_history_chars) and \
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
                self.max_history_chars
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
