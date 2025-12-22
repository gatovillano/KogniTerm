import os
import queue
import json # Importar json
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agent_state import AgentState # Importar AgentState desde el archivo consolidado
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console, Group # Importar Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text # Importar Text
from rich.syntax import Syntax # Importar Syntax
from rich.status import Status
from rich.align import Align

# Importar módulos de temas y componentes visuales
from .themes import ColorPalette, Icons, Gradients, TextStyles, get_kogniterm_theme
from .visual_components import (
    create_gradient_text,
    create_welcome_banner,
    create_info_panel,
    create_success_box,
    create_error_box,
    create_warning_box,
    create_status_message,
    create_separator,
    get_random_motivational_message,
    format_command,
    format_file_path
)

"""
This module contains the TerminalUI class, responsible for handling all user interface
related interactions in the KogniTerm application.
"""

class TerminalUI:
    def __init__(self, console: Console | None = None):
        self.console = console if console else Console(theme=get_kogniterm_theme())
        self.interrupt_queue = queue.Queue()
        self.kb = KeyBindings()
        self.prompt_session = PromptSession(key_bindings=self.kb) # Inicializar prompt_session aquí

        @self.kb.add('escape')
        def _(event):
            self.interrupt_queue.put("interrupt")
            event.app.current_buffer.cancel_completion() # Limpiar el prompt

    def refresh_theme(self):
        """Recarga el tema de la consola."""
        # Creamos una nueva consola con el tema actualizado
        self.console = Console(theme=get_kogniterm_theme())
        # Actualizamos también los estilos de texto que dependen de ColorPalette
        from .themes import TextStyles
        # Nota: TextStyles en Python no se actualiza automáticamente si sus atributos
        # fueron asignados por valor. Pero en themes.py, TextStyles usa ColorPalette.ATRIBUTO.
        # Al ser una clase con atributos de clase, deberíamos asegurar que se refresquen
        # si es necesario, aunque en la implementación actual de themes.py, 
        # TextStyles se define una sola vez al importar. 
        pass


    def print_stream(self, text: str):
        """
        Prints a chunk of text to the console without adding a newline,
        and flushes the output immediately.
        """
        self.console.print(text, end="")

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
            # Si es una actualización o cualquier otra operación con diff, usar Syntax para resaltado
            diff_syntax = Syntax(diff_content, "diff", theme="monokai", line_numbers=False, word_wrap=True)
            
            # Construir el contenido del panel con el mensaje y el diff formateado
            panel_content = Group(
                Text.from_markup(f"**Actualización de Archivo Requerida:**\n{message}\n\n"),
                diff_syntax # Usar Syntax para el diff
            )

            self.print_confirmation_panel(
                panel_content,
                f'Confirmación de Actualización: {file_path}',
                'yellow'
            )

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
                # La lógica para aplicar la actualización de archivo se moverá a CommandApprovalHandler
                # por ahora, se simula una respuesta.
                tool_message_content = f"Simulación: Actualización para '{file_path}' aplicada."
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

    def print_message(self, message: str, style: str = "", is_user_message: bool = False, status: str = None):
        """
        Prints a message to the console with optional styling.
        If is_user_message is True, the message will be enclosed in a Panel.
        If status is provided, adds contextual icon and color.
        """
        if is_user_message:
            self.console.print(Padding(Panel(
                Markdown(message),
                title=f"[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.SPEECH} Tu Mensaje[/bold {ColorPalette.PRIMARY_LIGHT}]",
                border_style=ColorPalette.PRIMARY,
                expand=False
            ), (1, 2)))
        elif status:
            # Usar el componente de mensaje de estado
            status_msg = create_status_message(message, status)
            self.console.print(status_msg)
        else:
            self.console.print(message, style=style)

    def get_interrupt_queue(self) -> queue.Queue:
        return self.interrupt_queue

    def print_confirmation_panel(self, content, title, border_style):
        """
        Imprime un panel de confirmación estandarizado con mejor estilo.
        """
        self.console.print(
            Padding(
                Panel(
                    content,
                    border_style=border_style,
                    title=f"{Icons.WARNING} {title}",
                    width=min(self.console.width, 100),  # Limitar el ancho del panel
                    expand=False
                ),
                (1, 2)
            )
        )
    
    def print_status(self, message: str, spinner_style: str = "dots"):
        """
        Muestra un mensaje de estado con un spinner.
        Útil para operaciones que toman tiempo.
        
        Args:
            message: Mensaje a mostrar
            spinner_style: Estilo del spinner
            
        Returns:
            Status: Objeto Status que puede ser usado con 'with' statement
        """
        return Status(
            f"{Icons.PROCESSING} {message}...",
            spinner=spinner_style,
            spinner_style=ColorPalette.SECONDARY
        )
    
    def print_success_box(self, message: str, title: str = "Éxito"):
        """
        Imprime un panel de éxito con estilo consistente.
        
        Args:
            message: Mensaje de éxito
            title: Título del panel
        """
        success_panel = create_success_box(message, title)
        self.console.print(success_panel)
    
    def print_error_box(self, message: str, title: str = "Error"):
        """
        Imprime un panel de error con estilo consistente.
        
        Args:
            message: Mensaje de error
            title: Título del panel
        """
        error_panel = create_error_box(message, title)
        self.console.print(error_panel)
    
    def print_warning_box(self, message: str, title: str = "Advertencia"):
        """
        Imprime un panel de advertencia con estilo consistente.
        
        Args:
            message: Mensaje de advertencia
            title: Título del panel
        """
        warning_panel = create_warning_box(message, title)
        self.console.print(warning_panel)

    def print_welcome_banner(self):
        """
        Prints the welcome banner for KogniTerm with improved gradient and motivational message.
        """
        banner_text = """
██╗  ██╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗███████╗██████╗ ███╗   ███╗
██║ ██╔╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║
█████╔╝ ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║
██╔═██╗ ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║
██║  ██╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║
╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝
"""
        # Usar el componente de banner con gradiente mejorado
        banner = create_welcome_banner(
            banner_text,
            subtitle=get_random_motivational_message(),
            gradient=Gradients.PRIMARY
        )
        self.console.print(banner)
        
        # Panel de bienvenida con mejor estilo
        welcome_panel = Panel(
            f"""Escribe '[{ColorPalette.SUCCESS}]%salir[/{ColorPalette.SUCCESS}]' para terminar o '[{ColorPalette.SUCCESS}]%help[/{ColorPalette.SUCCESS}]' para ver los comandos.""",
            title=f"[bold {ColorPalette.SUCCESS}]{Icons.SPARKLES} Bienvenido[/bold {ColorPalette.SUCCESS}]",
            border_style=ColorPalette.SUCCESS,
            expand=False
        )
        self.console.print(Align.center(welcome_panel))
        self.console.print()  # Margen inferior



