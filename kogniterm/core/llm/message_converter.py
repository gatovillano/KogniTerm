import json
import logging
from typing import List, Dict, Any, Optional, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import BaseTool
from .tool_parser import generate_short_id

logger = logging.getLogger(__name__)

def convert_langchain_tool_to_litellm(tool: BaseTool, model_name: str = "") -> dict:
    """Convierte una herramienta de LangChain (BaseTool) a un formato compatible con LiteLLM."""
    args_schema = {"type": "object", "properties": {}}

    # Obtener el esquema de argumentos de manera más robusta
    if hasattr(tool, 'args_schema') and tool.args_schema is not None:
        try:
            if isinstance(tool.args_schema, dict):
                args_schema = tool.args_schema
            elif hasattr(tool.args_schema, 'schema') and callable(getattr(tool.args_schema, 'schema', None)):
                try:
                    args_schema = tool.args_schema.schema()
                except Exception:
                    if hasattr(tool.args_schema, 'model_json_schema') and callable(getattr(tool.args_schema, 'model_json_schema', None)):
                        args_schema = tool.args_schema.model_json_schema()
            elif hasattr(tool.args_schema, 'model_json_schema'):
                args_schema = tool.args_schema.model_json_schema()
            else:
                if hasattr(tool.args_schema, 'model_fields'):
                    properties = {}
                    for field_name, field_info in tool.args_schema.model_fields.items():
                        if field_name not in ["account_id", "workspace_id", "telegram_id", "thread_id"] and not getattr(field_info, 'exclude', False):
                            field_type = 'string'
                            if hasattr(field_info, 'annotation'):
                                if field_info.annotation == str: field_type = 'string'
                                elif field_info.annotation == int: field_type = 'integer'
                                elif field_info.annotation == bool: field_type = 'boolean'
                                elif field_info.annotation == list: field_type = 'array'
                                elif field_info.annotation == dict: field_type = 'object'
                            properties[field_name] = {
                                "type": field_type,
                                "description": getattr(field_info, 'description', "") or f"Parámetro {field_name}"
                            }
                    args_schema = {
                        "type": "object",
                        "properties": properties,
                        "required": [name for name, info in tool.args_schema.model_fields.items() if info.is_required() and name in properties]
                    }
        except Exception as e:
            tool_name = getattr(tool, 'name', 'Desconocido')
            logger.error(f"Error extracting schema for tool {tool_name}: {e}")
            args_schema = {"type": "object", "properties": {}}
    elif hasattr(tool, 'parameters_schema') and tool.parameters_schema is not None:
        args_schema = tool.parameters_schema

    def clean_schema(s):
        if not isinstance(s, dict): return s
        s.pop("title", None)
        s.pop("additionalProperties", None)
        s.pop("definitions", None)
        s.pop("$defs", None)
        if "properties" in s:
            for prop_name, prop_val in s["properties"].items():
                if isinstance(prop_val, dict):
                    clean_schema(prop_val)
                    prop_val.pop("default", None)
        return s

    cleaned_schema = clean_schema(args_schema)

    if not cleaned_schema.get("properties"):
        cleaned_schema = {"type": "object", "properties": {}, "required": []}

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description[:1024],
            "parameters": cleaned_schema,
        }
    }

def from_litellm_message(message: Dict[str, Any], id_generator=None) -> BaseMessage:
    """Convierte un mensaje de LiteLLM a un formato compatible con LangChain."""
    if id_generator is None:
        id_generator = generate_short_id
        
    role = message.get("role")
    content = message.get("content", "")
    
    if role == "user":
        return HumanMessage(content=content)
    elif role == "assistant":
        tool_calls_data = message.get("tool_calls")
        if tool_calls_data:
            tool_calls = []
            for tc in tool_calls_data:
                function_data = tc.get("function")
                if function_data:
                    args = function_data.get("arguments", "")
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: args = {}
                    tool_calls.append({
                        "id": tc.get("id", id_generator()),
                        "name": function_data.get("name", ""),
                        "args": args
                    })
            return AIMessage(content=content, tool_calls=tool_calls)
        return AIMessage(content=content)
    elif role == "tool":
        return ToolMessage(content=content, tool_call_id=message.get("tool_call_id"))
    elif role == "system":
        return SystemMessage(content=content)
    return HumanMessage(content=content)

def to_litellm_message(message: BaseMessage, model_name: str, id_map: Optional[Dict[str, str]] = None, id_generator=None) -> Dict[str, Any]:
    """Convierte un mensaje de LangChain a un formato compatible con LiteLLM."""
    if id_generator is None:
        id_generator = generate_short_id
        
    is_mistral = "mistral" in model_name.lower()
    
    def get_compliant_id(original_id):
        if not is_mistral:
            return original_id or id_generator()
        if original_id and len(original_id) == 9 and original_id.isalnum():
            return original_id
        if not original_id:
            return id_generator()
        if id_map is not None:
            if original_id not in id_map:
                id_map[original_id] = id_generator()
            return id_map[original_id]
        return id_generator()

    if isinstance(message, HumanMessage):
        content = message.content
        if not isinstance(content, str):
            content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
        return {"role": "user", "content": content}
    elif isinstance(message, AIMessage):
        tool_calls = getattr(message, 'tool_calls', [])
        content = message.content
        if not isinstance(content, str):
            content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)

        msg = {"role": "assistant", "content": content or "..."}
        
        reasoning = message.additional_kwargs.get("reasoning_content") or getattr(message, 'reasoning_content', None)
        if reasoning:
            msg["reasoning_content"] = str(reasoning)

        if tool_calls:
            serialized_tool_calls = []
            for tc in tool_calls:
                tc_id = get_compliant_id(tc.get("id"))
                tc_name = tc.get("name", "")
                tc_args = tc.get("args", {})
                arguments_json = json.dumps(tc_args) if tc_args else "{}"
                
                serialized_tool_calls.append({
                    "id": tc_id,
                    "type": "function",
                    "function": {"name": tc_name, "arguments": arguments_json},
                })
            
            if not content or not str(content).strip():
                msg["content"] = "Ejecutando herramientas..."
            msg["tool_calls"] = serialized_tool_calls
        
        return msg
    elif isinstance(message, ToolMessage):
        content = message.content
        if not isinstance(content, str):
            content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
        if not content or not str(content).strip():
            content = "Operación completada (sin salida)."
        
        tc_id = get_compliant_id(getattr(message, 'tool_call_id', ''))
        return {"role": "tool", "content": content, "tool_call_id": tc_id}
    elif isinstance(message, SystemMessage):
        content = message.content
        if not isinstance(content, str):
            content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
        return {"role": "system", "content": content}
    
    content = getattr(message, 'content', str(message))
    if not isinstance(content, str):
        content = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
    return {"role": "user", "content": content}
