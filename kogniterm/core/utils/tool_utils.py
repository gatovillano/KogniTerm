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

def get_tool_action_description(tool: Any, tool_args: Dict[str, Any]) -> str:
    """Obtiene una descripción legible de la acción que realiza la herramienta."""
    # 1. Intentar usar el método propio de la herramienta si existe
    if hasattr(tool, 'get_action_description'):
        try:
            return tool.get_action_description(**tool_args)
        except Exception:
            pass
            
    # 2. Fallback: Inferencia basada en el nombre de la herramienta
    tool_name = getattr(tool, 'name', '').lower()
    
    if 'read_file' in tool_name or 'file_read' in tool_name:
        path = tool_args.get('path') or tool_args.get('file_path') or ''
        return f"Leyendo archivo: {path}"
    elif 'write_file' in tool_name or 'file_write' in tool_name:
        path = tool_args.get('path') or tool_args.get('file_path') or ''
        return f"Escribiendo en archivo: {path}"
    elif 'list_dir' in tool_name or 'file_list' in tool_name:
        path = tool_args.get('path') or tool_args.get('directory') or '.'
        return f"Listando directorio: {path}"
    elif 'search' in tool_name:
        query = (
            tool_args.get('query') or 
            tool_args.get('search_query') or 
            tool_args.get('pattern') or 
            tool_args.get('text') or 
            tool_args.get('target') or
            tool_args.get('regex_pattern') or
            tool_args.get('target_content') or
            ''
        )
        path = tool_args.get('path') or tool_args.get('file_path') or tool_args.get('directory') or ''
        
        if 'file' in tool_name or 'glob' in tool_name or path:
            if path and query:
                return f"Buscando '{query}' en {path}"
            elif path:
                return f"Buscando en {path}"
            elif query:
                return f"Buscando: {query}"
        
        return f"Buscando: {query}" if query else "Buscando..."
    elif 'execute_command' in tool_name:
        cmd = tool_args.get('command') or ''
        if len(cmd) > 40: cmd = cmd[:37] + "..."
        return f"Ejecutando comando: {cmd}"
    elif 'python_executor' in tool_name:
        return "Ejecutando código Python"
        
    return ""
