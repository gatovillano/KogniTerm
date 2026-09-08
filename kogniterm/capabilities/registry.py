"""Registro central de herramientas (tools) y decorador @tool para KogniTerm Capabilities."""

from dataclasses import dataclass
from functools import wraps
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, get_type_hints
from pydantic import BaseModel, Field, create_model

from kogniterm.core.utils.tool_utils import sanitize_tool_name, normalize_tool_parameters_schema


def create_model_from_signature(
    func: Callable[..., Any],
    model_name: str,
) -> Type[BaseModel]:
    """Construye dinámicamente un modelo Pydantic v2 a partir de la firma de una función."""
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    fields: Dict[str, Tuple[Type[Any], Any]] = {}

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        param_type = type_hints.get(param_name, Any)

        if param.default is inspect.Parameter.empty:
            fields[param_name] = (param_type, Field(...))
        else:
            fields[param_name] = (param_type, Field(default=param.default))

    return create_model(model_name, **fields)  # type: ignore[call-overload]


@dataclass
class ToolDefinition:
    """Metadatos y ejecutor de una herramienta nativa registrada."""

    name: str
    description: str
    params_schema: Type[BaseModel]
    handler: Callable[..., Any]
    agent_type: Optional[str] = None
    category: str = "general"
    _cached_schema: Optional[Dict[str, Any]] = None

    def to_litellm_schema(self) -> Dict[str, Any]:
        """Convierte la definición a formato OpenAI/LiteLLM estructurado y cacheado."""
        if self._cached_schema is not None:
            return self._cached_schema

        raw_schema = self.params_schema.model_json_schema()
        raw_schema.pop("title", None)
        cleaned_schema = normalize_tool_parameters_schema(raw_schema)

        if not cleaned_schema.get("properties"):
            cleaned_schema = {
                "type": "object",
                "properties": {},
                "required": [],
            }

        clean_name = sanitize_tool_name(self.name)
        schema = {
            "type": "function",
            "function": {
                "name": clean_name,
                "description": self.description[:1024] if self.description else f"Herramienta {clean_name}",
                "parameters": cleaned_schema,
            },
        }
        self._cached_schema = schema
        return schema


class ToolRegistry:
    """Registro singleton para herramientas nativas ultrarrápidas de KogniTerm."""

    _instance: Optional["ToolRegistry"] = None

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._cached_schemas = None
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_tools"):
            self._tools: Dict[str, ToolDefinition] = {}
            self._cached_schemas: Optional[List[Dict[str, Any]]] = None

    def register(self, definition: ToolDefinition) -> None:
        """Registra una nueva herramienta en el registro e invalida la caché de esquemas."""
        self._tools[definition.name] = definition
        clean_name = sanitize_tool_name(definition.name)
        if clean_name != definition.name:
            self._tools[clean_name] = definition
        self._cached_schemas = None

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Obtiene la definición de una herramienta por su nombre original o saneado."""
        return self._tools.get(name) or self._tools.get(sanitize_tool_name(name))

    def get_all(self) -> Dict[str, ToolDefinition]:
        """Retorna todas las herramientas registradas (sin duplicados por saneamiento)."""
        seen = set()
        unique = {}
        for name, tool_def in self._tools.items():
            if id(tool_def) not in seen:
                seen.add(id(tool_def))
                unique[tool_def.name] = tool_def
        return unique

    def get_schemas_for_litellm(self) -> List[Dict[str, Any]]:
        """Retorna la lista de esquemas en formato esperado por LiteLLM (cacheado en memoria)."""
        if self._cached_schemas is None:
            unique_tools = self.get_all().values()
            self._cached_schemas = [tool.to_litellm_schema() for tool in unique_tools]
        return self._cached_schemas

    def get_handler(self, name: str) -> Callable[..., Any]:
        """Retorna la función manejadora de una herramienta."""
        tool = self.get_tool(name)
        if not tool:
            raise KeyError(f"Herramienta no registrada: '{name}'")
        return tool.handler

    def unregister(self, name: str) -> None:
        """Elimina una herramienta del registro e invalida la caché."""
        tool = self._tools.pop(name, None)
        if tool:
            clean_name = sanitize_tool_name(tool.name)
            self._tools.pop(clean_name, None)
            self._cached_schemas = None

    def clear(self) -> None:
        """Limpia todas las herramientas registradas."""
        self._tools.clear()
        self._cached_schemas = None

    def count(self) -> int:
        """Retorna el número de herramientas únicas registradas."""
        return len(self.get_all())


default_tool_registry = ToolRegistry()


def tool(
    name: str,
    description: str,
    params_schema: Optional[Type[BaseModel]] = None,
    agent_type: Optional[str] = None,
    category: str = "general",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorador para registrar funciones como herramientas de primer nivel en ToolRegistry."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        nonlocal params_schema
        if params_schema is None:
            params_schema = create_model_from_signature(
                func, f"{sanitize_tool_name(name).capitalize()}Params"
            )

        definition = ToolDefinition(
            name=name,
            description=description,
            params_schema=params_schema,
            handler=func,
            agent_type=agent_type,
            category=category,
        )
        ToolRegistry().register(definition)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._tool_definition = definition  # type: ignore[attr-defined]
        return wrapper

    return decorator
