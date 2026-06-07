import logging
from kogniterm.utils.logger import setup_logger
setup_logger() # Initialize root logger early
import sys
import os
from dotenv import load_dotenv # Importar load_dotenv
from prompt_toolkit.completion import Completer, Completion
from rich.text import Text
from rich.syntax import Syntax
from rich.panel import Panel
import re

# Cargar primero el .env local del proyecto, luego el global con override.
# El global (~/.kogniterm/.env) siempre tiene precedencia: las API keys
# configuradas con /keys persisten independientemente del .env del proyecto.
import pathlib as _pathlib
_global_env = _pathlib.Path.home() / ".kogniterm" / ".env"
load_dotenv()  # local .env del proyecto (base)
if _global_env.exists():
    load_dotenv(_global_env, override=True)  # global siempre gana

# New helper function
def _format_text_with_basic_markdown(text: str) -> Text:
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

# --- Importar KogniTermTUI ---
from kogniterm.terminal.tui.tui_app import KogniTermTUI
from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor # Importar CommandExecutor
from kogniterm.core.agent_state import AgentState # Importar AgentState
import os
from rich.text import Text
from rich.syntax import Syntax
from rich.console import Console
from rich.padding import Padding
from rich.live import Live
from rich.markdown import Markdown
from rich.status import Status
import json
import asyncio
import re
import sys
import os
import asyncio
import threading # Importar threading para el watcher

from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager
from kogniterm.terminal.command_approval_handler import CommandApprovalHandler
from kogniterm.terminal.meta_command_processor import MetaCommandProcessor
from kogniterm.terminal.terminal_ui import TerminalUI
from kogniterm.terminal.cli import run_cli

logger = logging.getLogger("kogniterm.terminal")

console = Console()







import signal

async def _main_async():
    """Función principal asíncrona para iniciar la terminal de KogniTerm."""
    import sys
    from kogniterm.terminal.config_manager import ConfigManager
    from kogniterm.terminal.themes import set_kogniterm_theme
    # Cargar configuración y aplicar tema guardado antes de iniciar nada
    config_manager = ConfigManager()
    saved_theme = config_manager.get_config("theme") or "default"
    try:
        set_kogniterm_theme(saved_theme)
    except ValueError:
        set_kogniterm_theme("default")
    auto_approve = '-y' in sys.argv or '--yes' in sys.argv
    # Obtener el directorio de trabajo actual
    workspace_directory = os.getcwd()
    # --- INYECCIÓN DE CONFIGURACIÓN DE MODELO ---
    # Leer el modelo configurado por el usuario y establecerlo en las variables de entorno
    # ANTES de importar LLMService, ya que este lee os.environ al nivel de módulo.
    default_model = config_manager.get_config("default_model")
    if default_model:
        # Solo sobrescribir si no se pasó explícitamente por variable de entorno en esta ejecución
        # Esto permite overrides temporales: LITELLM_MODEL=foo kogniterm
        if "LITELLM_MODEL" not in os.environ:
            os.environ["LITELLM_MODEL"] = default_model
    # --- INYECCIÓN DE ESFUERZO DE RAZONAMIENTO ---
    saved_reasoning_effort = config_manager.get_config("reasoning_effort")
    if saved_reasoning_effort and "KOGNITERM_REASONING_EFFORT" not in os.environ:
        os.environ["KOGNITERM_REASONING_EFFORT"] = str(saved_reasoning_effort)
    # --- INYECCIÓN DE API KEYS ---
    # Mapeo de proveedores a variables de entorno
    api_key_mapping = {
        "openrouter": "OPENROUTER_API_KEY",
        "google": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "cohere": "COHERE_API_KEY",
        "zhipuai": "ZHIPUAI_API_KEY",
        "ollama_cloud": "OLLAMA_CLOUD_API_KEY",
        "litellm": "LITELLM_API_KEY"
    }

    for provider, env_var in api_key_mapping.items():
        if env_var not in os.environ:
            saved_key = config_manager.get_config(f"api_key_{provider}")
            if saved_key:
                os.environ[env_var] = saved_key
    
    # Disable console logging in TUI mode to prevent logs from disrupting the UI
    kogniterm_logger = logging.getLogger("kogniterm")
    kogniterm_logger.setLevel(logging.CRITICAL)
    for handler in kogniterm_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            kogniterm_logger.removeHandler(handler)
    kogniterm_logger.propagate = False
    # --- Centralización: La TUI actúa como cliente ---
    workspace_directory = os.getcwd()
    
    # Iniciar la TUI (KogniTermTUI se conectará al servidor central en on_mount)
    llm_service = LLMService()
    command_executor = CommandExecutor()
    agent_state = AgentState()
    app = KogniTermTUI(
        llm_service=llm_service,
        command_executor=command_executor,
        agent_state=agent_state,
        workspace_directory=workspace_directory
    )

    # Configurar manejador de señales para Ctrl+C
    def signal_handler(sig, frame):
        # Enviar señal de interrupción a la cola de la app
        if app and app.terminal_ui:
            app.terminal_ui.get_interrupt_queue().put_nowait(True)
            # También establecer la bandera directamente en el servicio LLM por si acaso
            if app.llm_service:
                app.llm_service.stop_generation_flag = True
        # No salimos de la app, solo interrumpimos la tarea actual

        # Configurar en Textual en su lugar
        pass

    # No llamamos a signal.signal con SIGINT cuando usamos TUI porque Textual maneja señales.
    # signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await app.run_async() # Textual App run inside an existing asyncio event loop
    except Exception as e:
        logger.error(f"Error fatal en la TUI: {e}")
    finally:
        # Cerrar el servicio LLM y liberar recursos (como ChromaDB)
        if hasattr(app, 'llm_service') and app.llm_service:
            app.llm_service.close()
            
        # Asegurarse de que el FileCompleter se limpie al salir (si fuese prompt_toolkit)
        if hasattr(app, 'prompt_session') and app.prompt_session and app.prompt_session.completer and hasattr(app.prompt_session.completer, 'dispose'):
            app.prompt_session.completer.dispose()

        _print_exit_banner()

def main():
    """Main entry point for KogniTerm."""
    # Desactivar telemetría de CrewAI
    os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

    # Silenciar logs de terceros
    logging.getLogger('litellm').setLevel(logging.CRITICAL)
    logging.getLogger('crewai').setLevel(logging.CRITICAL)
    logging.getLogger('CrewAIEventsBus').setLevel(logging.CRITICAL)

    # Si es un comando CLI, ejecutarlo y salir
    cli_result = run_cli()
    if cli_result:
        return

    # Iniciar la aplicación TUI
    try:
        asyncio.run(_main_async())
    except (RuntimeError, KeyboardInterrupt):
        pass
    finally:
        # Notificar al servidor que la sesión TUI cerró
        try:
            import httpx
            # Usamos un request síncrono para asegurar que se ejecute antes de salir
            httpx.post("http://127.0.0.1:8765/api/sessions/tui-default/close", timeout=2.0)
        except Exception as e:
            logger.warning(f"No se pudo notificar el cierre de sesión al servidor: {e}")

        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass
        os._exit(0)

if __name__ == "__main__":
    main()

def _print_exit_banner() -> None:
    """Muestra un banner ASCII personalizado al cerrar la TUI."""
    banner = """
░█░█░█▀█░█▀▀░█▀█░▀█▀░▀█▀░█▀█
░█▀▄░█░█░█░█░█░█░░█░░░█░░█░█
░▀░▀░▀▀▀░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀
░█▀█░▀█▀░░░░░█░░░█▀█░█▀▄░█▀▀
░█▀█░░█░░░░░░█░░░█▀█░█▀▄░▀▀█
░▀░▀░▀▀▀░░░░░▀▀▀░▀░▀░▀▀░░▀▀▀
""".strip("\n")

    console.print()
    console.print(f"[bold cyan]{banner}[/bold cyan]")
    console.print()
