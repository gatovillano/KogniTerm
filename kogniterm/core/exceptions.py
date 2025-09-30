from typing import Optional, Dict, Any

class UserConfirmationRequired(Exception):
    """Excepción personalizada para indicar que se requiere confirmación del usuario."""
    def __init__(self, message: str, tool_name: Optional[str] = None, tool_args: Optional[Dict[str, Any]] = None, raw_tool_output: Optional[str] = None):
        self.message = message
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.raw_tool_output = raw_tool_output # Nuevo campo para la salida cruda de la herramienta
        super().__init__(self.message)