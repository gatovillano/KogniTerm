import sys
import os
import asyncio
import logging
import json
import shutil
from typing import List, Optional

from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.utils.logger import setup_logger

logger = logging.getLogger("kogniterm.cli")

class CLIHandler:
    def __init__(self):
        self.config_manager = ConfigManager()

    def handle_config(self, args: List[str]):
        """Handles 'config' commands."""
        if len(args) < 1:
            print("Usage: kogniterm config [project] set <key> <value> | get <key> | list")
            return

        command = args[0]
        
        if command == 'set':
            if len(args) != 3:
                print("Usage: kogniterm config set <key> <value>")
                return
            key, value = args[1], args[2]
            self.config_manager.set_global_config(key, value)
            print(f"✅ Global config '{key}' set to '{value}'")
            
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
                print(f"✅ Project config '{key}' set to '{value}'")
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
            
        else:
            print(f"❌ Unknown config command: {command}")

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

    def handle_models(self, args: List[str]):
        """Handles 'models' commands."""
        if len(args) < 1:
            print("Usage: kogniterm models [use|current] ...")
            return

        command = args[0]

        if command == 'use':
            if len(args) != 2:
                print("Usage: kogniterm models use <model_name>")
                return
            model_name = args[1]
            self.config_manager.set_global_config("default_model", model_name)
            print(f"✅ Default model set to: {model_name}")
            print("ℹ️  Restart KogniTerm to apply changes.")

        elif command == 'current':
            model = self.config_manager.get_config("default_model")
            if model:
                print(f"🤖 Current configured model: {model}")
            else:
                print("🤖 No default model configured (using system environment variables).")
        
        else:
            print(f"❌ Unknown models command: {command}")

    def handle_keys(self, args: List[str]):
        """Handles 'keys' commands."""
        if len(args) < 1:
            print("Usage: kogniterm keys [set|list] ...")
            return
            
        command = args[0]
        valid_providers = ["openrouter", "google", "openai", "anthropic", "litellm", "ollama_cloud"]
        
        if command == 'set':
            if len(args) != 3:
                print(f"Usage: kogniterm keys set <provider> <key>")
                print(f"Providers: {', '.join(valid_providers)}")
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
    elif command == 'index':
        handler.handle_index(args)
        return True
    elif command == 'models':
        handler.handle_models(args)
        return True
    elif command == 'keys':
        handler.handle_keys(args)
        return True
    
    return False
