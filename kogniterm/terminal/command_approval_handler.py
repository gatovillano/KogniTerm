import logging
from typing import Optional, Dict, Any
import os
from prompt_toolkit import PromptSession
from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agents.bash_agent import AgentState
from kogniterm.terminal.terminal_ui import TerminalUI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from kogniterm.core.tools.file_update_tool import FileUpdateTool
from kogniterm.core.tools.advanced_file_editor_tool import AdvancedFileEditorTool
from kogniterm.core.tools.file_operations_tool import FileOperationsTool
from rich.padding import Padding
from rich.panel import Panel
from rich.markdown import Markdown
import json
from io import StringIO # Importar StringIO
from rich.console import Console as RichConsole # Importar RichConsole
from rich.text import Text # ¡Nueva importación!
from rich.syntax import Syntax # ¡Nueva importación!
from rich.console import Group # ¡Nueva importación!

import uuid # Importar uuid

# Importar DiffRenderer para visualización mejorada de diffs
from kogniterm.utils.diff_renderer import DiffRenderer

# Importar temas para mejorar visuales
try:
    from kogniterm.terminal.themes import ColorPalette, Icons
    from kogniterm.terminal.visual_components import create_separator, format_command
    THEMES_AVAILABLE = True
except ImportError:
    THEMES_AVAILABLE = False

logger = logging.getLogger(__name__)

"""
This module contains the CommandApprovalHandler class, responsible for
managing command approval from the user in the KogniTerm application.
"""

class CommandApprovalHandler:
    def __init__(self, llm_service: LLMService, command_executor: CommandExecutor,
                 prompt_session: PromptSession, terminal_ui: TerminalUI, agent_state: AgentState,
                 file_update_tool: FileUpdateTool, advanced_file_editor_tool: AdvancedFileEditorTool, file_operations_tool: FileOperationsTool):
        self.llm_service = llm_service
        self.command_executor = command_executor
        self.prompt_session = prompt_session
        self.terminal_ui = terminal_ui
        self.agent_state = agent_state
        self.interrupt_queue = terminal_ui.get_interrupt_queue()
        self.file_update_tool = file_update_tool
        self.advanced_file_editor_tool = advanced_file_editor_tool
        self.file_operations_tool = file_operations_tool
        
        # Inicializar DiffRenderer con colores del tema si están disponibles
        if THEMES_AVAILABLE:
            theme_colors = {
                'diff_add_color': ColorPalette.SUCCESS,
                'diff_delete_color': ColorPalette.ERROR,
                'diff_context_color': ColorPalette.TEXT_SECONDARY,
                'diff_hunk_header_color': ColorPalette.SECONDARY,
                'line_number_color': f'dim {ColorPalette.PRIMARY_LIGHT}'
            }
        else:
            theme_colors = None
        
        self.diff_renderer = DiffRenderer(theme_colors=theme_colors)

    def _is_command_safe(self, command: str) -> bool:
        """
        Determina si un comando es seguro para ejecución automática.
        Los comandos seguros son generalmente de solo lectura y no contienen redirecciones de escritura.
        """
        if not command:
            return False

        # Lista de comandos considerados seguros (solo lectura / informativos)
        SAFE_COMMANDS = {
            'ls', 'pwd', 'cat', 'grep', 'egrep', 'fgrep', 'find', 'locate', 
            'whoami', 'date', 'head', 'tail', 'wc', 'diff', 'cd', 'tree', 
            'history', 'ps', 'top', 'htop', 'man', 'help', 'which', 'type',
            'echo', 'printf', 'stat', 'du', 'df', 'free', 'uname', 'hostname',
            'uptime', 'jobs', 'bg', 'fg', 'clear'
        }

        # Verificar redirecciones de salida que podrían sobrescribir archivos
        if '>' in command:
            return False
        
        # Simplificación: dividir por operadores comunes de encadenamiento
        # Esto no es un parser completo de bash, pero cubre casos comunes
        parts = command.replace('|', ';').replace('&&', ';').split(';')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Obtener el primer token (el comando en sí)
            tokens = part.split()
            if not tokens:
                continue
                
            cmd = tokens[0]
            
            # Manejar asignaciones de variables al inicio (ej: VAR=val cmd)
            # Si el comando contiene =, asumimos que es una asignación y miramos el siguiente token si existe
            if '=' in cmd and len(tokens) > 1:
                 cmd = tokens[1]
            elif '=' in cmd:
                 # Solo asignación, seguro
                 continue

            if cmd not in SAFE_COMMANDS:
                return False
                
        return True

    async def handle_command_approval(self, command_to_execute: str, auto_approve: bool = False,
                                 is_user_confirmation: bool = False, is_file_update_confirmation: bool = False, confirmation_prompt: Optional[str] = None,
                                 tool_name: Optional[str] = None, raw_tool_output: Optional[str] = None,
                                 original_tool_args: Optional[Dict[str, Any]] = None) -> dict:
        logger.debug(f"DEBUG: handle_command_approval - raw_tool_output recibido: {raw_tool_output}") # <-- Añadir este log
        """
        Handles the approval process for a command generated by the agent or a user confirmation request.
        Can also handle file update confirmations by displaying a diff.
        Returns a dictionary with the updated agent state and tool message content.
        """
        # 1. Recuperar el tool_call_id del AIMessage más reciente
        # Asegurarse de que tool_call_id siempre sea una cadena válida
        tool_call_id = self.agent_state.tool_call_id_to_confirm if self.agent_state.tool_call_id_to_confirm else str(uuid.uuid4())

        # 2. Generar la explicación del comando o usar el prompt de confirmación
        explanation_text = ""
        panel_title = 'Confirmación de Comando'
        panel_content_markdown = ""
        full_command_output = "" # Inicializar aquí
        
        is_file_update_confirmation = False
        is_plan_confirmation = False # Nueva bandera para la confirmación del plan
        diff_content = ""
        file_path = ""
        message = ""
        plan_title = ""
        plan_steps = []

        if isinstance(raw_tool_output, dict) and raw_tool_output.get("status") == "requires_confirmation":
            if raw_tool_output.get("operation") == "plan_creation":
                logger.debug("DEBUG: raw_tool_output es un diccionario con status: requires_confirmation y operation: plan_creation.")
                is_plan_confirmation = True
                plan_title = raw_tool_output.get("plan_title", "Plan de Acción")
                plan_steps = raw_tool_output.get("plan_steps", [])
                message = raw_tool_output.get("message", "Se ha generado un plan. Por favor, revísalo y confírmalo para proceder.")
                tool_name = "plan_creation_tool" # Asegurar que el tool_name sea correcto
            else:
                logger.debug("DEBUG: raw_tool_output es un diccionario con status: requires_confirmation.")
                diff_content = raw_tool_output.get("diff", "")
                file_path = raw_tool_output.get("path", raw_tool_output.get("args", {}).get("path", "archivo desconocido"))
                message = raw_tool_output.get("action_description", f"Se detectaron cambios para '{file_path}'. Por favor, confirma para aplicar.")
                tool_name = raw_tool_output.get("operation", tool_name) # Actualizar tool_name con la operación real
                original_tool_args = raw_tool_output.get("args", original_tool_args)
                logger.debug(f"DEBUG: CommandApprovalHandler - original_tool_args después de asignación: {original_tool_args}") # <-- Añadir este log
                is_file_update_confirmation = True

        if is_plan_confirmation:
            logger.debug("DEBUG: is_plan_confirmation es True. Preparando panel de plan.")
            panel_title = f'Confirmación de Plan: {plan_title}'
            plan_markdown = f"**{message}**\n\n"
            for step in plan_steps:
                plan_markdown += f"- **Paso {step['step']}**: {step['description']}\n"
            panel_content_markdown = Markdown(plan_markdown)

            self.terminal_ui.console.print(
                Panel(
                    panel_content_markdown,
                    border_style='cyan', # Un color diferente para los planes
                    title=panel_title
                ),
                soft_wrap=True, overflow="fold", highlight=False, markup=True, end="\n"
            )
        elif is_file_update_confirmation:
            logger.debug("DEBUG: is_file_update_confirmation es True. Preparando panel de diff.")
            panel_title = f'[bold]Confirmación de Actualización:[/bold] [cyan]{file_path}[/cyan]'
            if tool_name == "file_operations" and original_tool_args and original_tool_args.get("operation") == "delete_file":
                # Si es una operación de eliminación, mostrar solo la ruta del archivo
                panel_content_markdown = Markdown(
                    f"""**Eliminación de Archivo Requerida:**\n{message}\n\n**Archivo a eliminar:**\n```\n{file_path}\n```\n"""
                )
                self.terminal_ui.console.print(
                    Panel(
                        panel_content_markdown,
                        border_style='yellow',
                        title=panel_title
                    ),
                    soft_wrap=True, overflow="fold", highlight=False, markup=True, end="\n"
                )
            else:
                # Usar DiffRenderer para visualización mejorada
                diff_table = self.diff_renderer.render_diff_from_string(diff_content, file_path)
                
                # Construir el contenido del panel con el mensaje y el diff renderizado
                # Usar Markdown para el mensaje para que se renderice correctamente (**texto**)
                panel_content = Group(
                    Markdown(f"**Actualización de Archivo Requerida:**\n{message}\n"),
                    diff_table
                )
                
                self.terminal_ui.console.print(
                    Panel(
                        panel_content,
                        border_style='yellow',
                        title=panel_title
                    ),
                    soft_wrap=False,
                    overflow="fold",
                    highlight=False, markup=True, end="\n"
                )
        elif is_user_confirmation and confirmation_prompt:
            explanation_text = confirmation_prompt
            panel_title = 'Confirmación de Usuario Requerida'
            panel_content_markdown = Markdown(f"""**Acción requerida:**\n{explanation_text}""")
        else:
            # Siempre intentar generar una explicación para el comando bash
            explanation_prompt = HumanMessage(
                content=f"Genera una explicación concisa del siguiente comando bash: `{command_to_execute}`. No incluyas el comando en la explicación, solo el texto explicativo. La explicación debe ser de máximo 2 frases."
            )
            temp_history_for_explanation = [
                msg for msg in self.agent_state.messages if msg.type != "tool"
            ]
            temp_history_for_explanation.append(explanation_prompt)
            
            try:
                explanation_response_generator = self.llm_service.invoke(temp_history_for_explanation, save_history=False) # No guardar historial para explicaciones
                full_response_content = ""
                
                # Asegurarse de que explanation_response_generator es un async generator
                for chunk in explanation_response_generator: # Siempre iterar sobre el generador
                    if isinstance(chunk, AIMessage):
                        # Si recibimos un AIMessage, solo usamos su contenido si no hemos acumulado nada vía streaming
                        # Esto evita duplicar el texto, ya que llm_service emite chunks de texto Y un AIMessage final con todo el contenido.
                        if not full_response_content and chunk.content:
                             full_response_content = chunk.content
                    elif isinstance(chunk, str):
                        full_response_content += chunk
                    else:
                        content_part = str(chunk)
                        # Evitar duplicación si el objeto convertido a string es igual a lo que ya tenemos (heurística simple)
                        if content_part not in full_response_content:
                            full_response_content += content_part

                explanation_text = full_response_content.strip() if full_response_content.strip() else "No se pudo generar una explicación concisa." # Manejo de respuesta vacía
                logger.debug(f"DEBUG: Longitud de explanation_text: {len(explanation_text)}") # Nuevo log

            except Exception as e:
                logger.error(f"Error al generar explicación para el comando: {e}")
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
        # logger.debug(f"DEBUG: is_file_update_confirmation: {is_file_update_confirmation}")
        # logger.debug(f"DEBUG: diff_content (primeras 100 chars): {diff_content[:100]}")
        # logger.debug(f"DEBUG: file_path: {file_path}")
        # logger.debug(f"DEBUG: message: {message}")
        # logger.debug(f"DEBUG: panel_title: {panel_title}")
        # logger.debug(f"DEBUG: panel_content_markdown (primeras 100 chars): {str(panel_content_markdown)[:100]}")

        if not is_plan_confirmation and not is_file_update_confirmation: # Solo imprimir si no se imprimió ya
            self.terminal_ui.print_confirmation_panel(
                panel_content_markdown,
                panel_title,
                'yellow'
            )
        # Forzar un re-renderizado del prompt para asegurar que el panel se muestre antes de la entrada

        # 4. Solicitar aprobación al usuario
        run_action = False
        
        # Verificar si el comando es seguro para auto-aprobación
        if not auto_approve and command_to_execute and not is_plan_confirmation and not is_file_update_confirmation and not is_user_confirmation:
            if self._is_command_safe(command_to_execute):
                auto_approve = True
                self.terminal_ui.print_message(f"Comando '{command_to_execute}' considerado seguro. Auto-aprobando.", style="green")

        if auto_approve:
            run_action = True
            self.terminal_ui.print_message("Acción auto-aprobada.", style="yellow")
        else:
            while True:
                # logger.debug("DEBUG: Esperando input de aprobación del usuario...")
                try:
                    approval_input = await self.prompt_session.prompt_async("¿Deseas ejecutar esta acción? (s/n): ")
                    # logger.debug(f"DEBUG: Input de aprobación recibido: {approval_input}")
                except Exception as e:
                    logger.error(f"ERROR: Excepción al solicitar input de aprobación: {e}", exc_info=True)
                    approval_input = "n" # Asumir denegación en caso de error
                
                if approval_input is None:
                    # logger.debug("DEBUG: approval_input es None. Asumiendo denegación.")
                    # Si el usuario interrumpe el prompt (ej. Ctrl+D), asumimos que deniega.
                    approval_input = "n"
                else:
                    approval_input = approval_input.lower().strip()
                    # logger.debug(f"DEBUG: approval_input procesado: {approval_input}")

                if approval_input == 's':
                    run_action = True
                    break
                elif approval_input == 'n':
                    run_action = False
                    break
                else:
                    self.terminal_ui.print_message("Respuesta no válida. Por favor, responde 's' o 'n'.", style="red")

        # 5. Ejecutar el comando y manejar la salida (o procesar la confirmación del usuario)
        tool_message_content = ""
        if run_action:
            if is_plan_confirmation:
                tool_message_content = json.dumps({
                    "status": "plan_approved",
                    "plan_title": plan_title,
                    "plan_steps": plan_steps,
                    "message": "Plan aprobado por el usuario."
                })
                self.terminal_ui.print_message(f"Plan '{plan_title}' aprobado. ¡A trabajar! 🚀", style="green")
            elif is_file_update_confirmation:
                # Re-ejecutar la herramienta con los args originales (que ya incluyen confirm=True)
                # logger.debug(f"DEBUG: CommandApprovalHandler - tool_name en re-invocación: {tool_name}") # <-- Añadir este log
                if tool_name == "file_update_tool":
                    result = self.file_update_tool._apply_update(file_path, original_tool_args.get("content", ""))
                    tool_message_content = json.loads(result).get("message", "")
                elif tool_name == "advanced_file_editor":
                    result = self.advanced_file_editor_tool._run(**original_tool_args)
                    tool_message_content = result.get("message", "")
                elif tool_name == "file_operations": # Añadir manejo para file_operations
                    # logger.debug(f"DEBUG: CommandApprovalHandler - Re-invocando file_operations con args: {original_tool_args}") # <-- Añadir este log
                    result = self.file_operations_tool._run(**original_tool_args)
                    # logger.debug(f"DEBUG: CommandApprovalHandler - Resultado de re-invocación de file_operations: {result}") # <-- Añadir este log
                    tool_message_content = result.get("message", str(result)) if isinstance(result, dict) else str(result) # Modificación aquí
                
                self.terminal_ui.print_message(f"Confirmación de actualización para '{file_path}': Aprobado. {tool_message_content}", style="green")
            elif is_user_confirmation:
                tool_message_content = f"Confirmación de usuario: Aprobado para '{confirmation_prompt}'."
                self.terminal_ui.print_message("Acción de usuario aprobada.", style="green")
            else:
                full_command_output = ""
                try:
                    # Separador visual antes del comando con temas
                    if THEMES_AVAILABLE:
                        separator_line = create_separator()
                        self.terminal_ui.console.print(separator_line)
                        self.terminal_ui.console.print(f"[bold {ColorPalette.SECONDARY}]{Icons.GEAR} Ejecutando:[/bold {ColorPalette.SECONDARY}] [{ColorPalette.SECONDARY_LIGHT}]{command_to_execute}[/{ColorPalette.SECONDARY_LIGHT}]")
                        self.terminal_ui.console.print(separator_line)
                    else:
                        # Fallback al separador original
                        separator = "━" * 80
                        self.terminal_ui.console.print(f"\n[cyan]{separator}[/cyan]")
                        self.terminal_ui.console.print(f"[bold cyan]🔧 Ejecutando:[/bold cyan] [yellow]{command_to_execute}[/yellow]")
                        self.terminal_ui.console.print(f"[cyan]{separator}[/cyan]\n")

                    for output_chunk in self.command_executor.execute(command_to_execute, cwd=os.getcwd(), interrupt_queue=self.interrupt_queue):
                        # NO imprimir aquí - command_executor ya imprime a stdout para interactividad
                        # self.terminal_ui.print_stream(output_chunk)
                        full_command_output += output_chunk
                    
                    # Separador visual después del comando con temas
                    if THEMES_AVAILABLE:
                        separator_line = create_separator()
                        self.terminal_ui.console.print(separator_line)
                        self.terminal_ui.console.print(f"[bold {ColorPalette.SUCCESS}]{Icons.SUCCESS} Comando completado[/bold {ColorPalette.SUCCESS}]")
                        self.terminal_ui.console.print(separator_line)
                    else:
                        # Fallback al separador original
                        self.terminal_ui.console.print(f"\n[cyan]{separator}[/cyan]")
                        self.terminal_ui.console.print(f"[bold green]✓ Comando completado[/bold green]")
                        self.terminal_ui.console.print(f"[cyan]{separator}[/cyan]\n")
                    
                    
                    # Truncamiento desactivado - mostrar salida completa
                    tool_message_content = full_command_output if full_command_output.strip() else "El comando se ejecutó correctamente y no produjo ninguna salida."

                except KeyboardInterrupt:
                    self.command_executor.terminate()
                    tool_message_content = "Comando cancelado por el usuario."
                    self.terminal_ui.print_message("\n\nComando cancelado por el usuario.", style="red")
                except Exception as e:
                    raise e # Re-lanzar la excepción
        else:
            if is_plan_confirmation:
                tool_message_content = json.dumps({
                    "status": "plan_denied",
                    "plan_title": plan_title,
                    "message": "Plan denegado por el usuario."
                })
                self.terminal_ui.print_message(f"Plan '{plan_title}' denegado. 😔", style="yellow")
            elif is_file_update_confirmation:
                tool_message_content = f"Confirmación de actualización para '{file_path}': Denegado. Cambios no aplicados."
                self.terminal_ui.print_message(f"Confirmación de actualización para '{file_path}': Denegado.", style="yellow")
            elif is_user_confirmation:
                tool_message_content = f"Confirmación de usuario: Denegado para '{confirmation_prompt}'."
                self.terminal_ui.print_message("Acción de usuario denegada.", style="yellow")
            else:
                tool_message_content = "Comando no ejecutado por el usuario."
                self.terminal_ui.print_message("Comando no ejecutado.", style="yellow")
            full_command_output = "" # Asegurar que full_command_output siempre tenga un valor

        # 6. Añadir el mensaje al historial (AIMessage si es denegado, ToolMessage si es ejecutado)
        # logger.debug(f"DEBUG: CommandApprovalHandler - run_action: {run_action}") # <-- Añadir este log
        # logger.debug(f"DEBUG: CommandApprovalHandler - tool_message_content antes de añadir al historial: {tool_message_content}") # <-- Añadir este log
        if run_action:
            # Si es una confirmación de plan, el contenido ya es un JSON que el agente puede parsear
            self.agent_state.messages.append(ToolMessage(
                content=tool_message_content,
                tool_call_id=tool_call_id # Usar el tool_call_id propagado
            ))
            # logger.debug(f"DEBUG: CommandApprovalHandler - ToolMessage añadido al historial con ID: {tool_call_id}") # <-- Añadir este log
        else: # Acción denegada
            self.agent_state.messages.append(AIMessage(content=tool_message_content))
            self.terminal_ui.print_message("Acción denegada por el usuario.", style="yellow")
            # logger.debug("DEBUG: CommandApprovalHandler - AIMessage de denegación añadido al historial.") # <-- Añadir este log

        # 7. Guardar el historial antes de la re-invocación
        self.llm_service._save_history(self.agent_state.messages)
        # logger.debug("DEBUG: CommandApprovalHandler - Historial guardado.") # <-- Añadir este log

        # 8. Devolver el estado actualizado y el contenido del ToolMessage
        return {"messages": self.agent_state.messages, "tool_message_content": tool_message_content, "approved": run_action, "command_output": full_command_output}

    def handle_approval(self, action_description: str, diff: Optional[str] = None) -> bool:
        """
        Versión síncrona y simplificada para ser llamada desde herramientas de CrewAI.
        Maneja internamente el bucle de eventos asíncronos.
        """
        import asyncio
        import nest_asyncio
        nest_asyncio.apply()

        # Crear un objeto de respuesta simulado para handle_command_approval
        raw_output = {
            "status": "requires_confirmation",
            "action_description": action_description,
            "diff": diff,
            "path": action_description.split("'")[1] if "'" in action_description else "archivo"
        }

        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(self.handle_command_approval(
                command_to_execute="",
                raw_tool_output=raw_output
            ))
            return result.get("approved", False)
        except Exception as e:
            logger.error(f"Error en handle_approval: {e}")
            return False