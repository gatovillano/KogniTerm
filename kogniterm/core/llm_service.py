import os
import sys
import time
import json
import queue
from typing import Optional, Any
from collections import deque
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from litellm import completion, litellm
import uuid
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading
from typing import Union # ¡Nueva importación para Union!

import logging

logger = logging.getLogger(__name__)

load_dotenv()

from .tools.tool_manager import get_callable_tools
from .context.workspace_context import WorkspaceContext # Nueva importación
from .context.folder_structure_analyzer import FolderStructure, FileNode, DirectoryNode # ¡Nuevas importaciones!

def _to_litellm_message(message):
    """Convierte un mensaje de LangChain a un formato compatible con LiteLLM."""
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    elif isinstance(message, AIMessage):
        if message.tool_calls:
            litellm_tool_calls = []
            for tc in message.tool_calls:
                # Asegurarse de que el ID de la herramienta se propague correctamente
                tool_call_id = tc.get("id", str(uuid.uuid4()))
                litellm_tool_calls.append({
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["args"])
                    }
                })
            content = message.content if message.content is not None else ""
            return {"role": "assistant", "content": content, "tool_calls": litellm_tool_calls}
        else:
            return {"role": "assistant", "content": message.content}
    elif isinstance(message, ToolMessage):
        tool_call_id = message.tool_call_id if message.tool_call_id is not None else str(uuid.uuid4())
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": message.content
        }
    elif isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    else:
        raise ValueError(f"Tipo de mensaje desconocido para LiteLLM: {type(message)}")

def _from_litellm_message(message):
    """Convierte un mensaje de LiteLLM a un formato compatible con LangChain."""
    role = message.get("role")
    content = message.get("content", "")
    if role == "user":
        return HumanMessage(content=content)
    elif role == "assistant":
        tool_calls_data = message.get("tool_calls")
        if tool_calls_data:
            tool_calls = []
            for tc in tool_calls_data:
                args = tc["function"]["arguments"]
                # Asegurarse de que los argumentos se manejen como un diccionario
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {} # Fallback si no es un JSON válido
                tool_calls.append({
                    "id": tc.get("id", str(uuid.uuid4())),
                    "name": tc["function"]["name"],
                    "args": args
                })
            return AIMessage(content=content, tool_calls=tool_calls)
        else:
            return AIMessage(content=content)
    elif role == "tool":
        return ToolMessage(content=content, tool_call_id=message.get("tool_call_id"))
    elif role == "system":
        return SystemMessage(content=content)
    else:
        raise ValueError(f"Tipo de mensaje desconocido de LiteLLM para LangChain: {role}")

def _convert_langchain_tool_to_litellm(tool: BaseTool) -> dict:
    """Convierte una herramienta de LangChain (BaseTool) a un formato compatible con LiteLLM."""
    args_schema = {"type": "object", "properties": {}}

    # Obtener el esquema de argumentos de manera más robusta
    if hasattr(tool, 'args_schema') and tool.args_schema is not None:
        try:
            # Si args_schema es directamente un dict, usarlo
            if isinstance(tool.args_schema, dict):
                args_schema = tool.args_schema
            # Intentar obtener el esquema usando el método schema() si está disponible (Pydantic v1)
            elif hasattr(tool.args_schema, 'schema') and callable(getattr(tool.args_schema, 'schema', None)):
                try:
                    args_schema = tool.args_schema.schema()
                except Exception:
                    # Si falla el método schema(), intentar model_json_schema() para Pydantic v2
                    if hasattr(tool.args_schema, 'model_json_schema') and callable(getattr(tool.args_schema, 'model_json_schema', None)):
                        args_schema = tool.args_schema.model_json_schema()
            # Si args_schema es una clase Pydantic, intentar obtener su esquema (Pydantic v2)
            elif hasattr(tool.args_schema, 'model_json_schema'):
                args_schema = tool.args_schema.model_json_schema()
            else:
                # Fallback: intentar usar model_fields para Pydantic v2
                if hasattr(tool.args_schema, 'model_fields'):
                    properties = {}
                    for field_name, field_info in tool.args_schema.model_fields.items():
                        # Excluir campos marcados con exclude=True o que no deberían estar en el esquema de argumentos
                        if not getattr(field_info, 'exclude', False): # Usar getattr para manejar 'exclude' opcional
                            field_type = 'string'  # Tipo por defecto
                            if hasattr(field_info, 'annotation'):
                                # Intentar inferir el tipo de la anotación
                                if field_info.annotation == str:
                                    field_type = 'string'
                                elif field_info.annotation == int:
                                    field_type = 'integer'
                                elif field_info.annotation == bool:
                                    field_type = 'boolean'
                                elif field_info.annotation == list:
                                    field_type = 'array'
                                elif field_info.annotation == dict:
                                    field_type = 'object'

                            properties[field_name] = {
                                'type': field_type,
                                'description': field_info.description or f'Parámetro {field_name}'
                            }
                    args_schema = {"type": "object", "properties": properties}
        except Exception as e:
            tool_name = getattr(tool, 'name', 'Desconocido')
            tool_type = type(tool)
            print(f"Advertencia: Error al obtener el esquema de la herramienta '{tool_name}' de tipo '{tool_type}': {e}. Se usará un esquema vacío.", file=sys.stderr)

    # Si el esquema está vacío pero sabemos que la herramienta necesita argumentos,
    # intentar inferirlos del método _run o de la documentación
    if not args_schema.get('properties') and hasattr(tool, 'name'):
        tool_name = tool.name
        # Para herramientas conocidas, proporcionar esquemas por defecto
        if tool_name == 'file_read_tool':
            args_schema = {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "La ruta del archivo a leer."
                    }
                },
                "required": ["path"]
            }
        elif tool_name == 'file_update_tool':
            args_schema = {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "La ruta del archivo a actualizar."
                    },
                    "content": {
                        "type": "string",
                        "description": "El nuevo contenido del archivo."
                    }
                },
                "required": ["path", "content"]
            }

    # Asegurarse de que cada propiedad en args_schema['properties'] tenga un 'type'
    if 'properties' in args_schema:
        for prop_name, prop_details in args_schema['properties'].items():
            if 'type' not in prop_details:
                # Intentar inferir el tipo o establecer un valor predeterminado
                args_schema['properties'][prop_name]['type'] = 'string'

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": args_schema
        }
    }

class LLMService:
    """Un servicio para interactuar con el modelo LLM a través de LiteLLM."""
    def __init__(self, interrupt_queue: Optional[queue.Queue] = None, workspace_context: Optional[WorkspaceContext] = None): # ¡Modificado! Añadido tipo para workspace_context
        self.console = None
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            print("Error: Ninguna de las variables de entorno OPENROUTER_API_KEY o GOOGLE_API_KEY está configurada.", file=sys.stderr)
            raise ValueError("Ninguna de las variables de entorno OPENROUTER_API_KEY o GOOGLE_API_KEY está configurada.")
        
        self.interrupt_queue = interrupt_queue
        self.tool_executor = ThreadPoolExecutor(max_workers=1)
        self.active_tool_future = None
        self.tool_execution_lock = threading.Lock()

        litellm_api_base = os.getenv("LITELLM_API_BASE")
        if litellm_api_base:
            litellm.api_base = litellm_api_base

        configured_model = os.getenv("LITELLM_MODEL")
        if not configured_model:
            configured_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            if not configured_model.startswith("gemini/"):
                configured_model = f"gemini/{configured_model}"
        else:
            known_prefixes = ("gemini/", "openai/", "openrouter/", "ollama/", "azure/", "anthropic/", "cohere/", "huggingface/")
            if not configured_model.startswith(known_prefixes):
                configured_model = f"openrouter/{configured_model}"
        self.model_name = configured_model

        self.workspace_context = workspace_context # ¡Nuevo! Almacenar el contexto del espacio de trabajo

        self.langchain_tools = get_callable_tools(llm_service_instance=self, interrupt_queue=self.interrupt_queue, workspace_context=self.workspace_context) # ¡Modificado! Pasar self.workspace_context

        self.litellm_tools = [_convert_langchain_tool_to_litellm(tool) for tool in self.langchain_tools]

        self.generation_params = {
            "temperature": 0.4,
        }

        self.call_timestamps = deque()
        self.rate_limit_calls = 10
        self.rate_limit_period = 60

        self.max_history_chars = 120000
        self.max_history_messages = 200
        self.stop_generation_flag = False
        self.history_file_path: Optional[str] = None
        self.conversation_history = []

    def set_console(self, console):
        """Establece la consola para el streaming de salida."""
        self.console = console

    def set_cwd_for_history(self, cwd: str):
        """
        Establece el directorio de trabajo actual y actualiza la ruta del archivo de historial.
        Carga el historial específico para este directorio.
        """
        kogniterm_dir = os.path.join(cwd, ".kogniterm")
        os.makedirs(kogniterm_dir, exist_ok=True)
        self.history_file_path = os.path.join(kogniterm_dir, "kogniterm_history.json")
        self._initialize_memory() # Inicializar memoria para el nuevo directorio
        self.conversation_history = self._load_history() # Cargar historial para el nuevo directorio
        if self.console:
            self.console.print(f"[dim]Historial cargado desde: {self.history_file_path}[/dim]")

    def _build_llm_context_message(self) -> Optional[SystemMessage]:
        """
        Construye un SystemMessage con un resumen dinámico del contexto actual del espacio de trabajo.
        Este mensaje es generado en cada invocación y prepended al historial para el LLM.
        """
        if not self.workspace_context:
            return None

        context_parts = []

        # 1. Información del directorio de trabajo
        cwd = self.workspace_context.get_working_directory()
        context_parts.append(f"Tu directorio de trabajo actual es: `{cwd}`\n")
        logger.debug(f"DEBUG: Directorio de trabajo añadido: {cwd}")

        # 2. Resumen de la estructura de carpetas
        if hasattr(self.workspace_context, 'folder_structure_analyzer') and self.workspace_context.folder_structure_analyzer:
            try:
                folder_structure_root = self.workspace_context.folder_structure_analyzer.get_folder_structure(cwd)
                if folder_structure_root:
                    structure_str = self._format_folder_structure_summary(folder_structure_root, max_depth=4) # Aumentar la profundidad
                    if structure_str:
                        context_parts.append(f"Resumen de la estructura de carpetas (raíz y hasta 4 niveles de profundidad):\n```\n{structure_str}\n```\n")
                        logger.debug("DEBUG: Estructura de carpetas añadida.")
                    else:
                        logger.debug("DEBUG: Estructura de carpetas vacía después de formatear.")
                else:
                    logger.debug("DEBUG: folder_structure_root es None.")
            except Exception as e:
                print(f"Advertencia: No se pudo obtener la estructura de carpetas para el contexto del LLM: {e}", file=sys.stderr)
                logger.debug(f"DEBUG: Error al obtener la estructura de carpetas: {e}")
        else:
            logger.debug("DEBUG: folder_structure_analyzer no está disponible en workspace_context.")

        # 3. Resumen de archivos de configuración
        if hasattr(self.workspace_context, 'config_file_analyzer') and self.workspace_context.config_file_analyzer:
            logger.debug("DEBUG: config_file_analyzer está disponible.")
            try:
                # Forzar un re-análisis para tener los datos más recientes
                self.workspace_context.config_file_analyzer.find_and_parse_config_files(cwd)
                config_files_data = self.workspace_context.config_file_analyzer.config_files
                
                logger.debug(f"DEBUG: Archivos de configuración detectados por analyzer: {config_files_data.keys()}")

                relevant_configs = {}
                for file_name, data in config_files_data.items():
                    logger.debug(f"DEBUG: Procesando archivo de configuración: {file_name}, data: {data}")
                    if data: # Solo incluir si hay datos parseados
                        # Para evitar enviar JSONs gigantes, podemos resumir
                        if file_name == "package.json" and isinstance(data, dict) and data.get("dependencies"):
                            data = {k:v for k,v in data.items() if k not in ["devDependencies", "optionalDependencies"]}
                            data["dependencies_count"] = len(data.get("dependencies", {}))
                            if "dependencies" in data: del data["dependencies"]
                        
                        relevant_configs[file_name] = data
                        logger.debug(f"DEBUG: Archivo de configuración '{file_name}' añadido a relevant_configs.")
                    else:
                        logger.debug(f"DEBUG: Archivo de configuración '{file_name}' no tiene datos parseados o es vacío.")

                if relevant_configs:
                    config_summary = "\n".join([f"- {name}: {json.dumps(data, indent=2, ensure_ascii=False)}" for name, data in relevant_configs.items()])
                    if config_summary:
                        context_parts.append(f"Archivos de configuración detectados (contenido resumido):\n```json\n{config_summary}\n```\n")
                        logger.debug("DEBUG: Archivos de configuración añadidos al contexto.")
                    else:
                        logger.debug("DEBUG: Resumen de archivos de configuración vacío después de formatear.")
                else:
                    logger.debug("DEBUG: No se encontraron archivos de configuración relevantes.")
            except Exception as e:
                print(f"Advertencia: No se pudo obtener el resumen de archivos de configuración para el contexto del LLM: {e}", file=sys.stderr)
                logger.debug(f"DEBUG: Error al obtener el resumen de archivos de configuración: {e}")
        else:
            logger.debug("DEBUG: config_file_analyzer no está disponible en workspace_context.")

        # 4. Estado de Git
        if hasattr(self.workspace_context, 'git_interaction_module') and self.workspace_context.git_interaction_module:
            try:
                git_status_raw = self.workspace_context.git_interaction_module.get_git_status()
                git_status: str = ""

                git_status_lines: list[str] = []
                if git_status_raw is None:
                    git_status_lines = []
                elif isinstance(git_status_raw, str):
                    git_status_lines = git_status_raw.splitlines()
                elif isinstance(git_status_raw, (list, tuple, set)):
                    git_status_lines = [str(item) for item in list(git_status_raw)]
                else:
                    git_status_lines = [str(git_status_raw)]
                
                git_status = "\n".join(git_status_lines)

                if git_status:
                    lines = git_status.strip().split('\n')
                    if len(lines) > 10:
                        git_status = "\n".join(lines[:10]) + "\n... (salida de git truncada para brevedad)"
                    context_parts.append(f"Estado del repositorio Git (cambios locales):\n```\n{git_status}\n```\n")
                    logger.debug("DEBUG: Estado de Git añadido.")
                else:
                    logger.debug("DEBUG: Estado de Git vacío.")
            except Exception as e:
                print(f"Advertencia: No se pudo obtener el estado de Git para el contexto del LLM: {e}", file=sys.stderr)
                logger.debug(f"DEBUG: Error al obtener el estado de Git: {e}")
        else:
            logger.debug("DEBUG: git_interaction_module no está disponible en workspace_context.")
        
        if context_parts:
            full_context_message_content = "### Contexto Actual del Proyecto:\n\n" + \
                                           "**¡ATENCIÓN!** Ya tienes un resumen COMPLETO de la estructura de carpetas del proyecto. **NO NECESITAS** usar herramientas de exploración de archivos (como `list_directory` o `read_file`) para obtener esta información nuevamente. Consulta el contexto proporcionado aquí. Solo usa esas herramientas si necesitas detalles MUY específicos de un archivo o directorio que no estén cubiertos en este resumen.\n\n" + \
                                           "Tu directorio de trabajo actual es: `" + cwd + "`\\n" + \
                                           "\\n".join(context_parts[1:]) # Excluir la primera parte que ya se añadió
            return SystemMessage(content=full_context_message_content)
        logger.debug("DEBUG: No se construyó ningún contexto para el LLM.")
        return None

    def _format_folder_structure_summary(self, node: Union[FileNode, DirectoryNode], max_depth: int = 2, current_depth: int = 0, indent: int = 2) -> str:
        """
        Formatea una estructura de carpetas (objeto DirectoryNode o FileNode) de manera concisa para el LLM.
        Se detiene en max_depth para evitar mensajes excesivamente largos.
        """
        if current_depth > max_depth:
            return ""

        lines = []
        prefix = " " * (current_depth * indent)

        if node['type'] == 'directory':
            lines.append(f"{prefix}📁 {node['name']}/")
            if current_depth < max_depth:
                for child in node['children']:
                    child_str = self._format_folder_structure_summary(child, max_depth, current_depth + 1, indent)
                    if child_str:
                        lines.append(child_str)
        elif node['type'] == 'file':
            lines.append(f"{prefix}📄 {node['name']}")

        return "\n".join(filter(None, lines))

    def _initialize_memory(self):
        """Inicializa la memoria si no existe."""
        memory_init_tool = self.get_tool("memory_init")
        if memory_init_tool:
            try:
                # La herramienta memory_init puede necesitar acceso al history_file_path
                # Si es así, se deberá pasar como argumento o hacer que la herramienta lo obtenga de llm_service.
                memory_init_tool.invoke({"history_file_path": self.history_file_path})
            except Exception as e:
                # print(f"Advertencia: Error al inicializar la memoria: {e}", file=sys.stderr)
                pass # No es crítico si falla la inicialización de memoria

    def _load_history(self) -> list:
        """Carga el historial de conversación desde un archivo JSON."""
        if not self.history_file_path:
            return [] # No hay ruta de historial configurada

        if os.path.exists(self.history_file_path):
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
                                    if isinstance(tc['args'], dict):
                                        formatted_tool_calls.append({'name': tc['name'], 'args': tc['args'], 'id': tc.get('id')})
                                    else:
                                        try:
                                            parsed_args = json.loads(tc['args'])
                                            formatted_tool_calls.append({'name': tc['name'], 'args': parsed_args, 'id': tc.get('id')})
                                        except (json.JSONDecodeError, TypeError):
                                            print(f"Advertencia: No se pudieron parsear los argumentos de la herramienta: {tc['args']}", file=sys.stderr)
                                            formatted_tool_calls.append({'name': tc['name'], 'args': {}, 'id': tc.get('id')})
                                loaded_history.append(AIMessage(content=item['content'], tool_calls=formatted_tool_calls))
                            else:
                                loaded_history.append(AIMessage(content=item['content']))
                        elif item['type'] == 'tool':
                            loaded_history.append(ToolMessage(content=item['content'], tool_call_id=item['tool_call_id']))
                        elif item['type'] == 'system':
                            loaded_history.append(SystemMessage(content=item['content']))
                        else:
                            pass
                    
                    return loaded_history
            except json.JSONDecodeError as e:
                print(f"Error al decodificar el historial JSON desde {self.history_file_path}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
            except Exception as e:
                print(f"Error inesperado al cargar el historial desde {self.history_file_path}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
        return []

    def _save_history(self, history: list):
        """Guarda el historial de conversación en un archivo JSON."""
        if not self.history_file_path:
            return # No hay ruta de historial configurada

        try:
            serializable_history = []
            for msg in history:
                if isinstance(msg, HumanMessage):
                    serializable_history.append({'type': 'human', 'content': msg.content})
                elif isinstance(msg, AIMessage):
                    if msg.tool_calls:
                        serializable_history.append({'type': 'ai', 'content': msg.content, 'tool_calls': [{'name': tc['name'], 'args': tc['args'], 'id': tc.get('id')} for tc in msg.tool_calls]})
                    else:
                        serializable_history.append({'type': 'ai', 'content': msg.content})
                elif isinstance(msg, ToolMessage):
                    serializable_history.append({'type': 'tool', 'content': msg.content, 'tool_call_id': msg.tool_call_id})
                elif isinstance(msg, SystemMessage):
                    serializable_history.append({'type': 'system', 'content': msg.content})
                else:
                    continue # Saltar mensajes desconocidos

            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar el historial en {self.history_file_path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

    def invoke(self, history: list, system_message: Optional[str] = None, interrupt_queue: Optional[queue.Queue] = None):
        """Invoca el modelo LLM con un historial de conversación y un mensaje de sistema opcional.

        Args:
            history: El historial completo de la conversación en el formato de LangChain.
            system_message: Un mensaje de sistema opcional para guiar al modelo.
            interrupt_queue: Una cola para verificar si se ha solicitado una interrupción.

        Returns:
            La respuesta del modelo, que puede incluir texto o llamadas a herramientas.
        """
        current_time = time.time()
        while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
            self.call_timestamps.popleft()

        if len(self.call_timestamps) >= self.rate_limit_calls:
            time_to_wait = self.rate_limit_period - (current_time - self.call_timestamps[0])
            if time_to_wait > 0:
                print(f"DEBUG: Rate limit hit. Waiting for {time_to_wait:.2f} seconds...", file=sys.stderr)
                time.sleep(time_to_wait)
                current_time = time.time()
                print(f"DEBUG: Finished waiting for rate limit.", file=sys.stderr)
                while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
                    self.call_timestamps.popleft()

        self.stop_generation_flag = False

        # 1. Construir todos los mensajes de sistema iniciales
        all_initial_system_messages_for_llm = []
        
        # Añadir el contexto dinámico del espacio de trabajo si está disponible
        workspace_context_message = self._build_llm_context_message()
        if workspace_context_message:
            all_initial_system_messages_for_llm.append(_to_litellm_message(workspace_context_message))

        if system_message:
            # Si ya hay un system_message del workspace_context, concatenar el system_message proporcionado
            if all_initial_system_messages_for_llm and all_initial_system_messages_for_llm[0]["role"] == "system":
                all_initial_system_messages_for_llm[0]["content"] += f"\n\n{system_message}"
            else:
                all_initial_system_messages_for_llm.append({"role": "system", "content": system_message})
        
        # 2. Convertir el historial de conversación (sin los mensajes de sistema estáticos/dinámicos)
        litellm_conversation_history = [_to_litellm_message(msg) for msg in history]

        # 3. Filtrar mensajes de asistente vacíos del historial de conversación
        filtered_conversation_messages = []
        for msg in litellm_conversation_history:
            is_assistant = msg.get("role") == "assistant"
            has_content = msg.get("content") and str(msg.get("content")).strip()
            has_tool_calls = msg.get("tool_calls")
            if is_assistant and not has_content and not has_tool_calls:
                continue
            filtered_conversation_messages.append(msg)
        
        # 4. Combinar todos los mensajes para el LLM
        litellm_messages = all_initial_system_messages_for_llm + filtered_conversation_messages

        # Añadir log de depuración para el system_message final
        final_system_message_content = ""
        for msg in all_initial_system_messages_for_llm:
            if msg["role"] == "system":
                final_system_message_content += msg["content"]
        if final_system_message_content:
            logger.debug(f"System Message final enviado al LLM:\n{final_system_message_content[:1000]}... (truncado para log)")

        # 5. Lógica de truncamiento y resumen del historial
        # Definir un mínimo de mensajes a mantener, que incluya todos los system messages + al menos 1 conversacional
        min_messages_to_keep_in_conversation = 1 # Mínimo de mensajes conversacionales a intentar mantener
        
        # Contar los mensajes actuales en el historial de conversación (excluyendo system messages)
        current_conversation_messages_count = len(filtered_conversation_messages)

        # Truncamiento/Resumen basado en `filtered_conversation_messages`
        # La lógica de resumen debe operar sobre `self.conversation_history` (LangChain messages)
        # y no debe afectar `all_initial_system_messages_for_llm`.
        
        # Calculamos la longitud total de `litellm_messages` (incluyendo system messages) para la decisión de resumen/truncamiento
        total_litellm_messages_length = sum(len(json.dumps(msg, ensure_ascii=False)) for msg in litellm_messages)
        
        if (len(filtered_conversation_messages) > self.max_history_messages or
            total_litellm_messages_length > self.max_history_chars) and \
           len(filtered_conversation_messages) > min_messages_to_keep_in_conversation:
            
            if self.console:
                self.console.print("[yellow]El historial de conversación es demasiado largo. Intentando resumir...[/yellow]")
            
            summary = self.summarize_conversation_history() # Opera en self.conversation_history
            if summary:
                max_summary_length = min(2000, self.max_history_chars // 4)
                if len(summary) > max_summary_length:
                    summary = summary[:max_summary_length] + "... [Resumen truncado para evitar bucles]"

                # El nuevo historial de conversación incluirá el resumen y los últimos mensajes relevantes.
                new_conversation_history_litellm = []
                new_conversation_history_litellm.append({"role": "system", "content": f"Resumen de la conversación anterior: {summary}"})
                
                # Seleccionar los últimos 5 mensajes (o menos si no hay tantos) de filtered_conversation_messages
                messages_to_keep_from_conversation = filtered_conversation_messages[-5:] 
                new_conversation_history_litellm.extend(messages_to_keep_from_conversation)
                
                # Actualizar `litellm_messages` con los system messages iniciales y el nuevo historial resumido
                litellm_messages = all_initial_system_messages_for_llm + new_conversation_history_litellm

                # Actualizar self.conversation_history para reflejar el resumen (en formato LangChain)
                # Esto es crucial para futuras llamadas a summarize_conversation_history
                # Solo guardamos el historial de conversación real, no los mensajes de contexto dinámicos.
                self.conversation_history = [
                    _from_litellm_message(msg) for msg in new_conversation_history_litellm
                ]
                self._save_history(self.conversation_history) # Guardar el historial de conversación resumido
                if self.console:
                    self.console.print("[green]Historial resumido y actualizado.[/green]")
            else:
                if self.console:
                    self.console.print("[red]No se pudo resumir el historial. Se procederá con el truncamiento.[/red]")
 
        # Post-procesamiento del historial para eliminar ToolMessages huérfanos
        # Esto se aplica a `litellm_messages` después del resumen/truncamiento.
        processed_litellm_messages = []
        tool_call_ids_in_aimessages = set()
        
        # Primero, identificar todos los tool_call_ids válidos de AIMessages
        for msg in litellm_messages:
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    if 'id' in tc:
                        tool_call_ids_in_aimessages.add(tc['id'])
        
        # Luego, reconstruir la lista filtrando ToolMessages huérfanos
        for msg in litellm_messages:
            if msg.get('role') == 'tool':
                tool_call_id = msg.get('tool_call_id')
                if tool_call_id and tool_call_id not in tool_call_ids_in_aimessages:
                    continue # Eliminar ToolMessage huérfano
            processed_litellm_messages.append(msg)
        
        litellm_messages = processed_litellm_messages

        # Truncamiento estándar si aún es necesario después del resumen
        # Ahora, solo truncamos la parte conversacional, manteniendo los system messages iniciales.
        current_conversational_messages = [msg for msg in litellm_messages if msg.get('role') != 'system']
        num_system_messages = len(all_initial_system_messages_for_llm)

        while (len(current_conversational_messages) > self.max_history_messages or
               sum(len(json.dumps(msg, ensure_ascii=False)) for msg in litellm_messages) > self.max_history_chars) and \
              len(current_conversational_messages) > min_messages_to_keep_in_conversation:
            
            # Remove from the oldest conversational messages
            if current_conversational_messages:
                removed_msg = current_conversational_messages.pop(0)
                # Recalculate total length for the next iteration
                litellm_messages = all_initial_system_messages_for_llm + current_conversational_messages
            else:
                break # No conversational messages left to truncate

        # Reconstruct litellm_messages with the truncated conversational part
        litellm_messages = all_initial_system_messages_for_llm + current_conversational_messages
        
        try:
            completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages, # Usar el historial final procesado
                "tools": self.litellm_tools,
                "stream": True,
                "api_key": self.api_key,
                "temperature": self.generation_params.get("temperature", 0.7),
            }
            if "top_p" in self.generation_params:
                completion_kwargs["top_p"] = self.generation_params["top_p"]
            if "top_k" in self.generation_params:
                completion_kwargs["top_k"] = self.generation_params["top_k"]

            start_time = time.perf_counter()
            response_generator = completion(
                **completion_kwargs
            )
            end_time = time.perf_counter()
            self.call_timestamps.append(time.time())
            
            full_response_content = ""
            tool_calls = []
            for chunk in response_generator:
                # Verificar la cola de interrupción
                if interrupt_queue and not interrupt_queue.empty():
                    while not interrupt_queue.empty(): # Vaciar la cola
                        interrupt_queue.get_nowait()
                    self.stop_generation_flag = True
                    print("DEBUG: Interrupción detectada desde la cola.", file=sys.stderr) # Para depuración
                    break # Salir del bucle de chunks

                if self.stop_generation_flag:
                    print("DEBUG: Generación detenida por bandera.", file=sys.stderr)
                    break

                choices = getattr(chunk, 'choices', None)
                if not choices or not isinstance(choices, list) or not choices[0]:
                    continue
                
                choice = choices[0]
                delta = getattr(choice, 'delta', None)
                if not delta:
                    continue
                
                if getattr(delta, 'content', None) is not None:
                    full_response_content += str(delta.content)
                    yield str(delta.content)
                
                tool_calls_from_delta = getattr(delta, 'tool_calls', None)
                if tool_calls_from_delta is not None:
                    # Acumular tool_calls, no emitir AIMessage aquí
                    for tc in tool_calls_from_delta:
                        if tc.index >= len(tool_calls):
                            tool_calls.extend([{"id": "", "function": {"name": "", "arguments": ""}}] * (tc.index - len(tool_calls) + 1))
                        
                        # Solo actualizar el ID si no está vacío y es diferente, o si es la primera vez que se asigna
                        if getattr(tc, 'id', None) is not None and (not tool_calls[tc.index]["id"] or tool_calls[tc.index]["id"] != tc.id):
                            tool_calls[tc.index]["id"] = tc.id
                        if getattr(tc, 'function', None) is not None:
                            if getattr(tc.function, 'name', None) is not None:
                                tool_calls[tc.index]["function"]["name"] = tc.function.name
                            if getattr(tc.function, 'arguments', None) is not None:
                                tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
            
            if self.stop_generation_flag:
                # Si se interrumpe, el AIMessage final se construye con el mensaje de interrupción
                yield AIMessage(content="Generación de respuesta interrumpida por el usuario. 🛑")
            elif tool_calls:
                formatted_tool_calls = []
                for tc in tool_calls:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    formatted_tool_calls.append({
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "args": args
                    })
                # El AIMessage final incluye el contenido acumulado y los tool_calls
                yield AIMessage(content=full_response_content, tool_calls=formatted_tool_calls)
            else:
                # El AIMessage final incluye solo el contenido acumulado
                yield AIMessage(content=full_response_content)

        except Exception as e:
            import traceback
            print(f"Error de LiteLLM: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            error_message = f"¡Ups! 😵 Ocurrió un error inesperado al comunicarme con el modelo (LiteLLM): {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!"""
            yield AIMessage(content=error_message)

    def summarize_conversation_history(self) -> Optional[str]:
        """Resume el historial de conversación actual utilizando el modelo LLM a través de LiteLLM."""
        if not self.conversation_history:
            return None
        
        # Convertir el historial a mensajes de LiteLLM para aplicar la lógica de filtrado
        litellm_history_for_summary = [_to_litellm_message(msg) for msg in self.conversation_history]

        # Aplicar la lógica de post-procesamiento para eliminar ToolMessages huérfanos
        processed_litellm_history = []
        tool_call_ids_in_aimessages = set()
        
        for msg in litellm_history_for_summary:
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    if 'id' in tc:
                        tool_call_ids_in_aimessages.add(tc['id'])
        
        for msg in litellm_history_for_summary:
            if msg.get('role') == 'tool':
                tool_call_id = msg.get('tool_call_id')
                if tool_call_id and tool_call_id not in tool_call_ids_in_aimessages:
                    continue
            processed_litellm_history.append(msg)
        
        # Convertir de nuevo a mensajes de LangChain para añadir el summarize_prompt
        langchain_processed_history = [_from_litellm_message(msg) for msg in processed_litellm_history]

        summarize_prompt = HumanMessage(content="Por favor, resume la siguiente conversación de manera CONCISA pero COMPLETA. Captura los puntos clave, decisiones tomadas, tareas pendientes y contexto esencial. Limita el resumen a máximo 1500 caracteres para evitar problemas de longitud. Sé específico pero económico con las palabras.")
        
        temp_history_for_summary = langchain_processed_history + [summarize_prompt]

        try:
            litellm_messages_for_summary = [_to_litellm_message(msg) for msg in temp_history_for_summary]
            
            litellm_generation_params = self.generation_params

            summary_completion_kwargs = {
                "model": self.model_name,
                "messages": litellm_messages_for_summary,
                "api_key": self.api_key,
                "temperature": litellm_generation_params.get("temperature", 0.7),
                "stream": False,
            }
            if "top_p" in litellm_generation_params:
                summary_completion_kwargs["top_p"] = litellm_generation_params["top_p"]
            if "top_k" in litellm_generation_params:
                summary_completion_kwargs["top_k"] = litellm_generation_params["top_k"]

            response = completion(
                **summary_completion_kwargs
            )
            
            # Asegurarse de que la respuesta no sea un generador inesperado y tenga el atributo 'choices'
            try:
                choices = getattr(response, 'choices', None)
                if choices is not None:
                    # Convertir a lista si es iterable
                    if hasattr(choices, '__iter__'):
                        try:
                            choices_list = list(choices)
                            if choices_list and len(choices_list) > 0:
                                first_choice = choices_list[0]
                                message = getattr(first_choice, 'message', None)
                                if message is not None:
                                    content = getattr(message, 'content', None)
                                    if content is not None:
                                        return str(content)
                        except (TypeError, AttributeError, IndexError):
                            pass
                    else:
                        # Si no es iterable, intentar acceso directo
                        if hasattr(choices, '__getitem__') and len(choices) > 0:
                            first_choice = choices[0]
                            message = getattr(first_choice, 'message', None)
                            if message is not None:
                                content = getattr(message, 'content', None)
                                if content is not None:
                                    return str(content)
            except Exception:
                pass
            return None
        except Exception as e:
            import traceback
            print(f"Error de LiteLLM al resumir el historial: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return f"¡Ups! 😵 Ocurrió un error inesperado al resumir el historial con LiteLLM: {e}. Por favor, revisa los logs para más detalles. ¡Intentemos de nuevo!"""

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """Encuentra y devuelve una herramienta de LangChain por su nombre."""
        for tool in self.langchain_tools:
            if tool.name == tool_name:
                return tool
        return None

    def _invoke_tool_with_interrupt(self, tool: BaseTool, tool_args: dict) -> Any:
        """Invoca una herramienta en un hilo separado, permitiendo la interrupción."""
        with self.tool_execution_lock:
            if self.active_tool_future is not None and self.active_tool_future.running():
                raise RuntimeError("Ya hay una herramienta en ejecución. No se puede iniciar otra.")
            
            # Usar functools.partial para pasar los argumentos a tool.invoke
            # Esto asegura que la función que se ejecuta en el hilo sea simple y reciba los args correctos
            future = self.tool_executor.submit(tool.invoke, tool_args)
            self.active_tool_future = future

        try:
            while True:
                try:
                    # Esperar el resultado de la tarea con un timeout corto
                    return future.result(timeout=0.01) 
                except TimeoutError:
                    # Si hay un timeout, verificar la cola de interrupción
                    if self.interrupt_queue and not self.interrupt_queue.empty():
                        print("DEBUG: _invoke_tool_with_interrupt - Interrupción detectada en la cola (via TimeoutError).", file=sys.stderr)
                        self.interrupt_queue.get() # Consumir la señal
                        if future.running():
                            print("DEBUG: _invoke_tool_with_interrupt - Intentando cancelar la tarea (via TimeoutError).", file=sys.stderr)
                            future.cancel() # Intentar cancelar la tarea
                            print("DEBUG: _invoke_tool_with_interrupt - Lanzando InterruptedError (via TimeoutError).", file=sys.stderr)
                            raise InterruptedError("Ejecución de herramienta interrumpida por el usuario.")
                except InterruptedError:
                    raise # Re-lanzar la excepción de interrupción
                except Exception as e:
                    # Capturar cualquier otra excepción de la herramienta
                    raise e
        except InterruptedError:
            raise # Re-lanzar la excepción de interrupción
        except Exception as e:
            # Capturar cualquier otra excepción de la herramienta
            raise e
        finally:
            with self.tool_execution_lock:
                if self.active_tool_future is future:
                    self.active_tool_future = None # Limpiar la referencia a la tarea activa
