import os
import queue
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
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


