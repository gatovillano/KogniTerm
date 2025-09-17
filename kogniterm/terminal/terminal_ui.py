import re
from rich.text import Text
from rich.syntax import Syntax
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.live import Live
from rich.status import Status

class TerminalUI:
    def __init__(self, console: Console | None = None):
        self.console = console if console else Console()
        self.rich_available = console is not None # Asumimos que si hay consola, rich está disponible

    def _format_text_with_basic_markdown(self, text: str) -> Text:
        """Applies basic Markdown-like formatting to a string using rich.Text."""
        formatted_text = Text()
        
        lines = text.split('\n')
        
        in_code_block = False
        code_block_lang = ""
        code_block_content = []

        for line in lines:
            code_block_match = re.match(r"```(\w*)", line)
            if code_block_match:
                if in_code_block: # End of code block
                    in_code_block = False
                    if code_block_content:
                        code_str = "\n".join(code_block_content)
                        lexer = code_block_lang if code_block_lang else "plaintext"
                        formatted_text.append(Text.from_ansi(str(Syntax(code_str, lexer, theme="monokai", line_numbers=False))))
                        code_block_content = []
                    formatted_text.append("\n")
                else: # Start of code block
                    in_code_block = True
                    code_block_lang = code_block_match.group(1) if code_block_match.group(1) else ""
                    formatted_text.append("\n")
            elif in_code_block:
                code_block_content.append(line)
            else:
                # Apply inline formatting (bold)
                parts = re.split(r"(\*\*.*?\*\*)", line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        formatted_text.append(part[2:-2], style="bold")
                    else:
                        formatted_text.append(part)
                formatted_text.append("\n")

        if in_code_block and code_block_content:
            code_str = "\n".join(code_block_content)
            lexer = code_block_lang if code_block_lang else "plaintext"
            formatted_text.append(Text.from_ansi(str(Syntax(code_str, lexer, theme="monokai", line_numbers=False))))

        return formatted_text

    def print_welcome_banner(self):
        """Imprime el banner de bienvenida con un degradado de colores."""
        self.console.print() # Margen superior
        banner_text = """
██╗  ██╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗███████╗██████╗ ███╗   ███╗
██║ ██╔╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║
█████╔╝ ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║
██╔═██╗ ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║
██║  ██╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║
╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝
"""
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

    def display_message(self, message: str, style: str = "white", padding_top: int = 0, padding_bottom: int = 0):
        if self.rich_available:
            self.console.print(Padding(Text(message, style=style), (padding_top, 2, padding_bottom, 2)))
        else:
            print(message)

    def display_markdown(self, markdown_text: str, title: str | None = None, border_style: str = "none", padding_top: int = 0, padding_bottom: int = 0):
        if self.rich_available:
            panel = Panel(Markdown(markdown_text), border_style=border_style, title=title)
            self.console.print(Padding(panel, (padding_top, 2, padding_bottom, 2)))
        else:
            print(markdown_text)

    def display_command_output(self, output: str):
        if self.rich_available:
            self.console.print(self._format_text_with_basic_markdown(output))
        else:
            print(output)

    def display_python_output(self, structured_output: dict):
        if not self.rich_available:
            print("--- Salida del Código Python ---")
            # Fallback para cuando rich no está disponible
            for item in structured_output.get("result", []):
                if item['type'] == 'stream':
                    print(f"STDOUT: {item['text']}")
                elif item['type'] == 'error':
                    print(f"ERROR ({item['ename']}): {item['evalue']}")
                    print(f"TRACEBACK:\n{''.join(item['traceback'])}")
                elif item['type'] == 'execute_result':
                    data_str = item['data'].get('text/plain', str(item['data']))
                    print(f"RESULTADO: {data_str}")
                elif item['type'] == 'display_data':
                    if 'image/png' in item['data']:
                        print("IMAGEN PNG GENERADA")
                    elif 'text/html' in item['data']:
                        print(f"HTML GENERADO: {item['data']['text/html'][:100]}...")
                    else:
                        print(f"DATOS DE VISUALIZACIÓN: {str(item['data'])}")
            print("--- Fin de la Salida Python ---")
            return

        self.console.print(Padding(Panel("[bold green]Salida del Código Python:[/bold green]", border_style='green'), (1, 2)))
        for item in structured_output.get("result", []):
            if item['type'] == 'stream':
                self.console.print(f"[cyan]STDOUT:[/cyan] {item['text']}")
            elif item['type'] == 'error':
                self.console.print(f"[red]ERROR ({item['ename']}):[/red] {item['evalue']}")
                self.console.print(f"[red]TRACEBACK:[/red]\n{''.join(item['traceback'])}")
            elif item['type'] == 'execute_result':
                data_str = item['data'].get('text/plain', str(item['data']))
                self.console.print(f"[green]RESULTADO:[/green] {data_str}")
            elif item['type'] == 'display_data':
                if 'image/png' in item['data']:
                    self.console.print("[magenta]IMAGEN PNG GENERADA[/magenta]")
                elif 'text/html' in item['data']:
                    self.console.print(f"[magenta]HTML GENERADO:[/magenta] {item['data']['text/html'][:100]}...")
                else:
                    self.console.print(f"[magenta]DATOS DE VISUALIZACIÓN:[/magenta] {str(item['data'])}")
        self.console.print(Padding(Panel("[bold green]Fin de la Salida Python[/bold green]", border_style='green'), (1, 2)))

    def display_error(self, message: str):
        if self.rich_available:
            self.console.print(Padding(f"[red]Error: {message}[/red]", (0, 2)))
        else:
            print(f"Error: {message}")
