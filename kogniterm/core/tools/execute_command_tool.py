import logging
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from ..command_executor import CommandExecutor # Adjusted import

logger = logging.getLogger(__name__)

import queue # Importar el módulo queue

class ExecuteCommandTool(BaseTool):
    name: str = "execute_command"
    description: str = "Ejecuta un comando bash y devuelve su salida."
    
    class ExecuteCommandInput(BaseModel):
        command: str = Field(description="El comando bash a ejecutar.")

    args_schema: Type[BaseModel] = ExecuteCommandInput

    command_executor: Optional[CommandExecutor] = None
    interrupt_queue: Optional[queue.Queue] = None # Nuevo atributo para la cola de interrupción

    def model_post_init(self, __context: Any) -> None:
        if self.command_executor is None:
            self.command_executor = CommandExecutor()

    def _run(self, command: str) -> str:
        """Usa el CommandExecutor para ejecutar el comando."""
        logger.debug(f"ExecuteCommandTool - Recibido comando: '{command}'")
        full_output = "" # Initialize full_output here
        assert self.command_executor is not None
        try:
            # Pasar el interrupt_queue al método execute del CommandExecutor
            for chunk in self.command_executor.execute(command, interrupt_queue=self.interrupt_queue):
                full_output += chunk # Still collect for the return value
            logger.debug(f"ExecuteCommandTool - Salida del comando: \"{full_output}\"\n")
            return full_output
        except Exception as e:
            error_message = f"ERROR: ExecuteCommandTool - Error al ejecutar el comando '{command}': {type(e).__name__}: {e}"
            logger.error(error_message, exc_info=True)
            return error_message

    def get_command_generator(self, command: str):
        """Devuelve un generador para ejecutar el comando de forma incremental."""
        logger.debug(f"ExecuteCommandTool - Obteniendo generador para comando: '{command}'")
        assert self.command_executor is not None
        # Pasar el interrupt_queue al método execute del CommandExecutor
        return self.command_executor.execute(command, interrupt_queue=self.interrupt_queue)

    async def _arun(self, command: str) -> str:
        """Run the tool asynchronously."""
        raise NotImplementedError("execute_command_tool does not support async")

