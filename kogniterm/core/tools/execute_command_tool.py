import logging
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from ..command_executor import CommandExecutor # Adjusted import

logger = logging.getLogger(__name__)

import queue # Importar el módulo queue
import os # Importar os para manejo de directorios

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

    def get_action_description(self, **kwargs) -> str:
        command = kwargs.get("command", "")
        return f"Ejecutando comando: {command}"

    def _run(self, command: str) -> Any:
        """Usa el CommandExecutor para ejecutar el comando, interceptando 'cd' para persistencia."""
        logger.debug(f"ExecuteCommandTool - Recibido comando: '{command}'")
        assert self.command_executor is not None

        # Interceptamos comandos 'cd' para cambiar el directorio de trabajo del proceso persistentemente
        stripped_cmd = command.strip()
        if stripped_cmd.startswith("cd ") or stripped_cmd == "cd":
            try:
                target_dir = stripped_cmd[3:].strip()
                if not target_dir:
                    target_dir = os.path.expanduser("~")
                else:
                    target_dir = os.path.expanduser(target_dir)
                
                os.chdir(target_dir)
                new_cwd = os.getcwd()
                success_msg = f"Directorio de trabajo cambiado a: {new_cwd}\n"
                logger.debug(f"ExecuteCommandTool - {success_msg.strip()}")
                yield success_msg
                return
            except Exception as e:
                error_msg = f"Error al cambiar de directorio: {e}\n"
                logger.error(error_msg)
                yield error_msg
                return

        try:
            # Pasar el interrupt_queue y el CWD actual al método execute del CommandExecutor
            # Nota: command_executor.execute usa por defecto el CWD del proceso si no se pasa cwd explícito,
            # así que al haber hecho os.chdir arriba, los siguientes comandos usarán el nuevo directorio.
            for chunk in self.command_executor.execute(command, interrupt_queue=self.interrupt_queue):
                yield chunk # Ceder cada chunk directamente
            logger.debug(f"ExecuteCommandTool - Comando '{command}' finalizado.\n")
        except Exception as e:
            error_message = f"ERROR: ExecuteCommandTool - Error al ejecutar el comando '{command}': {type(e).__name__}: {e}"
            logger.error(error_message, exc_info=True)
            yield error_message # Ceder el mensaje de error

    def get_command_generator(self, command: str):
        """Devuelve un generador para ejecutar el comando de forma incremental."""
        logger.debug(f"ExecuteCommandTool - Obteniendo generador para comando: '{command}'")
        assert self.command_executor is not None
        # Pasar el interrupt_queue al método execute del CommandExecutor
        return self.command_executor.execute(command, interrupt_queue=self.interrupt_queue)

    async def _arun(self, command: str) -> str:
        """Run the tool asynchronously."""
        raise NotImplementedError("execute_command_tool does not support async")

