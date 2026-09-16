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
        elif cmd == "mcp":
            await self._handle_mcp(cmd_parts[1:] if len(cmd_parts) > 1 else [])
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
                if hasattr(self.app, "agent_interaction_manager") and self.app.agent_interaction_manager:
                    self.app.agent_interaction_manager.set_model(selected)
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
            ("ollama", "Ollama Local"),
            ("ollama_cloud", "Ollama Cloud"),
            ("kilocode", "KiloCode Gateway"),
            ("inception", "Inception Labs"),
            ("antigravity", "Google Antigravity (Session OAuth2)"),
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
                    if hasattr(self.app, "agent_interaction_manager") and self.app.agent_interaction_manager:
                        self.app.agent_interaction_manager.set_model(new_model)
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
            ("kilocode", "KILOCODE_API_KEY"),
            ("inception", "INCEPTION_API_KEY")
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

    async def _handle_mcp(self, args: list):
        """Maneja la configuración y gestión de servidores MCP."""
        import shlex
        from kogniterm.terminal.config_manager import ConfigManager
        from kogniterm.core.mcp.mcp_manager import MCPManager

        cm = ConfigManager()
        manager = MCPManager.get_instance()

        subcmd = args[0].lower() if args else None

        if subcmd == "list":
            statuses = manager.get_all_servers_status()
            if not statuses:
                self.terminal_ui.print_message("⚠️ No hay servidores MCP configurados.", style="yellow")
                return
            lines = ["[bold cyan]🔌 Servidores MCP Configurados:[/bold cyan]"]
            for name, info in statuses.items():
                transport = info.get("transport", "stdio")
                status = info.get("status", "disconnected")
                tools = info.get("tools", [])
                icon = "🟢" if status == "connected" else ("⏸️" if status == "disabled" else "🔴")
                lines.append(f"  {icon} [bold]{name}[/bold] ({transport}) - Estado: {status}")
                if tools:
                    lines.append(f"     Herramientas: {', '.join(tools)}")
                elif info.get("error"):
                    lines.append(f"     Error: {info.get('error')}")
            self.terminal_ui.print_message("\n".join(lines))
            return

        elif subcmd == "toggle":
            if len(args) < 2:
                self.terminal_ui.print_message("Uso: /mcp toggle <nombre_servidor>", style="yellow")
                return
            name = args[1]
            servers = cm.get_mcp_servers()
            if name not in servers:
                self.terminal_ui.print_message(f"❌ Servidor '{name}' no encontrado.", style="red")
                return
            conf = servers[name]
            conf["disabled"] = not conf.get("disabled", False)
            cm.set_mcp_server(name, conf)
            await manager.reload()
            if self.app.llm_service:
                self.app.llm_service.sync_tools()
            state_str = "deshabilitado" if conf["disabled"] else "habilitado"
            self.terminal_ui.print_message(f"✅ Servidor '{name}' {state_str}.", style="green")
            return

        elif subcmd == "reload":
            self.terminal_ui.print_message("🔄 Recargando servidores MCP...", style="cyan")
            await manager.reload()
            if self.app.llm_service:
                self.app.llm_service.sync_tools()
            self.terminal_ui.print_message(f"✅ MCP recargado. Herramientas activas: {len(manager.active_tools)}", style="green")
            return

        elif subcmd in ("remove", "delete"):
            if len(args) < 2:
                self.terminal_ui.print_message("Uso: /mcp remove <nombre_servidor>", style="yellow")
                return
            name = args[1]
            cm.delete_mcp_server(name)
            await manager.reload()
            if self.app.llm_service:
                self.app.llm_service.sync_tools()
            self.terminal_ui.print_message(f"🗑️ Servidor '{name}' eliminado.", style="green")
            return

        elif subcmd == "add":
            if len(args) < 3:
                self.terminal_ui.print_message("Uso: /mcp add <nombre> <comando> [args...]", style="yellow")
                return
            name = args[1]
            command = args[2]
            server_args = args[3:]
            conf = {
                "transport": "stdio",
                "command": command,
                "args": server_args,
                "disabled": False
            }
            cm.set_mcp_server(name, conf)
            await manager.reload()
            if self.app.llm_service:
                self.app.llm_service.sync_tools()
            self.terminal_ui.print_message(f"✅ Servidor stdio '{name}' agregado.", style="green")
            return

        # Modo Interactivo: Si no hay argumentos o subcomando no reconocido
        options = [
            ("status", "📋 Ver estado de servidores y herramientas"),
            ("add_stdio", "➕ Agregar servidor local (stdio)"),
            ("add_sse", "🌐 Agregar servidor remoto (SSE)"),
            ("toggle", "🔄 Alternar servidor (Activar / Desactivar)"),
            ("test", "🧪 Probar conexión de servidor"),
            ("reload", "🔄 Recargar servidores y sincronizar con LLM"),
            ("delete", "🗑️ Eliminar servidor"),
        ]

        action = await self.terminal_ui.ask_radiolist_async(
            title="🔌 Gestión de Servidores MCP",
            text="Selecciona una acción:",
            values=options
        )

        if not action:
            return

        if action == "status":
            statuses = manager.get_all_servers_status()
            if not statuses:
                await self.terminal_ui.ask_message_async(
                    title="Servidores MCP",
                    text="No hay servidores MCP configurados actualmente."
                )
                return
            lines = []
            for name, info in statuses.items():
                transport = info.get("transport", "stdio")
                status = info.get("status", "disconnected")
                tools = info.get("tools", [])
                icon = "🟢" if status == "connected" else ("⏸️" if status == "disabled" else "🔴")
                lines.append(f"{icon} {name} [{transport}] - {status}")
                if tools:
                    lines.append(f"   Herramientas ({len(tools)}): {', '.join(tools)}")
                elif info.get("error"):
                    lines.append(f"   Error: {info.get('error')}")
                lines.append("")
            await self.terminal_ui.ask_message_async(
                title="Estado de Servidores MCP",
                text="\n".join(lines).strip()
            )

        elif action == "add_stdio":
            name = await self.terminal_ui.ask_input_async(
                title="Nuevo Servidor MCP (stdio)",
                text="Identificador único (ej: filesystem):"
            )
            if not name:
                return
            cmd = await self.terminal_ui.ask_input_async(
                title="Comando",
                text="Comando a ejecutar (ej: npx o python3):"
            )
            if not cmd:
                return
            args_str = await self.terminal_ui.ask_input_async(
                title="Argumentos",
                text="Argumentos separados por espacio (opcional):"
            )
            server_args = shlex.split(args_str) if args_str else []
            conf = {
                "transport": "stdio",
                "command": cmd,
                "args": server_args,
                "disabled": False
            }
            cm.set_mcp_server(name, conf)
            await manager.reload()
            if self.app.llm_service:
                self.app.llm_service.sync_tools()
            self.terminal_ui.print_message(f"✅ Servidor '{name}' guardado y conectado.", style="green")

        elif action == "add_sse":
            name = await self.terminal_ui.ask_input_async(
                title="Nuevo Servidor MCP (SSE)",
                text="Identificador único (ej: mi-servidor):"
            )
            if not name:
                return
            url = await self.terminal_ui.ask_input_async(
                title="URL de SSE",
                text="URL del servidor SSE (ej: http://localhost:8000/sse):"
            )
            if not url:
                return
            conf = {
                "transport": "sse",
                "url": url,
                "disabled": False
            }
            cm.set_mcp_server(name, conf)
            await manager.reload()
            if self.app.llm_service:
                self.app.llm_service.sync_tools()
            self.terminal_ui.print_message(f"✅ Servidor SSE '{name}' guardado y conectado.", style="green")

        elif action == "toggle":
            servers = cm.get_mcp_servers()
            if not servers:
                self.terminal_ui.print_message("⚠️ No hay servidores configurados.", style="yellow")
                return
            server_opts = [
                (name, f"{name} ({'deshabilitado' if conf.get('disabled') else 'habilitado'})")
                for name, conf in servers.items()
            ]
            sel = await self.terminal_ui.ask_radiolist_async(
                title="Alternar Servidor MCP",
                text="Selecciona el servidor para alternar:",
                values=server_opts
            )
            if sel:
                conf = servers[sel]
                conf["disabled"] = not conf.get("disabled", False)
                cm.set_mcp_server(sel, conf)
                await manager.reload()
                if self.app.llm_service:
                    self.app.llm_service.sync_tools()
                st_str = "deshabilitado" if conf["disabled"] else "habilitado"
                self.terminal_ui.print_message(f"✅ Servidor '{sel}' ahora está {st_str}.", style="green")

        elif action == "test":
            servers = cm.get_mcp_servers()
            if not servers:
                self.terminal_ui.print_message("⚠️ No hay servidores configurados.", style="yellow")
                return
            server_opts = [(name, name) for name in servers.keys()]
            sel = await self.terminal_ui.ask_radiolist_async(
                title="Probar Conexión MCP",
                text="Selecciona el servidor a probar:",
                values=server_opts
            )
            if sel:
                self.terminal_ui.print_message(f"🧪 Probando conexión con '{sel}'...", style="cyan")
                res = await manager.test_connection(servers[sel])
                if res.get("status") == "ok":
                    tools = res.get("tools", [])
                    await self.terminal_ui.ask_message_async(
                        title=f"Prueba Exitosa: {sel}",
                        text=f"✅ Conexión establecida con éxito.\nHerramientas detectadas ({len(tools)}):\n" + "\n".join(f"• {t}" for t in tools)
                    )
                else:
                    await self.terminal_ui.ask_message_async(
                        title=f"Fallo en Prueba: {sel}",
                        text=f"❌ Error al conectar:\n{res.get('message', 'Error desconocido')}"
                    )

        elif action == "reload":
            self.terminal_ui.print_message("🔄 Recargando servidores MCP...", style="cyan")
            await manager.reload()
            if self.app.llm_service:
                self.app.llm_service.sync_tools()
            self.terminal_ui.print_message(f"✅ Recarga completa. Herramientas activas: {len(manager.active_tools)}", style="green")

        elif action == "delete":
            servers = cm.get_mcp_servers()
            if not servers:
                self.terminal_ui.print_message("⚠️ No hay servidores configurados.", style="yellow")
                return
            server_opts = [(name, f"Eliminar {name}") for name in servers.keys()]
            sel = await self.terminal_ui.ask_radiolist_async(
                title="Eliminar Servidor MCP",
                text="Selecciona el servidor a eliminar:",
                values=server_opts
            )
            if sel:
                cm.delete_mcp_server(sel)
                await manager.reload()
                if self.app.llm_service:
                    self.app.llm_service.sync_tools()
                self.terminal_ui.print_message(f"🗑️ Servidor '{sel}' eliminado.", style="green")

    async def _handle_help(self):
        """Muestra menú de ayuda con comandos disponibles."""
        help_text = (
            "[bold cyan]Comandos de Configuración:[/bold cyan]\n"
            "  /models   : Cambiar modelo del agente central\n"
            "  /provider : Cambiar proveedor de LLM\n"
            "  /keys     : Configurar API Keys en el servidor\n"
            "  /mcp      : Administrar servidores y herramientas MCP\n"
            "  /theme    : Cambiar tema visual de la TUI\n"
            "  /reset    : Reiniciar la conversación\n"
            "  /undo     : Deshacer última interacción\n"
            "\n"
            "[dim]Nota: Estos comandos configuran el servidor central.[/dim]"
        )
        await self.terminal_ui.ask_message_async(title="Ayuda KogniTerm", text=help_text)
