from typing import Optional
import os
from prompt_toolkit import PromptSession
from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agents.bash_agent import AgentState
from kogniterm.terminal.terminal_ui import TerminalUI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from kogniterm.core.tools.file_update_tool import FileUpdateTool
from rich.padding import Padding
from rich.panel import Panel
from rich.markdown import Markdown # Importar Markdown

"""
This module contains the CommandApprovalHandler class, responsible for
managing command approval from the user in the KogniTerm application.
"""

class CommandApprovalHandler:
    def __init__(self, llm_service: LLMService, command_executor: CommandExecutor,
                 prompt_session: PromptSession, terminal_ui: TerminalUI, agent_state: AgentState, file_update_tool: FileUpdateTool):
        self.llm_service = llm_service
        self.command_executor = command_executor
        self.prompt_session = prompt_session
        self.terminal_ui = terminal_ui
        self.agent_state = agent_state
        self.interrupt_queue = terminal_ui.get_interrupt_queue() # Obtener la cola de interrupción de TerminalUI
        self.file_update_tool = file_update_tool

    async def handle_file_update_confirmation(self, diff_json_str: str, original_tool_call: dict) -> dict:
        """
        Handles the approval process for a file update operation, displaying the diff and requesting confirmation.
        Returns a dictionary with the tool message content and an 'approved' flag.
        """
        try:
            diff_data = json.loads(diff_json_str)
            diff_content = diff_data.get("diff", "")
            file_path = diff_data.get("path", "archivo desconocido")
            message = diff_data.get("message", f"Se detectaron cambios para '{file_path}'. Por favor, confirma para aplicar.")
            new_content = original_tool_call.get("args", {}).get("content", "")

            # Preparar el diff para mostrarlo con colores
            colored_diff_lines = []
            for line in diff_content.splitlines():
                if line.startswith('+'):
                    colored_diff_lines.append(f"[green]{line}[/green]")
                elif line.startswith('-'):
                    colored_diff_lines.append(f"[red]{line}[/red]")
                else:
                    colored_diff_lines.append(line)
            
            formatted_diff = "\n".join(colored_diff_lines)

            panel_content_markdown = Markdown(
                f"""**Actualización de Archivo Requerida:**\n{message}\n\n```diff\n{formatted_diff}\n```\n"""
            )

            self.terminal_ui.console.print(Padding(Panel(
                panel_content_markdown,
                border_style='yellow',
                title=f'Confirmación de Actualización: {file_path}'
            ), (1, 2)))

            run_update = False
            while True:
                approval_input = await self.prompt_session.prompt_async("¿Deseas aplicar estos cambios? (s/n): ")

                if approval_input is None:
                    approval_input = "n"
                else:
                    approval_input = approval_input.lower().strip()

                if approval_input == 's':
                    run_update = True
                    break
                elif approval_input == 'n':
                    run_update = False
                    break
                else:
                    self.terminal_ui.print_message("Respuesta no válida. Por favor, responde 's' o 'n'.", style="red")

            tool_message_content = ""
            if run_update:
                # Llamar directamente a _apply_update de FileUpdateTool
                result = self.file_update_tool._apply_update(file_path, new_content)
                tool_message_content = json.loads(result).get("message", "")
                self.terminal_ui.print_message(f"Confirmación de actualización para '{file_path}': Aprobado. {tool_message_content}", style="green")
            else:
                tool_message_content = f"Confirmación de actualización para '{file_path}': Denegado. Cambios no aplicados."
                self.terminal_ui.print_message(f"Confirmación de actualización para '{file_path}': Denegado.", style="yellow")
            
            return {"tool_message_content": tool_message_content, "approved": run_update}

        except json.JSONDecodeError:
            self.terminal_ui.print_message("Error: La salida de la herramienta no es un JSON válido para la confirmación de actualización.", style="red")
            return {"tool_message_content": "Error al procesar la confirmación de actualización de archivo.", "approved": False}
        except Exception as e:
            self.terminal_ui.print_message(f"Error inesperado al manejar la confirmación de actualización de archivo: {e}", style="red")
            return {"tool_message_content": f"Error inesperado: {e}", "approved": False}
        self.file_update_tool = file_update_tool

    async def handle_command_approval(self, command_to_execute: str, auto_approve: bool = False,
                                is_user_confirmation: bool = False, confirmation_prompt: Optional[str] = None) -> dict:
        """
        Handles the approval process for a command generated by the agent or a user confirmation request.
        Returns a dictionary with the updated agent state and tool message content.
        """
        # 1. Recuperar el tool_call_id del AIMessage más reciente
        last_ai_message = None
        for msg in reversed(self.agent_state.messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                last_ai_message = msg
                break
        
        tool_call_id = None
        if not is_user_confirmation: # Solo buscar/generar tool_call_id si no es una confirmación de usuario
            if last_ai_message and last_ai_message.tool_calls and last_ai_message.tool_calls[0] and 'id' in last_ai_message.tool_calls[0]:
                tool_call_id = last_ai_message.tool_calls[0]['id']
            else:
                # Generar un tool_call_id temporal si no se encuentra uno asociado
                tool_call_id = f"manual_tool_call_{os.urandom(8).hex()}"
                self.terminal_ui.print_message(f"Advertencia: No se encontró un tool_call_id asociado. Generando ID temporal: {tool_call_id}", style="yellow")

        # 2. Generar la explicación del comando o usar el prompt de confirmación
        explanation_text = ""
        panel_title = 'Confirmación de Comando'
        panel_content_markdown = ""

        if is_user_confirmation and confirmation_prompt:
            explanation_text = confirmation_prompt
            panel_title = 'Confirmación de Usuario Requerida'
            panel_content_markdown = Markdown(f"""**Acción requerida:**\n{explanation_text}""")
        else:
            if tool_call_id:
                temp_history_for_explanation = [
                    msg for msg in self.agent_state.messages if msg is not last_ai_message
                ]
                explanation_prompt = HumanMessage(
                    content=f"Explica en lenguaje natural y de forma concisa qué hará el siguiente comando y por qué es útil para la tarea actual. No incluyas el comando en la explicación, solo el texto explicativo. Comando: `{command_to_execute}`"
                )
                temp_history_for_explanation.append(explanation_prompt)
                
                try:
                    explanation_response = self.llm_service.invoke(temp_history_for_explanation)
                    full_response_content = ""
                    if hasattr(explanation_response, '__iter__'):
                        last_chunk_content = ""
                        for chunk in explanation_response:
                            if isinstance(chunk, AIMessage):
                                if isinstance(chunk.content, str):
                                    last_chunk_content = chunk.content
                                else:
                                    last_chunk_content = str(chunk.content)
                            elif isinstance(chunk, str):
                                last_chunk_content = chunk
                        full_response_content = last_chunk_content
                    else:
                        if isinstance(explanation_response, str):
                            full_response_content = explanation_response
                        else:
                            full_response_content = str(explanation_response)

                    explanation_text = full_response_content.strip()

                except Exception as e:
                    explanation_text = f"No se pudo generar una explicación para el comando. Error: {e}"

            if not explanation_text:
                explanation_text = "No se pudo generar una explicación para el comando."
            
            panel_content_markdown = Markdown(f"""**Comando a ejecutar:**
```bash
{command_to_execute}
```
**Explicación:**
{explanation_text}""")

        # 3. Mostrar la explicación y pedir confirmación
        self.terminal_ui.console.print(Padding(Panel(
            panel_content_markdown,
            border_style='yellow',
            title=panel_title
        ), (1, 2)))

        # 4. Solicitar aprobación al usuario
        run_command = False
        if auto_approve:
            run_command = True
            self.terminal_ui.print_message("Comando auto-aprobado.", style="yellow")
        else:
            while True:
                approval_input = await self.prompt_session.prompt_async("¿Deseas ejecutar este comando? (s/n): ")

                if approval_input is None:
                    # Si el usuario interrumpe el prompt (ej. Ctrl+D), asumimos que deniega.
                    approval_input = "n"
                else:
                    approval_input = approval_input.lower().strip()

                if approval_input == 's':
                    run_command = True
                    break
                elif approval_input == 'n':
                    run_command = False
                    break
                else:
                    self.terminal_ui.print_message("Respuesta no válida. Por favor, responde 's' o 'n'.", style="red")

        # 5. Ejecutar el comando y manejar la salida (o procesar la confirmación del usuario)
        tool_message_content = ""
        if run_command:
            if is_user_confirmation:
                tool_message_content = f"Confirmación de usuario: Aprobado para '{confirmation_prompt}'."
                self.terminal_ui.print_message("Acción de usuario aprobada.", style="green")
            else:
                full_command_output = ""
                try:
                    self.terminal_ui.print_message("Ejecutando comando... (Presiona Ctrl+C para cancelar)", style="yellow")

                    for output_chunk in self.command_executor.execute(command_to_execute, cwd=os.getcwd(), interrupt_queue=self.interrupt_queue):
                        full_command_output += output_chunk
                        print(output_chunk, end='', flush=True)
                    print()
                    tool_message_content = full_command_output if full_command_output.strip() else "El comando se ejecutó correctamente y no produjo ninguna salida."

                except KeyboardInterrupt:
                    self.command_executor.terminate()
                    tool_message_content = "Comando cancelado por el usuario."
                    self.terminal_ui.print_message("\n\nComando cancelado por el usuario.", style="red")
        else:
            if is_user_confirmation:
                tool_message_content = f"Confirmación de usuario: Denegado para '{confirmation_prompt}'."
                self.terminal_ui.print_message("Acción de usuario denegada.", style="yellow")
            else:
                tool_message_content = "Comando no ejecutado por el usuario."
                self.terminal_ui.print_message("Comando no ejecutado.", style="yellow")

        # 6. Añadir el mensaje al historial (AIMessage si es denegado, ToolMessage si es ejecutado)
        if run_command:
            if is_user_confirmation:
                self.agent_state.messages.append(ToolMessage(content=tool_message_content))
            else:
                self.agent_state.messages.append(ToolMessage(
                    content=tool_message_content,
                    tool_call_id=tool_call_id
                ))
        else: # Comando denegado
            # Si el comando es denegado, añadimos un AIMessage para que el modelo lo procese
            # sin esperar un tool_call correspondiente.
            self.agent_state.messages.append(AIMessage(content=tool_message_content))
            self.terminal_ui.print_message("Acción denegada por el usuario.", style="yellow")

        # 7. Guardar el historial antes de la re-invocación
        self.llm_service._save_history(self.agent_state.messages)

        # 8. Devolver el estado actualizado y el contenido del ToolMessage
        return {"messages": self.agent_state.messages, "tool_message_content": tool_message_content}
