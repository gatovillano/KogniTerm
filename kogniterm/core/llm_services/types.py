"""
Tipos compartidos entre los módulos del servicio LLM.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """
    Representa una llamada a herramienta generada por el LLM (formato OpenAI).

    Este es el formato esperado por LiteLLM cuando se invoca `completion(..., tools=...)`.
    """
    type: str = "function"
    function: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.type != "function":
            raise ValueError(f"Tipo no soportado: {self.type}")


@dataclass
class ParsedToolCall:
    """
    Representa una llamada a herramienta parseada desde texto LLM.

    Incluye metadatos sobre la confianza y el origen del parseo.
    """
    id: str
    name: str
    args: Dict[str, Any]
    confidence: float = 1.0
    source_pattern: str = "unknown"
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "args": self.args,
            "confidence": self.confidence,
            "source_pattern": self.source_pattern,
            "raw_text": self.raw_text,
        }

    def __repr__(self) -> str:
        return (
            f"ParsedToolCall(name={self.name!r}, confidence={self.confidence:.2f}, "
            f"source={self.source_pattern}, id={self.id})"
        )


@dataclass
class ToolDefinition:
    """
    Definición declarativa de una herramienta.

    Similar a la representación LiteLLM pero con campos opcionales
    extendidos para uso interno.
    """
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    strict: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_litellm_format(self) -> Dict[str, Any]:
        """
        Convierte esta definición al formato esperado por LiteLLM.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"ToolDefinition(name={self.name!r}, strict={self.strict})"
