import sys
import queue
import json
import shutil
from rich.console import Console, Group
from rich.status import Status
from rich.panel import Panel
from rich.padding import Padding
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.align import Align
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from .security import scrub_secrets

from .themes import ColorPalette, Icons, Gradients
from .visual_components import (
    create_status_message, 
    create_thought_bubble, 
    create_success_box, 
    create_error_box, 
    create_warning_box, 
    create_welcome_banner,
    get_random_motivational_message,
    get_kogniterm_theme
)

class TerminalUI:
    def __init__(self, console: Console | None = None):
        # True when output is a terminal (supports colors/interactive features)
        self.is_tty = sys.stdout.isatty()
        self.console = console or Console(theme=get_kogniterm_theme())
        self.prompt_session = PromptSession()
        self.interrupt_queue = queue.Queue()

        if not self.is_tty:
            # For non-tty (dumb) terminals, disable color and terminal features
            pass

        # El binding de Escape se maneja ahora centralmente en KogniTermApp para evitar conflictos
        # con el historial y el autocompletado.

        # Callback de resize para notificar a la aplicación principal
        self.resize_callback = None

    def handle_resize(self):
        """Maneja el redimensionamiento de la terminal refrescando la consola."""
        # Obtener dimensiones actuales de forma explícita usando shutil
        size = shutil.get_terminal_size()
        
        # Actualizar la consola existente si es posible para mantener el estado
        # Rich detecta automáticamente el ancho si no se especifica, pero aquí lo forzamos
        # para asegurar consistencia tras la señal SIGWINCH.
        self.console.width = size.columns
        self.console.height = size.lines
        
        # Opcionalmente, recreamos con el nuevo tamaño si hay problemas de buffers
        # Pero mantenemos el tema original.
        self.console = Console(
            theme=get_kogniterm_theme(),
            width=size.columns,
            height=size.lines,
            force_terminal=True,
            soft_wrap=True # Habilitar soft_wrap global para evitar desestructurar paneles
        )
        
        # Notificar a la aplicación principal (callback)
        if self.resize_callback:
            try:
                self.resize_callback(size.columns, size.lines)
            except Exception:
                pass # No propagar errores del callback
        
        # Si hay procesos de streaming activos, esto asegurará que el próximo chunk use el nuevo ancho.    def refresh_theme(self):
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

    def handle_resize(self):
        """Maneja el redimensionamiento de la terminal refrescando la consola."""
        # Obtener dimensiones actuales de forma explícita usando shutil
        size = shutil.get_terminal_size()
        
        # Actualizar la consola existente si es posible para mantener el estado
        # Rich detecta automáticamente el ancho si no se especifica, pero aquí lo forzamos
        # para asegurar consistencia tras la señal SIGWINCH.
        self.console.width = size.columns
        self.console.height = size.lines
        
        # Opcionalmente, recreamos con el nuevo tamaño si hay problemas de buffers
        # Pero mantenemos el tema original.
        self.console = Console(
            theme=get_kogniterm_theme(),
            width=size.columns,
            height=size.lines,
            force_terminal=True,
            soft_wrap=True # Habilitar soft_wrap global para evitar desestructurar paneles
        )
        
        # Si hay procesos de streaming activos, esto asegurará que el próximo chunk use el nuevo ancho.

    def get_terminal_dimensions(self) -> tuple[int, int]:
        """Retorna dimensiones actuales de terminal para ejecutar comandos PTY."""
        size = shutil.get_terminal_size(fallback=(120, 30))
        cols = max(40, int(size.columns))
        rows = max(12, int(size.lines))
        return cols, rows


    def print_stream(self, text: str):
        """
        Prints a chunk of text to the console without adding a newline,
        and flushes the output immediately.
        """
        text = scrub_secrets(text)
        self.console.print(text, end="")

    def update_live(self, renderable):
        """Actualiza el contenido en streaming (sobrescrito en adaptadores)."""
        pass

    def update_terminal_output(self, tool_name: str, output: str):
        """
        Actualiza específicamente un panel de salida de terminal.
        Los adaptadores pueden usar esto para manejar cursores o refrescos por tiempo.
        """
        from .visual_components import create_terminal_output_panel
        panel = create_terminal_output_panel(tool_name, output)
        self.update_live(panel)

    def stop_live(self):
        """Finaliza el streaming y consolida el mensaje (sobrescrito en adaptadores)."""
        pass

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
                if self.is_tty:
                    approval_input = input("¿Deseas aplicar estos cambios? (s/n): ")
                else:
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

    async def ask_approval_async(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
    ) -> bool:
        """
        Versión asíncrona para solicitar aprobación.
        En CLI usa prompt_async, en TUI usa un modal.
        """
        self.print_confirmation_panel(
            f"**{message}**\n\n{diff_content}" if diff_content else message,
            title,
            'yellow'
        )
        approval_input = await self.prompt_session.prompt_async("¿Deseas proceder? (s/n): ")
        return (approval_input or "").lower().strip() == 's'

    def ask_approval_sync(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
    ) -> bool:
        """
        Versión síncrona para solicitar aprobación.
        En CLI usa input(), en TUI bloquea el hilo worker hasta respuesta.
        """
        if self.is_tty:
            self.print_confirmation_panel(
                f"**{message}**\n\n{diff_content}" if diff_content else message,
                title,
                'yellow'
            )
            approval_input = input("¿Deseas proceder? (s/n): ")
        else:
            # Fallback (usualmente sobreescrito en TUI)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # No podemos bloquear el hilo del loop
                    return False 
                else:
                    approval_input = loop.run_until_complete(self.prompt_session.prompt_async("¿Deseas proceder? (s/n): "))
            except:
                approval_input = input("¿Deseas proceder? (s/n): ")
        
        return (approval_input or "").lower().strip() == 's'

    def ask_question_sync(
        self,
        question: str,
        options: list,
        title: str = "Consulta del Agente",
        allow_freeform: bool = True,
    ) -> str:
        """Versión síncrona de fallback para preguntar al usuario en modo CLI básico."""
        self.console.print(f"\n[bold #A78BFA]❓ {title}[/bold #A78BFA]")
        self.console.print(f"[bold white]{question}[/bold white]\n")
        for i, opt in enumerate(options, start=1):
            self.console.print(f"  [bold cyan]{i}.[/bold cyan] {opt}")
        if allow_freeform:
            self.console.print("  [dim](o escribe tu respuesta personalizada)[/dim]")

        while True:
            try:
                raw = input(f"Selecciona [1-{len(options)}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return "Cancelado por el usuario."
            if not raw:
                continue
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            if allow_freeform:
                return raw

    def ask_approval_sync(
        self,
        message: str,
        title: str = "Aprobación Requerida",
        diff_content: str = "",
        file_path: str = "",
    ) -> bool:
        """
        Versión síncrona para solicitar aprobación.
        En CLI usa input(), en TUI bloquea el hilo worker hasta respuesta.
        """
        self.print_confirmation_panel(
            f"**{message}**\n\n{diff_content}" if diff_content else message,
            title,
            'yellow'
        )
        if self.is_tty:
            approval_input = input("¿Deseas proceder? (s/n): ")
        else:
            # Fallback a un bucle sobre prompt_async si no estamos en TUI pero sí en un loop
            # Pero en TerminalUI sync usualmente es para CLI real.
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Esto es peligroso en el loop principal, pero útil en hilos
                    from concurrent.futures import Future
                    future = Future()
                    def _do_prompt():
                        try:
                            res = loop.run_until_complete(self.prompt_session.prompt_async("¿Deseas proceder? (s/n): "))
                            future.set_result(res)
                        except Exception as e:
                            future.set_exception(e)
                    # Nota: run_until_complete no puede llamarse desde el hilo del loop.
                    # Este método suele sobreescribirse en adaptadores (como TUI).
                    return False 
                else:
                    approval_input = loop.run_until_complete(self.prompt_session.prompt_async("¿Deseas proceder? (s/n): "))
            except:
                approval_input = input("¿Deseas proceder? (s/n): ")
        
        return (approval_input or "").lower().strip() == 's'

    def set_terminal_cursor(self, active: bool, executor=None):
        """
        Activa o desactiva el cursor visual de terminal en la UI.
        Sobreescrito en adaptadores que lo soporten (TUI).
        """
        pass

    def print_message(self, message: str, style: str = "", is_user_message: bool = False, status: str = None, use_bubble: bool = False):
        """
        Prints a message to the console with optional styling.
        If is_user_message is True, the message will be enclosed in a Panel.
        If status is provided, adds contextual icon and color.
        If use_bubble is True, uses the thought bubble style.
        """
        if is_user_message:
            self.console.print(Padding(Panel(
                Markdown(message),
                title=f"[bold {ColorPalette.PRIMARY_LIGHT}]{Icons.SPEECH} Tu Mensaje[/]",
                border_style=ColorPalette.PRIMARY,
                expand=False
            ), (1, 2)))
        elif status:
            # Usar el componente de mensaje de estado
            status_msg = create_status_message(message, status)
            self.console.print(status_msg)
        elif use_bubble:
            # Usar burbuja de pensamiento si se solicita explícitamente
            if message.strip():
                thought_bubble = create_thought_bubble(
                    message,
                    title="KogniTerm",
                    icon=Icons.ROBOT,
                    color=ColorPalette.SECONDARY
                )
                self.console.print(Align.center(thought_bubble))
        else:
            # Por defecto, imprimir como Markdown o texto plano
            if message.strip():
                message = scrub_secrets(message)
                content = Markdown(message) if not style else message
                # Aplicar el mismo margen que en el stream (sangría de 4 espacios)
                renderable = Padding(content, (0, 4)) if not style else content
                self.console.print(Align.center(renderable))

    def get_interrupt_queue(self) -> queue.Queue:
        return self.interrupt_queue

    def print_confirmation_panel(self, content, title, border_style):
        """
        Imprime un panel de confirmación estandarizado con mejor estilo.
        """
        from rich import box
        title_text = Text(f"{Icons.WARNING} {title}", style=f"bold {border_style}")
        group = Group(title_text, "", content)
        
        self.console.print(
            Padding(
                Panel(
                    group,
                    width=min(self.console.width - 4, 100),  # Ajustar dinámicamente al ancho menos padding
                    expand=False,
                    box=None  # Sin bordes exteriores ni líneas divisorias
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
        banner_text = (
            "░█░█░█▀█░█▀▀░█▀█░▀█▀░▀█▀░█▀▀░█▀▄░█▄█\n"
            "░█▀▄░█░█░█░█░█░█░░█░░░█░░█▀▀░█▀▄░█░█\n"
            "░▀░▀░▀▀▀░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀░▀░▀░▀░▀"
        )
        # Usar el componente de banner con gradiente mejorado
        banner = create_welcome_banner(
            banner_text,
            subtitle=get_random_motivational_message(),
            color=ColorPalette.PRIMARY
        )
        self.console.print(banner)
        
        # Panel de bienvenida con mejor estilo
        welcome_panel = Panel(
            f"""Escribe '[{ColorPalette.SUCCESS}]%salir[/{ColorPalette.SUCCESS}]' para terminar o '[{ColorPalette.SUCCESS}]%help[/{ColorPalette.SUCCESS}]' para ver los comandos.""",
            title=f"[bold {ColorPalette.SUCCESS}]{Icons.SPARKLES} Bienvenido[/]",
            border_style=ColorPalette.SUCCESS,
            expand=False
        )
        self.console.print(Align.center(welcome_panel))
        self.console.print()  # Margen inferior



