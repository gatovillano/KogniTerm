import sys
import asyncio
import os
import threading
from .security import scrub_secrets, mask_url_credentials
from kogniterm.core.llm_service import LLMService
from kogniterm.core.insights import KogniInsightsEngine
from kogniterm.core.agents.bash_agent import AgentState, get_system_message
from kogniterm.terminal.terminal_ui import TerminalUI
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, HumanMessage
from rich.panel import Panel
from rich.markdown import Markdown
from rich.padding import Padding
from rich.table import Table # Importar Table
import json
from kogniterm.terminal.visual_components import (
    create_thought_bubble, 
    create_tool_output_panel,
    create_terminal_output_panel
)
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
        Processes meta-commands like /exit, /reset, /undo, /help, /compress.
        Returns True if a meta-command was processed, False otherwise.
        """
        if not user_input or not isinstance(user_input, str):
            return False

        # Si empieza por %, es un meta-comando. Si no lo procesamos abajo,
        # retornamos True al final para que NO se registre en el log.
        is_meta = user_input.strip().startswith('/')

        if user_input.lower().strip() in ['/exit', 'exit', 'quit', '/quit']:
            if hasattr(self.kogniterm_app, 'exit'):
                self.kogniterm_app.exit()
                return True
            sys.exit()

        if user_input.lower().strip() == '/reset':
            self.agent_state.reset() # Reiniciar el estado
            # También reiniciamos el historial de llm_service al resetear la conversación
            self.llm_service.conversation_history = []
            # IMPORTANT! Re-add get_system_message(self.llm_service) after reset
            self.llm_service.conversation_history.append(get_system_message(self.llm_service))
            # Guardar historial CON el get_system_message(self.llm_service)
            self.llm_service._save_history(self.llm_service.conversation_history)
            # Sincronizar agent_state.messages con el historial
            self.agent_state.messages = self.llm_service.conversation_history.copy()
            
            # Clear chat screen
            if hasattr(self.terminal_ui, "clear_chat"):
                self.terminal_ui.clear_chat()
            else:
                # Try to clear console and refresh theme to avoid rendering glitches
                try:
                    self.terminal_ui.console.clear()
                except Exception:
                    pass
                # Recreate console (if applicable) to reapply Rich options
                try:
                    self.terminal_ui.refresh_theme()
                except Exception:
                    pass
                # Finally print banner again
                self.terminal_ui.print_welcome_banner()
            self.terminal_ui.print_message(f"Conversation reset.", style="green")
            if hasattr(self.kogniterm_app, "session_manager") and self.kogniterm_app.session_manager:
                self.kogniterm_app.session_manager.current_session_name = None
            return True

        if user_input.lower().strip() == '/undo':
            if len(self.agent_state.messages) >= 3:
                self.agent_state.messages.pop() # Remove AI response
                self.agent_state.messages.pop() # Remove user input
                self.terminal_ui.print_message("Last interaction undone.", style="green")
            else:
                self.terminal_ui.print_message("Nothing to undo.", style="yellow")
            return True
        
        if user_input.lower().strip().startswith('/init'):
            # Si estamos en la aplicación TUI (Textual), delegamos la indexación al worker con barra inferior
            # y arrancamos una sesión conversacional para que el agente haga la investigación en tiempo real.
            if hasattr(self, 'kogniterm_app') and self.kogniterm_app:
                self.terminal_ui.print_message("🚀 Iniciando indexación de vectores en segundo plano con la barra inferior...")
                try:
                    self.kogniterm_app._start_indexing()
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ No se pudo iniciar la barra de progreso de indexación: {e}", style="red")
                
                # Iniciar la investigación conversacional del BashAgent en tiempo real
                self.terminal_ui.print_message("🤖 Iniciando proceso conversacional con el BashAgent para investigar el proyecto...", style="yellow")
                
                prompt = (
                    "Inicia una investigación local del proyecto. Revisa la estructura de directorios, "
                    "los archivos clave y el README.md. Luego, utiliza la herramienta `memory_init` "
                    "y tus capacidades de edición para escribir los hallazgos en `.kogniterm/llm_context.md`. "
                    "Describe detalladamente el propósito, la arquitectura, los comandos y las convenciones del proyecto.\n\n"
                    "Por favor, ve explicando paso a paso en el chat lo que vas descubriendo e investigando."
                )
                
                try:
                    self.kogniterm_app.process_agent_request(prompt)
                except Exception as e:
                    self.terminal_ui.print_message(f"❌ Error al iniciar la investigación conversacional: {e}", style="red")
                return True

            command_parts = user_input.strip().split(' ', 1)
            files_to_include = None
            force = False
            
            if len(command_parts) > 1:
                args_str = command_parts[1].strip()
                if args_str.startswith('-f') or args_str.startswith('--force'):
                    force = True
                    remaining = args_str.split(' ', 1)
                    if len(remaining) > 1:
                        args_str = remaining[1].strip()
                    else:
                        args_str = ""
                
                if args_str:
                    files_to_include = [f.strip() for f in args_str.split(',') if f.strip()]
            
            self.terminal_ui.print_message("Initializing workspace context... ⏳", style="yellow")
            
            # 1. Investigar localmente y crear/actualizar llm_context.md
            from kogniterm.core.context.project_memory_builder import ProjectMemoryBuilder
            workspace_directory = os.getcwd()
            builder = ProjectMemoryBuilder(workspace_directory)
            context_path = os.path.join(workspace_directory, ".kogniterm", "llm_context.md")
            
            should_write = True
            if os.path.exists(context_path) and not force:
                self.terminal_ui.print_message("ℹ️  .kogniterm/llm_context.md already exists. Skipping memory rebuild (use '/init -f' to overwrite).", style="yellow")
                should_write = False
                
            if should_write:
                self.terminal_ui.print_message("📝 Performing local investigation to build contextual memory...", style="yellow")
                try:
                    content = builder.build_markdown(llm_service=self.llm_service)
                    builder.write_memory_file(content)
                    self.terminal_ui.print_message("✅ Project memory created/updated at .kogniterm/llm_context.md", style="green")
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️  Error building contextual memory: {e}", style="red")
            
            # 2. Ejecutar indexación de la base de código para RAG
            self.terminal_ui.print_message("🔍 Indexing repository into Vector DB for code search...", style="yellow")
            from kogniterm.core.context.codebase_indexer import CodebaseIndexer
            from kogniterm.core.context.vector_db_manager import VectorDBManager
            
            vector_db = None
            try:
                indexer = CodebaseIndexer(workspace_directory)
                vector_db = VectorDBManager(workspace_directory)
                
                def cb(current, total, desc):
                    step = max(1, total // 5)
                    if current == 1 or current == total or current % step == 0:
                        self.terminal_ui.print_message(f"  [{current}/{total}] {desc}...", style="cyan")

                chunks = await indexer.index_project(workspace_directory, show_progress=False, progress_callback=cb)
                
                if chunks:
                    self.terminal_ui.print_message(f"✅ Generated {len(chunks)} code chunks. Storing in Vector DB...", style="cyan")
                    vector_db.clear_collection()
                    vector_db.add_chunks(chunks)
                    self.terminal_ui.print_message("✨ Vector DB indexing complete!", style="green")
                else:
                    self.terminal_ui.print_message("⚠️  No chunks generated for vector database indexing.", style="yellow")
            except Exception as e:
                self.terminal_ui.print_message(f"❌ Error during codebase indexing: {e}", style="red")
            finally:
                if vector_db:
                    vector_db.close()
            
            # 3. Inicializar el contexto de trabajo en memoria
            try:
                self.llm_service.initialize_workspace_context(files_to_include=files_to_include)
                self.terminal_ui.print_message("Workspace context initialized successfully. ✨", style="green")
            except Exception as e:
                self.terminal_ui.print_message(f"Error initializing workspace context: {e} ❌", style="red")
                
            return True
            
        if user_input.lower().strip().startswith('/mouse'):
            if hasattr(self, 'kogniterm_app') and hasattr(self.kogniterm_app, 'action_toggle_mouse'):
                self.kogniterm_app.action_toggle_mouse()
            else:
                self.terminal_ui.print_message("The /mouse command is only available in the TUI interface.", style="yellow")
            return True
            
        if user_input.lower().strip().startswith('/theme'):
            parts = user_input.strip().split()
            theme_name = None
            if len(parts) > 1:
                theme_name = parts[1].lower()
            else:
                from kogniterm.terminal.themes import _THEMES
                theme_options = [(name, f"Theme {name}") for name in _THEMES.keys()]
                theme_name = await self._show_radiolist(
                    title="🎨 Select Color Theme",
                    text="Choose a theme to customize KogniTerm's appearance:",
                    values=theme_options
                )
                
            if theme_name:
                try:
                    # Apply to TUI if we are in it
                    if hasattr(self, 'kogniterm_app') and hasattr(self.kogniterm_app, 'apply_theme'):
                        self.kogniterm_app.apply_theme(theme_name)
                    else:
                        set_kogniterm_theme(theme_name)
                        self.terminal_ui.print_welcome_banner()
                    
                    # Persist theme globally
                    config_manager = ConfigManager()
                    config_manager.set_global_config("theme", theme_name)
                    
                except ValueError:
                     self.terminal_ui.print_message(f"Theme '{theme_name}' not found.", style="red")
                     self._show_themes_table()
            return True


        if user_input.lower().strip().startswith('/session'):
            parts = user_input.strip().split()
            subcommand = parts[1].lower() if len(parts) > 1 else "list"
            args = parts[2:] if len(parts) > 2 else []

            session_manager = self.kogniterm_app.session_manager

            if subcommand == "list":
                sessions = session_manager.list_sessions()
                if not sessions:
                    self.terminal_ui.print_message("No saved sessions found.", style="yellow")
                else:
                    table = Table(title="Saved Sessions")
                    table.add_column("Name", style="cyan")
                    table.add_column("Type", style="magenta")
                    table.add_column("Modified", style="dim")
                    table.add_column("Messages", justify="right")
                    
                    for s in sessions:
                        session_type = "autosave" if s.get("source") == "history" or s["name"].startswith("autosave_") else "manual"
                        table.add_row(s.get("display_name", s["name"]), session_type, s["modified"], str(s["messages"]))
                    
                    self.terminal_ui.console.print(table)
                    
                    current = session_manager.get_current_session_name()
                    if current:
                        self.terminal_ui.print_message(f"Current session: {current}", style="green")
                    else:
                        self.terminal_ui.print_message("You are in a temporary session (unsaved).", style="dim")

            elif subcommand == "save":
                if not args:
                    # If no name, try using the current one or ask for one
                    current = session_manager.get_current_session_name()
                    if current:
                        name = current
                    else:
                        self.terminal_ui.print_message("Usage: /session save <name>", style="red")
                        return True
                else:
                    name = args[0]
                
                if session_manager.save_session(name, self.llm_service.conversation_history):
                    self.terminal_ui.print_message(f"Session '{name}' saved successfully. ✅", style="green")
                else:
                    self.terminal_ui.print_message(f"Error saving session '{name}'. ❌", style="red")

            elif subcommand == "load":
                if not args:
                    self.terminal_ui.print_message("Usage: /session load <name>", style="red")
                    return True
                name = args[0]
                
                history = session_manager.load_session(name)
                if history:
                    self.llm_service.conversation_history = history
                    self.agent_state.messages = history
                    self.llm_service._save_history(history) # Update active history
                    self.terminal_ui.print_message(f"Session '{name}' loaded. History updated. 🔄", style="green")
                else:
                    self.terminal_ui.print_message(f"Could not load session '{name}'.", style="red")

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
                    self.terminal_ui.print_message(f"New session '{name}' created and started. ✨", style="green")
                else:
                    session_manager.current_session_name = None
                    self.terminal_ui.print_message("New temporary session started. ✨", style="green")

            elif subcommand == "delete":
                if not args:
                    self.terminal_ui.print_message("Usage: /session delete <name>", style="red")
                    return True
                name = args[0]
                if session_manager.delete_session(name):
                    self.terminal_ui.print_message(f"Session '{name}' deleted. 🗑️", style="green")
                else:
                    self.terminal_ui.print_message(f"Error deleting session '{name}'.", style="red")
            
            else:
                self.terminal_ui.print_message("Available subcommands: list, save, load, new, delete", style="yellow")

            return True

        if user_input.lower().strip().startswith('/autosave'):
            """Comando para gestionar versiones versionadas de autoguardos."""
            parts = user_input.strip().split(maxsplit=2)
            subcommand = parts[1].lower() if len(parts) > 1 else "list"
            args = parts[2:] if len(parts) > 2 else []
            
            llm_service = self.llm_service
            
            if subcommand == "list":
                # Listar versiones de autoguardos de la sesión actual
                versions = llm_service.get_autosave_versions()
                if not versions:
                    all_versions = llm_service.get_all_autosave_versions()
                    if all_versions:
                        self.terminal_ui.print_message("No autosaves in current session. Available versions from other sessions:", style="yellow")
                        table = Table(title="📦 All Autosave Versions")
                    else:
                        self.terminal_ui.print_message("No autosave versions found.", style="yellow")
                        return True
                else:
                    self.terminal_ui.print_message(f"Found {len(versions)} autosave version(s) in current session:", style="cyan")
                    all_versions = versions
                    table = Table(title="📦 Autosave Versions (Current Session)")
                
                table.add_column("File", style="cyan", no_wrap=False)
                table.add_column("Messages", justify="right", style="green")
                table.add_column("Modified", style="dim")
                
                for v in all_versions[:20]:  # Mostrar máximo 20 versiones
                    filename = v.get("filename", v.get("path", "unknown"))
                    messages = v.get("message_count", "?")
                    modified = v.get("modified", v.get("timestamp", "?"))[:19]  # Truncar timestamp
                    table.add_row(filename, str(messages), modified)
                
                self.terminal_ui.console.print(table)
                
                stats = llm_service.get_autosave_statistics()
                if stats:
                    self.terminal_ui.print_message(
                        f"📊 Statistics: {stats.get('current_session_versions', 0)} versions in current session, "
                        f"{stats.get('total_versions', 0)} total versions across {stats.get('sessions_count', 0)} session(s).",
                        style="dim"
                    )

            elif subcommand == "restore":
                # Restaurar una versión específica
                all_versions = llm_service.get_all_autosave_versions()
                if not all_versions:
                    self.terminal_ui.print_message("No autosave versions available to restore.", style="yellow")
                    return True
                
                if not args:
                    # Mostrar selector de versiones
                    options = []
                    for i, v in enumerate(all_versions[:10]):
                        filename = v.get("filename", "unknown")
                        modified = v.get("modified", "?")[:19]
                        options.append((str(i), f"{filename} ({modified})"))
                    
                    selected = await self._show_radiolist(
                        title="Restore Autosave",
                        text="Select an autosave version to restore:",
                        values=options
                    )
                    
                    if selected is not None:
                        idx = int(selected)
                        file_path = all_versions[idx].get("path")
                    else:
                        self.terminal_ui.print_message("Restore cancelled.", style="yellow")
                        return True
                else:
                    # Buscar por nombre de archivo
                    target_filename = args[0]
                    matching = [v for v in all_versions if target_filename in v.get("filename", "")]
                    if not matching:
                        self.terminal_ui.print_message(f"No autosave version matching '{target_filename}' found.", style="red")
                        return True
                    file_path = matching[0].get("path")
                
                # Cargar la versión
                history = llm_service.load_autosave_version(file_path)
                if history:
                    llm_service.conversation_history = history
                    self.agent_state.messages = history
                    llm_service._save_history(history)
                    self.terminal_ui.print_message(
                        f"✅ Restored autosave with {len(history)} messages. "
                        f"From: {file_path.split('/')[-1]}",
                        style="green"
                    )
                else:
                    self.terminal_ui.print_message(f"Error loading autosave version.", style="red")

            else:
                help_text = """
Available `/autosave` subcommands:
  • list              : 📋 List all autosave versions (current session + others)
  • restore [file]    : 🔄 Restore a specific autosave version
  • restore           : 🔄 Restore (interactive selector)

Example: /autosave restore autosave_20250515_141530
                """
                self.terminal_ui.print_message(help_text.strip(), style="cyan")

            return True

        if user_input.lower().strip().startswith('/resume'):
            # /resume [name] -> If no name, show recent sessions selector
            parts = user_input.strip().split()
            name = parts[1] if len(parts) > 1 else None
            session_manager = getattr(self.kogniterm_app, 'session_manager', None)
            if not session_manager:
                self.terminal_ui.print_message("Gestor de sesiones no disponible.", style="red")
                return True

            sessions = session_manager.list_sessions()
            if not sessions:
                self.terminal_ui.print_message("No saved sessions to resume.", style="yellow")
                return True

            if not name:
                options = []
                for s in sessions:
                    session_type = "autosave" if s.get("source") == "history" or s["name"].startswith("autosave_") else "manual"
                    label = f"{s.get('display_name', s['name'])} — {s['modified']} ({s['messages']} msgs, {session_type})"
                    options.append((s['name'], label))
                selected = await self._show_radiolist(title="Resume Session", text="Select a session to resume:", values=options)
                if not selected:
                    self.terminal_ui.print_message("Selection canceled.", style="dim")
                    return True
                name = selected

            history = session_manager.load_session(name)
            if history:
                # Replace active history with selected session
                self.llm_service.conversation_history = history
                # Sincronizar agent_state
                self.agent_state.messages = history.copy()
                # Persistir como historial activo (intentar, sin fallar si no funciona)
                try:
                    self.llm_service._save_history(self.llm_service.conversation_history)
                except Exception:
                    pass
                # Mark session as current in SessionManager
                try:
                    session_manager.current_session_name = name
                except Exception:
                    pass

                # Clear UI and notify
                if hasattr(self.terminal_ui, "clear_chat"):
                    self.terminal_ui.clear_chat()
                else:
                    try:
                        self.terminal_ui.console.clear()
                    except Exception:
                        pass

                # Renderizar el historial cargado en la TUI
                self._render_history_in_ui(history)

                self.terminal_ui.print_message(f"Session '{name}' resumed with {len([m for m in history if hasattr(m, 'type') and m.type in ('human', 'ai')])} messages.", style="green")
            else:
                self.terminal_ui.print_message(f"Could not load session '{name}'.", style="red")
            return True

        if user_input.lower().strip() == '/help':
            from prompt_toolkit.shortcuts import radiolist_dialog
            
            help_options = [
                ("/models", "🤖 Change AI Model (Select model from current provider)"),
                ("/reasoning", "🧠 Reasoning Level (low / medium / high)"),
                ("/summarymodel", "📝 Change Summary Model (To compress history)"),
                ("/provider", "🌐 Change LLM Provider (OpenRouter, Google, OpenAI, Anthropic, Ollama Cloud, Antigravity)"),
                ("/agy-login", "🛸 Google Antigravity Login (Session authentication without API Keys)"),
                ("/keys", "🔑 Manage API Keys (Configure provider keys)"),
                ("/embeddings", "🧠 Configure Embeddings (Local/FastEmbed, Gemini, OpenAI, etc.)"),
                ("/reset", "🔄 Reset Conversation (Clear current memory)"),
                ("/undo", "↩️ Undo (Remove last interaction)"),
                ("/compress [force]", "🗜️ Compress History (Use 'force' if exceeding limits)"),
                ("/theme", "🎨 Change Theme (View list of available themes)"),
                ("/session", "🗂️ Session Management (list, save, load, new, delete)"),
                ("/instructions", "🧾 Agent Instructions (Global / Workspace)"),
                ("/resume", "🔁 Resume Session (Resumes a saved session)"),
                ("/skills", "🧩 Skills disponibles (Lista e invoca skills directamente)"),
                ("/mouse", "🖱️ Toggle Mouse (Enable/Disable native selection)"),
                ("/insights", "📊 Usage Insights (Costs, Tokens, Patterns)"),
                ("/init", "📁 Initialize Context (Index key files)"),
                ("/exit", "🚪 Exit KogniTerm"),
            ]
            
            selected_command = await self._show_radiolist(
                title="KogniTerm Help Menu",
                text="Select a command to execute it or see more information:",
                values=help_options
            )

            if selected_command:
                # Execute direct commands
                if selected_command in ["/models", "/reasoning", "/summarymodel", "/provider", "/keys", "/reset", "/compress", "/undo", "/mouse", "/exit", "/resume", "/instructions", "/skills", "/agy-login"]:
                    # Recursive call to process selected command
                    return await self.process_meta_command(selected_command)
                
                # Comandos que requieren argumentos o interacción especial
                elif selected_command == "/theme":
                    # Running /theme without arguments shows the theme list
                    return await self.process_meta_command("/theme")

                elif selected_command == "/session":
                    self.terminal_ui.print_message("ℹ️  Session Management (/session)", style="bold cyan")
                    self.terminal_ui.print_message("Usage: /session <subcommand> [arguments]", style="blue")
                    self.terminal_ui.print_message("Available subcommands:", style="yellow")
                    self.terminal_ui.print_message("  • list           : 📋 Shows all saved sessions.", style="dim")
                    self.terminal_ui.print_message("  • save <name>    : 💾 Saves current session.", style="dim")
                    self.terminal_ui.print_message("  • load <name>    : 🔄 Loads a previous session.", style="dim")
                    self.terminal_ui.print_message("  • new [name]     : ✨ Starts a new clean session.", style="dim")
                    self.terminal_ui.print_message("  • delete <name>  : 🗑️  Deletes a saved session.", style="dim")
                    self.terminal_ui.print_message("\nExample: /session save my_project", style="italic dim")
                
                elif selected_command == "/init":
                    self.terminal_ui.print_message("ℹ️  Usage: /init [files]", style="blue")
                    self.terminal_ui.print_message("Example: /init README.md,src/main.py", style="dim")
                    self.terminal_ui.print_message("Tip: Use this command to load specific context into memory.", style="dim")
            
            return True

        # Agent instructions management command (workspace or global)
        if user_input.lower().strip().startswith('/instructions'):
            config_manager = ConfigManager()

            options = [
                ("add_project", "➕ Add instruction (Workspace)"),
                ("add_global", "➕ Add instruction (Global)"),
                ("list", "📋 List current instructions"),
                ("remove_project", "🗑️ Remove instruction (Workspace)"),
                ("remove_global", "🗑️ Remove instruction (Global)"),
                ("clear_project", "🧹 Clear all (Workspace)"),
                ("clear_global", "🧹 Clear all (Global)"),
            ]

            selected = await self._show_radiolist(title="Agent Instructions", text="Select an action:", values=options)
            if not selected:
                self.terminal_ui.print_message("Operation canceled.", style="dim")
                return True

            # Helper to load list
            def _get_list(scope: str):
                if scope == 'global':
                    return config_manager.load_global_config().get('agent_instructions', []) or []
                return config_manager.load_project_config().get('agent_instructions', []) or []

            # Helper to save list
            def _save_list(scope: str, lst):
                if scope == 'global':
                    config_manager.set_global_config('agent_instructions', lst)
                else:
                    config_manager.set_project_config('agent_instructions', lst)

            if selected in ('add_project', 'add_global'):
                scope = 'project' if selected == 'add_project' else 'global'
                instr = await self._show_input(title="New Instruction", text=f"Write the instruction for the agent ({scope}):")
                if not instr:
                    self.terminal_ui.print_message("No instruction provided. Canceled.", style="yellow")
                    return True
                lst = _get_list(scope)
                lst.append(instr)
                _save_list(scope, lst)
                self.terminal_ui.print_message(f"Instruction saved in {scope}.", style="green")
                return True

            if selected == 'list':
                global_list = _get_list('global')
                project_list = _get_list('project')
                if not global_list and not project_list:
                    self.terminal_ui.print_message("No instructions configured.", style="yellow")
                    return True
                if project_list:
                    self.terminal_ui.print_message("Instructions (Workspace):", style="bold cyan")
                    for i, itm in enumerate(project_list, 1):
                        self.terminal_ui.print_message(f"  {i}. {itm}", style="dim")
                if global_list:
                    self.terminal_ui.print_message("Instructions (Global):", style="bold magenta")
                    for i, itm in enumerate(global_list, 1):
                        self.terminal_ui.print_message(f"  {i}. {itm}", style="dim")
                return True

            if selected in ('remove_project', 'remove_global'):
                scope = 'project' if selected == 'remove_project' else 'global'
                lst = _get_list(scope)
                if not lst:
                    self.terminal_ui.print_message(f"No instructions in {scope} to remove.", style="yellow")
                    return True
                options = [(str(i), itm) for i, itm in enumerate(lst, 1)]
                chosen = await self._show_radiolist(title="Remove Instruction", text="Select the instruction to remove:", values=options)
                if not chosen:
                    self.terminal_ui.print_message("Operation canceled.", style="dim")
                    return True
                idx = int(chosen) - 1
                removed = lst.pop(idx)
                _save_list(scope, lst)
                self.terminal_ui.print_message(f"Instruction removed: {removed}", style="green")
                return True

            if selected in ('clear_project', 'clear_global'):
                scope = 'project' if selected == 'clear_project' else 'global'
                _save_list(scope, [])
                self.terminal_ui.print_message(f"All instructions from {scope} have been cleared.", style="green")
                return True

            return True

        if user_input.lower().strip().startswith('/compress'):
            force = 'force' in user_input.lower()
            
            # Validar que el historial tenga contenido antes de intentar resumir
            if not self.llm_service.conversation_history:
                self.terminal_ui.print_message("⚠️ Not enough history to compress.", style="yellow")
                return True

            self.terminal_ui.print_message("Summarizing conversation history...", style="yellow")
            if force:
                self.terminal_ui.print_message("⚠️ FORCE mode activated: history will be truncated if exceeding token limits.", style="bold red")
            
            try:
                # Get summary generated by summarize_conversation_history
                summary = self.llm_service.summarize_conversation_history(force_truncate=force)
            except Exception as e:
                self.terminal_ui.print_message(f"Error generating summary: {e}", style="red")
                return True

            # Validar el resumen: error explícito, o string vacío (fallo silencioso del LLM)
            summary_failed = (
                not summary
                or summary.startswith("Error")
                or summary.startswith("Could not")
            )

            if summary_failed:
                error_msg = summary if summary else "Could not generate summary (model returned an empty response)."
                self.terminal_ui.print_message(error_msg, style="red")
                if "RateLimitError" in error_msg or "quota" in error_msg.lower():
                    self.terminal_ui.print_message("\n💡 Tip: Model has reached its quota limit. Try using [bold]/compress force[/bold] to summarize only the most recent part that fits.", style="cyan")
            else:
                # Mostrar el resumen en un panel
                summary_panel = Panel(
                    Markdown(summary),
                    title="[bold green]📊 Compressed History Summary[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                )
                
                # Create a new SystemMessage with the summary
                summary_sys_msg = SystemMessage(content=f"📊 Previous conversation summary (compressed history):\n\n{summary}")
                
                # Get recent messages (last 10)
                recent_messages = self.llm_service.conversation_history[-10:]
                
                # Clean up messages that could break LLM message sequence (repeated SystemMessages or orphaned ToolMessages)
                while recent_messages and isinstance(recent_messages[0], (SystemMessage, ToolMessage)):
                    recent_messages.pop(0)
                
                # Obtener mensaje de sistema base
                base_system_message = get_system_message(self.llm_service)
                
                # NO preservamos el project_context_msg en el historial de mensajes.
                # El servicio LLM (_prepare_payload) ya lo inyecta automáticamente 
                # en el System Message si no está presente, lo cual es más eficiente.
                
                # Nuevo historial: Base + Resumen + Recientes
                new_history = [base_system_message, summary_sys_msg]
                new_history.extend(recent_messages)
                
                self.llm_service.conversation_history = new_history
                # Usar .copy() para que agent_state tenga su propia lista independiente
                self.agent_state.messages = new_history.copy()
                # Persistir el historial comprimido en disco
                self.llm_service._save_history(self.llm_service.conversation_history)
                
                # Show result to user
                if hasattr(self.terminal_ui, "clear_chat"):
                    self.terminal_ui.clear_chat()
                    # In TUI, console.print writes to ChatLogWidget
                    self.terminal_ui.console.print(summary_panel)
                    self.terminal_ui.print_message(f"🗜️ **History compressed successfully.** Kept the last {len(recent_messages)} messages for context.", style="green")
                else:
                    # Classic terminal
                    self.terminal_ui.console.print(summary_panel)
                    self.terminal_ui.console.print(Panel(Markdown(f"✅ **History compressed successfully.** Kept the last {len(recent_messages)} messages."), border_style="green"))
            return True

        if user_input.lower().strip() == '/summarize':
            self.terminal_ui.print_message("🔄 Summarizing history to improve context...", style="yellow")
            
            result = self.llm_service.force_summarize_history()
            
            if "successfully" in result.lower():
                self.terminal_ui.print_message(result, style="green")
                self.terminal_ui.print_message("💡 The agent should now maintain the conversation thread better.", style="cyan")
            else:
                self.terminal_ui.print_message(f"⚠️ {result}", style="yellow")
            
            return True

        if user_input.lower().strip() == '/reasoning':
            current_effort = self.llm_service.generation_params.get("reasoning_effort", "medium")
            values = [
                ("low", "Low (fast, less reasoning)"),
                ("medium", "Medium (balanced)"),
                ("high", "High (deeper, may take longer)"),
            ]

            selected_effort = await self._show_radiolist(
                title="Reasoning Level",
                text=f"Current level: {current_effort}\n\nSelect reasoning effort for compatible models:",
                values=values,
                default=current_effort if current_effort in {"low", "medium", "high"} else "medium",
            )

            if not selected_effort:
                self.terminal_ui.print_message("Configuration canceled.", style="dim")
                return True

            self.llm_service.generation_params["reasoning_effort"] = selected_effort
            os.environ["KOGNITERM_REASONING_EFFORT"] = selected_effort

            config_manager = ConfigManager()
            config_manager.set_global_config("reasoning_effort", selected_effort)

            self.terminal_ui.print_message(
                f"✅ Reasoning level updated to: {selected_effort}",
                style="green"
            )
            self.terminal_ui.print_message(
                "ℹ️ Will apply to the next response and is persisted in global config.",
                style="dim"
            )
            return True

        if user_input.lower().strip() == '/models':
            from prompt_toolkit.shortcuts import radiolist_dialog
            import httpx
            import json

            # Función auxiliar para obtener modelos de Google
            async def _fetch_google_models():
                try:
                    google_key = os.environ.get("GOOGLE_API_KEY")
                    if not google_key:
                        self.terminal_ui.print_message("⚠️ GOOGLE_API_KEY not found in environment.", style="yellow")
                        return []
                    
                    self.terminal_ui.print_message("⏳ Fetching updated models from Google AI...", style="dim")
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
                                    
                                    # Add version or capability info if relevant
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
                            self.terminal_ui.print_message(f"⚠️ Google API Error: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Error connecting with Google: {e}", style="red")
                    return []

            # Helper function to fetch OpenRouter models
            async def _fetch_openrouter_models():
                try:
                    self.terminal_ui.print_message("⏳ Fetching models list from OpenRouter...", style="dim")
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
                            self.terminal_ui.print_message(f"⚠️ Error fetching OpenRouter models: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Exception connecting to OpenRouter: {e}", style="red")
                    return []

            # Helper function to fetch Ollama Cloud models
            async def _fetch_ollama_cloud_models():
                try:
                    self.terminal_ui.print_message("⏳ Fetching models list from Ollama Cloud...", style="dim")
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
                                self.terminal_ui.print_message("⚠️ Unexpected response from Ollama Cloud: 'models' key not found", style="yellow")
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
                            self.terminal_ui.print_message(f"⚠️ Error fetching Ollama Cloud models: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Exception connecting to Ollama Cloud: {e}", style="red")
                    return []

            # Función auxiliar para obtener modelos de KiloCode Gateway
            async def _fetch_kilocode_models():
                try:
                    api_key = os.getenv("KILOCODE_API_KEY")
                    if not api_key:
                        self.terminal_ui.print_message("⚠️ No se encontró KILOCODE_API_KEY en el entorno.", style="yellow")
                        return []

                    self.terminal_ui.print_message("⏳ Fetching models list from KiloCode Gateway...", style="dim")
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
                            self.terminal_ui.print_message(f"⚠️ Error fetching KiloCode models: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Exception connecting to KiloCode Gateway: {e}", style="red")
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
                    # Show routes we're going to try
                    self.terminal_ui.print_message(f"⏳ Fetching Ollama Local models at {candidates[0]} (trying alternatives)...", style="dim")
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
                            self.terminal_ui.print_message("⚠️ Could not connect to Ollama Local on expected routes.", style="yellow")
                            return []
                        if response.status_code == 200:
                            data = response.json()
                            models = []
                            # Accept various response formats: {'models': [...]}, {'data': [...]}, or a list
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
                            self.terminal_ui.print_message(f"⚠️ Error fetching models from Ollama Local: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Excepción al conectar con Ollama Local: {e}", style="red")
                    return []

            current_model = self.llm_service.model_name
            
            # Detectar proveedor actual
            current_provider = "unknown"
            if current_model.startswith("openrouter/"):
                current_provider = "openrouter"
            elif current_model.startswith("antigravity/"):
                current_provider = "antigravity"
            elif current_model.startswith("gemini/"):
                current_provider = "google"
            elif current_model.startswith("ollama/"):
                # Distinguir entre local y cloud según variables de entorno y configuración explícita.
                api_base = os.environ.get("OLLAMA_API_BASE")
                cloud_base = os.environ.get("OLLAMA_CLOUD_API_BASE", "https://ollama.com/v1")
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
                        # But if no cloud key, the only one left is local.
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
            elif current_provider == "antigravity":
                from kogniterm.core.antigravity_client import AntigravityClient
                self.terminal_ui.print_message("⏳ Cargando lista de modelos desde Google Antigravity...", style="dim")
                target_list = AntigravityClient.fetch_available_models()
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
                # If no models, show only a message, do not fallback to OpenRouter
                if not target_list:
                    self.terminal_ui.print_message("⚠️ No models found in Ollama Cloud. Check your API Key or access.", style="yellow")
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
                title=f"Select AI Model ({len(values)} available)",
                text=f"Current model: {current_model}\nProvider: {current_provider.capitalize()}\n\nType to search/filter in the list:",
                values=values,
                default=current_model if any(m[0] == current_model for m in values) else None
            )

            if selected_model:
                if selected_model != current_model:
                    self.terminal_ui.print_message(f"Changing model to: {selected_model}...", style="yellow")
                    try:
                        # Extraer el proveedor del modelo (ej: "openrouter" de "openrouter/google/gemini-...")
                        model_prefix = selected_model.split('/')[0] if '/' in selected_model else None
                        
                        self.llm_service.set_model(selected_model)
                        
                        # Actualizar proveedor preferido en MultiProviderManager
                        from kogniterm.core.multi_provider_manager import set_preferred_provider
                        if model_prefix:
                            set_preferred_provider(model_prefix)
                        
                        # Persistir en .env de forma inteligente según el proveedor
                        if DOTENV_AVAILABLE:
                            dotenv_path = find_dotenv()
                            if dotenv_path:
                                if selected_model.startswith("gemini/"):
                                    # Para Google AI Studio
                                    gemini_pure_name = selected_model.replace("gemini/", "")
                                    set_key(dotenv_path, "GEMINI_MODEL", gemini_pure_name)
                                    os.environ["GEMINI_MODEL"] = gemini_pure_name
                                    # ALWAYS set LITELLM_MODEL for consistency
                                    set_key(dotenv_path, "LITELLM_MODEL", selected_model)
                                    os.environ["LITELLM_MODEL"] = selected_model
                                else:
                                    # Para otros proveedores (OpenRouter, OpenAI, etc.)
                                    set_key(dotenv_path, "LITELLM_MODEL", selected_model)
                                    os.environ["LITELLM_MODEL"] = selected_model
                                    # Clear GEMINI_MODEL
                                    unset_key(dotenv_path, "GEMINI_MODEL")
                                    if "GEMINI_MODEL" in os.environ: del os.environ["GEMINI_MODEL"]
                        
                        # Persistir el cambio globalmente en el config manager
                        config_manager = ConfigManager()
                        config_manager.set_global_config("default_model", selected_model)
                        
                        self.terminal_ui.print_message(f"✅ Model successfully changed to: {selected_model}", style="green")
                        # Actualizar footer si estamos en TUI
                        if hasattr(self.kogniterm_app, "update_status_footer"):
                            self.kogniterm_app.update_status_footer(selected_model)
                        self.terminal_ui.print_message(f"ℹ️  Configuration persisted in .env ({'GEMINI_MODEL' if selected_model.startswith('gemini/') else 'LITELLM_MODEL'}).", style="dim")
                        self.terminal_ui.print_message(f"ℹ️  Configuration saved as default.", style="dim")
                    except Exception as e:
                        self.terminal_ui.print_message(f"❌ Error changing model: {e}", style="red")
                else:
                    self.terminal_ui.print_message("Model not changed (identical selection).", style="dim")
            
            return True

        if user_input.lower().strip() == '/summarymodel':
            """Allows changing the model used for summarizing/compressing history."""
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
                    
                    self.terminal_ui.print_message("⏳ Fetching updated models from Google AI...", style="dim")
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
                    self.terminal_ui.print_message("⏳ Fetching models list from OpenRouter...", style="dim")
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
                            self.terminal_ui.print_message(f"⚠️ Error fetching models from OpenRouter: {response.status_code}", style="yellow")
                            return []
                except Exception as e:
                    self.terminal_ui.print_message(f"⚠️ Error al conectar con OpenRouter: {e}", style="red")
                    return []

            async def _fetch_ollama_cloud_models():
                try:
                    self.terminal_ui.print_message("⏳ Fetching models from Ollama Cloud...", style="dim")
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
            values = [(current_model, f"Use main model ({current_model}) [Recommended]")]
            for model_id, model_label in target_list:
                if model_id != current_model:
                    values.append((model_id, model_label))
            
            # También agregar opción de Gemini 1.5 Flash como fallback gratuito
            if current_model != "gemini/gemini-1.5-flash":
                values.append(("gemini/gemini-1.5-flash", "Gemini 1.5 Flash (Free, fast)"))
            
            selected_model = await self._show_radiolist(
                title="Select Summary Model",
                text=f"Current summary model: {current_summary_model}\nMain model: {current_model}\n\nThis model is used to compress history with /compress:",
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
                        
                        self.terminal_ui.print_message(f"✅ Summary model changed to: {selected_model}", style="green")
                        self.terminal_ui.print_message(f"ℹ️  This model will be used to compress history with /compress", style="dim")
                    except Exception as e:
                        self.terminal_ui.print_message(f"❌ Error changing summary model: {e}", style="red")
                else:
                    self.terminal_ui.print_message("Summary model not changed (identical selection).", style="dim")
            
            return True

        if user_input.lower().strip() == '/provider':
            from prompt_toolkit.shortcuts import radiolist_dialog

            providers = [
                ("openrouter", "🌐 OpenRouter (Access to multiple models)"),
                ("google", "🤖 Google AI (Gemini nativo)"),
                ("openai", "🧠 OpenAI (GPT-4, GPT-3.5)"),
                ("anthropic", "🎭 Anthropic (Claude)"),
                ("ollama", "🦙 Ollama Local (servidor local)",),
                ("ollama_cloud", "☁️  Ollama Cloud (Ollama Models)"),
                ("kilocode", "⚡ KiloCode Gateway (Routing inteligente)"),
                ("antigravity", "🛸 Google Antigravity (Dynamic Session OAuth2)"),
            ]

            selected_provider = await self._show_radiolist(
                title="Select LLM Provider",
                text="Select the provider you wish to use. This will update your default configuration:",
                values=providers
            )

            if selected_provider:
                if selected_provider == "antigravity":
                    from kogniterm.core.antigravity_client import AntigravityClient
                    if not AntigravityClient.is_logged_in():
                        self.terminal_ui.print_message("⚠️ No hay sesión activa de Antigravity. Iniciando inicio de sesión...", style="yellow")
                        success = await self._process_agy_login()
                        if not success:
                            self.terminal_ui.print_message("❌ Inicio de sesión cancelado o fallido. No se cambió el proveedor.", style="red")
                            return True

                self.terminal_ui.print_message(f"Changing provider to: {selected_provider.capitalize()}...", style="yellow")
                # Definir modelo por defecto para cada proveedor
                default_models = {
                    "openrouter": "openrouter/google/gemini-2.0-flash-exp:free",
                    "google": "gemini/gemini-1.5-flash",
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-3-5-sonnet-20240620",
                    "ollama": "ollama/llama3",
                    "ollama_cloud": "ollama/llama3",
                    "kilocode": "kilocode/kilo/auto",
                    "antigravity": "antigravity/gemini-3-flash",
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
                        # Enmascarar URL si contiene credenciales
                        masked_url = mask_url_credentials(ollama_url)
                            
                        self.terminal_ui.print_message(f"🔗 URL de Ollama Local configurada: {masked_url}", style="dim")
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
                    # Actualizar proveedor preferido en MultiProviderManager
                    from kogniterm.core.multi_provider_manager import set_preferred_provider
                    set_preferred_provider(selected_provider)
                    # Persistir en .env si es posible
                    if DOTENV_AVAILABLE:
                        dotenv_path = find_dotenv()
                        if dotenv_path:
                            set_key(dotenv_path, "LITELLM_MODEL", new_model)
                    # Persistir en ConfigManager
                    config_manager = ConfigManager()
                    config_manager.set_global_config("default_model", new_model)
                    self.terminal_ui.print_message(f"✅ Provider changed to {selected_provider.capitalize()}.", style="green")
                    # Actualizar footer si estamos en TUI
                    if hasattr(self.kogniterm_app, "update_status_footer"):
                        self.kogniterm_app.update_status_footer(new_model)
                    self.terminal_ui.print_message(f"🤖 Default model set: {new_model}", style="dim")
                    self.terminal_ui.print_message("ℹ️  You can change the specific model with /models", style="italic dim")
                except Exception as e:
                    self.terminal_ui.print_message(f"❌ Error changing provider: {e}", style="red")
            
            return True

        if user_input.lower().strip() == '/agy-login':
            await self._process_agy_login()
            return True

        if user_input.lower().strip() == '/keys':
            await self._manage_keys_interactive()
            return True

        if user_input.lower().strip().startswith('/embeddings'):
            await self._manage_embeddings_interactive()
            return True
        if user_input.lower().strip().startswith('/insights'):
            await self._process_insights_command(user_input)
            return True

        # ─────────────────────── SKILL COMMANDS ───────────────────────
        # /skills → listar todas las skills disponibles
        if user_input.lower().strip() in ('/skills', '/skill'):
            await self._list_skills_command()
            return True

        # /skill_name [args_json | key=value ...] → invocar skill directamente
        if is_meta and hasattr(self.llm_service, 'skill_manager'):
            slash_cmd = user_input.strip()
            cmd_parts = slash_cmd.split(None, 1)
            skill_cmd = cmd_parts[0].lstrip('/')  # ej. "task_tracker"
            skill_args_raw = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

            tool = self.llm_service.get_tool(skill_cmd)
            if tool is not None:
                await self._invoke_skill_command(skill_cmd, tool, skill_args_raw)
                return True

        return is_meta

    async def _list_skills_command(self):
        """Muestra una tabla con todas las skills disponibles en el sistema."""
        import json
        sm = getattr(self.llm_service, 'skill_manager', None)
        if not sm:
            self.terminal_ui.print_message("⚠️ SkillManager no disponible.", style="yellow")
            return

        skills_info = sm.list_skills()
        if not skills_info:
            self.terminal_ui.print_message("No hay skills registradas. Usa `skill_factory` para crear una.", style="yellow")
            return

        table = Table(title="🧩 Skills Disponibles en KogniTerm")
        table.add_column("Skill", style="cyan", no_wrap=True)
        table.add_column("Estado", justify="center")
        table.add_column("Herramientas", justify="right")
        table.add_column("Categoría", style="dim")
        table.add_column("Descripción")

        for s in sorted(skills_info, key=lambda x: x['name']):
            status = "[green]✅ Cargada[/green]" if s['loaded'] else "[yellow]⏸ No cargada[/yellow]"
            desc = (s.get('description') or "")[:60] + ("…" if len(s.get('description', '')) > 60 else "")
            table.add_row(
                f"/{s['name']}",
                status,
                str(s['tool_count']),
                s.get('category', '—'),
                desc
            )

        self.terminal_ui.console.print(Padding(table, (1, 2)))
        self.terminal_ui.print_message(
            "💡 Invoca una skill directamente: [bold cyan]/nombre_skill[/bold cyan] [dim][args_json opcional][/dim]",
            style="dim"
        )

    async def _invoke_skill_command(self, skill_name: str, tool, args_raw: str):
        """Invoca una skill directamente desde el input del usuario."""
        import json
        from rich.panel import Panel
        from rich.markdown import Markdown

        # Parsear argumentos: JSON o key=value
        tool_args = {}
        if args_raw:
            # Intentar JSON primero
            try:
                parsed = json.loads(args_raw)
                if isinstance(parsed, dict):
                    tool_args = parsed
                else:
                    tool_args = {"input": parsed}
            except json.JSONDecodeError:
                # Intentar key=value simple
                for part in args_raw.split():
                    if '=' in part:
                        k, v = part.split('=', 1)
                        tool_args[k.strip()] = v.strip()
                    else:
                        # Argumento posicional → lo asignamos a 'input' o primer parámetro
                        tool_args['input'] = args_raw
                        break

        sm = getattr(self.llm_service, 'skill_manager', None)
        skill_info = sm.get_skill_info(skill_name) if sm else None
        category = skill_info.get('category', '') if skill_info else ''

        self.terminal_ui.print_message(
            f"🧩 Ejecutando skill [bold cyan]/{skill_name}[/bold cyan]" +
            (f" [dim]({category})[/dim]" if category else "") +
            (f" con args: [dim]{json.dumps(tool_args)}[/dim]" if tool_args else ""),
            style="blue"
        )

        try:
            # Invocar usando el wrapper inject del LLMService
            result = self.llm_service._invoke_tool_with_interrupt(tool, tool_args)
            # Consumir generador si es necesario
            output_parts = []
            if hasattr(result, '__iter__') and not isinstance(result, str):
                for chunk in result:
                    output_parts.append(str(chunk))
                output = ''.join(output_parts)
            else:
                output = str(result)

            # Mostrar resultado en un panel
            self.terminal_ui.console.print(Padding(
                Panel(
                    Markdown(output) if output.strip().startswith('#') or '**' in output else output,
                    title=f"[bold green]✅ Resultado: /{skill_name}[/bold green]",
                    border_style="green",
                    padding=(1, 2)
                ), (1, 2)
            ))

            # Registrar en historial de conversación para que el LLM tenga contexto
            from langchain_core.messages import AIMessage as _AI, ToolMessage as _TM
            tool_id = f"skill_direct_{skill_name}"
            self.agent_state.messages.append(_TM(content=output, tool_call_id=tool_id))
            self.llm_service._save_history(self.agent_state.messages)

        except Exception as e:
            self.terminal_ui.print_message(f"❌ Error al ejecutar la skill '{skill_name}': {e}", style="red")

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
                    self.terminal_ui.print_message(f"❌ Could not create .env file: {e}", style="red")
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
            
            options.append(("CUSTOM", "➕ Add another variable..."))
            options.append(("BACK", "⬅️  Back"))
            
            selected_key = await self._show_radiolist(
                title="API Keys / Environment Variables Management",
                text=f"File: {os.path.basename(dotenv_path)}\nSelect a key to edit or delete it:",
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

            # Action for selected key
            current_val = os.environ.get(selected_key, "")
            masked_val = f"{current_val[:4]}...{current_val[-4:]}" if len(current_val) > 8 else ("****" if current_val else "Vacío")
            
            action = await self._show_radiolist(
                title=f"Acción para {selected_key}",
                text=f"Variable: {selected_key}\nValor actual: {masked_val}",
                values=[
                    ("SET", "✏️  Set / Change value"),
                    ("DELETE", "🗑️  Delete key"),
                    ("CANCEL", "🚫 Cancel")
                ]
            )
            
            if action == "SET":
                new_val = await self._show_input(
                    title=f"Set {selected_key}",
                    text=f"Introduce el valor para {selected_key}:",
                    password=True
                )
                
                if new_val is not None: # Permitir valor vacío si el usuario pulsa OK
                    new_val = new_val.strip() # Clean up spaces and newlines that can truncate the key
                    
                    # Validación de seguridad: no permitir guardar API Keys en LITELLM_MODEL
                    if selected_key == "LITELLM_MODEL" and new_val.startswith("AIza"):
                        await self._show_message(
                            title="⚠️ Configuration Error",
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
                            title="Success", 
                            text=f"Key {selected_key} saved successfully.\nLength: {key_len} characters.\nPreview: {masked_preview}"
                        )
                    except Exception as e:
                        await self._show_message(title="Error", text=f"Could not save key: {e}")
            
            elif action == "DELETE":
                try:
                    unset_key(dotenv_path, selected_key)
                    if selected_key in os.environ:
                        del os.environ[selected_key]
                    await self._show_message(title="Success", text=f"Key {selected_key} deleted from file and environment.")
                except Exception as e:
                    await self._show_message(title="Error", text=f"Could not delete key: {e}")

    def _render_history_in_ui(self, history: list):
        """Renderiza los mensajes de un historial cargado en la TUI."""
        if not history:
            return
        chat_log = None
        try:
            chat_log = self.terminal_ui.app.chat_log
        except Exception:
            pass

        for msg in history:
            msg_type = getattr(msg, "type", None)
            content = getattr(msg, "content", "")
            
            # 1. Manejar HumanMessage
            if msg_type == "human" or isinstance(msg, HumanMessage):
                if not content: continue
                if chat_log is not None:
                    chat_log.write_user_message(content)
                else:
                    self.terminal_ui.print_message(content, is_user_message=True)
            
            # 2. Manejar AIMessage (puede tener pensamientos y tool_calls)
            elif msg_type == "ai" or isinstance(msg, AIMessage):
                # a) Renderizar Pensamiento (si existe en additional_kwargs)
                reasoning = ""
                if hasattr(msg, "additional_kwargs"):
                    reasoning = msg.additional_kwargs.get("reasoning_content", "")
                
                if reasoning:
                    if chat_log is not None:
                        # ChatLogWidget.write acepta renderizables
                        chat_log.write(create_thought_bubble(reasoning))
                    else:
                        self.terminal_ui.console.print(create_thought_bubble(reasoning))
                
                # b) Renderizar Tool Calls (si existen)
                tool_calls = getattr(msg, "tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        tool_name = tc.get("name", "unknown")
                        args = tc.get("args", {})
                        action_desc = f"Llamando a {tool_name} con {json.dumps(args)}"
                        
                        if chat_log is not None:
                            chat_log.write_tool_notification(tool_name, action_desc)
                        else:
                            from kogniterm.terminal.themes import ColorPalette, Icons
                            from rich.text import Text
                            notify = Text.from_markup(f"{Icons.TOOL} [bold {ColorPalette.SECONDARY}]Acción:[/] {action_desc}")
                            self.terminal_ui.console.print(Padding(notify, (0, 4)))

                # c) Renderizar Contenido de Texto
                if content and isinstance(content, str):
                    if chat_log is not None:
                        chat_log.write_agent_message(content)
                    else:
                        self.terminal_ui.print_message(content)
            
            # 3. Manejar ToolMessage (resultado de ejecución)
            elif msg_type == "tool" or isinstance(msg, ToolMessage):
                if not content: continue
                tool_name = getattr(msg, "name", "tool")
                
                if chat_log is not None:
                    chat_log.write_tool_output(content, tool_name)
                else:
                    # En CLI, usar el panel de visual_components
                    # Detectar si es salida de terminal (bash)
                    if tool_name == "bash" or "comando" in tool_name.lower():
                        panel = create_terminal_output_panel(tool_name, content)
                    else:
                        panel = create_tool_output_panel(tool_name, content)
                    self.terminal_ui.console.print(panel)

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
        self.terminal_ui.print_message(f"Use [bold cyan]/theme <name>[/bold cyan] to change.", style="dim")

    
    async def _process_insights_command(self, user_input: str):
        """Processes the /insights command to show usage analytics."""
        parts = user_input.strip().split()
        days = 30  # Default
        
        if len(parts) > 1:
            try:
                days = int(parts[1])
            except ValueError:
                self.terminal_ui.print_message("Uso incorrecto. Uso: /insights [dias]", style="yellow")
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
                ("PROVIDER", f"🌐 Change Provider (Current: {current_provider})"),
            ]
            
            if current_provider == "fastembed":
                options.append(("MODEL", f"🤖 Change Local Model (Current: {current_model})"))
            
            options.append(("BACK", "⬅️  Back"))

            choice = await self._show_radiolist(
                title="Configuración de Embeddings",
                text=f"Current provider: {current_provider}\nCurrent model: {current_model}\n\nSelect an option:",
                values=options
            )

            if not choice or choice == "BACK":
                break

            if choice == "PROVIDER":
                providers = [
                    ("fastembed", "🚀 Local (FastEmbed) - Autonomous and Fast"),
                    ("gemini", "♊ Google Gemini - Alta Calidad (Requiere API Key)"),
                    ("openai", "🧠 OpenAI - Estándar de la Industria (Requiere API Key)"),
                    ("ollama", "🦙 Ollama - Contenedor Externo (Requiere Ollama corriendo)"),
                ]
                
                new_provider = await self._show_radiolist(
                    title="Select Embedding Provider",
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
                        title="Success",
                        text=f"Proveedor de embeddings cambiado a: {new_provider}\n\nNota: Es posible que necesites reiniciar KogniTerm para aplicar los cambios en el servicio activo."
                    )

            elif choice == "MODEL" and current_provider == "fastembed":
                # Lista de modelos populares en fastembed
                models = [
                    ("BAAI/bge-small-en-v1.5", "BGE Small (En) - Very fast and efficient"),
                    ("BAAI/bge-base-en-v1.5", "BGE Base (En) - Balance entre velocidad y calidad"),
                    ("snowflake/snowflake-arctic-embed-m", "Snowflake Arctic M - Gran rendimiento"),
                    ("sentence-transformers/all-MiniLM-L6-v2", "MiniLM-L6-v2 - Clásico y ligero"),
                ]
                
                new_model = await self._show_radiolist(
                    title="Select Local Model (FastEmbed)",
                    text="Select the model to be downloaded and used locally:",
                    values=models,
                    default=current_model
                )

                if new_model and new_model != current_model:
                    config_manager.set_global_config("embeddings_model", new_model)
                    current_model = new_model
                    await self._show_message(
                        title="Success",
                        text=f"Modelo local cambiado a: {new_model}\n\nNota: La primera vez que lo uses, se descargará automáticamente."
                    )

    async def _process_agy_login(self) -> bool:
        """Procesa el flujo de autenticación de Antigravity de forma interactiva en la terminal."""
        from kogniterm.core.antigravity_client import AntigravityClient, run_login_flow
        
        if AntigravityClient.is_logged_in():
            action = await self._show_radiolist(
                title="Sesión de Antigravity Activa",
                text="Ya tienes una sesión activa de Antigravity. ¿Qué deseas hacer?",
                values=[
                    ("REAUTH", "🔄 Re-autenticar (Crear nueva sesión)"),
                    ("LOGOUT", "🗑️ Cerrar sesión (Eliminar credenciales locales)"),
                    ("CANCEL", "🚫 Cancelar / Mantener sesión actual")
                ]
            )
            if action == "CANCEL" or not action:
                return True
            if action == "LOGOUT":
                token_path = os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token")
                try:
                    if os.path.exists(token_path):
                        os.remove(token_path)
                    self.terminal_ui.print_message("✅ Sesión cerrada y token eliminado.", style="green")
                except Exception as e:
                    self.terminal_ui.print_message(f"❌ Error al eliminar el token: {e}", style="red")
                return True

        self.terminal_ui.print_message("🛸 Iniciando flujo de autenticación para Google Antigravity...", style="cyan bold")
        
        def status_callback(msg):
            self.terminal_ui.print_message(f"🛸 {msg}", style="cyan")

        import asyncio
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, run_login_flow, status_callback)
        
        if success:
            self.terminal_ui.print_message("✨ ¡Autenticación completada exitosamente!", style="green bold")
            return True
        else:
            self.terminal_ui.print_message("❌ La autenticación de Antigravity falló o fue cancelada.", style="red bold")
            return False