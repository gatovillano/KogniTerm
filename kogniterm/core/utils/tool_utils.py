import sys
import re
import hashlib
from copy import deepcopy
from typing import Dict, Any, Optional
from langchain_core.tools import BaseTool


CONTENT_REQUIRED_EDITOR_ACTIONS = {
    'insert_line',
    'insert_after_match',
    'insert_before_match',
    'prepend_content',
    'append_content',
    'full_replacement',
}


def sanitize_tool_name(name: Optional[str]) -> str:
    """
    Sanea el nombre de una herramienta o parámetro para cumplir estrictamente con los requisitos
    de las APIs de LLM (Google AI Studio, Vertex AI, Gemini, OpenAI, Anthropic, etc.):
    - Debe comenzar con una letra [a-zA-Z] o un guion bajo [_].
    - Solo puede contener caracteres alfanuméricos [a-zA-Z0-9] y guiones bajos [_].
    - Convierte guiones (-), puntos (.), espacios ( ), dos puntos (:), barras (/), etc. en guiones bajos [_].
    - Longitud máxima de 64 caracteres.
    """
    if not name or not isinstance(name, str):
        return "_unnamed_function"

    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    sanitized = re.sub(r'_+', '_', sanitized)

    if not sanitized or not re.match(r'^[a-zA-Z_]', sanitized):
        sanitized = f"_{sanitized}"

    if len(sanitized) > 64:
        name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:6]
        sanitized = f"{sanitized[:57]}_{name_hash}"

    return sanitized


def tool_requires_content_for_confirmation(tool_name: str, tool_args: Dict[str, Any]) -> bool:
    """Indica si la herramienta necesita `content` al reintentarse tras confirmación."""
    if tool_name == 'file_update_tool':
        return True

    if tool_name not in {
        'advanced_file_editor',
        'advanced_file_editor_tool',
        'sophisticated_editor_tool',
    }:
        return False

    return tool_args.get('action') in CONTENT_REQUIRED_EDITOR_ACTIONS


def normalize_tool_parameters_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza JSON Schema para proveedores estrictos como Google AI Studio / Vertex."""

    def _normalize(node: Any) -> Any:
        if isinstance(node, list):
            return [_normalize(item) for item in node]

        if not isinstance(node, dict):
            return node

        node = deepcopy(node)
        node.pop("title", None)
        node.pop("additionalProperties", None)
        node.pop("definitions", None)
        node.pop("$defs", None)
        node.pop("default", None)

        properties = node.get("properties")
        if isinstance(properties, dict):
            clean_props = {}
            for prop_name, prop_schema in properties.items():
                clean_name = sanitize_tool_name(prop_name)
                clean_props[clean_name] = _normalize(prop_schema) if isinstance(prop_schema, dict) else {"type": "string"}
            node["properties"] = clean_props

        if "required" in node and isinstance(node["required"], list):
            node["required"] = [sanitize_tool_name(r) for r in node["required"] if isinstance(r, str)]

        for keyword in ("anyOf", "oneOf", "allOf"):
            variants = node.get(keyword)
            if isinstance(variants, list):
                node[keyword] = [
                    _normalize(variant) if isinstance(variant, dict) else {"type": "string"}
                    for variant in variants
                ]

        if "items" in node:
            items = node["items"]
            if isinstance(items, dict):
                node["items"] = _normalize(items)
            elif isinstance(items, list):
                normalized_items = [
                    _normalize(item) if isinstance(item, dict) else {"type": "string"}
                    for item in items
                ]
                node["items"] = normalized_items[0] if normalized_items else {"type": "string"}
            else:
                node["items"] = {"type": "string"}

        if "type" not in node:
            if "properties" in node:
                node["type"] = "object"
            elif "items" in node:
                node["type"] = "array"
            else:
                node["type"] = "string"

        if node.get("type") == "object":
            node.setdefault("properties", {})
        elif node.get("type") == "array":
            items = node.get("items")
            if not isinstance(items, dict):
                node["items"] = {"type": "string"}
            elif "type" not in items:
                node["items"]["type"] = "string"

        return node

    normalized = _normalize(schema or {"type": "object", "properties": {}})
    if not isinstance(normalized, dict):
        normalized = {"type": "object", "properties": {}}

    normalized["type"] = "object"
    normalized.setdefault("properties", {})
    normalized.setdefault("required", [])
    return normalized

def convert_langchain_tool_to_litellm(tool: BaseTool) -> Dict[str, Any]:
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
                        # como account_id, workspace_id, telegram_id, thread_id
                        if field_name not in ["account_id", "workspace_id", "telegram_id", "thread_id"] and not getattr(field_info, 'exclude', False):
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

    args_schema = normalize_tool_parameters_schema(args_schema)

    raw_tool_name = getattr(tool, 'name', None) or getattr(tool, '__name__', str(tool))
    clean_tool_name = sanitize_tool_name(raw_tool_name)
    tool_desc = getattr(tool, 'description', None) or getattr(tool, '__doc__', '') or ''
    if not isinstance(tool_desc, str):
        tool_desc = str(tool_desc)

    return {
        "type": "function",
        "function": {
            "name": clean_tool_name,
            "description": tool_desc[:1024] if tool_desc else f"Herramienta {clean_tool_name}",
            "parameters": args_schema
        }
    }

def get_tool_action_description(
    tool: Any,
    tool_args: Dict[str, Any],
    tool_name: Optional[str] = None,
) -> str:
    """Obtiene una descripción legible de la acción que realiza la herramienta."""
    if not isinstance(tool_args, dict):
        tool_args = {}

    # 1. Resolver el nombre de la herramienta de forma flexible
    resolved_name = (
        tool_name
        or getattr(tool, "name", None)
        or getattr(tool, "__name__", None)
        or (getattr(tool, "_tool_definition", None) and getattr(tool._tool_definition, "name", None))
        or (tool if isinstance(tool, str) else "")
    )
    clean_name = str(resolved_name or "").lower().strip()

    # 2. Intentar usar el método propio get_action_description si existe
    action_fn = (
        getattr(tool, "get_action_description", None)
        or (getattr(tool, "_tool_definition", None) and getattr(tool._tool_definition, "get_action_description", None))
    )
    if callable(action_fn):
        try:
            desc = action_fn(**tool_args)
            if desc and isinstance(desc, str) and desc.strip():
                return desc.strip()
        except Exception:
            pass

    # 3. Extraer argumentos clave comunes
    raw_path = (
        tool_args.get("path")
        or tool_args.get("file_path")
        or tool_args.get("filepath")
        or tool_args.get("file")
        or tool_args.get("filename")
        or tool_args.get("target_file")
        or tool_args.get("source_file")
        or tool_args.get("dest")
        or tool_args.get("destination")
        or tool_args.get("dir_path")
        or tool_args.get("directory")
        or ""
    )
    if isinstance(raw_path, (list, tuple)) and raw_path:
        path = str(raw_path[0])
    else:
        path = str(raw_path) if raw_path else ""

    query = (
        tool_args.get("query")
        or tool_args.get("search_query")
        or tool_args.get("q")
        or tool_args.get("pattern")
        or tool_args.get("text")
        or tool_args.get("terms")
        or tool_args.get("target")
        or tool_args.get("regex_pattern")
        or tool_args.get("target_content")
        or ""
    )
    if isinstance(query, (list, tuple)) and query:
        query = str(query[0])
    else:
        query = str(query) if query else ""

    url = tool_args.get("url") or tool_args.get("uri") or tool_args.get("link") or ""
    if url:
        url = str(url)

    cmd = tool_args.get("command") or tool_args.get("cmd") or ""
    if cmd:
        cmd = str(cmd)

    # 4. Inferencia según tipo de herramienta

    # A) Búsquedas web y obtención de contenido web
    if (
        "web_search" in clean_name
        or "tavily_search" in clean_name
        or "duckduckgo" in clean_name
        or "google_search" in clean_name
        or ("web" in clean_name and "search" in clean_name)
    ):
        if query:
            return f"Buscando en la web: '{query}'"
        return "Buscando en la web"

    if (
        "web_fetch" in clean_name
        or "web_scraping" in clean_name
        or ("web" in clean_name and any(k in clean_name for k in ("fetch", "scrape", "get", "read")))
        or "fetch_url" in clean_name
    ):
        if url:
            return f"Consultando web: {url}"
        return "Consultando página web"

    if "browser" in clean_name or "navigate" in clean_name:
        if url:
            return f"Navegando a: {url}"
        action = tool_args.get("action")
        if action:
            return f"Navegador: {action}"
        return "Navegando en la web"

    # B) Operaciones de archivos
    # B.1) Lectura de archivo
    if any(k in clean_name for k in ("read_file", "file_read", "cat", "view_file", "load_file")):
        if path:
            start = tool_args.get("start_line") or tool_args.get("offset")
            end = tool_args.get("end_line")
            if start and end:
                return f"Leyendo archivo: {path} (líneas {start}-{end})"
            elif start:
                return f"Leyendo archivo: {path} (desde línea {start})"
            return f"Leyendo archivo: {path}"
        return "Leyendo archivo"

    # B.2) Creación de archivo
    if any(k in clean_name for k in ("create_file", "file_create", "new_file", "touch")):
        if path:
            return f"Creando archivo: {path}"
        return "Creando archivo"

    # B.3) Escritura en archivo
    if any(k in clean_name for k in ("write_file", "file_write")):
        if path:
            return f"Escribiendo en archivo: {path}"
        return "Escribiendo en archivo"

    # B.4) Edición / Actualización / Reemplazo en archivo
    if any(
        k in clean_name
        for k in (
            "edit_file",
            "file_editor",
            "advanced_file_editor",
            "file_update",
            "update_file",
            "replace_all",
            "replace_lines",
            "patch",
            "modify_file",
        )
    ):
        action = tool_args.get("action")
        if path and action:
            return f"Editando archivo ({action}): {path}"
        elif path:
            if "replace" in clean_name:
                return f"Reemplazando en archivo: {path}"
            elif "update" in clean_name:
                return f"Actualizando archivo: {path}"
            return f"Editando archivo: {path}"
        return "Editando archivo"

    # B.5) Eliminación de archivo
    if any(k in clean_name for k in ("delete_file", "file_delete", "remove_file", "rm_file")):
        if path:
            return f"Eliminando archivo: {path}"
        return "Eliminando archivo"

    # B.6) Listado de directorio
    if any(
        k in clean_name
        for k in (
            "list_dir",
            "file_list",
            "list_directory",
            "directory_list",
            "read_directory",
            "file_read_directory",
        )
    ):
        target_dir = path or tool_args.get("directory") or "."
        return f"Listando directorio: {target_dir}"

    # B.7) Búsqueda en archivos o código
    if (
        any(
            k in clean_name
            for k in (
                "search_in_file",
                "file_search",
                "glob_search",
                "codebase_search",
                "find_by_name",
                "grep_search",
            )
        )
        or ("search" in clean_name and any(k in clean_name for k in ("file", "code", "dir")))
    ):
        if path and query:
            return f"Buscando '{query}' en {path}"
        elif path:
            return f"Buscando archivos en {path}"
        elif query:
            return f"Buscando código: '{query}'"
        return "Buscando en archivos..."

    # C) Búsquedas generales
    if "search" in clean_name or "find" in clean_name:
        if path and query:
            return f"Buscando '{query}' en {path}"
        elif query:
            return f"Buscando: '{query}'"
        elif path:
            return f"Buscando en {path}"
        return "Buscando..."

    # D) Comandos de terminal
    if any(
        k in clean_name
        for k in (
            "execute_command",
            "run_command",
            "bash",
            "terminal",
            "cmd_execution",
            "shell",
        )
    ):
        if cmd:
            preview = cmd if len(cmd) <= 50 else cmd[:47] + "..."
            return f"Ejecutando comando: {preview}"
        return "Ejecutando comando de terminal"

    # E) Ejecución de Python
    if any(k in clean_name for k in ("python_executor", "python_exec", "python")):
        code = tool_args.get("code") or ""
        if code:
            single = str(code).strip().replace("\n", " ")
            preview = single if len(single) <= 40 else single[:37] + "..."
            return f"Ejecutando Python: {preview}"
        return "Ejecutando código Python"

    # F) Preguntas e interacción
    if "ask_question" in clean_name:
        q = tool_args.get("question") or ""
        if not q and tool_args.get("questions") and isinstance(tool_args["questions"], list):
            first_q = tool_args["questions"][0]
            q = first_q.get("question", "") if isinstance(first_q, dict) else str(first_q)
        if q:
            preview = q if len(q) <= 50 else q[:47] + "..."
            return f"Preguntando al usuario: '{preview}'"
        return "Preguntando al usuario"

    # G) Tareas en segundo plano
    if "background_task" in clean_name or "manage_task" in clean_name:
        action = tool_args.get("action") or ""
        task_id = tool_args.get("task_id") or tool_args.get("TaskId") or ""
        if action and task_id:
            return f"Gestionando tarea {task_id} ({action})"
        elif action:
            return f"Gestionando tarea en segundo plano ({action})"
        return "Gestionando tarea en segundo plano"

    # 5. Fallback contextual por presencia de parámetros si no hubo coincidencia previa
    if path:
        return f"Operando archivo: {path}"
    if query:
        return f"Buscando: '{query}'"
    if url:
        return f"Consultando web: {url}"
    if cmd:
        preview = cmd if len(cmd) <= 50 else cmd[:47] + "..."
        return f"Ejecutando comando: {preview}"

    return ""

