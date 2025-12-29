import json
import os
import uuid
from typing import List, Union, Callable, Any, Optional, Dict, Set
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage
import sys
import tiktoken

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
    MIN_MESSAGES_TO_KEEP = 5 # Aumentado para mantener más contexto
    MAX_SUMMARY_LENGTH_RATIO = 0.25  # 25% del max_history_chars
    DEFAULT_MAX_SUMMARY_LENGTH = 2000
    SUMMARY_TRUNCATION_SUFFIX = "... [Resumen truncado para evitar bucles]"
    MAX_TOOL_MESSAGE_CONTENT_LENGTH_ASSUMED = 100000
    
    def __init__(self, history_file_path: str, max_history_messages: int = 50, max_history_chars: int = 75000):
        self.history_file_path = history_file_path
        self.max_history_messages = max_history_messages
        self.max_history_chars = max_history_chars
        self.conversation_history: List[BaseMessage] = self._load_history() or []
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self._message_length_cache: Dict[int, int] = {}

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
                        loaded_history.append(AIMessage(content=item['content'], tool_calls=formatted_tool_calls))
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
        if history is None:
            history = []
        if not self.history_file_path:
            return

        if self.conversation_history is None:
            self.conversation_history = []

        if self.conversation_history is not history:
            self.conversation_history[:] = history # <<--- MODIFICADO: Actualizar in-place para mantener referencias

        history_dir = os.path.dirname(self.history_file_path)
        os.makedirs(history_dir, exist_ok=True)

        serializable_history = []
        for message in history:
            if isinstance(message, HumanMessage):
                serializable_history.append({'type': 'human', 'content': message.content})
            elif isinstance(message, AIMessage):
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
                    serializable_history.append({
                        'type': 'ai', 
                        'content': message.content, 
                        'tool_calls': tool_calls_for_save
                    })
                else:
                    serializable_history.append({'type': 'ai', 'content': message.content})
            elif isinstance(message, ToolMessage):
                serializable_history.append({
                    'type': 'tool', 
                    'content': message.content, 
                    'tool_call_id': message.tool_call_id
                })
            elif isinstance(message, SystemMessage):
                serializable_history.append({'type': 'system', 'content': message.content})

        with open(self.history_file_path, 'w', encoding='utf-8') as f:
            # Optimización: Eliminar indentación para reducir tamaño de archivo y tiempo de I/O
            json.dump(serializable_history, f, ensure_ascii=False, separators=(',', ':'))

    def add_message(self, message: BaseMessage):
        """Agrega un mensaje al historial y lo guarda."""
        self.conversation_history.append(message)
        self._save_history(self.conversation_history)

    def get_history(self) -> List[BaseMessage]:
        """Retorna el historial de conversación."""
        return self.conversation_history

    def clear_history(self):
        """Limpia el historial de conversación."""
        self.conversation_history.clear()
        self._save_history([])
        self._message_length_cache.clear()

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
            is_assistant = msg.get("role") == "assistant"
            has_content = msg.get("content") and str(msg.get("content")).strip()
            has_tool_calls = msg.get("tool_calls")
            
            # Omitir mensajes de asistente vacíos sin tool_calls
            if is_assistant and not has_content and not has_tool_calls:
                continue
            
            filtered.append(msg)
        return filtered

    def _remove_orphan_tool_messages(self, history: List[BaseMessage]) -> List[BaseMessage]:
        """
        Elimina ToolMessages que no tienen un AIMessage correspondiente.
        
        Args:
            history: Historial en formato LangChain
            
        Returns:
            Historial sin ToolMessages huérfanos
        """
        # Recopilar todos los tool_call_ids válidos
        valid_tool_call_ids: Set[str] = set()
        for msg in history:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    if 'id' in tc and tc['id']:
                        valid_tool_call_ids.add(tc['id'])
        
        # Filtrar mensajes
        filtered_history = []
        for i, msg in enumerate(history):
            if isinstance(msg, ToolMessage):
                # Omitir ToolMessages sin AIMessage correspondiente
                # PERO: Si el ToolMessage no tiene ID, o el ID está vacío,
                # verificamos si el mensaje ANTERIOR es un AIMessage con tool_calls.
                # Si es así, asumimos que es su par y lo mantenemos.
                if not msg.tool_call_id:
                     if i > 0 and isinstance(history[i-1], AIMessage) and history[i-1].tool_calls:
                         filtered_history.append(msg)
                         continue
                
                if msg.tool_call_id and msg.tool_call_id not in valid_tool_call_ids:
                    # Si el ID no coincide con ninguno conocido, es un huérfano definitivo.
                    # La heurística anterior de "si el anterior es AIMessage" es peligrosa porque
                    # permite pasar ToolMessages con IDs incorrectos que hacen fallar a LiteLLM.
                    # print(f"DEBUG: Eliminando ToolMessage huérfano. ID: {msg.tool_call_id}, IDs válidos: {valid_tool_call_ids}", file=sys.stderr)
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
        
        # Si el último mensaje es un ToolMessage, verificar que tenga su AIMessage
        if isinstance(history[-1], ToolMessage):
            last_tool_msg = history[-1]
            tool_call_id = last_tool_msg.tool_call_id
            
            # Buscar el AIMessage correspondiente
            found_ai_message = False
            
            # Si no tiene ID, verificar simplemente si el anterior es un AIMessage con tools
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
            
            # Si no se encuentra, eliminar el ToolMessage huérfano
            if not found_ai_message:
                history = history[:-1]
        
        # Eliminar AIMessage vacío final
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
        
        # Identificar pares AIMessage-ToolMessage y tratarlos como unidades
        message_units = []
        i = 0
        while i < len(conversational_messages):
            msg = conversational_messages[i]
            if isinstance(msg, AIMessage) and msg.tool_calls:
                # Crear una unidad con el AIMessage
                current_unit = [msg]
                
                # Recopilar IDs de tools llamados por este mensaje
                expected_tool_ids = set()
                for tc in msg.tool_calls:
                    if tc.get('id'):
                        expected_tool_ids.add(tc.get('id'))
                
                # Buscar ToolMessages correspondientes inmediatamente después
                # Avanzamos i para mirar los siguientes mensajes
                next_idx = i + 1
                while next_idx < len(conversational_messages):
                    next_msg = conversational_messages[next_idx]
                    if isinstance(next_msg, ToolMessage):
                        # Si tiene ID y coincide, o si no tiene ID (asumimos coincidencia por posición), lo agregamos
                        if (next_msg.tool_call_id and next_msg.tool_call_id in expected_tool_ids) or \
                           (not next_msg.tool_call_id):
                            current_unit.append(next_msg)
                            next_idx += 1
                        else:
                            # Es un ToolMessage pero no coincide con los IDs esperados
                            # Podría ser de una llamada anterior o huérfano, paramos de agrupar
                            break
                    else:
                        # No es un ToolMessage, terminamos el grupo
                        break
                
                message_units.append(current_unit)
                # Actualizar i para saltar los mensajes ya procesados
                # Restamos 1 porque el bucle principal hace i += 1
                i = next_idx - 1 
            else:
                message_units.append([msg])
            i += 1
        
        # Calcular longitud total de las unidades de mensajes
        def get_unit_length(unit: List[BaseMessage]) -> int:
            return sum(self._get_message_length(msg) for msg in unit)

        total_length = sum(get_unit_length(unit) for unit in message_units)
        
        # Truncar mientras se excedan los límites, priorizando mensajes recientes
        while (len(message_units) > max_messages or total_length > max_chars) and \
              len(message_units) > self.MIN_MESSAGES_TO_KEEP:
            
            # Intentar truncar el contenido de ToolMessages grandes dentro de las unidades más antiguas
            truncated_any_content = False
            if total_length > max_chars:
                for unit_idx in range(len(message_units) - self.MIN_MESSAGES_TO_KEEP -1): # No tocar los últimos mensajes
                    for msg_idx, msg in enumerate(message_units[unit_idx]):
                        if isinstance(msg, ToolMessage):
                            original_content = msg.content
                            if len(original_content) > 5000: # Umbral para truncar contenido de ToolMessage
                                truncated_content = original_content[:2500] + "\n\n... [Contenido truncado por límite de historial] ...\n\n" + original_content[-2500:]
                                if msg.content != truncated_content: # Solo actualizar si hay cambio
                                    old_length = self._get_message_length(msg)
                                    msg.content = truncated_content
                                    self._message_length_cache[self._get_message_hash(msg)] = len(json.dumps(self._to_litellm_message_for_len_calc(msg), ensure_ascii=False))
                                    total_length -= (old_length - self._get_message_length(msg))
                                    truncated_any_content = True
                                    if total_length <= max_chars:
                                        break
                        if truncated_any_content and total_length <= max_chars:
                            break
            
            # Si aún excedemos los límites, eliminar la unidad de mensaje más antigua
            if not truncated_any_content or len(message_units) > max_messages or total_length > max_chars:
                if len(message_units) > self.MIN_MESSAGES_TO_KEEP:
                    removed_unit = message_units.pop(0)
                    total_length -= get_unit_length(removed_unit)
                else:
                    break # No se pueden eliminar más mensajes sin violar MIN_MESSAGES_TO_KEEP
            
        # Reconstruir la lista de mensajes a partir de las unidades
        final_conversational_messages = []
        for unit in message_units:
            final_conversational_messages.extend(unit)
        
        return system_messages + final_conversational_messages
    def _convert_litellm_to_langchain(self, messages_litellm: List[Dict[str, Any]]) -> List[BaseMessage]:
        """
        Convierte mensajes de formato LiteLLM a formato LangChain.
        
        Args:
            messages_litellm: Lista de mensajes en formato LiteLLM
            
        Returns:
            Lista de mensajes en formato LangChain
        """
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
        """
        Asegura que un ToolMessage tenga su AIMessage correspondiente en el historial final.
        
        Args:
            tool_msg: ToolMessage que necesita su AIMessage
            final_messages: Lista de mensajes finales (se modifica in-place)
            all_messages: Lista completa de mensajes disponibles
            
        Returns:
            Longitud adicional agregada al historial
        """
        tool_call_id = tool_msg.tool_call_id
        additional_length = 0
        
        # Verificar si ya existe el AIMessage en final_messages
        found_ai_message = False
        for prev_msg in final_messages[:-1]:
            if isinstance(prev_msg, AIMessage) and prev_msg.tool_calls:
                for tc in prev_msg.tool_calls:
                    if tc.get('id') == tool_call_id:
                        found_ai_message = True
                        break
            if found_ai_message:
                break
        
        # Si no se encuentra, buscarlo en all_messages y agregarlo
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
        """
        Genera un resumen de los mensajes antiguos y mantiene los recientes.
        
        Args:
            history: Historial completo en formato LangChain
            summarize_method: Método para generar el resumen
            console: Objeto console para mostrar mensajes
            
        Returns:
            Nuevo historial con resumen y mensajes recientes
        """
        if console:
            console.print("[yellow]El historial de conversación es demasiado largo. Resumiendo mensajes antiguos...[/yellow]")
        
        # 1. Determinar qué mensajes resumir y cuáles mantener
        # Mantenemos los últimos N mensajes (ej. 50% del límite) para contexto inmediato
        # Aseguramos mantener al menos MIN_MESSAGES_TO_KEEP
        keep_count = max(self.MIN_MESSAGES_TO_KEEP, int(self.max_history_messages * 0.5))
        
        if len(history) <= keep_count:
            return history

        # Ajustar keep_count para no cortar pares AIMessage-ToolMessage
        # Si el primer mensaje a mantener es un ToolMessage, necesitamos incluir su AIMessage anterior
        split_index = len(history) - keep_count
        while split_index > 0 and split_index < len(history):
            msg = history[split_index]
            if isinstance(msg, ToolMessage):
                # Estamos cortando en un ToolMessage, retroceder para incluir el AIMessage
                split_index -= 1
                keep_count += 1
            else:
                # Es seguro cortar aquí (o es AIMessage o HumanMessage)
                # Nota: Si es AIMessage, verificamos que no sea parte de un grupo anterior... 
                # Pero asumimos que AIMessage inicia grupo.
                break
        
        messages_to_keep = history[-keep_count:]
        messages_to_summarize = history[:-keep_count]
        
        # 2. Generar resumen de los mensajes antiguos
        # Pasamos explícitamente los mensajes a resumir
        summary = summarize_method(messages_to_summarize)
        
        if not summary:
            if console:
                console.print("[red]No se pudo resumir el historial. Se procederá con el truncamiento estándar.[/red]")
            return history
            
        # 3. Crear nuevo mensaje de sistema con el resumen
        summary_message = SystemMessage(content=f"Resumen de la conversación anterior: {summary}")
        
        # 4. Construir nuevo historial
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
        """
        Procesa el historial de conversación aplicando filtrado, resumen y truncamiento en pasadas optimizadas.
        """
        # Asegurar límites mínimos para preservar contexto
        self.max_history_messages = max(max_history_messages, 30)
        self.max_history_chars = max(max_history_chars, 50000)
        
        # Determinar qué historial procesar
        target_history = history if history is not None else self.conversation_history
        if not target_history:
            return []
            
        # Asegurarnos de que target_history sea una lista mutable
        if not isinstance(target_history, list):
            target_history = list(target_history)

        # PASADA 1: Limpieza de huérfanos y validación de integridad (Unificada)
        valid_tool_call_ids: Set[str] = {
            tc['id'] for msg in target_history 
            if isinstance(msg, AIMessage) and msg.tool_calls 
            for tc in msg.tool_calls if tc.get('id')
        }
        
        cleaned_history = []
        for i, msg in enumerate(target_history):
            if isinstance(msg, ToolMessage):
                # Mantener solo si el ID es válido o si es el par inmediato del anterior
                if msg.tool_call_id in valid_tool_call_ids:
                    cleaned_history.append(msg)
                elif not msg.tool_call_id and i > 0 and isinstance(target_history[i-1], AIMessage) and target_history[i-1].tool_calls:
                    cleaned_history.append(msg)
                continue
            
            # Omitir AIMessages vacíos al final
            if i == len(target_history) - 1 and isinstance(msg, AIMessage) and not msg.content and not msg.tool_calls:
                continue
                
            cleaned_history.append(msg)

        # PASADA 2: Cálculo de longitud y decisión de resumen/truncamiento
        total_length = sum(self._get_message_length(msg) for msg in cleaned_history)
        
        if (len(cleaned_history) > self.max_history_messages or total_length > self.max_history_chars) and \
           len(cleaned_history) > self.MIN_MESSAGES_TO_KEEP:
            
            # Intentar resumir si es necesario
            cleaned_history = self._summarize_and_compress(
                cleaned_history,
                llm_service_summarize_method,
                console
            )
            
            # Re-validar tras resumen (el resumen puede haber cortado pares)
            cleaned_history = self._remove_orphan_tool_messages(cleaned_history)
            cleaned_history = self._truncate_history(
                cleaned_history,
                self.max_history_messages,
                self.max_history_chars
            )
            cleaned_history = self._ensure_tool_message_pairs(cleaned_history)

        # Actualizar y guardar si se solicita
        if save_history:
            if cleaned_history is not self.conversation_history:
                self.conversation_history[:] = cleaned_history
            self._save_history(self.conversation_history)
        
        return cleaned_history

    def _to_litellm_message_for_len_calc(self, message: BaseMessage) -> Dict[str, Any]:
        """
        Convierte un mensaje de LangChain a formato LiteLLM para cálculo de longitud.
        
        Este método maneja ToolMessages de manera similar a LLMService._to_litellm_message
        para consistencia en el cálculo de tokens.
        
        Args:
            message: Mensaje en formato LangChain
            
        Returns:
            Mensaje en formato LiteLLM (diccionario)
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            if message.tool_calls:
                serialized_tool_calls = []
                for tc in message.tool_calls:
                    tc_id = tc.get("id", str(uuid.uuid4()))
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})
                    serialized_tool_calls.append({
                        "id": tc_id,
                        "function": {
                            "name": tc_name,
                            "arguments": json.dumps(tc_args)
                        }
                    })
                return {
                    "role": "assistant", 
                    "content": message.content, 
                    "tool_calls": serialized_tool_calls
                }
            return {"role": "assistant", "content": message.content}
        elif isinstance(message, ToolMessage):
            # Usar un contenido truncado para el cálculo de longitud
            content = message.content
            if len(content) > self.MAX_TOOL_MESSAGE_CONTENT_LENGTH_ASSUMED:
                content = content[:self.MAX_TOOL_MESSAGE_CONTENT_LENGTH_ASSUMED] + "... [Salida de herramienta truncada]"
            return {
                "role": "tool", 
                "content": content, 
                "tool_call_id": message.tool_call_id
            }
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        
        # Fallback para tipos desconocidos
        return {"role": "user", "content": str(message)}

"""
