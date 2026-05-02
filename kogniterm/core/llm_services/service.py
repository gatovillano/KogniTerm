"""
Servicio LLM principal que coordina parseo, proveedores y herramientas.
"""
from typing import Any, Dict, List, Optional

from kogniterm.core.llm_services.config import LLMConfig
from kogniterm.core.llm_services.errors import (
    InvalidToolCallError,
    ToolInvocationError,
)
from kogniterm.core.llm_services.parser import (
    parse_tool_calls_from_text_enhanced,
    format_tool_calls_for_litellm,
)
from kogniterm.core.llm_services.providers import LLMProvider
from kogniterm.core.llm_services.tools import SYSTEM_TOOLS, find_tool_definition


class LLMService:
    """
    Servicio LLM que maneja interacciones con modelos de lenguaje,
    incluyendo invocación de herramientas y parseo de respuestas.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: Optional[List[Dict[str, Any]]] = None,
        auto_invoke_tools: bool = True,
    ):
        self.provider = provider
        self.tools = tools or SYSTEM_TOOLS
        self.auto_invoke_tools = auto_invoke_tools
        self._tool_registry = {t["name"]: t for t in self.tools}

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tool_rounds: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ejecuta una conversación con soporte para herramientas.

        Args:
            messages: Lista de mensajes con roles 'user'/'assistant'
            tools: Herramientas disponibles (por defecto todas)
            max_tool_rounds: Máximo de iteraciones de tool calls
            **kwargs: Argumentos adicionales para el proveedor

        Returns:
            Diccionario con resultado de la conversación
        """
        tools = tools or self.tools
        tool_defs = self._prepare_tool_definitions(tools)
        history = messages.copy()
        round_num = 0

        while round_num < max_tool_rounds:
            round_num += 1

            # Generar respuesta del LLM
            response = self.provider.generate_with_tools(
                prompt=self._format_messages(history),
                tools=tool_defs,
                **kwargs,
            )

            response_text = response.get("text", "")

            # Intentar parsear tool calls
            tool_calls = parse_tool_calls_from_text_enhanced(
                response_text,
                require_at_least_one=False,
            )

            if not tool_calls:
                # No hay tool calls, devolver respuesta final
                return {
                    "status": "completed",
                    "message": response_text,
                    "history": history,
                    "rounds": round_num,
                }

            # Invocar herramientas
            tool_results = []
            for tc in tool_calls:
                try:
                    result = self._invoke_tool(tc)
                    tool_results.append(
                        {
                            "tool_call": {
                                "id": tc.id,
                                "name": tc.name,
                                "args": tc.args,
                            },
                            "result": result,
                            "status": "success",
                        }
                    )
                    # Añadir resultado al historial para siguiente ronda
                    history.append(
                        {"role": "assistant", "content": response_text}
                    )
                    history.append(
                        {
                            "role": "tool",
                            "name": tc.name,
                            "content": str(result),
                        }
                    )
                except Exception as e:
                    tool_results.append(
                        {
                            "tool_call": {
                                "id": tc.id,
                                "name": tc.name,
                                "args": tc.args,
                            },
                            "error": str(e),
                            "status": "error",
                        }
                    )
                    if not self.auto_invoke_tools:
                        raise ToolInvocationError(
                            tc.name, f"Error invocando herramienta: {e}", e
                        )

            if not self.auto_invoke_tools:
                return {
                    "status": "tool_calls_pending",
                    "message": response_text,
                    "tool_calls": [tc.__dict__ for tc in tool_calls],
                    "tool_results": tool_results,
                    "history": history,
                    "rounds": round_num,
                }

            # Continuar con siguiente ronda

        return {
            "status": "max_rounds_reached",
            "message": (
                "Se alcanzó el máximo de rondas de herramientas."
            ),
            "history": history,
            "rounds": round_num,
        }

    def generate(
        self,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> str:
        """
        Genera texto simple sin soporte de herramientas.
        """
        return self.provider.generate(prompt, **kwargs)

    def _prepare_tool_definitions(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prepara definiciones de herramientas para el proveedor."""
        # Extrae metadatos relevantes para cada tool
        tool_defs = []
        for tool in tools:
            td = find_tool_definition(tool["name"])
            if td:
                tool_defs.append(td)
            else:
                # Construye una definición genérica
                tool_defs.append(
                    {
                        "name": tool["name"],
                        "description": tool.get(
                            "description", "Herramienta del sistema"
                        ),
                        "parameters": tool.get("parameters", {}),
                    }
                )
        return tool_defs

    def _invoke_tool(self, tool_call) -> Any:
        """Invoca una herramienta por nombre con argumentos."""
        tool_def = self._tool_registry.get(tool_call.name)
        if not tool_def:
            raise InvalidToolCallError(
                f"Herramienta desconocida: {tool_call.name}"
            )

        callable_func = tool_def.get("callable")
        if callable_func:
            return callable_func(**tool_call.args)

        raise ToolInvocationError(
            tool_call.name,
            "La herramienta no tiene un callable asociado",
        )

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Formatea mensajes como un prompt simple."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"[{role}]: {content}")
        return "\n".join(parts)
