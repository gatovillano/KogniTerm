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
from kogniterm.terminal.themes import set_kogniterm_theme, get_available_themes
from kogniterm.terminal.config_manager import ConfigManager


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
                     self.terminal_ui.print_message(f"Tema '{theme_name}' no encontrado. Temas disponibles: {', '.join(get_available_themes())}", style="red")
            else:
                self.terminal_ui.print_message(f"Temas disponibles: {', '.join(get_available_themes())}", style="blue")
            return True


        if user_input.lower().strip() == '%help':
            from prompt_toolkit.shortcuts import radiolist_dialog
            
            help_options = [
                ("%models", "🤖 Cambiar Modelo de IA (Seleccionar proveedor/modelo)"),
                ("%reset", "🔄 Reiniciar Conversación (Borrar memoria actual)"),
                ("%compress", "🗜️ Comprimir Historial (Resumir para ahorrar tokens)"),
                ("%undo", "↩️ Deshacer (Eliminar última interacción)"),
                ("%theme", "🎨 Cambiar Tema (Ver lista de temas disponibles)"),
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
                if selected_command in ["%models", "%reset", "%compress", "%undo", "%salir"]:
                    # Llamada recursiva para procesar el comando seleccionado
                    return await self.process_meta_command(selected_command)
                
                # Comandos que requieren argumentos o interacción especial
                elif selected_command == "%theme":
                    # Ejecutar %theme sin argumentos muestra la lista de temas
                    return await self.process_meta_command("%theme")
                
                elif selected_command == "%init":
                    self.terminal_ui.print_message("ℹ️  Uso: %init [archivos]", style="blue")
                    self.terminal_ui.print_message("Ejemplo: %init README.md,src/main.py", style="dim")
                    self.terminal_ui.print_message("Tip: Usa este comando para cargar contexto específico en la memoria.", style="dim")
            
            return True

        if user_input.lower().strip() == '%compress':
            self.terminal_ui.print_message("Resumiendo historial de conversación...", style="yellow")
            
            summary = self.llm_service.summarize_conversation_history()
            
            if summary.startswith("Error") or summary.startswith("No se pudo"):
                self.terminal_ui.print_message(summary, style="red")
            else:
                self.llm_service.conversation_history = [SYSTEM_MESSAGE, AIMessage(content=summary)]
                self.agent_state.messages = self.llm_service.conversation_history
                self.llm_service._save_history(self.llm_service.conversation_history) # Guardar historial comprimido
                self.terminal_ui.console.print(Panel(Markdown(f"Historial comprimido:\n{summary}"), border_style="green", title="[bold green]Historial Comprimido[/bold green]"))
            return True

        if user_input.lower().strip() == '%models':
            from prompt_toolkit.shortcuts import radiolist_dialog
            import httpx
            import json

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
                target_list = [
                    ("gemini/gemini-2.0-flash-exp", "Gemini 2.0 Flash Exp"),
                    ("gemini/gemini-1.5-pro", "Gemini 1.5 Pro"),
                    ("gemini/gemini-1.5-flash", "Gemini 1.5 Flash"),
                    ("gemini/gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B"),
                    ("gemini/gemini-1.0-pro", "Gemini 1.0 Pro"),
                    ("gemini/gemini-pro-vision", "Gemini Pro Vision"),
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
                        
                        # Persistir el cambio globalmente
                        config_manager = ConfigManager()
                        config_manager.set_global_config("default_model", selected_model)
                        
                        self.terminal_ui.print_message(f"✅ Modelo cambiado exitosamente a: {selected_model}", style="green")
                        self.terminal_ui.print_message(f"ℹ️  Configuración guardada como predeterminada.", style="dim")
                    except Exception as e:
                        self.terminal_ui.print_message(f"❌ Error al cambiar el modelo: {e}", style="red")
                else:
                    self.terminal_ui.print_message("Modelo no cambiado (selección idéntica).", style="dim")
            
            return True

        return False