import sys
import asyncio
import os
import threading
from kogniterm.core.llm_service import LLMService
from kogniterm.core.insights import KogniInsightsEngine
from kogniterm.core.agents.bash_agent import AgentState, get_system_message
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
        self.kogniterm_app = kogniterm_app

    async def _show_radiolist(self, title, text, values, default=None):
        if hasattr(self.terminal_ui, "ask_radiolist_async"):
            return await self.terminal_ui.ask_radiolist_async(title, text, values, default)
        from prompt_toolkit.shortcuts import radiolist_dialog
        return await radiolist_dialog(title=title, text=text, values=values, default=default).run_async()

    async def _show_input(self, title, text, password=False):
        if hasattr(self.terminal_ui, "ask_input_async"):
            return await self.terminal_ui.ask_input_async(title, text, password)
        from prompt_toolkit.shortcuts import input_dialog
        return await input_dialog(title=title, text=text, password=password).run_async()

    async def _show_message(self, title, text):
        if hasattr(self.terminal_ui, "ask_message_async"):
            return await self.terminal_ui.ask_message_async(title, text)
        from prompt_toolkit.shortcuts import message_dialog
        return await message_dialog(title=title, text=text).run_async()

    async def process_meta_command(self, user_input: str) -> bool:
        """
        Processes meta-commands like %salir, %reset, %undo, %help, %compress.
        Returns True if a meta-command was processed, False otherwise.
        """
        if user_input.lower().strip() in ['%salir', 'salir', 'exit']:
            if hasattr(self.kogniterm_app, 'exit'):
                self.kogniterm_app.exit()
                return True
            sys.exit()

        if user_input.lower().strip() == '%reset':
            self.agent_state.reset() # Reiniciar el estado
            # También reiniciamos el historial de llm_service al resetear la conversación
            self.llm_service.conversation_history = []
            # ¡IMPORTANTE! Re-añadir el get_system_message(self.llm_service) después de resetear
            self.llm_service.conversation_history.append(get_system_message(self.llm_service))
            # Guardar historial CON el get_system_message(self.llm_service)
            self.llm_service._save_history(self.llm_service.conversation_history)
            # Sincronizar agent_state.messages con el historial
            self.agent_state.messages = self.llm_service.conversation_history.copy()
            
            # Limpiar la pantalla de la terminal
            if hasattr(self.terminal_ui, "clear_chat"):
                self.terminal_ui.clear_chat()
            else:
                # Intentar limpiar la consola y refrescar el tema/console para evitar
                # glitches de renderizado (ej. el banner dividido en franjas tras %reset).
                try:
                    self.terminal_ui.console.clear()
                except Exception:
                    pass
                # Recrear la consola (si aplica) para reaplicar opciones de Rich
                try:
                    self.terminal_ui.refresh_theme()
                except Exception:
                    pass
                # Finalmente volver a imprimir el banner
                self.terminal_ui.print_welcome_banner()
            self.terminal_ui.print_message(f"Conversación reiniciada.", style="green")
            if hasattr(self.kogniterm_app, "session_manager") and self.kogniterm_app.session_manager:
                self.kogniterm_app.session_manager.current_session_name = None
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
            
        if user_input.lower().strip().startswith('%mouse'):
            if hasattr(self, 'kogniterm_app') and hasattr(self.kogniterm_app, 'action_toggle_mouse'):
                self.kogniterm_app.action_toggle_mouse()
            else:
                self.terminal_ui.print_message("El comando %mouse solo está disponible en la interfaz TUI.", style="yellow")
            return True
            
        if user_input.lower().strip().startswith('%theme') or user_input.lower().strip().startswith('%tema'):
            parts = user_input.strip().split()
            theme_name = None
            if len(parts) > 1:
                theme_name = parts[1].lower()
            else:
                from kogniterm.terminal.themes import _THEMES
                theme_options = [(name, f"Tema {name}") for name in _THEMES.keys()]
                theme_name = await self._show_radiolist(
                    title="🎨 Seleccionar Tema de Color",
                    text="Elige un tema para personalizar la apariencia de KogniTerm:",
                    values=theme_options
                )
                
            if theme_name:
                try:
                    # Aplicar a la TUI si estamos en ella
                    if hasattr(self, 'kogniterm_app') and hasattr(self.kogniterm_app, 'apply_theme'):
                        self.kogniterm_app.apply_theme(theme_name)
                    else:
                        set_kogniterm_theme(theme_name)
                        self.terminal_ui.print_welcome_banner()
                    
                    # Persistir el tema globalmente
                    config_manager = ConfigManager()
                    config_manager.set_global_config("theme", theme_name)
                    
                except ValueError:
                     self.terminal_ui.print_message(f"Tema '{theme_name}' no encontrado.", style="red")
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
                self.llm_service.conversation_history.append(get_system_message(self.llm_service))
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

        if user_input.lower().strip().startswith('%resume'):
            # %resume [nombre] -> Si no hay nombre, mostrar selector de sesiones recientes
            parts = user_input.strip().split()
            name = parts[1] if len(parts) > 1 else None
            session_manager = getattr(self.kogniterm_app, 'session_manager', None)
            if not session_manager:
                self.terminal_ui.print_message("Gestor de sesiones no disponible.", style="red")
                return True

            sessions = session_manager.list_sessions()
            if not sessions:
                self.terminal_ui.print_message("No hay sesiones guardadas para reanudar.", style="yellow")
                return True

            if not name:
                options = [(s['name'], f"{s['name']} — {s['modified']} ({s['messages']} msgs)") for s in sessions]
                selected = await self._show_radiolist(title="Reanudar Sesión", text="Selecciona una sesión para reanudar:", values=options)
                if not selected:
                    self.terminal_ui.print_message("Selección cancelada.", style="dim")
                    return True
                name = selected

            history = session_manager.load_session(name)
            if history:
                # Reemplazar el historial activo con la sesión seleccionada
                self.llm_service.conversation_history = history
                # Sincronizar agent_state
                self.agent_state.messages = history.copy()
                # Persistir como historial activo (intentar, sin fallar si no funciona)
                try:
                    self.llm_service._save_history(self.llm_service.conversation_history)
                except Exception:
                    pass
                # Marcar sesión como actual en el SessionManager
                try:
                    session_manager.current_session_name = name
                except Exception:
                    pass

                # Limpiar UI y notificar
                if hasattr(self.terminal_ui, "clear_chat"):
                    self.terminal_ui.clear_chat()
                else:
                    try:
                        self.terminal_ui.console.clear()
                    except Exception:
                        pass
                self.terminal_ui.print_message(f"Sesión '{name}' reanudada. Historial cargado.", style="green")
            else:
                self.terminal_ui.print_message(f"No se pudo cargar la sesión '{name}'.", style="red")
            return True

        if user_input.lower().strip() == '%help':
            from prompt_toolkit.shortcuts import radiolist_dialog
            
            help_options = [
                ("%models", "🤖 Cambiar Modelo de IA (Seleccionar modelo del proveedor actual)"),
                ("%summarymodel", "📝 Cambiar Modelo de Resumen (Para comprimir historial)"),
                ("%provider", "🌐 Cambiar Proveedor de LLM (OpenRouter, Google, OpenAI, Anthropic, Ollama Cloud)"),
                ("%keys", "🔑 Gestionar API Keys (Configurar llaves de proveedores)"),
                ("%embeddings", "🧠 Configurar Embeddings (Local/FastEmbed, Gemini, OpenAI, etc.)"),
                ("%reset", "🔄 Reiniciar Conversación (Borrar memoria actual)"),
                ("%undo", "↩️ Deshacer (Eliminar última interacción)"),
                ("%compress [force]", "🗜️ Comprimir Historial (Usa 'force' si excede límites)"),
                ("%theme", "🎨 Cambiar Tema (Ver lista de temas disponibles)"),
                ("%session", "🗂️ Gestión de Sesiones (list, save, load, new, delete)"),
                ("%resume", "🔁 Reanudar Sesión (Reanuda una sesión guardada)"),
                ("%mouse", "🖱️ Alternar Ratón (Activa/Desactiva selección nativa)"),
                ("%insights", "📊 Analitica de Uso (Costos, Tokens, Patrones)"),
                ("%init", "📁 Inicializar Contexto (Indexar archivos clave)"),
                ("%salir", "🚪 Salir de KogniTerm"),
            ]
            
            selected_command = await self._show_radiolist(
                title="Menú de Ayuda KogniTerm",
                text="Selecciona un comando para ejecutarlo o ver más información:",
                values=help_options
            )

            if selected_command:
                # Ejecutar comandos directos
                if selected_command in ["%models", "%summarymodel", "%provider", "%keys", "%reset", "%compress", "%undo", "%mouse", "%salir", "%resume"]:
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

            # Validar el resumen: error explícito, o string vacío (fallo silencioso del LLM)
            summary_failed = (
                not summary
                or summary.startswith("Error")
                or summary.startswith("No se pudo")
            )

            if summary_failed:
                error_msg = summary if summary else "No se pudo generar el resumen (el modelo devolvió una respuesta vacía)."
                self.terminal_ui.print_message(error_msg, style="red")
                if "RateLimitError" in error_msg or "quota" in error_msg.lower():
                    self.terminal_ui.print_message("\n💡 Tip: El modelo ha alcanzado su límite de cuota. Prueba usando [bold]%compress force[/bold] para resumir solo la parte más reciente que quepa en el límite.", style="cyan")
            else:
                # Reemplazar el historial: SOLO system message + resumen
                new_history = [get_system_message(self.llm_service), AIMessage(content=summary)]
                self.llm_service.conversation_history = new_history
                # Usar .copy() para que agent_state tenga su propia lista independiente
                self.agent_state.messages = new_history.copy()
                # Persistir el historial comprimido en disco
                self.llm_service._save_history(self.llm_service.conversation_history)

                # Si estamos en la TUI, limpiar el chat log visualmente y mostrar solo el resumen
                if hasattr(self.terminal_ui, "clear_chat"):
                    self.terminal_ui.clear_chat()
                    self.terminal_ui.print_message("🗜️ **Historial comprimido.** Solo queda el resumen en el contexto:", style="green")
                    self.terminal_ui.print_message(summary)
                else:
                    # Terminal clásica: panel Rich como antes
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

            # Función auxiliar para obtener modelos de Ollama Cloud
            async def _fetch_ollama_cloud_models():
                try:
                    self.terminal_ui.print_message("⏳ Obteniendo lista de modelos de Ollama Cloud...", style="dim")
                    api_key = os.getenv("OLLAMA_CLOUD_API_KEY")
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get("https://ollama.com/api/tags", headers=headers)
                        if response.status_code == 200:
                            data = response.json()
                            if not isinstance(data, dict) or 'models' not in data:
                                self.terminal_ui.print_message("⚠️ Respuesta inesperada de Ollama Cloud: no se encontró la clave 'models'", style="yellow")
                                return []
                            models = []
                            for m in data.get('models', []):
                                model_id = f"ollama/{m['name']}"
                                name = m.get('name', m['name'])
                                size = m.get('size', 0)
                                size_str = f" ({size / (1024**3):.1f} GB)" if size else ""
                                label = f"{name}{size_str}"
                                models.append((model_id, label))
                            models.sort(key=lambda x: x[1])
                            return models
                        else:
                            self.terminal_ui.print_message(f"⚠️ Error al obtener modelos de Ollama Cloud: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Excepción al conectar con Ollama Cloud: {e}", style="red")
                    return []

            # Función auxiliar para obtener modelos de KiloCode Gateway
            async def _fetch_kilocode_models():
                try:
                    api_key = os.getenv("KILOCODE_API_KEY")
                    if not api_key:
                        self.terminal_ui.print_message("⚠️ No se encontró KILOCODE_API_KEY en el entorno.", style="yellow")
                        return []

                    self.terminal_ui.print_message("⏳ Obteniendo lista de modelos de KiloCode Gateway...", style="dim")
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            "https://api.kilo.ai/api/gateway/models",
                            headers={"Authorization": f"Bearer {api_key}"},
                            timeout=30.0
                        )
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            # KiloCode devuelve una lista directamente o con clave 'models' según la docs
                            model_list = data if isinstance(data, list) else data.get('models', data.get('data', []))
                            for m in model_list:
                                # El ID puede venir como 'kilocode/xxx' o solo 'xxx'
                                model_id = m.get('id', m.get('model', ''))
                                if not model_id.startswith('kilocode/'):
                                    model_id = f"kilocode/{model_id}"
                                name = m.get('name', m.get('id', model_id))
                                # Precio si está disponible
                                pricing = m.get('pricing', {})
                                price_str = ""
                                if pricing:
                                    prompt = float(pricing.get('prompt', 0)) * 1000000
                                    completion = float(pricing.get('completion', 0)) * 1000000
                                    price_str = f" [${prompt:.2f}/M in, ${completion:.2f}/M out]"
                                # Context length
                                context = m.get('context_length', m.get('context', 0))
                                context_str = f" ({int(context/1024)}k ctx)" if context else ""
                                label = f"{name}{context_str}{price_str}"
                                models.append((model_id, label))

                            models.sort(key=lambda x: x[1])
                            return models
                        else:
                            self.terminal_ui.print_message(f"⚠️ Error al obtener modelos de KiloCode: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Excepción al conectar con KiloCode Gateway: {e}", style="red")
                    return []

            # Función auxiliar para obtener modelos de Ollama Local
            async def _fetch_ollama_local_models():
                try:
                    ollama_url = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434/v1")
                    # Construir varias rutas candidatas para compatibilidad (/api/tags, /tags, /v1/tags)
                    base = ollama_url.rstrip('/')
                    # Normalizar si el usuario proporcionó /v1 o /api
                    if base.endswith('/v1'):
                        base = base[:-3].rstrip('/')
                    if base.endswith('/api'):
                        base = base[:-4].rstrip('/')
                    candidates = [
                        base + "/api/tags",
                        base + "/tags",
                        ollama_url.rstrip('/') + "/tags",
                    ]
                    # Mostrar las rutas que vamos a intentar
                    self.terminal_ui.print_message(f"⏳ Obteniendo modelos de Ollama Local en {candidates[0]} (probando alternativas)...", style="dim")
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = None
                        for url in candidates:
                            try:
                                response = await client.get(url)
                                if response.status_code == 200:
                                    break
                            except Exception:
                                response = None
                                continue
                        if not response:
                            self.terminal_ui.print_message("⚠️ No se pudo conectar a Ollama Local en las rutas esperadas.", style="yellow")
                            return []
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            # Aceptar varias formas de respuesta: {'models': [...]}, {'data': [...]}, o una lista
                            if isinstance(data, dict) and 'models' in data:
                                items = data.get('models', [])
                            elif isinstance(data, dict) and 'data' in data:
                                items = data.get('data', [])
                            elif isinstance(data, list):
                                items = data
                            else:
                                items = []
                            for m in items:
                                # m puede ser un dict con 'name' o una cadena
                                if isinstance(m, dict):
                                    name = m.get('name') or m.get('id')
                                elif isinstance(m, str):
                                    name = m
                                else:
                                    name = None
                                if not name:
                                    continue
                                model_id = f"ollama/{name}"
                                label = name
                                models.append((model_id, label))
                            models.sort(key=lambda x: x[1])
                            return models
                        else:
                            self.terminal_ui.print_message(f"⚠️ Error al obtener modelos de Ollama Local: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Excepción al conectar con Ollama Local: {e}", style="red")
                    return []

            current_model = self.llm_service.model_name
            
            # Detectar proveedor actual
            current_provider = "unknown"
            if current_model.startswith("openrouter/"):
                current_provider = "openrouter"
            elif current_model.startswith("gemini/"):
                current_provider = "google"
            elif current_model.startswith("ollama/"):
                # Distinguir entre local y cloud según variables de entorno y configuración explícita.
                api_base = os.environ.get("OLLAMA_API_BASE")
                cloud_base = os.environ.get("OLLAMA_CLOUD_API_BASE", "https://ollama.com")
                cloud_key = os.environ.get("OLLAMA_CLOUD_API_KEY")
                explicit = (os.environ.get("OLLAMA_PROVIDER_TARGET") or "").strip().lower()

                if explicit in ["cloud", "ollama_cloud"]:
                    current_provider = "ollama_cloud" if (cloud_key or cloud_base) else "ollama"
                elif explicit in ["local", "ollama"]:
                    current_provider = "ollama"
                else:
                    if api_base:
                        # Si la base apunta a localhost, es local
                        if any(h in api_base for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1")):
                            current_provider = "ollama"
                        # Si la base menciona ollama.com o es HTTPS y hay clave cloud, asumir cloud
                        elif "ollama.com" in api_base or (api_base.startswith("https://") and cloud_key):
                            current_provider = "ollama_cloud"
                        else:
                            # Base personalizada no identificada: preferir local
                            current_provider = "ollama"
                    else:
                        # Sin API_BASE: si hay clave cloud, preferir cloud para evitar usar local por defecto si no está configurado
                        # Pero si no hay clave cloud, el único que queda es local.
                        # MEJORA: Si estamos aquí y el modelo no tiene prefijo cloud, preferir local.
                        current_provider = "ollama" if not cloud_key else "ollama_cloud"
            elif "gpt" in current_model:
                current_provider = "openai"
            elif "claude" in current_model:
                current_provider = "anthropic"
            elif "kilocode" in current_model:
                current_provider = "kilocode"
            
            target_list = []

            # Obtener lista según proveedor
            if current_provider == "openrouter":
                target_list = await _fetch_openrouter_models()
                if not target_list:
                    target_list = [
                        ("openrouter/google/gemini-2.0-flash-exp:free", "Gemini 2.0 Flash Exp (Free)"),
                        ("openrouter/google/gemini-flash-1.5-8b", "Gemini Flash 1.5 8B"),
                        ("openrouter/anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet"),
                        ("openrouter/openai/gpt-4o", "GPT-4o"),
                    ]
            elif current_provider == "google":
                target_list = await _fetch_google_models()
                if not target_list:
                    target_list = [
                        ("gemini/gemini-2.0-flash-exp", "Gemini 2.0 Flash Exp"),
                        ("gemini/gemini-1.5-pro", "Gemini 1.5 Pro"),
                        ("gemini/gemini-1.5-flash", "Gemini 1.5 Flash"),
                        ("gemini/gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B"),
                        ("gemini/gemini-1.0-pro", "Gemini 1.0 Pro"),
                    ]
            elif current_provider == "ollama":
                target_list = await _fetch_ollama_local_models()
                if not target_list:
                    target_list = [
                        ("ollama/llama3", "Llama 3 (local)"),
                        ("ollama/mistral", "Mistral (local)"),
                        ("ollama/phi3", "Phi-3 (local)"),
                        ("ollama/codellama", "CodeLlama (local)"),
                    ]
            elif current_provider == "ollama_cloud":
                target_list = await _fetch_ollama_cloud_models()
                # Si no hay modelos, mostrar solo un mensaje, no hacer fallback a OpenRouter
                if not target_list:
                    self.terminal_ui.print_message("⚠️ No se encontraron modelos en Ollama Cloud. Verifica tu API Key o acceso.", style="yellow")
                    target_list = []
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
            elif current_provider == "kilocode":
                target_list = await _fetch_kilocode_models()
                if not target_list:
                    # Fallback a lista básica si la API falla
                    target_list = [
                        ("kilocode/kilo/auto", "Kilo Auto (Smart Routing)"),
                        ("kilocode/anthropic/claude-sonnet-4", "Claude Sonnet 4 via Kilo"),
                        ("kilocode/openai/gpt-4o", "GPT-4o via Kilo"),
                        ("kilocode/google/gemini-3-pro-preview", "Gemini 3 Pro via Kilo"),
                    ]
            else:
                target_list = await _fetch_openrouter_models()

            # Crear lista de opciones para el diálogo
            values = []
            for model_id, model_label in target_list:
                values.append((model_id, model_label))
            
            selected_model = await self._show_radiolist(
                title=f"Seleccionar Modelo de IA ({len(values)} disponibles)",
                text=f"Modelo actual: {current_model}\nProveedor: {current_provider.capitalize()}\n\nEscribe para buscar/filtrar en la lista (clásico):",
                values=values,
                default=current_model if any(m[0] == current_model for m in values) else None
            )

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
                                    # SIEMPRE establecer LITELLM_MODEL para consistencia
                                    set_key(dotenv_path, "LITELLM_MODEL", selected_model)
                                    os.environ["LITELLM_MODEL"] = selected_model
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
                        # Actualizar footer si estamos en TUI
                        if hasattr(self.kogniterm_app, "update_status_footer"):
                            self.kogniterm_app.update_status_footer(selected_model)
                        self.terminal_ui.print_message(f"ℹ️  Configuración persistida en .env ({'GEMINI_MODEL' if selected_model.startswith('gemini/') else 'LITELLM_MODEL'}).", style="dim")
                        self.terminal_ui.print_message(f"ℹ️  Configuración guardada como predeterminada.", style="dim")
                    except Exception as e:
                        self.terminal_ui.print_message(f"❌ Error al cambiar el modelo: {e}", style="red")
                else:
                    self.terminal_ui.print_message("Modelo no cambiado (selección idéntica).", style="dim")
            
            return True

        if user_input.lower().strip() == '%summarymodel':
            """Permite cambiar el modelo usado para resumir/comprimir el historial."""
            current_summary_model = self.llm_service.summary_model
            current_model = self.llm_service.model_name
            current_provider = self.llm_service.model_name.split('/')[0] if '/' in self.llm_service.model_name else 'google'
            
            # Función auxiliar para obtener modelos (reutilizada de %models)
            async def _fetch_google_models():
                try:
                    google_key = os.environ.get("GOOGLE_API_KEY")
                    if not google_key:
                        self.terminal_ui.print_message("⚠️ No se encontró GOOGLE_API_KEY en el entorno.", style="yellow")
                        return []
                    
                    self.terminal_ui.print_message("⏳ Obteniendo modelos actualizados de Google AI...", style="dim")
                    async with httpx.AsyncClient() as client:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}"
                        response = await client.get(url)
                        
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            for m in data.get('models', []):
                                if 'generateContent' in m.get('supportedGenerationMethods', []):
                                    model_id = m['name'].replace('models/', 'gemini/')
                                    display_name = m.get('displayName', m['name'].split('/')[-1])
                                    version = ""
                                    if "1.5" in model_id: version = " (1.5)"
                                    elif "2.0" in model_id: version = " (2.0)"
                                    label = f"{display_name}{version}"
                                    models.append((model_id, label))
                            
                            models.sort(key=lambda x: x[0], reverse=True)
                            return models
                        else:
                            self.terminal_ui.print_message(f"⚠️ Error API Google: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Error al conectar con Google: {e}", style="red")
                    return []

            async def _fetch_openrouter_models():
                try:
                    self.terminal_ui.print_message("⏳ Obteniendo lista de modelos de OpenRouter...", style="dim")
                    async with httpx.AsyncClient() as client:
                        response = await client.get("https://openrouter.ai/api/v1/models")
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            for m in data.get('data', []):
                                model_id = f"openrouter/{m['id']}"
                                name = m.get('name', m['id'])
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
                            
                            models.sort(key=lambda x: x[1])
                            return models
                        else:
                            self.terminal_ui.print_message(f"⚠️ Error al obtener modelos de OpenRouter: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Error al conectar con OpenRouter: {e}", style="red")
                    return []

            async def _fetch_ollama_cloud_models():
                try:
                    self.terminal_ui.print_message("⏳ Obteniendo modelos de Ollama Cloud...", style="dim")
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            "https://ollama.com/api/models",
                            headers={"Authorization": f"Bearer {os.environ.get('OLLAMA_CLOUD_API_KEY', '')}"}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            for m in data.get('models', []):
                                model_id = f"ollama/{m.get('name', m.get('id'))}"
                                label = m.get('name', m.get('id'))
                                models.append((model_id, label))
                            models.sort(key=lambda x: x[1])
                            return models
                        else:
                            return []
                except Exception:
                    return []

            # Obtener lista de modelos según el proveedor actual
            if current_provider in ["google", "gemini"]:
                target_list = await _fetch_google_models()
            elif current_provider == "ollama_cloud":
                target_list = await _fetch_ollama_cloud_models()
            elif current_provider == "openai":
                target_list = [
                    ("gpt-4o", "GPT-4o"),
                    ("gpt-4o-mini", "GPT-4o Mini"),
                    ("gpt-4-turbo", "GPT-4 Turbo"),
                ]
            elif current_provider == "anthropic":
                target_list = [
                    ("claude-3-5-sonnet-20240620", "Claude 3.5 Sonnet"),
                    ("claude-3-opus-20240229", "Claude 3 Opus"),
                ]
            else:
                target_list = await _fetch_openrouter_models()

            # Agregar opción para usar el mismo que el modelo principal
            values = [(current_model, f"Usar modelo principal ({current_model}) [Recomendado]")]
            for model_id, model_label in target_list:
                if model_id != current_model:
                    values.append((model_id, model_label))
            
            # También agregar opción de Gemini 1.5 Flash como fallback gratuito
            if current_model != "gemini/gemini-1.5-flash":
                values.append(("gemini/gemini-1.5-flash", "Gemini 1.5 Flash (Gratis, rápido)"))
            
            selected_model = await self._show_radiolist(
                title="Seleccionar Modelo de Resumen",
                text=f"Modelo actual de resumen: {current_summary_model}\nModelo principal: {current_model}\n\nEste modelo se usa para comprimir el historial con %compress:",
                values=values,
                default=current_summary_model
            )

            if selected_model:
                if selected_model != current_summary_model:
                    try:
                        self.llm_service.set_summary_model(selected_model)
                        
                        # Persistir en .env y ConfigManager
                        if DOTENV_AVAILABLE:
                            dotenv_path = find_dotenv()
                            if dotenv_path:
                                set_key(dotenv_path, "SUMMARY_MODEL", selected_model)
                        
                        config_manager = ConfigManager()
                        config_manager.set_global_config("summary_model", selected_model)
                        
                        self.terminal_ui.print_message(f"✅ Modelo de resumen cambiado a: {selected_model}", style="green")
                        self.terminal_ui.print_message(f"ℹ️  Este modelo se usará para comprimir el historial con %compress", style="dim")
                    except Exception as e:
                        self.terminal_ui.print_message(f"❌ Error al cambiar el modelo de resumen: {e}", style="red")
                else:
                    self.terminal_ui.print_message("Modelo de resumen no cambiado (selección idéntica).", style="dim")
            
            return True

        if user_input.lower().strip() == '%provider':
            from prompt_toolkit.shortcuts import radiolist_dialog

            providers = [
                ("openrouter", "🌐 OpenRouter (Acceso a múltiples modelos)"),
                ("google", "🤖 Google AI (Gemini nativo)"),
                ("openai", "🧠 OpenAI (GPT-4, GPT-3.5)"),
                ("anthropic", "🎭 Anthropic (Claude)"),
                ("ollama", "🦙 Ollama Local (servidor local)",),
                ("ollama_cloud", "☁️  Ollama Cloud (Modelos de Ollama)"),
                ("kilocode", "⚡ KiloCode Gateway (Routing inteligente)"),
            ]

            selected_provider = await self._show_radiolist(
                title="Seleccionar Proveedor de LLM",
                text="Selecciona el proveedor que deseas utilizar. Esto actualizará tu configuración predeterminada:",
                values=providers
            )

            if selected_provider:
                self.terminal_ui.print_message(f"Cambiando proveedor a: {selected_provider.capitalize()}...", style="yellow")
                # Definir modelo por defecto para cada proveedor
                default_models = {
                    "openrouter": "openrouter/google/gemini-2.0-flash-exp:free",
                    "google": "gemini/gemini-1.5-flash",
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-3-5-sonnet-20240620",
                    "ollama": "ollama/llama3",
                    "ollama_cloud": "ollama/llama3",
                    "kilocode": "kilocode/kilo/auto",
                }
                new_model = default_models.get(selected_provider)

                ollama_url = None
                if selected_provider == "ollama":
                    ollama_url = await self._show_input(
                        title="Configurar URL de Ollama Local",
                        text="Introduce la URL de tu servidor Ollama local (ejemplo: http://localhost:11434/v1):"
                    )
                    if ollama_url:
                        # Guardar en variable de entorno y persistir en .env si es posible
                        os.environ["OLLAMA_API_BASE"] = ollama_url
                        os.environ["OLLAMA_PROVIDER_TARGET"] = "local"
                        if DOTENV_AVAILABLE:
                            dotenv_path = find_dotenv()
                            if dotenv_path:
                                set_key(dotenv_path, "OLLAMA_API_BASE", ollama_url)
                                set_key(dotenv_path, "OLLAMA_PROVIDER_TARGET", "local")
                        # También persistir en ConfigManager si aplica
                        config_manager = ConfigManager()
                        config_manager.set_global_config("ollama_api_base", ollama_url)
                        config_manager.set_global_config("ollama_provider_target", "local")
                        self.terminal_ui.print_message(f"🔗 URL de Ollama Local configurada: {ollama_url}", style="dim")
                        self.terminal_ui.print_message(f"🎯 Target de Ollama establecido a: LOCAL", style="dim")
                    else:
                        os.environ["OLLAMA_PROVIDER_TARGET"] = "local"
                        if DOTENV_AVAILABLE:
                            dotenv_path = find_dotenv()
                            if dotenv_path: set_key(dotenv_path, "OLLAMA_PROVIDER_TARGET", "local")
                        self.terminal_ui.print_message("⚠️  No se configuró URL de Ollama Local. Usando valor por defecto y estableciendo target a LOCAL.", style="yellow")

                try:
                    # Gestionar OLLAMA_PROVIDER_TARGET si es necesario
                    if selected_provider == "ollama_cloud":
                        os.environ["OLLAMA_PROVIDER_TARGET"] = "cloud"
                        if DOTENV_AVAILABLE:
                            dotenv_path = find_dotenv()
                            if dotenv_path: set_key(dotenv_path, "OLLAMA_PROVIDER_TARGET", "cloud")
                    
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
                    # Actualizar footer si estamos en TUI
                    if hasattr(self.kogniterm_app, "update_status_footer"):
                        self.kogniterm_app.update_status_footer(new_model)
                    self.terminal_ui.print_message(f"🤖 Modelo predeterminado establecido: {new_model}", style="dim")
                    self.terminal_ui.print_message("ℹ️  Puedes cambiar el modelo específico con %models", style="italic dim")
                except Exception as e:
                    self.terminal_ui.print_message(f"❌ Error al cambiar el proveedor: {e}", style="red")
            
            return True

        if user_input.lower().strip() == '%keys':
            await self._manage_keys_interactive()
            return True

        if user_input.lower().strip().startswith('%embeddings'):
            await self._manage_embeddings_interactive()
            return True
        if user_input.lower().strip().startswith('%insights'):
            await self._process_insights_command(user_input)
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
            "OLLAMA_CLOUD_API_KEY",
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
            
            is_tui = getattr(self.terminal_ui, "is_tui", False)
            for key in all_keys:
                val = os.environ.get(key, "")
                if val:
                    # Enmascarar valor: mostrar solo inicio y fin
                    masked = f"{val[:4]}...{val[-4:]}" if len(val) > 8 else "****"
                    if is_tui:
                        status = f'✅ [cyan]{masked}[/cyan]'
                    else:
                        status = f'✅ <style fg="cyan">{masked}</style>'
                else:
                    if is_tui:
                        status = '❌ [dim]No configurada[/dim]'
                    else:
                        status = '❌ <style fg="#888888">No configurada</style>'
                
                if is_tui:
                    options.append((key, f'{key:<20} | {status}'))
                else:
                    # Usar HTML para que prompt_toolkit renderice los estilos
                    options.append((key, HTML(f'{key:<20} | {status}')))
            
            options.append(("CUSTOM", "➕ Añadir otra variable..."))
            options.append(("BACK", "⬅️  Volver"))
            
            selected_key = await self._show_radiolist(
                title="Gestión de API Keys / Variables de Entorno",
                text=f"Archivo: {os.path.basename(dotenv_path)}\nSelecciona una llave para editarla o eliminarla:",
                values=options
            )
            
            if not selected_key or selected_key == "BACK":
                break
                
            if selected_key == "CUSTOM":
                custom_name = await self._show_input(
                    title="Nueva Variable",
                    text="Introduce el nombre de la variable (ej: MY_SERVICE_KEY):"
                )
                if custom_name:
                    selected_key = custom_name.strip().upper()
                else:
                    continue

            # Acción para la llave seleccionada
            current_val = os.environ.get(selected_key, "")
            masked_val = f"{current_val[:4]}...{current_val[-4:]}" if len(current_val) > 8 else ("****" if current_val else "Vacío")
            
            action = await self._show_radiolist(
                title=f"Acción para {selected_key}",
                text=f"Variable: {selected_key}\nValor actual: {masked_val}",
                values=[
                    ("SET", "✏️  Establecer / Cambiar valor"),
                    ("DELETE", "🗑️  Eliminar llave"),
                    ("CANCEL", "🚫 Cancelar")
                ]
            )
            
            if action == "SET":
                new_val = await self._show_input(
                    title=f"Establecer {selected_key}",
                    text=f"Introduce el valor para {selected_key}:",
                    password=True
                )
                
                if new_val is not None: # Permitir valor vacío si el usuario pulsa OK
                    new_val = new_val.strip() # Limpiar espacios y saltos de línea que pueden truncar la clave
                    
                    # Validación de seguridad: no permitir guardar API Keys en LITELLM_MODEL
                    if selected_key == "LITELLM_MODEL" and new_val.startswith("AIza"):
                        await self._show_message(
                            title="⚠️ Error de Configuración",
                            text=f"Parece que estás intentando guardar una API Key en LITELLM_MODEL.\nEsta variable debe contener el nombre del modelo (ej: google/gemini-1.5-flash), no la clave.\n\nLa clave debe ir en GOOGLE_API_KEY o OPENROUTER_API_KEY."
                        )
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
                        await self._show_message(
                            title="Éxito", 
                            text=f"Llave {selected_key} guardada correctamente.\nLongitud: {key_len} caracteres.\nVista previa: {masked_preview}"
                        )
                    except Exception as e:
                        await self._show_message(title="Error", text=f"No se pudo guardar la llave: {e}")
            
            elif action == "DELETE":
                try:
                    unset_key(dotenv_path, selected_key)
                    if selected_key in os.environ:
                        del os.environ[selected_key]
                    await self._show_message(title="Éxito", text=f"Llave {selected_key} eliminada del archivo y del entorno.")
                except Exception as e:
                    await self._show_message(title="Error", text=f"No se pudo eliminar la llave: {e}")

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

    
    async def _process_insights_command(self, user_input: str):
        """Procesa el comando %insights para mostrar analitica de uso."""
        parts = user_input.strip().split()
        days = 30  # Default
        
        if len(parts) > 1:
            try:
                days = int(parts[1])
            except ValueError:
                self.terminal_ui.print_message("Uso incorrecto. Uso: %insights [dias]", style="yellow")
                return
        
        self.terminal_ui.print_message(f"Generando reporte de analitica (ultimos {days} dias)...", style="dim")
        
        try:
            insights = KogniInsightsEngine()
            report = insights.generate_report(days=days)
            
            from rich.panel import Panel
            from rich.table import Table
            
            # Panel de resumen
            summary_data = []
            summary_data.append(f"Total de Sesiones: {report['summary']['total_sessions']}")
            summary_data.append(f"Costo Total: ${report['summary']['total_cost']:.4f}")
            summary_data.append(f"Tokens Totales: {report['summary']['total_tokens']:,}")
            summary_data.append(f"Modelo Mas Usado: {report['summary']['top_model']}")
            summary_data.append(f"Herramienta Mas Activa: {report['summary']['top_tool']}")
            
            summary_text = "\n".join(summary_data)
            self.terminal_ui.console.print(Panel(summary_text, title="📊 Resumen de Uso", border_style="cyan"))
            
            # Tabla de modelos
            if report['model_ranking']:
                models_table = Table(title="🏆 Ranking de Modelos")
                models_table.add_column("Pos.", justify="center", style="cyan")
                models_table.add_column("Modelo", style="green")
                models_table.add_column("Sesiones", justify="right")
                models_table.add_column("Tokens", justify="right")
                models_table.add_column("Costo", justify="right")
                
                for i, model in enumerate(report['model_ranking'][:5], 1):
                    models_table.add_row(
                        str(i), model['model'], str(model['sessions']),
                        f"{model['tokens']:,}", f"${model['cost']:.4f}"
                    )
                self.terminal_ui.console.print(models_table)
            
            # Tabla de herramientas
            if report['tool_ranking']:
                tools_table = Table(title="🛠️ Ranking de Herramientas")
                tools_table.add_column("Pos.", justify="center", style="cyan")
                tools_table.add_column("Herramienta", style="magenta")
                tools_table.add_column("Usos", justify="right")
                
                for i, tool in enumerate(report['tool_ranking'][:5], 1):
                    tools_table.add_row(str(i), tool['tool'], str(tool['count']))
                self.terminal_ui.console.print(tools_table)
                
        except Exception as e:
            self.terminal_ui.print_message(f"Error al generar reporte: {e}", style="red")


    async def _manage_embeddings_interactive(self):
        """Muestra una interfaz interactiva para gestionar la configuración de embeddings."""
        from prompt_toolkit.shortcuts import radiolist_dialog, message_dialog
        
        config_manager = ConfigManager()
        current_config = config_manager.get_all_config()
        
        current_provider = current_config.get("embeddings_provider", "fastembed")
        current_model = current_config.get("embeddings_model", "BAAI/bge-small-en-v1.5" if current_provider == "fastembed" else "N/A")

        while True:
            options = [
                ("PROVIDER", f"🌐 Cambiar Proveedor (Actual: {current_provider})"),
            ]
            
            if current_provider == "fastembed":
                options.append(("MODEL", f"🤖 Cambiar Modelo Local (Actual: {current_model})"))
            
            options.append(("BACK", "⬅️  Volver"))

            choice = await self._show_radiolist(
                title="Configuración de Embeddings",
                text=f"Proveedor actual: {current_provider}\nModelo actual: {current_model}\n\nSelecciona una opción:",
                values=options
            )

            if not choice or choice == "BACK":
                break

            if choice == "PROVIDER":
                providers = [
                    ("fastembed", "🚀 Local (FastEmbed) - Autónomo y Rápido"),
                    ("gemini", "♊ Google Gemini - Alta Calidad (Requiere API Key)"),
                    ("openai", "🧠 OpenAI - Estándar de la Industria (Requiere API Key)"),
                    ("ollama", "🦙 Ollama - Contenedor Externo (Requiere Ollama corriendo)"),
                ]
                
                new_provider = await self._show_radiolist(
                    title="Seleccionar Proveedor de Embeddings",
                    text="Elige el proveedor que deseas utilizar:",
                    values=providers,
                    default=current_provider
                )

                if new_provider and new_provider != current_provider:
                    config_manager.set_global_config("embeddings_provider", new_provider)
                    current_provider = new_provider
                    # Reset model when provider changes to default
                    if new_provider == "fastembed":
                        current_model = "BAAI/bge-small-en-v1.5"
                        config_manager.set_global_config("embeddings_model", current_model)
                    
                    await self._show_message(
                        title="Éxito",
                        text=f"Proveedor de embeddings cambiado a: {new_provider}\n\nNota: Es posible que necesites reiniciar KogniTerm para aplicar los cambios en el servicio activo."
                    )

            elif choice == "MODEL" and current_provider == "fastembed":
                # Lista de modelos populares en fastembed
                models = [
                    ("BAAI/bge-small-en-v1.5", "BGE Small (En) - Muy rápido y eficiente"),
                    ("BAAI/bge-base-en-v1.5", "BGE Base (En) - Balance entre velocidad y calidad"),
                    ("snowflake/snowflake-arctic-embed-m", "Snowflake Arctic M - Gran rendimiento"),
                    ("sentence-transformers/all-MiniLM-L6-v2", "MiniLM-L6-v2 - Clásico y ligero"),
                ]
                
                new_model = await self._show_radiolist(
                    title="Seleccionar Modelo Local (FastEmbed)",
                    text="Selecciona el modelo que se descargará y usará localmente:",
                    values=models,
                    default=current_model
                )

                if new_model and new_model != current_model:
                    config_manager.set_global_config("embeddings_model", new_model)
                    current_model = new_model
                    await self._show_message(
                        title="Éxito",
                        text=f"Modelo local cambiado a: {new_model}\n\nNota: La primera vez que lo uses, se descargará automáticamente."
                    )