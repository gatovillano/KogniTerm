import sys
import asyncio
import os
import threading
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import AgentState, SYSTEM_MESSAGE
from kogniterm.terminal.terminal_ui import TerminalUI
from langchain_core.messages import AIMessage
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table # Importar Table
from kogniterm.terminal.themes import set_kogniterm_theme, get_available_themes
from kogniterm.terminal.config_manager import ConfigManager
try:
    from dotenv import set_key, unset_key, find_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from prompt_toolkit.formatted_text import HTML


"""
This module contains the MetaCommandProcessor class, responsible for handling
special meta-commands in the KogniTerm application.
"""

class MetaCommandProcessor:
    def __init__(self, llm_service: LLMService, agent_state: AgentState, terminal_ui: TerminalUI, kogniterm_app):
        self.llm_service = llm_service
        self.agent_state = agent_state
        self.terminal_ui = terminal_ui
        self.kogniterm_app = kogniterm_app # Referencia a la instancia de KogniTermApp

    async def process_meta_command(self, user_input: str) -> bool:
        """
        Processes meta-commands like %salir, %reset, %undo, %help, %compress.
        Returns True if a meta-command was processed, False otherwise.
        """
        if user_input.lower().strip() in ['%salir', 'salir', 'exit']:
            sys.exit()

        if user_input.lower().strip() == '%reset':
            self.agent_state.reset() # Reiniciar el estado
            # También reiniciamos el historial de llm_service al resetear la conversación
            self.llm_service.conversation_history = []
            # ¡IMPORTANTE! Re-añadir el SYSTEM_MESSAGE después de resetear
            self.llm_service.conversation_history.append(SYSTEM_MESSAGE)
            # Guardar historial CON el SYSTEM_MESSAGE
            self.llm_service._save_history(self.llm_service.conversation_history)
            # Sincronizar agent_state.messages con el historial
            self.agent_state.messages = self.llm_service.conversation_history.copy()
            
            # Limpiar la pantalla de la terminal
            os.system('cls' if os.name == 'nt' else 'clear')
            self.kogniterm_app.terminal_ui.print_welcome_banner() # Volver a imprimir el banner de bienvenida
            self.terminal_ui.print_message(f"Conversación reiniciada.", style="green")
            return True

        if user_input.lower().strip() == '%undo':
            if len(self.agent_state.messages) >= 3:
                self.agent_state.messages.pop() # Eliminar respuesta del AI
                self.agent_state.messages.pop() # Eliminar input del usuario
                self.terminal_ui.print_message("Última interacción deshecha.", style="green")
            else:
                self.terminal_ui.print_message("No hay nada que deshacer.", style="yellow")
            return True
        
        if user_input.lower().strip().startswith('%init'):
            command_parts = user_input.strip().split(' ', 1)
            files_to_include = None
            if len(command_parts) > 1:
                files_to_include = [f.strip() for f in command_parts[1].split(',')]
            
            self.terminal_ui.print_message("Inicializando contexto del espacio de trabajo... Esto puede tardar un momento. ⏳", style="yellow")
            try:
                self.llm_service.initialize_workspace_context(files_to_include=files_to_include)
                self.terminal_ui.print_message("Contexto del espacio de trabajo inicializado correctamente. ✨", style="green")
            except Exception as e:
                self.terminal_ui.print_message(f"Error al inicializar el contexto del espacio de trabajo: {e} ❌", style="red")
            return True

        if user_input.lower().strip().startswith('%theme') or user_input.lower().strip().startswith('%tema'):
            parts = user_input.strip().split()
            if len(parts) > 1:
                theme_name = parts[1].lower()
                try:
                    set_kogniterm_theme(theme_name)
                    # Update console theme if necessary
                    if hasattr(self.terminal_ui, 'refresh_theme'):
                         self.terminal_ui.refresh_theme()
                    
                    # Persistir el tema globalmente
                    config_manager = ConfigManager()
                    config_manager.set_global_config("theme", theme_name)
                    
                    self.terminal_ui.print_message(f"Tema cambiado a '{theme_name}' y guardado como preferencia global. ✨", style="green")
                    # Reprint banner to show off new colors
                    self.terminal_ui.print_welcome_banner()
                except ValueError:
                     self.terminal_ui.print_message(f"Tema '{theme_name}' no encontrado.", style="red")
                     self._show_themes_table()
            else:
                self._show_themes_table()
            return True


        if user_input.lower().strip().startswith('%session'):
            parts = user_input.strip().split()
            subcommand = parts[1].lower() if len(parts) > 1 else "list"
            args = parts[2:] if len(parts) > 2 else []

            session_manager = self.kogniterm_app.session_manager

            if subcommand == "list":
                sessions = session_manager.list_sessions()
                if not sessions:
                    self.terminal_ui.print_message("No hay sesiones guardadas.", style="yellow")
                else:
                    table = Table(title="Sesiones Guardadas")
                    table.add_column("Nombre", style="cyan")
                    table.add_column("Modificado", style="dim")
                    table.add_column("Mensajes", justify="right")
                    
                    for s in sessions:
                        table.add_row(s["name"], s["modified"], str(s["messages"]))
                    
                    self.terminal_ui.console.print(table)
                    
                    current = session_manager.get_current_session_name()
                    if current:
                        self.terminal_ui.print_message(f"Sesión actual: {current}", style="green")
                    else:
                        self.terminal_ui.print_message("Estás en una sesión temporal (no guardada).", style="dim")

            elif subcommand == "save":
                if not args:
                    # Si no hay nombre, intentar usar el actual o pedir uno
                    current = session_manager.get_current_session_name()
                    if current:
                        name = current
                    else:
                        self.terminal_ui.print_message("Uso: %session save <nombre>", style="red")
                        return True
                else:
                    name = args[0]
                
                if session_manager.save_session(name, self.llm_service.conversation_history):
                    self.terminal_ui.print_message(f"Sesión '{name}' guardada exitosamente. ✅", style="green")
                else:
                    self.terminal_ui.print_message(f"Error al guardar la sesión '{name}'. ❌", style="red")

            elif subcommand == "load":
                if not args:
                    self.terminal_ui.print_message("Uso: %session load <nombre>", style="red")
                    return True
                name = args[0]
                
                history = session_manager.load_session(name)
                if history:
                    self.llm_service.conversation_history = history
                    self.agent_state.messages = history
                    self.llm_service._save_history(history) # Actualizar historial activo
                    self.terminal_ui.print_message(f"Sesión '{name}' cargada. Historial actualizado. 🔄", style="green")
                else:
                    self.terminal_ui.print_message(f"No se pudo cargar la sesión '{name}'.", style="red")

            elif subcommand == "new":
                name = args[0] if args else None
                
                # Resetear estado
                self.agent_state.reset()
                self.llm_service.conversation_history = []
                self.llm_service.conversation_history.append(SYSTEM_MESSAGE)
                self.agent_state.messages = self.llm_service.conversation_history.copy()
                self.llm_service._save_history(self.llm_service.conversation_history)
                
                if name:
                    session_manager.save_session(name, self.llm_service.conversation_history)
                    self.terminal_ui.print_message(f"Nueva sesión '{name}' creada e iniciada. ✨", style="green")
                else:
                    session_manager.current_session_name = None
                    self.terminal_ui.print_message("Nueva sesión temporal iniciada. ✨", style="green")

            elif subcommand == "delete":
                if not args:
                    self.terminal_ui.print_message("Uso: %session delete <nombre>", style="red")
                    return True
                name = args[0]
                if session_manager.delete_session(name):
                    self.terminal_ui.print_message(f"Sesión '{name}' eliminada. 🗑️", style="green")
                else:
                    self.terminal_ui.print_message(f"Error al eliminar sesión '{name}'.", style="red")
            
            else:
                self.terminal_ui.print_message("Subcomandos disponibles: list, save, load, new, delete", style="yellow")

            return True

        if user_input.lower().strip() == '%help':
            from prompt_toolkit.shortcuts import radiolist_dialog
            
            help_options = [
                ("%models", "🤖 Cambiar Modelo de IA (Seleccionar modelo del proveedor actual)"),
                ("%provider", "🌐 Cambiar Proveedor de LLM (OpenRouter, Google, OpenAI, etc.)"),
                ("%keys", "🔑 Gestionar API Keys (Configurar llaves de proveedores)"),
                ("%reset", "🔄 Reiniciar Conversación (Borrar memoria actual)"),
                ("%undo", "↩️ Deshacer (Eliminar última interacción)"),
                ("%compress [force]", "🗜️ Comprimir Historial (Usa 'force' si excede límites)"),
                ("%theme", "🎨 Cambiar Tema (Ver lista de temas disponibles)"),
                ("%session", "🗂️ Gestión de Sesiones (list, save, load, new, delete)"),
                ("%init", "📁 Inicializar Contexto (Indexar archivos clave)"),
                ("%salir", "🚪 Salir de KogniTerm"),
            ]
            
            selected_command = await radiolist_dialog(
                title="Menú de Ayuda KogniTerm",
                text="Selecciona un comando para ejecutarlo o ver más información:",
                values=help_options
            ).run_async()

            if selected_command:
                # Ejecutar comandos directos
                if selected_command in ["%models", "%provider", "%keys", "%reset", "%compress", "%undo", "%salir"]:
                    # Llamada recursiva para procesar el comando seleccionado
                    return await self.process_meta_command(selected_command)
                
                # Comandos que requieren argumentos o interacción especial
                elif selected_command == "%theme":
                    # Ejecutar %theme sin argumentos muestra la lista de temas
                    return await self.process_meta_command("%theme")

                elif selected_command == "%session":
                    self.terminal_ui.print_message("ℹ️  Gestión de Sesiones (%session)", style="bold cyan")
                    self.terminal_ui.print_message("Uso: %session <subcomando> [argumentos]", style="blue")
                    self.terminal_ui.print_message("Subcomandos disponibles:", style="yellow")
                    self.terminal_ui.print_message("  • list           : 📋 Muestra todas las sesiones guardadas.", style="dim")
                    self.terminal_ui.print_message("  • save <nombre>  : 💾 Guarda la sesión actual.", style="dim")
                    self.terminal_ui.print_message("  • load <nombre>  : 🔄 Carga una sesión anterior.", style="dim")
                    self.terminal_ui.print_message("  • new [nombre]   : ✨ Inicia una nueva sesión limpia.", style="dim")
                    self.terminal_ui.print_message("  • delete <nombre>: 🗑️  Elimina una sesión guardada.", style="dim")
                    self.terminal_ui.print_message("\nEjemplo: %session save mi_proyecto", style="italic dim")
                
                elif selected_command == "%init":
                    self.terminal_ui.print_message("ℹ️  Uso: %init [archivos]", style="blue")
                    self.terminal_ui.print_message("Ejemplo: %init README.md,src/main.py", style="dim")
                    self.terminal_ui.print_message("Tip: Usa este comando para cargar contexto específico en la memoria.", style="dim")
            
            return True

        if user_input.lower().strip().startswith('%compress'):
            force = 'force' in user_input.lower()
            self.terminal_ui.print_message("Resumiendo historial de conversación...", style="yellow")
            if force:
                self.terminal_ui.print_message("⚠️ Modo FORCE activado: se truncará el historial si excede los límites de tokens.", style="bold red")
            
            summary = self.llm_service.summarize_conversation_history(force_truncate=force)
            
            if summary.startswith("Error") or summary.startswith("No se pudo"):
                self.terminal_ui.print_message(summary, style="red")
                if "RateLimitError" in summary or "quota" in summary.lower():
                    self.terminal_ui.print_message("\n💡 Tip: El modelo ha alcanzado su límite de cuota. Prueba usando [bold]%compress force[/bold] para resumir solo la parte más reciente que quepa en el límite.", style="cyan")
            else:
                self.llm_service.conversation_history = [SYSTEM_MESSAGE, AIMessage(content=summary)]
                self.agent_state.messages = self.llm_service.conversation_history
                self.llm_service._save_history(self.llm_service.conversation_history) # Guardar historial comprimido
                self.terminal_ui.console.print(Panel(Markdown(f"Historial comprimido exitosamente:\n{summary}"), border_style="green", title="[bold green]Historial Comprimido[/bold green]"))
            return True

        if user_input.lower().strip() == '%models':
            from prompt_toolkit.shortcuts import radiolist_dialog
            import httpx
            import json

            # Función auxiliar para obtener modelos de Google
            async def _fetch_google_models():
                try:
                    google_key = os.environ.get("GOOGLE_API_KEY")
                    if not google_key:
                        self.terminal_ui.print_message("⚠️ No se encontró GOOGLE_API_KEY en el entorno.", style="yellow")
                        return []
                    
                    self.terminal_ui.print_message("⏳ Obteniendo modelos actualizados de Google AI...", style="dim")
                    async with httpx.AsyncClient() as client:
                        # Usar la API de Google para listar modelos
                        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}"
                        response = await client.get(url)
                        
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            for m in data.get('models', []):
                                # Filtrar solo modelos que soporten generación de contenido
                                if 'generateContent' in m.get('supportedGenerationMethods', []):
                                    model_id = m['name'].replace('models/', 'gemini/')
                                    display_name = m.get('displayName', m['name'].split('/')[-1])
                                    
                                    # Añadir info de versión o capacidades si es relevante
                                    description = m.get('description', '')
                                    version = ""
                                    if "1.5" in model_id: version = " (1.5)"
                                    elif "2.0" in model_id: version = " (2.0)"
                                    
                                    label = f"{display_name}{version}"
                                    models.append((model_id, label))
                            
                            # Ordenar: primero los más nuevos (2.0, luego 1.5)
                            models.sort(key=lambda x: x[0], reverse=True)
                            return models
                        else:
                            self.terminal_ui.print_message(f"⚠️ Error API Google: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Error al conectar con Google: {e}", style="red")
                    return []

            # Función auxiliar para obtener modelos de OpenRouter
            async def _fetch_openrouter_models():
                try:
                    self.terminal_ui.print_message("⏳ Obteniendo lista de modelos de OpenRouter...", style="dim")
                    async with httpx.AsyncClient() as client:
                        response = await client.get("https://openrouter.ai/api/v1/models")
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            for m in data.get('data', []):
                                model_id = f"openrouter/{m['id']}" # Prefijo necesario para litellm
                                name = m.get('name', m['id'])
                                # Intentar obtener info de precios si existe
                                pricing = m.get('pricing', {})
                                price_str = ""
                                if pricing:
                                    prompt = float(pricing.get('prompt', 0)) * 1000000
                                    completion = float(pricing.get('completion', 0)) * 1000000
                                    price_str = f" [${prompt:.2f}/M in, ${completion:.2f}/M out]"
                                
                                context_length = m.get('context_length', 0)
                                context_str = f" ({int(context_length/1024)}k ctx)" if context_length else ""
                                
                                label = f"{name}{context_str}{price_str}"
                                models.append((model_id, label))
                            
                            # Ordenar alfabéticamente
                            models.sort(key=lambda x: x[1])
                            return models
                        else:
                            self.terminal_ui.print_message(f"⚠️ Error al obtener modelos de OpenRouter: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Excepción al conectar con OpenRouter: {e}", style="red")
                    return []

            current_model = self.llm_service.model_name
            
            # Detectar proveedor actual
            current_provider = "unknown"
            if current_model.startswith("openrouter/"):
                current_provider = "openrouter"
            elif current_model.startswith("gemini/"):
                current_provider = "google"
            elif "gpt" in current_model:
                current_provider = "openai"
            elif "claude" in current_model:
                current_provider = "anthropic"
            
            target_list = []

            # Obtener lista según proveedor
            if current_provider == "openrouter":
                target_list = await _fetch_openrouter_models()
                # Fallback si falla la API
                if not target_list:
                    target_list = [
                        ("openrouter/google/gemini-2.0-flash-exp:free", "Gemini 2.0 Flash Exp (Free)"),
                        ("openrouter/google/gemini-flash-1.5-8b", "Gemini Flash 1.5 8B"),
                        ("openrouter/anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet"),
                        ("openrouter/openai/gpt-4o", "GPT-4o"),
                    ]
            elif current_provider == "google":
                target_list = await _fetch_google_models()
                # Fallback si falla la API
                if not target_list:
                    target_list = [
                        ("gemini/gemini-2.0-flash-exp", "Gemini 2.0 Flash Exp"),
                        ("gemini/gemini-1.5-pro", "Gemini 1.5 Pro"),
                        ("gemini/gemini-1.5-flash", "Gemini 1.5 Flash"),
                        ("gemini/gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B"),
                        ("gemini/gemini-1.0-pro", "Gemini 1.0 Pro"),
                    ]
            elif current_provider == "openai":
                target_list = [
                    ("gpt-4o", "GPT-4o"),
                    ("gpt-4o-mini", "GPT-4o Mini"),
                    ("gpt-4-turbo", "GPT-4 Turbo"),
                    ("gpt-4", "GPT-4"),
                    ("gpt-3.5-turbo", "GPT-3.5 Turbo"),
                ]
            elif current_provider == "anthropic":
                target_list = [
                    ("claude-3-5-sonnet-20240620", "Claude 3.5 Sonnet"),
                    ("claude-3-opus-20240229", "Claude 3 Opus"),
                    ("claude-3-haiku-20240307", "Claude 3 Haiku"),
                    ("claude-2.1", "Claude 2.1"),
                ]
            else:
                # Si no se reconoce, mostrar una mezcla o OpenRouter por defecto
                target_list = await _fetch_openrouter_models()

            # Crear lista de opciones para el diálogo
            values = []
            for model_id, model_label in target_list:
                values.append((model_id, model_label))
            
            selected_model = await radiolist_dialog(
                title=f"Seleccionar Modelo de IA ({len(values)} disponibles)",
                text=f"Modelo actual: {current_model}\nProveedor: {current_provider.capitalize()}\n\nEscribe para buscar/filtrar en la lista:",
                values=values,
                default=current_model if any(m[0] == current_model for m in values) else None
            ).run_async()

            if selected_model:
                if selected_model != current_model:
                    self.terminal_ui.print_message(f"Cambiando modelo a: {selected_model}...", style="yellow")
                    try:
                        self.llm_service.set_model(selected_model)
                        
                        # Persistir en .env de forma inteligente según el proveedor
                        if DOTENV_AVAILABLE:
                            dotenv_path = find_dotenv()
                            if dotenv_path:
                                if selected_model.startswith("gemini/"):
                                    # Para Google AI Studio
                                    gemini_pure_name = selected_model.replace("gemini/", "")
                                    set_key(dotenv_path, "GEMINI_MODEL", gemini_pure_name)
                                    os.environ["GEMINI_MODEL"] = gemini_pure_name
                                    # Limpiar LITELLM_MODEL para evitar conflictos al reiniciar
                                    unset_key(dotenv_path, "LITELLM_MODEL")
                                    if "LITELLM_MODEL" in os.environ: del os.environ["LITELLM_MODEL"]
                                else:
                                    # Para otros proveedores (OpenRouter, OpenAI, etc.)
                                    set_key(dotenv_path, "LITELLM_MODEL", selected_model)
                                    os.environ["LITELLM_MODEL"] = selected_model
                                    # Limpiar GEMINI_MODEL
                                    unset_key(dotenv_path, "GEMINI_MODEL")
                                    if "GEMINI_MODEL" in os.environ: del os.environ["GEMINI_MODEL"]
                        
                        # Persistir el cambio globalmente en el config manager
                        config_manager = ConfigManager()
                        config_manager.set_global_config("default_model", selected_model)
                        
                        self.terminal_ui.print_message(f"✅ Modelo cambiado exitosamente a: {selected_model}", style="green")
                        self.terminal_ui.print_message(f"ℹ️  Configuración persistida en .env ({'GEMINI_MODEL' if selected_model.startswith('gemini/') else 'LITELLM_MODEL'}).", style="dim")
                        self.terminal_ui.print_message(f"ℹ️  Configuración guardada como predeterminada.", style="dim")
                    except Exception as e:
                        self.terminal_ui.print_message(f"❌ Error al cambiar el modelo: {e}", style="red")
                else:
                    self.terminal_ui.print_message("Modelo no cambiado (selección idéntica).", style="dim")
            
            return True

        if user_input.lower().strip() == '%provider':
            from prompt_toolkit.shortcuts import radiolist_dialog

            providers = [
                ("openrouter", "🌐 OpenRouter (Acceso a múltiples modelos)"),
                ("google", "🤖 Google AI (Gemini nativo)"),
                ("openai", "🧠 OpenAI (GPT-4, GPT-3.5)"),
                ("anthropic", "🎭 Anthropic (Claude)"),
            ]

            selected_provider = await radiolist_dialog(
                title="Seleccionar Proveedor de LLM",
                text="Selecciona el proveedor que deseas utilizar. Esto actualizará tu configuración predeterminada:",
                values=providers
            ).run_async()

            if selected_provider:
                self.terminal_ui.print_message(f"Cambiando proveedor a: {selected_provider.capitalize()}...", style="yellow")
                
                # Definir modelo por defecto para cada proveedor
                default_models = {
                    "openrouter": "openrouter/google/gemini-2.0-flash-exp:free",
                    "google": "gemini/gemini-1.5-flash",
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-3-5-sonnet-20240620"
                }
                
                new_model = default_models.get(selected_provider)
                
                try:
                    # Actualizar LLMService
                    self.llm_service.set_model(new_model)
                    
                    # Persistir en .env si es posible
                    if DOTENV_AVAILABLE:
                        dotenv_path = find_dotenv()
                        if dotenv_path:
                            set_key(dotenv_path, "LITELLM_MODEL", new_model)
                    
                    # Persistir en ConfigManager
                    config_manager = ConfigManager()
                    config_manager.set_global_config("default_model", new_model)
                    
                    self.terminal_ui.print_message(f"✅ Proveedor cambiado a {selected_provider.capitalize()}.", style="green")
                    self.terminal_ui.print_message(f"🤖 Modelo predeterminado establecido: {new_model}", style="dim")
                    self.terminal_ui.print_message("ℹ️  Puedes cambiar el modelo específico con %models", style="italic dim")
                except Exception as e:
                    self.terminal_ui.print_message(f"❌ Error al cambiar el proveedor: {e}", style="red")
            
            return True

        if user_input.lower().strip() == '%keys':
            if not DOTENV_AVAILABLE:
                self.terminal_ui.print_message("❌ El módulo 'python-dotenv' no está disponible. No se pueden gestionar las llaves.", style="red")
                return True
            
            await self._manage_keys_interactive()
            return True

        return False

    async def _manage_keys_interactive(self):
        """Muestra una interfaz interactiva para gestionar API Keys."""
        from prompt_toolkit.shortcuts import radiolist_dialog, input_dialog, message_dialog
        
        dotenv_path = find_dotenv()
        if not dotenv_path:
            # Si no existe, crearlo en el CWD
            dotenv_path = os.path.join(os.getcwd(), '.env')
            if not os.path.exists(dotenv_path):
                try:
                    with open(dotenv_path, 'w') as f:
                        f.write("# KogniTerm Environment Variables\n")
                except Exception as e:
                    self.terminal_ui.print_message(f"❌ No se pudo crear el archivo .env: {e}", style="red")
                    return

        common_keys = [
            "OPENROUTER_API_KEY",
            "GOOGLE_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "BRAVE_API_KEY",
            "GITHUB_TOKEN"
        ]
        
        while True:
            options = []
            # Obtener todas las llaves actuales del .env para incluirlas si no están en common_keys
            current_env_keys = []
            if os.path.exists(dotenv_path):
                try:
                    with open(dotenv_path, 'r') as f:
                        for line in f:
                            if '=' in line and not line.strip().startswith('#'):
                                k = line.split('=')[0].strip()
                                if k:
                                    current_env_keys.append(k)
                except Exception:
                    pass
            
            all_keys = sorted(list(set(common_keys + current_env_keys)))
            
            for key in all_keys:
                val = os.environ.get(key, "")
                if val:
                    # Enmascarar valor: mostrar solo inicio y fin
                    masked = f"{val[:4]}...{val[-4:]}" if len(val) > 8 else "****"
                    status = f'✅ <style fg="cyan">{masked}</style>'
                else:
                    status = '❌ <style fg="#888888">No configurada</style>'
                
                # Usar HTML para que prompt_toolkit renderice los estilos
                options.append((key, HTML(f'{key:<20} | {status}')))
            
            options.append(("CUSTOM", "➕ Añadir otra variable..."))
            options.append(("BACK", "⬅️  Volver"))
            
            selected_key = await radiolist_dialog(
                title="Gestión de API Keys / Variables de Entorno",
                text=f"Archivo: {os.path.basename(dotenv_path)}\nSelecciona una llave para editarla o eliminarla:",
                values=options
            ).run_async()
            
            if not selected_key or selected_key == "BACK":
                break
                
            if selected_key == "CUSTOM":
                custom_name = await input_dialog(
                    title="Nueva Variable",
                    text="Introduce el nombre de la variable (ej: MY_SERVICE_KEY):"
                ).run_async()
                if custom_name:
                    selected_key = custom_name.strip().upper()
                else:
                    continue

            # Acción para la llave seleccionada
            current_val = os.environ.get(selected_key, "")
            masked_val = f"{current_val[:4]}...{current_val[-4:]}" if len(current_val) > 8 else ("****" if current_val else "Vacío")
            
            action = await radiolist_dialog(
                title=f"Acción para {selected_key}",
                text=f"Variable: {selected_key}\nValor actual: {masked_val}",
                values=[
                    ("SET", "✏️  Establecer / Cambiar valor"),
                    ("DELETE", "🗑️  Eliminar llave"),
                    ("CANCEL", "🚫 Cancelar")
                ]
            ).run_async()
            
            if action == "SET":
                new_val = await input_dialog(
                    title=f"Establecer {selected_key}",
                    text=f"Introduce el valor para {selected_key}:",
                    password=True
                ).run_async()
                
                if new_val is not None: # Permitir valor vacío si el usuario pulsa OK
                    new_val = new_val.strip() # Limpiar espacios y saltos de línea que pueden truncar la clave
                    
                    # Validación de seguridad: no permitir guardar API Keys en LITELLM_MODEL
                    if selected_key == "LITELLM_MODEL" and new_val.startswith("AIza"):
                        await message_dialog(
                            title="⚠️ Error de Configuración",
                            text=f"Parece que estás intentando guardar una API Key en LITELLM_MODEL.\nEsta variable debe contener el nombre del modelo (ej: google/gemini-1.5-flash), no la clave.\n\nLa clave debe ir en GOOGLE_API_KEY o OPENROUTER_API_KEY."
                        ).run_async()
                        continue

                    try:
                        set_key(dotenv_path, selected_key, new_val)
                        os.environ[selected_key] = new_val
                        
                        # Actualizar LLMService si es necesario
                        if selected_key == "OPENROUTER_API_KEY":
                            self.llm_service.api_key = new_val
                        elif selected_key == "GOOGLE_API_KEY" and "gemini" in self.llm_service.model_name:
                            self.llm_service.api_key = new_val
                            
                        key_len = len(new_val)
                        masked_preview = f"{new_val[:4]}...{new_val[-4:]}" if key_len > 8 else "****"
                        await message_dialog(
                            title="Éxito", 
                            text=f"Llave {selected_key} guardada correctamente.\nLongitud: {key_len} caracteres.\nVista previa: {masked_preview}"
                        ).run_async()
                    except Exception as e:
                        await message_dialog(title="Error", text=f"No se pudo guardar la llave: {e}").run_async()
            
            elif action == "DELETE":
                try:
                    unset_key(dotenv_path, selected_key)
                    if selected_key in os.environ:
                        del os.environ[selected_key]
                    await message_dialog(title="Éxito", text=f"Llave {selected_key} eliminada del archivo y del entorno.").run_async()
                except Exception as e:
                    await message_dialog(title="Error", text=f"No se pudo eliminar la llave: {e}").run_async()

    def _show_themes_table(self):
        """Muestra una tabla con los temas disponibles y sus colores."""
        from rich.table import Table
        from rich.text import Text
        from rich.padding import Padding
        from kogniterm.terminal.themes import _THEMES
        
        table = Table(
            title=f"🎨 Temas Disponibles en KogniTerm",
            border_style="bright_blue",
            header_style="bold magenta",
            show_lines=True
        )
        
        table.add_column("Tema", style="bold cyan", justify="center")
        table.add_column("Previsualización", justify="center")
        table.add_column("Descripción", style="italic")
        
        descriptions = {
            "default": "El tema clásico de KogniTerm (Morado/Cian).",
            "ocean": "Tonos azules y cianes relajantes.",
            "matrix": "Estilo terminal hacker clásico (Verde).",
            "sunset": "Colores cálidos (Naranja/Amarillo).",
            "cyberpunk": "Neones vibrantes y contrastes altos.",
            "nebula": "Inspirado en el espacio profundo (Morado/Rosa).",
            "dracula": "El esquema de colores favorito de los devs."
        }
        
        for name, colors in _THEMES.items():
            # Crear una pequeña barra de colores para previsualización
            preview = Text()
            preview.append("██", style=colors["PRIMARY"])
            preview.append(" ", style="default")
            preview.append("██", style=colors["SECONDARY"])
            preview.append(" ", style="default")
            preview.append("██", style=colors["ACCENT_PINK"])
            preview.append(" ", style="default")
            preview.append("██", style=colors["SUCCESS"])
            
            desc = descriptions.get(name, "Tema personalizado.")
            table.add_row(name, preview, desc)
            
        self.terminal_ui.console.print(Padding(table, (1, 2)))
        self.terminal_ui.print_message(f"Usa [bold cyan]%theme <nombre>[/bold cyan] para cambiar.", style="dim")