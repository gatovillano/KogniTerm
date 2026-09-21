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
        """Muestra modal para cambiar el modelo (soporta modo servidor y fallback a modo local)."""
        try:
            # 1. Obtener la configuración actual para saber el proveedor activo
            active_provider = "google"
            server_connected = False
            try:
                config = await get_llm_config()
                active_provider = config.get("provider", "google")
                server_connected = True
            except Exception as e:
                logger.debug(f"Servidor no disponible para get_llm_config ({e}), usando modo local.")
                if self.app.llm_service:
                    model_cur = getattr(self.app.llm_service, "model_name", "")
                    if model_cur.startswith("openrouter/"):
                        active_provider = "openrouter"
                    elif model_cur.startswith("antigravity/"):
                        active_provider = "antigravity"
                    elif model_cur.startswith("gemini/"):
                        active_provider = "google"
                    elif model_cur.startswith("ollama/"):
                        active_provider = "ollama"
                    elif "gpt" in model_cur:
                        active_provider = "openai"
                    elif "claude" in model_cur:
                        active_provider = "anthropic"
                    elif "kilocode" in model_cur:
                        active_provider = "kilocode"
                    elif "inception" in model_cur or "mercury" in model_cur:
                        active_provider = "inception"

            options = []

            # 2. Intentar obtener modelos del servidor si está disponible
            if server_connected:
                try:
                    models_data = await get_available_models()
                    providers = models_data.get("providers", [])
                    for p in providers:
                        p_id = p.get("id", "unknown")
                        p_name = p.get("name", p_id)
                        if p_id == active_provider:
                            models = p.get("models", [])
                            for m in models:
                                options.append((m, f"[{p_name}] {m}"))
                except Exception as e:
                    logger.debug(f"Fallo al consultar modelos desde el servidor: {e}")
                    options = []

            # 3. Fallback a resolución local si no hay opciones desde el servidor
            if not options:
                local_models = []
                p_display_name = active_provider.capitalize()

                if active_provider == "antigravity":
                    p_display_name = "Google Antigravity"
                    try:
                        from kogniterm.core.antigravity_client import AntigravityClient
                        tuples = AntigravityClient.fetch_available_models()
                        for m_id, label in tuples:
                            full_id = m_id if m_id.startswith("antigravity/") else f"antigravity/{m_id}"
                            local_models.append((full_id, label))
                    except Exception as e:
                        logger.warning(f"Error resolviendo modelos locales de Antigravity: {e}")
                        local_models = [
                            ("antigravity/gemini-3-flash", "Gemini 3 Flash (High / Preview)"),
                            ("antigravity/gemini-3-pro", "Gemini 3 Pro (High / Reasoning)"),
                            ("antigravity/gemini-2.5-flash", "Gemini 2.5 Flash"),
                            ("antigravity/gemini-2.5-pro", "Gemini 2.5 Pro"),
                            ("antigravity/gemini-1.5-pro", "Gemini 1.5 Pro"),
                            ("antigravity/gemini-1.5-flash", "Gemini 1.5 Flash"),
                        ]
                elif active_provider == "google":
                    p_display_name = "Google AI (Gemini)"
                    local_models = [
                        ("gemini/gemini-2.0-flash-exp", "Gemini 2.0 Flash Exp"),
                        ("gemini/gemini-1.5-pro", "Gemini 1.5 Pro"),
                        ("gemini/gemini-1.5-flash", "Gemini 1.5 Flash"),
                        ("gemini/gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B"),
                    ]
                elif active_provider == "openai":
                    p_display_name = "OpenAI (GPT)"
                    local_models = [
                        ("gpt-4o", "GPT-4o"),
                        ("gpt-4o-mini", "GPT-4o Mini"),
                        ("gpt-4-turbo", "GPT-4 Turbo"),
                        ("gpt-3.5-turbo", "GPT-3.5 Turbo"),
                    ]
                elif active_provider == "anthropic":
                    p_display_name = "Anthropic (Claude)"
                    local_models = [
                        ("claude-3-5-sonnet-20240620", "Claude 3.5 Sonnet"),
                        ("claude-3-opus-20240229", "Claude 3 Opus"),
                        ("claude-3-haiku-20240307", "Claude 3 Haiku"),
                    ]
                elif active_provider == "openrouter":
                    p_display_name = "OpenRouter"
                    local_models = [
                        ("openrouter/google/gemini-2.0-flash-exp:free", "Gemini 2.0 Flash Exp (Free)"),
                        ("openrouter/anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet"),
                        ("openrouter/openai/gpt-4o", "GPT-4o"),
                    ]
                elif active_provider in ("ollama", "ollama_cloud"):
                    p_display_name = "Ollama"
                    local_models = [
                        ("ollama/llama3", "Llama 3"),
                        ("ollama/mistral", "Mistral"),
                        ("ollama/codellama", "CodeLlama"),
                    ]
                elif active_provider == "kilocode":
                    p_display_name = "KiloCode Gateway"
                    local_models = [
                        ("kilocode/kilo/auto", "Kilo Auto (Smart Routing)"),
                        ("kilocode/anthropic/claude-sonnet-4", "Claude Sonnet 4"),
                        ("kilocode/openai/gpt-4o", "GPT-4o"),
                    ]
                elif active_provider == "inception":
                    p_display_name = "Inception Labs"
                    local_models = [
                        ("inception/mercury-2", "Mercury 2"),
                        ("inception/mercury-2.5", "Mercury 2.5"),
                    ]

                for m_id, label in local_models:
                    options.append((m_id, f"[{p_display_name}] {label}"))
            
            if not options:
                self.terminal_ui.print_message(f"⚠️ No hay modelos disponibles para el proveedor actual: '{active_provider}'", style="yellow")
                return

            selected = await self.terminal_ui.ask_radiolist_async(
                title=f"Seleccionar Modelo ({active_provider.capitalize()})",
                text=f"Selecciona el modelo para el proveedor configurado '{active_provider}':",
                values=options
            )
            
            if selected:
                # Intentar sincronizar con el servidor si está activo
                try:
                    await set_llm_config(model_name=selected)
                except Exception as ex:
                    logger.debug(f"Servidor no disponible para actualizar modelo: {ex}")

                # Actualizar localmente siempre
                if self.app.llm_service:
                    self.app.llm_service.set_model(selected)
                if hasattr(self.app, "agent_interaction_manager") and self.app.agent_interaction_manager:
                    self.app.agent_interaction_manager.set_model(selected)
                self.app.update_status_footer(selected)

                try:
                    from kogniterm.terminal.config_manager import ConfigManager
                    ConfigManager().set_global_config("default_model", selected)
                except Exception:
                    pass

                from kogniterm.core.multi_provider_manager import set_preferred_provider
                model_prefix = selected.split('/')[0] if '/' in selected else None
                if model_prefix:
                    try:
                        set_preferred_provider(model_prefix)
                    except Exception:
                        pass

                self.terminal_ui.print_message(f"✅ Modelo actualizado: {selected}", style="green")
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
            default_models = {
                "google": "gemini/gemini-1.5-flash",
                "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-sonnet-20240620",
                "openrouter": "openrouter/google/gemini-2.0-flash-exp:free",
                "ollama": "ollama/llama3",
                "ollama_cloud": "ollama/llama3",
                "kilocode": "kilocode/kilo/auto",
                "inception": "inception/mercury-2",
                "antigravity": "antigravity/gemini-3-flash",
            }
            fallback_model = default_models.get(selected)
            new_model = fallback_model
            try:
                await set_llm_config(provider=selected)
                config = await get_llm_config()
                if config.get("model"):
                    new_model = config.get("model")
            except Exception as ex:
                logger.debug(f"Servidor no disponible para actualizar proveedor: {ex}")

            if new_model:
                if self.app.llm_service:
                    self.app.llm_service.set_model(new_model)
                if hasattr(self.app, "agent_interaction_manager") and self.app.agent_interaction_manager:
                    self.app.agent_interaction_manager.set_model(new_model)
                self.app.update_status_footer(new_model)
                try:
                    from kogniterm.terminal.config_manager import ConfigManager
                    ConfigManager().set_global_config("default_model", new_model)
                except Exception:
                    pass
                from kogniterm.core.multi_provider_manager import set_preferred_provider
                try:
                    set_preferred_provider(selected)
                except Exception:
                    pass
            self.terminal_ui.print_message(f"✅ Proveedor actualizado: {selected}", style="green")

    async def _handle_keys(self):
        """Muestra modal para configurar API Keys (soporta servidor y guardado local)."""
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
            text="Selecciona el proveedor para configurar su llave:",
            values=keys
        )
        
        if selected_provider:
            key_val = await self.terminal_ui.ask_input_async(
                title=f"API Key para {selected_provider}",
                text="Introduce la llave:",
                password=True
            )
            
            if key_val:
                saved_server = False
                try:
                    await set_llm_config(provider=selected_provider, api_key=key_val)
                    saved_server = True
                except Exception as ex:
                    logger.debug(f"Servidor no disponible para guardar key: {ex}")

                # Guardar siempre en ConfigManager local
                try:
                    from kogniterm.terminal.config_manager import ConfigManager
                    ConfigManager().set_api_key(selected_provider, key_val)
                    # Y en os.environ para la sesión actual
                    env_name = dict(keys).get(selected_provider)
                    if env_name:
                        import os
                        os.environ[env_name] = key_val
                except Exception as ex:
                    logger.warning(f"Error guardando key localmente: {ex}")

                if saved_server:
                    self.terminal_ui.print_message(f"✅ Llave para {selected_provider} guardada (servidor y local).", style="green")
                else:
                    self.terminal_ui.print_message(f"✅ Llave para {selected_provider} guardada localmente.", style="green")

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
