import os
import queue
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agent_state_types import AgentState # Importar AgentState desde el nuevo archivo
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel

"""
This module contains the TerminalUI class, responsible for handling all user interface
related interactions in the KogniTerm application.
"""

class TerminalUI:
    def __init__(self, console: Console | None = None):
        self.console = console if console else Console()
        self.interrupt_queue = queue.Queue()
        self.kb = KeyBindings()

        @self.kb.add('escape')
        def _(event):
            self.interrupt_queue.put("interrupt")
            event.app.current_buffer.cancel_completion() # Limpiar el prompt

    def print_stream(self, text: str):
        """
        Prints a chunk of text to the console without adding a newline,
        and flushes the output immediately.
        """
        self.console.file.write(text)
        self.console.file.flush()

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

            # Preparar el diff para mostrarlo en un bloque de código Markdown
            # El resaltado de sintaxis para 'diff' será manejado por el bloque de código Markdown.
            formatted_diff = diff_content

            panel_content_markdown = Markdown(
                f"""**Actualización de Archivo Requerida:**\n{message}\n\n```diff
\n{formatted_diff}\n
```\n"""
            )

            self.console.print(Padding(Panel(
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
                    self.print_message("Respuesta no válida. Por favor, responde 's' o 'n'.", style="red")

            tool_message_content = ""
            if run_update:
                # Llamar directamente a _apply_update de FileUpdateTool
                result = self.file_update_tool._apply_update(file_path, new_content)
                tool_message_content = json.loads(result).get("message", "")
                self.print_message(f"Confirmación de actualización para '{file_path}': Aprobado. {tool_message_content}", style="green")
            else:
                tool_message_content = f"Confirmación de actualización para '{file_path}': Denegado. Cambios no aplicados."
                self.print_message(f"Confirmación de actualización para '{file_path}': Denegado.", style="yellow")
            
            return {"tool_message_content": tool_message_content, "approved": run_update}

        except json.JSONDecodeError:
            self.print_message("Error: La salida de la herramienta no es un JSON válido para la confirmación de actualización.", style="red")
            return {"tool_message_content": "Error al procesar la confirmación de actualización de archivo.", "approved": False}
        except Exception as e:
            self.print_message(f"Error inesperado al manejar la confirmación de actualización de archivo: {e}", style="red")
            return {"tool_message_content": f"Error inesperado: {e}", "approved": False}

    def print_message(self, message: str, style: str = "", is_user_message: bool = False):

        """
        Prints a message to the console with optional styling.
        If is_user_message is True, the message will be enclosed in a Panel.
        """
        if is_user_message:
            self.console.print(Padding(Panel(
                Markdown(message),
                title="[bold dim]Tu Mensaje[/bold dim]",
                border_style="dim",
                expand=False
            ), (1, 2)))
        else:
            self.console.print(message, style=style)

    def get_interrupt_queue(self) -> queue.Queue:
        return self.interrupt_queue

    def print_welcome_banner(self):
        """
        Prints the welcome banner for KogniTerm.
        """
        banner_text = """
██╗  ██╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗███████╗██████╗ ███╗   ███╗
██║ ██╔╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║
█████╔╝ ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║
██╔═██╗ ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║
██║  ██╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║
╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝
"""
        self.console.print() # Margen superior
        # Paleta de lilas y morados para un degradado más suave
        colors = [
            "#d1c4e9", # Light Lilac
            "#c5b7e0",
            "#b9aad7",
            "#ad9dce",
            "#a190c5",
            "#9583bc",
        ]
        
        lines = banner_text.strip().split('\n')
        num_lines = len(lines)
        
        for i, line in enumerate(lines):
            # Interpolar colores para un degradado más suave
            self.console.print(f"[{colors[i % len(colors)]}]{line}[/]", justify="center")
        
        self.console.print(Panel(f"""Escribe '[green]%salir[/green]' para terminar o '[green]%help[/green]' para ver los comandos.""", title="[bold green]Bienvenido[/bold green]", expand=False), justify="center")


"""
This module contains the CommandApprovalHandler class, responsible for
managing command approval from the user in the KogniTerm application.
"""

class CommandApprovalHandler:
    def __init__(self, llm_service: LLMService, command_executor: CommandExecutor,
                 terminal_ui: TerminalUI, agent_state: AgentState):
        self.llm_service = llm_service
        self.command_executor = command_executor
        self.terminal_ui = terminal_ui
        self.agent_state = agent_state
        self.prompt_session = PromptSession(key_bindings=self.terminal_ui.kb) # Usar los KeyBindings de TerminalUI

    def handle_command_approval(self, command_to_execute: str, auto_approve: bool = False) -> dict:
        """
        Handles the approval process for a command generated by the agent.
        Returns a dictionary with the updated agent state and tool message content.
        """
        # 1. Recuperar el tool_call_id del AIMessage más reciente
        last_ai_message = None
        for msg in reversed(self.agent_state.messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                last_ai_message = msg
                break
        
        tool_call_id = None
        if last_ai_message and last_ai_message.tool_calls:
            tool_call_id = last_ai_message.tool_calls[0]['id']

        # 2. Generar la explicación del comando
        explanation_text = ""
        if tool_call_id:
            temp_history_for_explanation = [
                msg for msg in self.agent_state.messages if msg is not last_ai_message
            ]
            explanation_prompt = HumanMessage(
                content=f"""Genera una explicación concisa y directa en lenguaje natural sobre qué hará el siguiente comando y por qué es útil para la tarea actual. Tu respuesta debe ser ÚNICAMENTE la explicación, sin preámbulos, frases conversacionales, ni el comando en sí. Comando: `{command_to_execute}`"""
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

        # 3. Mostrar la explicación y pedir confirmación
        self.terminal_ui.console.print(Padding(Panel(
            Markdown(f"""**Comando a ejecutar:**
```bash
{command_to_execute}
```
**Explicación:**
{explanation_text}"""),
            border_style='yellow',
            title='Confirmación de Comando'
        ), (1, 2)))

        # 4. Solicitar aprobación al usuario
        run_command = False
        if auto_approve:
            run_command = True
            self.terminal_ui.print_message("Comando auto-aprobado.", style="yellow")
        else:
            while True:
                approval_input = self.prompt_session.prompt("¿Deseas ejecutar este comando? (s/n): ").lower().strip()
                if approval_input == 's':
                    run_command = True
                    break
                elif approval_input == 'n':
                    run_command = False
                    break
                else:
                    self.terminal_ui.print_message("Respuesta no válida. Por favor, responde 's' o 'n'.", style="red")

        # 5. Ejecutar el comando y manejar la salida
        tool_message_content = ""
        if run_command:
            full_command_output = ""
            try:
                self.terminal_ui.print_message("Ejecutando comando... (Presiona Ctrl+C para cancelar)", style="yellow")

                for output_chunk in self.command_executor.execute(command_to_execute, cwd=os.getcwd()):
                    full_command_output += output_chunk
                    print(output_chunk, end='', flush=True)
                print()
                tool_message_content = full_command_output if full_command_output.strip() else "El comando se ejecutó correctamente y no produjo ninguna salida."

            except KeyboardInterrupt:
                self.command_executor.terminate()
                tool_message_content = "Comando cancelado por el usuario."
                self.terminal_ui.print_message("\n\nComando cancelado por el usuario.", style="red")
        else:
            tool_message_content = "Comando no ejecutado por el usuario."
            self.terminal_ui.print_message("Comando no ejecutado.", style="yellow")

        # 6. Añadir ToolMessage al historial
        if tool_call_id:
            # Añadir un AIMessage vacío con el tool_call_id para asegurar que el ToolMessage no sea considerado huérfano
            # Esto es necesario porque el AIMessage original que generó el tool_call puede haber sido truncado o resumido.
            self.agent_state.messages.append(AIMessage(
                content="",
                tool_calls=[{'id': tool_call_id, 'name': 'execute_command', 'args': {'command': command_to_execute}}]
            ))
            self.agent_state.messages.append(ToolMessage(
                content=tool_message_content,
                tool_call_id=tool_call_id
            ))
        else:
            self.terminal_ui.print_message("Error: No se encontró el tool_call_id para asociar la salida del comando.", style="red")
            return {"messages": self.agent_state.messages, "tool_message_content": tool_message_content}

        # 7. Guardar el historial antes de la re-invocación
        self.llm_service._save_history(self.agent_state.messages)

        # 8. Devolver el estado actualizado y el contenido del ToolMessage
        return {"messages": self.agent_state.messages, "tool_message_content": tool_message_content}
