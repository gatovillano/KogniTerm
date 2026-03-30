import logging
from typing import Optional, Dict, Any
import os
from prompt_toolkit import PromptSession
from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agents.bash_agent import AgentState
from kogniterm.terminal.terminal_ui import TerminalUI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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
from kogniterm.terminal.visual_components import create_terminal_output_panel

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
                 file_update_tool: Any = None, advanced_file_editor_tool: Any = None, file_operations_tool: Any = None):
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
            'uptime', 'jobs', 'bg', 'fg', 'clear', 'git status', 'git diff',
            'git log', 'git branch', 'git remote -v', 'git show --stat',
            'cat', 'env', 'grep', 'ls', 'ls -la', 'ls -l', 'ls -R'
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
                
            # Manejar comandos de varios tokens (ej: 'git status')
            cmd = tokens[0]
            if cmd == "git" and len(tokens) > 1:
                cmd_full = f"{tokens[0]} {tokens[1]}"
                if cmd_full in SAFE_COMMANDS:
                    continue
            
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

    def handle_command_approval(self, command_to_execute: str, auto_approve: bool = False,
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
        # --- OPTIMIZACIÓN DE LATENCIA ---
        # 3. Verificar si el comando es seguro para auto-aprobación ANTES de generar explicaciones
        run_action = False
        
        # Atajo: si el comando ya viene auto-aprobado por el agente o el usuario eligió "Aceptar siempre"
        if auto_approve:
            run_action = True
        
        # Verificar seguridad del comando si no está aprobado aún
        if not run_action and command_to_execute and not is_plan_confirmation and not is_file_update_confirmation and not is_user_confirmation:
            if self._is_command_safe(command_to_execute):
                run_action = True
                auto_approve = True # Marcar para feedback visual posterior
                # self.terminal_ui.print_message(f"Comando '{command_to_execute}' considerado seguro. Auto-aprobando.", style="green")

        # 4. Generar explicación SOLO si no está auto-aprobado y necesitamos mostrar el panel
        if not run_action:
            if is_user_confirmation and confirmation_prompt:
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
                            if not full_response_content and chunk.content:
                                 full_response_content = chunk.content
                        elif isinstance(chunk, str):
                            if chunk.startswith("__THINKING__:") or chunk.startswith("THINKING:"):
                                continue
                            full_response_content += chunk
                        else:
                            content_part = str(chunk)
                            if content_part not in full_response_content and not content_part.startswith("__THINKING__:") and not content_part.startswith("THINKING:"):
                                full_response_content += content_part

                    import re
                    explanation_text = full_response_content.strip()
                    explanation_text = re.sub(r'(__THINKING__:?|THINKING:?|\bTHINKING\b:?)', '', explanation_text, flags=re.IGNORECASE)
                    explanation_text = re.sub(r'\s*__\s*', ' ', explanation_text).strip()
                    explanation_text = re.sub(r'<think>.*?</think>', '', explanation_text, flags=re.DOTALL).strip()
                    
                    if not explanation_text:
                        explanation_text = "No se pudo generar una explicación concisa."

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

        # 5. Mostrar la explicación y pedir confirmación si no está auto-aprobado
        if not run_action:
            if not is_plan_confirmation and not is_file_update_confirmation:
                self.terminal_ui.print_confirmation_panel(
                    panel_content_markdown,
                    panel_title,
                    'yellow'
                )

            # Solicitar aprobación de forma síncrona
            approval_message = message if message else explanation_text
            if not approval_message:
                approval_message = "Confirmación requerida para proceder."
            
            diff_to_pass = diff_content
            file_path_to_pass = file_path
            
            if not is_file_update_confirmation and command_to_execute:
                 diff_to_pass = command_to_execute
                 file_path_to_pass = "bash"

            run_action = self.terminal_ui.ask_approval_sync(
                message=approval_message,
                title=panel_title,
                diff_content=diff_to_pass,
                file_path=file_path_to_pass,
            )
        elif auto_approve and command_to_execute:
            # Opción: mostrar un pequeño feedback de que se aprobó automáticamente
            # self.terminal_ui.print_message(f"Ejecutando comando seguro: [bold cyan]{command_to_execute}[/bold cyan]", style="dim cyan")
            pass

        # 6. Ejecutar el comando y manejar la salida
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
                # Ejecutar directamente la operación de archivo
                if tool_name in ["file_update_tool", "file_update"]:
                    # Intentar usar el método de aplicación si es el objeto legacy, 
                    # o llamar a la skill si es la nueva implementación.
                    if hasattr(self.file_update_tool, '_apply_update'):
                        result = self.file_update_tool._apply_update(file_path, original_tool_args.get("content", ""))
                        tool_message_content = json.loads(result).get("message", "")
                    else:
                        # Para la skill, como no tiene 'confirm' en el schema todavía, 
                        # buscamos la función _apply_file_update en su módulo si podemos,
                        # o simplemente usamos una función helper si está disponible.
                        from kogniterm.skills.bundled.file_update.scripts.tool import _apply_file_update
                        result = _apply_file_update(file_path, original_tool_args.get("content", ""))
                        tool_message_content = json.loads(result).get("message", "")

                elif tool_name in ["advanced_file_editor", "advanced_file_editor_tool"]:
                    if hasattr(self.advanced_file_editor_tool, '_apply_advanced_update'):
                        advanced_result = self.advanced_file_editor_tool._apply_advanced_update(
                            file_path, 
                            original_tool_args.get("new_content", original_tool_args.get("content", ""))
                        )
                        tool_message_content = advanced_result.get("message", "")
                    else:
                        # Para la skill advanced_file_editor, podemos llamarla con confirm=True
                        # o usar su función interna.
                        from kogniterm.skills.bundled.advanced_file_editor.scripts.tool import _apply_advanced_update_with_validation
                        advanced_result = _apply_advanced_update_with_validation(
                            file_path, 
                            original_tool_args.get("new_content", original_tool_args.get("content", ""))
                        )
                        tool_message_content = advanced_result.get("message", "")

                elif tool_name in ["file_operations", "file_operations_tool"]:
                    op_type = original_tool_args.get("operation")
                    if hasattr(self.file_operations_tool, '_perform_write_file') and op_type != "delete_file":
                        file_ops_result = self.file_operations_tool._perform_write_file(
                            original_tool_args.get("path", file_path),
                            original_tool_args.get("content", "")
                        )
                        # Asegurar que el contenido sea un string para el ToolMessage
                        if isinstance(file_ops_result, dict):
                            tool_message_content = json.dumps(file_ops_result)
                        else:
                            tool_message_content = str(file_ops_result)
                    else:
                        # Para la skill file_operations
                        if op_type == "delete_file":
                            from kogniterm.skills.bundled.file_operations.scripts.tool import _delete_file
                            file_ops_result = _delete_file(
                                original_tool_args.get("path", file_path),
                                confirm=True
                            )
                        else:
                            from kogniterm.skills.bundled.file_operations.scripts.tool import _write_file
                            file_ops_result = _write_file(
                                original_tool_args.get("path", file_path),
                                original_tool_args.get("content", ""),
                                confirm=True
                            )
                        # Asegurar que el contenido sea un string para el ToolMessage
                        if isinstance(file_ops_result, dict):
                            tool_message_content = json.dumps(file_ops_result)
                        else:
                            tool_message_content = str(file_ops_result)
                
                # NO imprimir mensaje de confirmación aquí - el ToolMessage en el historial es suficiente
            elif is_user_confirmation:
                tool_message_content = f"Confirmación de usuario: Aprobado para '{confirmation_prompt}'."
                # NO imprimir mensaje de confirmación aquí - evitar duplicación
            else:
                full_command_output = ""
                try:
                    # Activar modo terminal interactiva y cursor antes de ejecutar
                    self.terminal_ui.set_terminal_cursor(True, self.command_executor)

                    # Mostrar panel inmediatamente para feedback visual
                    initial_panel = create_terminal_output_panel("Ejecución de Comando", "", max_lines=15)
                    self.terminal_ui.update_live(initial_panel)
                    
                    full_command_output = ""

                    for output_chunk in self.command_executor.execute(command_to_execute, cwd=os.getcwd(), interrupt_queue=self.interrupt_queue):
                        if output_chunk:
                            logger.info(f"Chunk recibido ({len(output_chunk)} bytes)")
                            full_command_output += output_chunk
                            # Actualizar la terminal a través del nuevo método que soporta cursor
                            self.terminal_ui.update_terminal_output("Ejecución de Comando", full_command_output)
                    
                    # Desactivar modo terminal al finalizar
                    self.terminal_ui.set_terminal_cursor(False)
                    self.terminal_ui.stop_live()
                    
                    # Separador visual después del comando con temas
                    if THEMES_AVAILABLE:
                        self.terminal_ui.console.print(f"\n[bold {ColorPalette.SUCCESS}]{Icons.SUCCESS} Comando completado[/bold {ColorPalette.SUCCESS}]\n")
                    else:
                        # Fallback al separador original
                        self.terminal_ui.console.print(f"\n[bold green]✓ Comando completado[/bold green]\n")
                    
                    
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
                # NO imprimir mensaje aquí - el AIMessage en el historial es suficiente
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
            # NO imprimir mensaje aquí - el AIMessage en el historial es suficiente
            # El LLM procesará la denegación correctamente desde el historial

        # 7. Guardar el historial antes de la re-invocación
        self.llm_service._save_history(self.agent_state.messages)
        # logger.debug("DEBUG: CommandApprovalHandler - Historial guardado.") # <-- Añadir este log

        # 8. Devolver el estado actualizado y el contenido del ToolMessage
        return {"messages": self.agent_state.messages, "tool_message_content": tool_message_content, "approved": run_action, "command_output": full_command_output}

    # La función handle_approval (síncrona) ha sido eliminada por ser peligrosa
    # y causar crashes al usar loops anidados en hilos worker.
    # El flujo de confirmación ahora es puramente asíncrono y se maneja
    # burbujeando el estado al hilo principal TUI.