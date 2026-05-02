"""
Servicios LLM - Núcleo de integración con modelos de lenguaje.

Este módulo proporciona:
- Tipos compartidos para llamadas a herramientas (ToolCall, ParsedToolCall)
- Definiciones de herramientas del sistema (ToolDefinition)
- Parseo multi-formato de tool calls emitidas por LLMs
- Deduplicación y normalización de llamadas
- Exportación a formatos compatibles (LiteLLM)
- Proveedores LLM (Gemini, OpenAI)
- Servicio LLM unificado con orquestación de herramientas
"""

# ── Tipos base ──────────────────────────────────────────────────────
from .types import ToolCall, ParsedToolCall, ToolDefinition

# ── Sistema de herramientas ─────────────────────────────────────────
from .tools import (
    SYSTEM_TOOLS,
    get_system_tool_definitions,
    find_tool_definition,
)

# ── Parseo y formato ────────────────────────────────────────────────
from .parser import (
    ParseError,
    DuplicateToolCallError,
    parse_tool_calls_from_text,
    parse_tool_calls_from_text_enhanced,
    deduplicate_tool_calls,
    format_tool_calls_for_litellm,
)

# ── Configuración ────────────────────────────────────────────────────
from .config import LLMConfig, FAST_CONFIG, DEEP_CONFIG, TOOL_CONFIG, DEFAULT_CONFIG

# ── Errores ──────────────────────────────────────────────────────────
from .errors import (
    LLMError,
    ToolInvocationError,
    ToolDefinitionError,
    LLMConnectionError,
    LLMTimeoutError,
    LLMRateLimitError,
    InvalidToolCallError,
)

# ── Proveedores ─────────────────────────────────────────────────────
from .providers import LLMProvider, GeminiProvider, OpenAIProvider

# ── Servicio LLM ────────────────────────────────────────────────────
from .service import LLMService


__all__ = [
    # Tipos
    "ToolCall",
    "ParsedToolCall",
    "ToolDefinition",
    # Sistema de herramientas
    "SYSTEM_TOOLS",
    "get_system_tool_definitions",
    "find_tool_definition",
    # Parseo y formato
    "ParseError",
    "DuplicateToolCallError",
    "parse_tool_calls_from_text",
    "parse_tool_calls_from_text_enhanced",
    "deduplicate_tool_calls",
    "format_tool_calls_for_litellm",
    # Configuración
    "LLMConfig",
    "FAST_CONFIG",
    "DEEP_CONFIG",
    "TOOL_CONFIG",
    "DEFAULT_CONFIG",
    # Errores
    "LLMError",
    "ToolInvocationError",
    "ToolDefinitionError",
    "LLMConnectionError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "InvalidToolCallError",
    # Proveedores
    "LLMProvider",
    "GeminiProvider",
    "OpenAIProvider",
    # Servicio
    "LLMService",
]
