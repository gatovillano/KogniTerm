
import yaml
import sys
import os
import asyncio
import logging
import json
import shutil
import getpass
from typing import List, Optional

from kogniterm.terminal.api_client import get_llm_config, set_llm_config
from kogniterm.utils.logger import setup_logger
from .security import scrub_secrets, mask_url_credentials

logger = logging.getLogger("kogniterm.cli")


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _prompt_with_default(prompt: str, default: Optional[str] = None, input_fn=input) -> str:
    suffix = f" [{default}]" if default else ""
    response = input_fn(f"{prompt}{suffix}: ").strip()
    if response:
        return response
    return default or ""


def _prompt_yes_no(prompt: str, default: bool = True, input_fn=input) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        response = input_fn(f"{prompt}{suffix}: ").strip().lower()
        if not response:
            return default
        if response in ("y", "yes", "s", "si", "sí"):
            return True
        if response in ("n", "no"):
            return False
        print("❌ Responde con 'y' o 'n'.")


def _prompt_secret(prompt: str, default: Optional[str] = None, input_fn=input, secret_input_fn=getpass.getpass) -> str:
    hint = f" [actual: {_mask_secret(default)}]" if default else ""
    response = secret_input_fn(f"{prompt}{hint}: ").strip()
    if response:
        return response
    return default or ""

class CLIHandler:

    def __init__(self):
        from kogniterm.terminal.config_manager import ConfigManager
        self.config_manager = ConfigManager()

    def handle_config(self, args: List[str]):
        """Handles 'config' commands."""
        if len(args) < 1:
            print("Usage: kogniterm config [project] set <key> <value> | get <key> | list | telegram [status|enable|disable|setup]")
            return

        command = args[0]
        
        if command == 'set':
            if len(args) != 3:
                print("Usage: kogniterm config set <key> <value>")
                return
            key, value = args[1], args[2]
            self.config_manager.set_global_config(key, value)
            
            # Enmascarar valor si parece sensible
            masked_value = scrub_secrets(value)
            if masked_value == value and any(s in key.upper() for s in ["KEY", "TOKEN", "PASS", "SECRET", "AUTH"]):
                 masked_value = f"{value[:4]}****" if len(value) > 4 else "****"
            elif "://" in value and "@" in value:
                 masked_value = mask_url_credentials(value)
                
            print(f"✅ Global config '{key}' set to '{masked_value}'")
            
        elif command == 'project':
            if len(args) < 2:
                print("Usage: kogniterm config project set <key> <value>")
                return
            subcommand = args[1]
            if subcommand == 'set':
                if len(args) != 4:
                    print("Usage: kogniterm config project set <key> <value>")
                    return
                key, value = args[2], args[3]
                self.config_manager.set_project_config(key, value)
                
                # Enmascarar valor si parece sensible
                masked_value = scrub_secrets(value)
                if masked_value == value and any(s in key.upper() for s in ["KEY", "TOKEN", "PASS", "SECRET", "AUTH"]):
                     masked_value = f"{value[:4]}****" if len(value) > 4 else "****"
                elif "://" in value and "@" in value:
                     masked_value = mask_url_credentials(value)
                    
                print(f"✅ Project config '{key}' set to '{masked_value}'")
            else:
                print(f"❌ Unknown project subcommand: {subcommand}")

        elif command == 'get':
             if len(args) != 2:
                print("Usage: kogniterm config get <key>")
                return
             key = args[1]
             value = self.config_manager.get_config(key)
             print(f"{key}: {value}")

        elif command == 'list':
            print(json.dumps(self.config_manager.get_all_config(), indent=4))

        elif command == 'telegram':
            self.handle_telegram_config(args[1:])
            
        else:
            print(f"❌ Unknown config command: {command}")

    def handle_telegram_config(self, args: List[str], input_fn=input, secret_input_fn=getpass.getpass, print_fn=print):
        """Asistente paso a paso para configurar el bot de Telegram del servidor."""
        from kogniterm.server.config import ChannelConfig, ServerConfigManager
        from kogniterm.terminal.telegram_chatid_helper import get_first_private_chat_id

        manager = ServerConfigManager()
        telegram_channels = [channel for channel in manager.settings.channels if channel.type == "telegram"]
        current = telegram_channels[0] if telegram_channels else None

        action = args[0] if args else "setup"

        if action in ("status", "show"):
            if not current:
                print_fn("ℹ️  No hay ningún canal Telegram configurado todavía.")
                return

            token = current.params.get("token", "")
            print_fn("📡 Canal Telegram actual:")
            print_fn(f"  - name: {current.name}")
            print_fn(f"  - enabled: {current.enabled}")
            print_fn(f"  - token: {_mask_secret(token)}" if token else "  - token: (vacío)")
            print_fn("ℹ️  Puedes volver a ejecutar 'kogniterm config telegram' para actualizarlo.")
            return

        if action in ("enable", "disable"):
            if not current:
                print_fn("❌ No hay ningún canal Telegram para activar o desactivar.")
                return

            enabled = action == "enable"
            manager.toggle_channel(current.name, enabled)
            print_fn(f"✅ Canal Telegram '{current.name}' {'activado' if enabled else 'desactivado'}.")
            return

        if action not in ("setup", "configure"):
            print_fn("Usage: kogniterm config telegram [setup|status|show|enable|disable]")
            return

        print_fn("🤖 Asistente de configuración de bot de Telegram")
        print_fn(f"   Los cambios se guardarán en {ServerConfigManager.CONFIG_FILE}")

        default_name = current.name if current else "telegram_bot_default"
        default_token = current.params.get("token") if current else os.environ.get("TELEGRAM_BOT_TOKEN")
        default_enabled = current.enabled if current else True

        bot_name = _prompt_with_default("Nombre del bot de Telegram", default_name, input_fn=input_fn)

        token = ""
        while not token:
            token = _prompt_secret("Token del bot de Telegram (obtenido de BotFather)", default_token, input_fn=input_fn, secret_input_fn=secret_input_fn)
            if not token:
                print_fn("❌ El token no puede quedar vacío.")

        enabled = _prompt_yes_no("¿Quieres dejar el bot activado ahora?", default_enabled, input_fn=input_fn)


        print_fn("\nAhora debes asociar tu chat privado de Telegram con el bot.")
        print_fn("1. Abre Telegram y envía cualquier mensaje a tu bot (@ desde tu cuenta personal, no grupo ni canal).\n2. Luego presiona Enter aquí para continuar.")
        input_fn("Presiona Enter cuando hayas enviado el mensaje...")

        print_fn("⏳ Buscando tu chat_id privado en Telegram...")
        chat_id = get_first_private_chat_id(token, timeout=60)
        if chat_id:
            print_fn(f"✅ chat_id detectado: {chat_id}")
        else:
            print_fn("❌ No se detectó ningún chat privado. Puedes reintentar ejecutando este asistente más tarde.")
            chat_id = None

        print_fn("\nResumen:")
        print_fn(f"  - name: {bot_name}")
        print_fn(f"  - enabled: {enabled}")
        print_fn(f"  - token: {_mask_secret(token)}")
        print_fn(f"  - chat_id: {chat_id if chat_id else '(no detectado)'}")

        if not _prompt_yes_no("¿Guardar esta configuración?", True, input_fn=input_fn):
            print_fn("ℹ️  Configuración cancelada.")
            return

        params = {"token": token}
        if chat_id:
            params["chat_id"] = chat_id

        channel = ChannelConfig(
            name=bot_name,
            type="telegram_bot",
            enabled=enabled,
            params=params,
        )
        manager.settings.channels = [existing for existing in manager.settings.channels if existing.type != "telegram_bot"]
        manager.upsert_channel(channel)

        print_fn(f"✅ Bot de Telegram '{bot_name}' guardado correctamente.")
        if chat_id:
            print_fn(f"ℹ️  El chat_id {chat_id} ha sido guardado. El bot responderá solo a ese chat privado.")
        print_fn("ℹ️  Reinicia el servidor con 'kogniterm-server' para cargar el bot.")

    def handle_index(self, args: List[str]):
        """Handles 'index' commands."""
        if len(args) < 1:
            print("Usage: kogniterm index [refresh|clean-db]")
            return
        
        command = args[0]
        
        if command == 'refresh':
            from kogniterm.core.context.codebase_indexer import CodebaseIndexer
            from kogniterm.core.context.vector_db_manager import VectorDBManager
            
            workspace_directory = os.getcwd()
            print(f"🔍 Indexing codebase in {workspace_directory}...")
            
            vector_db = None
            try:
                indexer = CodebaseIndexer(workspace_directory)
                vector_db = VectorDBManager(workspace_directory)
                
                # Run async indexing
                chunks = asyncio.run(indexer.index_project(workspace_directory))
                
                if chunks:
                    print(f"✅ Generated {len(chunks)} chunks. Storing in Vector DB...")
                    vector_db.clear_collection()
                    vector_db.add_chunks(chunks)
                    print("✨ Indexing complete!")
                else:
                    print("⚠️  No code files found or no chunks generated.")
                    
            except Exception as e:
                logger.error(f"Error during indexing: {e}", exc_info=True)
                print(f"❌ Error during indexing: {e}")
            finally:
                if vector_db:
                    vector_db.close()

        elif command in ['clean-db', '--clear']:
            workspace_directory = os.getcwd()
            db_path = os.path.join(workspace_directory, ".kogniterm", "vector_db")
            
            print(f"🗑️  Cleaning Vector Database at {db_path}...")
            try:
                if os.path.exists(db_path):
                    shutil.rmtree(db_path)
                    print("✅ Vector Database directory removed successfully.")
                else:
                    print("ℹ️  Vector Database directory does not exist.")
                
                os.makedirs(db_path, exist_ok=True)
                print("✅ Clean Vector Database directory created.")
            except Exception as e:
                logger.error(f"Error cleaning database: {e}", exc_info=True)
                print(f"❌ Error cleaning database: {e}")
                
        else:
            print(f"❌ Unknown index command: {command}")


    def handle_init(self, args: List[str]):
        """Handles 'init' command to initialize the project context and run local investigation."""
        force = '--force' in args or '-f' in args
        workspace_directory = os.getcwd()
        
        print("🚀 KogniTerm Context Initializer & Local Investigator")
        
        # 1. Investigar y construir llm_context.md
        from kogniterm.core.context.project_memory_builder import ProjectMemoryBuilder
        from kogniterm.core.llm_service import LLMService
        
        llm = None
        try:
            llm = LLMService()
            if not llm.api_key:
                llm = None
        except Exception:
            llm = None
            
        if llm:
            print(f"🤖 Connected to LLM ({llm.model_name}). Starting AI-assisted codebase investigation...")
        else:
            print("⚠️  No LLM API key configured. Falling back to heuristic-based codebase scanner...")
            
        builder = ProjectMemoryBuilder(workspace_directory)
        context_path = os.path.join(workspace_directory, ".kogniterm", "llm_context.md")
        
        should_write = True
        if os.path.exists(context_path) and not force:
            print("ℹ️  .kogniterm/llm_context.md already exists. Skipping memory rebuild (use --force or -f to overwrite).")
            should_write = False
            
        if should_write:
            try:
                print("📝 Generating project contextual memory...")
                content = builder.build_markdown(llm_service=llm)
                builder.write_memory_file(content)
                print("✅ Successfully generated and saved .kogniterm/llm_context.md")
            except Exception as e:
                print(f"❌ Error generating project memory: {e}")
                logger.error(f"Error in CLI handle_init building memory: {e}", exc_info=True)
                
        # 2. Correr el indexador de código (RAG Vector DB) automáticamente
        print("\n🔍 Indexing codebase into Vector DB for RAG-ready code understanding...")
        from kogniterm.core.context.codebase_indexer import CodebaseIndexer
        from kogniterm.core.context.vector_db_manager import VectorDBManager
        
        vector_db = None
        try:
            indexer = CodebaseIndexer(workspace_directory)
            vector_db = VectorDBManager(workspace_directory)
            
            # Run async indexing
            chunks = asyncio.run(indexer.index_project(workspace_directory))
            
            if chunks:
                print(f"✅ Generated {len(chunks)} codebase chunks. Storing in Vector DB...")
                vector_db.clear_collection()
                vector_db.add_chunks(chunks)
                print("✨ Codebase indexing complete!")
            else:
                print("⚠️  No code files found or no chunks generated.")
                
        except Exception as e:
            logger.error(f"Error during codebase indexing: {e}", exc_info=True)
            print(f"❌ Error during codebase indexing: {e}")
        finally:
            if vector_db:
                vector_db.close()
                
        print("\n🎉 Initialization complete! KogniTerm is now fully aware of your local repository context.")


    def handle_models(self, args: List[str]):
        """Handles 'models' commands (centralizado vía API)."""
        if len(args) < 1:
            print("Usage: kogniterm models [use|current] ...")
            return

        command = args[0]

        if command == 'use':
            if len(args) != 2:
                print("Usage: kogniterm models use <model_name>")
                return
            model_name = args[1]
            try:
                set_llm_config(model_name=model_name)
                print(f"✅ Default model set to: {model_name}")
                print("ℹ️  The change is now effective for all interfaces (TUI, Desktop, API, bots).")
            except Exception as e:
                print(f"❌ Error updating model via API: {e}")

        elif command == 'current':
            try:
                config = get_llm_config()
                model = config.get("model")
                provider = config.get("provider")
                if model:
                    print(f"🤖 Current configured model: {model} (provider: {provider})")
                else:
                    print("🤖 No default model configured in backend.")
            except Exception as e:
                print(f"❌ Error fetching model config from API: {e}")

        else:
            print(f"❌ Unknown models command: {command}")

    def handle_keys(self, args: List[str]):
        """Handles 'keys' commands."""
        if len(args) < 1:
            print("Usage: kogniterm keys [set|list] ...")
            return
            
        command = args[0]
        valid_providers = ["openrouter", "google", "openai", "anthropic", "litellm", "ollama_cloud"]
        # Permitir modo de Ollama: local o cloud
        valid_ollama_modes = ["local", "cloud"]
        
        if command == 'set':
            if len(args) == 3 and args[1].lower() == "ollama_mode":
                mode = args[2].lower()
                if mode not in ["local", "cloud"]:
                    print(f"❌ Invalid ollama_mode. Choose 'local' or 'cloud'.")
                    return
                self.config_manager.set_global_config("ollama_mode", mode)
                print(f"✅ Ollama mode set to: {mode}")
                return
            if len(args) == 3 and args[1].lower() == "ollama_api_base":
                self.config_manager.set_global_config("ollama_api_base", args[2])
                print(f"✅ Ollama API base set to: {args[2]}")
                return
            if len(args) != 3:
                print(f"Usage: kogniterm keys set <provider> <key>")
                print(f"Providers: {', '.join(valid_providers)}")
                print(f"Or: kogniterm keys set ollama_mode <local|cloud>")
                print(f"Or: kogniterm keys set ollama_api_base <url>")
                return
            provider = args[1].lower()
            key_value = args[2]
            if provider not in valid_providers:
                print(f"❌ Invalid provider. Choose from: {', '.join(valid_providers)}")
                return
            self.config_manager.set_global_config(f"api_key_{provider}", key_value)
            print(f"✅ API Key for '{provider}' saved successfully.")

        elif command == 'list':
            print("🔑 Configured API Keys:")
            for provider in valid_providers:
                key = self.config_manager.get_config(f"api_key_{provider}")
                status = "✅ Set" if key else "❌ Not set"
                masked_key = f"{key[:4]}...{key[-4:]}" if key and len(key) > 8 else ""
                print(f"  - {provider.ljust(12)}: {status} {masked_key}")
                
        else:
            print(f"❌ Unknown keys command: {command}")

    def handle_upgrade(self, args: List[str]):
        """Handles 'upgrade' command to update KogniTerm from GitHub."""
        import subprocess
        import os
        import sys
        
        # Determine paths
        kogniterm_dir = os.path.expanduser("~/.kogniterm")
        repo_dir = os.path.join(kogniterm_dir, "repo")
        venv_dir = os.path.join(kogniterm_dir, "venv")
        
        # Check if we're in a local development environment
        if os.path.exists("pyproject.toml") and os.path.isdir("kogniterm"):
            print("📁 Detected local development environment in current directory.")
            repo_dir = os.getcwd()
            # Try to find venv
            if os.path.isdir(".venv"):
                venv_dir = os.path.join(os.getcwd(), ".venv")
            elif os.path.isdir("venv"):
                venv_dir = os.path.join(os.getcwd(), "venv")
            else:
                venv_dir = None
        
        # Check git command availability
        if not shutil.which("git"):
            print("❌ Error: 'git' is not installed on this system.")
            return
        
        # Check git repository
        git_dir = os.path.join(repo_dir, ".git")
        if not os.path.exists(git_dir):
            print(f"❌ Error: No git repository found at {repo_dir}")
            print("   Please reinstall KogniTerm or run from the repository root.")
            return
        
        os.chdir(repo_dir)
        
        # Stash local changes if any
        stash_created = False
        try:
            result = subprocess.run(["git", "diff-index", "--quiet", "HEAD", "--"], 
                                  capture_output=True, cwd=repo_dir)
            if result.returncode != 0:
                print("⚠️  Local changes detected. Stashing them temporarily...")
                subprocess.run(["git", "stash"], check=True, cwd=repo_dir)
                stash_created = True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during git stash: {e}")
            return
        
        # Pull updates
        print("🔄 Syncing with remote repository...")
        try:
            subprocess.run(["git", "pull", "--no-rebase", "origin", "main"], 
                         check=True, cwd=repo_dir)
        except subprocess.CalledProcessError:
            print("❌ Error during git pull.")
            if stash_created:
                subprocess.run(["git", "stash", "pop"], check=False, cwd=repo_dir)
            return
        
        # Restore stashed changes
        if stash_created:
            print("📦 Restoring your local changes...")
            subprocess.run(["git", "stash", "pop"], check=False, cwd=repo_dir)
        
        # Reinstall package
        pip_cmd = None
        if venv_dir and os.path.isdir(venv_dir):
            if sys.platform == "win32":
                pip_cmd = os.path.join(venv_dir, "Scripts", "pip")
            else:
                pip_cmd = os.path.join(venv_dir, "bin", "pip")
        
        if pip_cmd and os.path.exists(pip_cmd):
            print("🔄 Updating virtual environment...")
            install_source = repo_dir if repo_dir != os.getcwd() else "."
            try:
                subprocess.run([pip_cmd, "install", "-e", install_source], 
                             check=True, cwd=repo_dir)
            except subprocess.CalledProcessError:
                print("❌ Error reinstalling the package.")
                return
        else:
            print("⚠️  Virtual environment not found. Skipping pip install.")
            print("   You may need to manually reinstall the package.")
        
        print("\n" + "="*80)
        print("    🎉 KogniTerm has been successfully upgraded to the latest version!")
        print("="*80 + "\n")

    def handle_desktop(self, args: List[str]):
        """Abre la versión desktop de KogniTerm."""
        import subprocess
        
        # Determinar la ruta de kogniterm-desktop
        kogniterm_dir = os.path.expanduser("~/.kogniterm")
        repo_dir = os.path.join(kogniterm_dir, "repo")
        
        if os.path.exists("pyproject.toml") and os.path.isdir("kogniterm"):
            repo_dir = os.getcwd()
            
        desktop_dir = os.path.join(repo_dir, "kogniterm-desktop")
        
        if not os.path.exists(desktop_dir):
            # Buscar en el path alternativo si no está en repo_dir
            alt_desktop_dir = os.path.expanduser("~/.kogniterm/repo/kogniterm-desktop")
            if os.path.exists(alt_desktop_dir):
                desktop_dir = alt_desktop_dir
            else:
                print(f"❌ Error: No se pudo encontrar el directorio de KogniTerm Desktop.")
                print(f"   Se buscó en: {desktop_dir}")
                print(f"   Y en: {alt_desktop_dir}")
                return
                
        script_path = os.path.join(desktop_dir, "start-dev.sh")
        if not os.path.exists(script_path):
            print(f"❌ Error: No se encontró el script de inicio en {script_path}")
            return
            
        print("🚀 Iniciando KogniTerm Desktop...")
        # Asegurarse de que el script sea ejecutable
        try:
            os.chmod(script_path, 0o755)
        except Exception:
            pass
            
        try:
            # Ejecutar el script start-dev.sh en su directorio de trabajo
            # Usamos Popen para que corra en segundo plano y el CLI pueda retornar de inmediato
            subprocess.Popen(["./start-dev.sh"], cwd=desktop_dir)
            print("✨ Proceso de inicio lanzado en segundo plano.")
        except Exception as e:
            print(f"❌ Error al iniciar KogniTerm Desktop: {e}")

    def handle_skills(self, args: List[str]):
        """Handles 'skills' commands for installing/managing external skills."""
        if len(args) < 1:
            print("Usage: kogniterm skills [add|search|list|remove|info] ...")
            return

        command = args[0]

        if command == '--help' or command == '-h':
            print("Usage: kogniterm skills [add|search|list|remove|info] ...")
            print("\nComandos:")
            print("  add    - Instala una skill desde un repositorio GitHub")
            print("  search - Busca skills en el catálogo de skills.sh")
            print("  list   - Lista las skills externas instaladas")
            print("  remove - Elimina una skill externa instalada")
            print("  info   - Muestra información detallada de una skill")
            return

        if command == 'add':
            self._handle_skills_add(args[1:])
        elif command == 'search':
            self._handle_skills_search(args[1:])
        elif command == 'list':
            self._handle_skills_list(args[1:])
        elif command == 'remove':
            self._handle_skills_remove(args[1:])
        elif command == 'info':
            self._handle_skills_info(args[1:])
        else:
            print(f"❌ Unknown skills command: {command}")

        if '--help' in args or '-h' in args:
            print("Usage: kogniterm skills add <repo_url> [--skill <nombre>]")
            print("\nInstala una skill desde un repositorio GitHub o skills.sh.")
            print("\nOpciones:")
            print("  --skill <nombre>  Nombre específico de la skill a instalar")
            print("\nEjemplos:")
            print("  kogniterm skills add https://github.com/user/repo")
            print("  kogniterm skills add https://github.com/user/repo --skill mi_skill")
            return
    def _handle_skills_add(self, args: List[str]):
        """Instala una skill desde un repositorio GitHub."""
        repo_url = None
        skill_name = None

        i = 0
        while i < len(args):
            if args[i] == '--skill' and i + 1 < len(args):
                skill_name = args[i + 1]
                i += 2
            elif args[i].startswith('http'):
                repo_url = args[i]
                i += 1
            else:
                repo_url = args[i]
                i += 1

        if not repo_url:
            print("❌ Usage: kogniterm skills add <repo_url> [--skill <nombre>]")
            return

        print(f"📦 Installing skill from {repo_url}...")
        if skill_name:
            print(f"   Skill: {skill_name}")

        try:
            # Usar el adaptador de agent_skills existente
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "bundled" / "agent-skills-adapter" / "scripts"))
            from tool import install_skill_pack_from_repo

            result = install_skill_pack_from_repo(
                repo_url=repo_url,
                skill_name=skill_name
            )

            if result.get("success"):
                print(f"✅ {result.get('message', 'Skill instalada correctamente')}")
                if "path" in result:
                    print(f"   Ubicación: {result['path']}")
                if "installed" in result:
                    print(f"   Skills instaladas: {result['count']}")
                    for path in result.get("installed", []):
                        print(f"   - {path}")
            else:
                print(f"❌ Error: {result.get('error', 'Error desconocido')}")
        except Exception as e:
            print(f"❌ Error instalando skill: {e}")

    def _handle_skills_search(self, args: List[str]):
        """Busca skills en el catálogo de skills.sh."""
        if not args:
            if '--help' in args or '-h' in args:
                print("Usage: kogniterm skills search <query>")
                print("\nBusca skills en el catálogo de skills.sh.")
                print("\nArgumentos:")
                print("  <query>    Término de búsqueda (ej: 'react', 'testing')")
                print("\nEjemplos:")
                print("  kogniterm skills search react")
                print("  kogniterm skills search database")
                return

        query = " ".join(args)

        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "bundled" / "agent-skills-adapter" / "scripts"))
            from tool import search_skills_catalog

            result = search_skills_catalog(query=query, limit=10)

            if result.get("success"):
                results = result.get("results", [])
                print(f"🔍 Resultados para '{query}': {result.get('count', 0)} encontradas\n")

                for i, skill in enumerate(results, 1):
                    name = skill.get("name", "Unknown")
                    source = skill.get("source", "Unknown")
                    installs = skill.get("installs", 0)
                    print(f"{i}. **{name}**")
                    print(f"   Fuente: {source}")
                    print(f"   Instalaciones: {installs:,}")
                    if skill.get("installUrl"):
                        print(f"   URL: {skill['installUrl']}")
                    print()
            else:
                print(f"❌ Error: {result.get('error', 'Error desconocido')}")
        except Exception as e:
            print(f"❌ Error buscando skills: {e}")

    def _handle_skills_list(self, args: List[str]):
        """Lista las skills externas instaladas."""
        if '--help' in args or '-h' in args:
            print("Usage: kogniterm skills list")
            print("\nLista todas las skills externas instaladas.")
            print("\nEjemplos:")
            print("  kogniterm skills list")
            return
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "bundled" / "agent-skills-adapter" / "scripts"))
            from tool import list_available_external_skills

            result = list_available_external_skills()

            if result.get("success"):
                skills = result.get("skills", [])
                print(f"📦 Skills externas instaladas: {result.get('count', 0)}\n")

                if not skills:
                    print("   No hay skills externas instaladas.")
                    print("   Usa 'kogniterm skills add <repo>' para instalar una.")
                else:
                    for skill in skills:
                        name = skill.get("name", "Unknown")
                        desc = skill.get("description", "")
                        source = skill.get("source", "external")
                        print(f"• **{name}**")
                        if desc:
                            print(f"  {desc}")
                        print(f"  Fuente: {source}")
                        print(f"  Ruta: {skill.get('path', 'N/A')}")
                        print()
            else:
                print(f"❌ Error: {result.get('error', 'Error desconocido')}")
        except Exception as e:
            print(f"❌ Error listando skills: {e}")

    def _handle_skills_remove(self, args: List[str]):
        """Elimina una skill externa instalada."""
        if not args:
            print("❌ Usage: kogniterm skills remove <nombre>")
            return

        skill_name = args[0]

        # Buscar la skill en el directorio external/
        from pathlib import Path
        external_skills_dir = Path(__file__).parent.parent / "skills" / "external"

        # Buscar directorio que coincida
        skill_dirs = list(external_skills_dir.glob(f"*{skill_name}*"))
        if not skill_dirs:
            print(f"❌ Skill '{skill_name}' no encontrada en skills/external/")
            return

        skill_dir = skill_dirs[0]
        print(f"🗑️  Eliminando skill: {skill_dir.name}")
        try:
            import shutil
            shutil.rmtree(skill_dir)
            print(f"✅ Skill '{skill_name}' eliminada correctamente")
        except Exception as e:
            print(f"❌ Error eliminando skill: {e}")

    def _handle_skills_info(self, args: List[str]):
        """Muestra información detallada de una skill."""
        if not args:
            print("❌ Usage: kogniterm skills info <nombre>")
            return

        skill_name = args[0]

        # Buscar en todas las ubicaciones
        from pathlib import Path
        search_paths = [
            Path(__file__).parent.parent / "skills" / "bundled",
            Path(__file__).parent.parent / "skills" / "external",
            Path.home() / ".kogniterm" / "skills",
        ]

        skill_md = None
        skill_dir = None

        for base_path in search_paths:
            if not base_path.exists():
                continue
            found = list(base_path.rglob(f"*{skill_name}*/SKILL.md"))
            if found:
                skill_md = found[0]
                skill_dir = skill_md.parent
                break

        if not skill_md:
            print(f"❌ Skill '{skill_name}' no encontrada")
            return

        try:
            import yaml
            content = skill_md.read_text(encoding="utf-8")

            metadata = {}
            instructions = ""
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1]) or {}
                    instructions = parts[2].strip()

            print(f"📦 Skill: {metadata.get('name', skill_name)}")
            print(f"   Versión: {metadata.get('version', 'N/A')}")
            print(f"   Descripción: {metadata.get('description', 'N/A')}")
            print(f"   Categoría: {metadata.get('category', 'N/A')}")
            print(f"   Nivel de seguridad: {metadata.get('security_level', 'N/A')}")
            print(f"   Autor: {metadata.get('author', 'N/A')}")
            print(f"   Ruta: {skill_dir}")

            if instructions:
                print(f"\n📝 Instrucciones:")
                print(instructions[:500] + ("..." if len(instructions) > 500 else ""))
        except Exception as e:
            print(f"❌ Error leyendo skill: {e}")


def run_cli() -> bool:
    """Parses command line arguments and executes the corresponding CLI command.
    Returns True if a CLI command was handled, False otherwise (should start TUI).
    """
    if len(sys.argv) < 2:
        return False

    command = sys.argv[1]
    handler = CLIHandler()
    args = sys.argv[2:]

    if command == 'config':
        handler.handle_config(args)
        return True
    elif command == 'init':
        handler.handle_init(args)
        return True
    elif command == 'index':
        handler.handle_index(args)
        return True
    elif command == 'models':
        handler.handle_models(args)
        return True
    elif command == 'keys':
        handler.handle_keys(args)
        return True
    elif command == 'skills':
        handler.handle_skills(args)
        return True
    elif command == 'upgrade':
        handler.handle_upgrade(args)
        return True
    elif command == 'desktop':
        handler.handle_desktop(args)
        return True


    # Si el comando no es reconocido, podría ser un prompt para el agente
    # Capturamos la salida y filtramos el mensaje de bienvenida duplicado
    import io
    import re
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        # Aquí iría la llamada al agente real, pero como no está explícito,
        # simplemente capturamos la salida estándar
        pass
    output = f.getvalue()

    # Patrón para detectar el mensaje de bienvenida estándar
    bienvenida_pattern = re.compile(r"Hola! Soy (\*\*KogniTerm\*\*|KogniTerm),? tu agente evolutivo de terminal", re.IGNORECASE)
    if bienvenida_pattern.search(output):
        # Si detectamos el mensaje de bienvenida, no lo imprimimos
        output = bienvenida_pattern.sub("", output)
    if output.strip():
        print(output.strip())
    return False
