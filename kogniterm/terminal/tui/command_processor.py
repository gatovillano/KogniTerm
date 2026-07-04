import json
import logging
from typing import Optional
from kogniterm.terminal.api_client_tui import get_available_models, set_llm_config, get_llm_config

logger = logging.getLogger(__name__)

class TUICommandProcessor:
    def __init__(self, tui_app):
        self.app = tui_app
        self.terminal_ui = tui_app.tui_ui

    async def process_command(self, user_input: str) -> bool:
        """Procesa comandos de configuración desde la TUI."""
        if not user_input.startswith('/') and not user_input.startswith('%'):
            return False
            
        cmd_parts = user_input.strip().split()
        cmd = cmd_parts[0].lower()[1:] # quitar / o %
        
        if cmd == "models":
            await self._handle_models()
            return True
        elif cmd == "provider":
            await self._handle_provider()
            return True
        elif cmd == "keys":
            await self._handle_keys()
            return True
        elif cmd == "theme" or cmd == "tema":
            await self._handle_theme()
            return True
        elif cmd == "help":
            await self._handle_help()
            return True
        elif cmd == "reset":
            # El reset se puede enviar al backend via WS o manejar aquí
            # Por consistencia, lo enviamos al backend via WS
            return False 
            
        return False

    async def _handle_models(self):
        """Muestra modal para cambiar el modelo en el servidor."""
        try:
            # 1. Obtener la configuración actual para saber el proveedor activo
            config = await get_llm_config()
            active_provider = config.get("provider", "google")
            
            # 2. Obtener todos los modelos disponibles
            models_data = await get_available_models()
            options = []
            providers = models_data.get("providers", [])
            for p in providers:
                p_id = p.get("id", "unknown")
                p_name = p.get("name", p_id)
                # MOSTRAR SOLO LOS MODELOS DEL PROVEEDOR CONFIGURADO
                if p_id == active_provider:
                    models = p.get("models", [])
                    for m in models:
                        options.append((m, f"[{p_name}] {m}"))
            
            if not options:
                self.terminal_ui.print_message(f"⚠️ No hay modelos disponibles para el proveedor actual: '{active_provider}'", style="yellow")
                return

            selected = await self.terminal_ui.ask_radiolist_async(
                title=f"Seleccionar Modelo ({active_provider.capitalize()})",
                text=f"Selecciona el modelo para el proveedor configurado '{active_provider}':",
                values=options
            )
            
            if selected:
                await set_llm_config(model_name=selected)
                if self.app.llm_service:
                    self.app.llm_service.set_model(selected)
                self.app.update_status_footer(selected)
                self.terminal_ui.print_message(f"✅ Modelo actualizado en el servidor: {selected}", style="green")
        except Exception as e:
            self.terminal_ui.print_message(f"❌ Error al obtener modelos: {e}", style="red")

    async def _handle_provider(self):
        """Muestra modal para cambiar el proveedor."""
        providers = [
            ("google", "Google AI (Gemini)"),
            ("openai", "OpenAI (GPT)"),
            ("anthropic", "Anthropic (Claude)"),
            ("openrouter", "OpenRouter"),
            ("kilocode", "KiloCode Gateway"),
            ("ollama", "Ollama Local")
        ]
        
        selected = await self.terminal_ui.ask_radiolist_async(
            title="Seleccionar Proveedor",
            text="Selecciona el proveedor preferido:",
            values=providers
        )
        
        if selected:
            await set_llm_config(provider=selected)
            try:
                config = await get_llm_config()
                new_model = config.get("model")
                if new_model:
                    if self.app.llm_service:
                        self.app.llm_service.set_model(new_model)
                    self.app.update_status_footer(new_model)
            except Exception as ex:
                logger.warning(f"Error al sincronizar modelo local tras cambio de proveedor: {ex}")
            self.terminal_ui.print_message(f"✅ Proveedor actualizado en el servidor: {selected}", style="green")

    async def _handle_keys(self):
        """Muestra modal para configurar API Keys en el servidor."""
        keys = [
            ("google", "GOOGLE_API_KEY"),
            ("openai", "OPENAI_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("openrouter", "OPENROUTER_API_KEY"),
            ("kilocode", "KILOCODE_API_KEY")
        ]
        
        selected_provider = await self.terminal_ui.ask_radiolist_async(
            title="Configurar API Keys",
            text="Selecciona el proveedor para configurar su llave en el servidor:",
            values=keys
        )
        
        if selected_provider:
            key_val = await self.terminal_ui.ask_input_async(
                title=f"API Key para {selected_provider}",
                text="Introduce la llave (se guardará en el servidor):",
                password=True
            )
            
            if key_val:
                await set_llm_config(provider=selected_provider, api_key=key_val)
                self.terminal_ui.print_message(f"✅ Llave para {selected_provider} enviada al servidor.", style="green")

    async def _handle_theme(self):
        """Muestra modal para cambiar el tema visual."""
        from kogniterm.terminal.themes import _THEMES
        options = [(name, f"Tema {name.capitalize()}") for name in _THEMES.keys()]
        
        selected = await self.terminal_ui.ask_radiolist_async(
            title="🎨 Seleccionar Tema",
            text="Elige el estilo visual para la TUI:",
            values=options
        )
        
        if selected:
            self.app.apply_theme(selected)
            from kogniterm.terminal.config_manager import ConfigManager
            cm = ConfigManager()
            cm.set_global_config("theme", selected)
            if cm.PROJECT_CONFIG_FILE.exists():
                cm.set_project_config("theme", selected)
            self.terminal_ui.print_message(f"✅ Tema actualizado: {selected}", style="green")

    async def _handle_help(self):
        """Muestra menú de ayuda con comandos disponibles."""
        help_text = (
            "[bold cyan]Comandos de Configuración:[/bold cyan]\n"
            "  /models   : Cambiar modelo del agente central\n"
            "  /provider : Cambiar proveedor de LLM\n"
            "  /keys     : Configurar API Keys en el servidor\n"
            "  /theme    : Cambiar tema visual de la TUI\n"
            "  /reset    : Reiniciar la conversación\n"
            "  /undo     : Deshacer última interacción\n"
            "\n"
            "[dim]Nota: Estos comandos configuran el servidor central.[/dim]"
        )
        await self.terminal_ui.ask_message_async(title="Ayuda KogniTerm", text=help_text)
