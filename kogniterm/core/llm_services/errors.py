"""
Excepciones específicas para servicios LLM.
"""


class LLMError(Exception):
    """Excepción base para errores LLM."""


class ToolInvocationError(LLMError):
    """Error al invocar una herramienta."""

    def __init__(self, tool_name: str, message: str, original_error: Exception = None):
        self.tool_name = tool_name
        self.message = message
        self.original_error = original_error
        super().__init__(f"[{tool_name}] {message}")


class ToolDefinitionError(LLMError):
    """Error en la definición de una herramienta."""


class LLMConnectionError(LLMError):
    """Error de conexión con el servicio LLM."""


class LLMTimeoutError(LLMConnectionError):
    """Timeout al conectar con el servicio LLM."""


class LLMRateLimitError(LLMConnectionError):
    """Límite de tasa excedido."""


class InvalidToolCallError(LLMError):
    """Llamada a herramienta inválida."""
