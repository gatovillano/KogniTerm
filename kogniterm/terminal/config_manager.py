import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Gestor de configuración para KogniTerm.
    - Soporta settings globales (~/.kogniterm/config.json) y por workspace (.kogniterm/config.json).
    - Permite guardar y recuperar credenciales/API keys por provider (multi-workspace, multi-provider).
    - Las settings del proyecto sobrescriben las globales.
    """

    GLOBAL_CONFIG_DIR = Path.home() / ".kogniterm"
    GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"
    PROJECT_CONFIG_DIR = Path(".kogniterm")
    PROJECT_CONFIG_FILE = PROJECT_CONFIG_DIR / "config.json"

    def __init__(self, workspace_dir: Optional[str] = None):
        if not workspace_dir:
            # 1. Intentar obtener de LLMService context vars
            try:
                import sys
                if "kogniterm.core.llm_service" in sys.modules:
                    llm_service_mod = sys.modules["kogniterm.core.llm_service"]
                    if hasattr(llm_service_mod, "LLMService") and hasattr(llm_service_mod.LLMService, "_context_current_workspace_dir"):
                        workspace_dir = llm_service_mod.LLMService._context_current_workspace_dir.get()
            except Exception:
                pass
            
            # 2. Si no, intentar obtener de pool en kogniterm.server.session_pool
            if not workspace_dir:
                try:
                    import sys
                    if "kogniterm.server.session_pool" in sys.modules:
                        pool_mod = sys.modules["kogniterm.server.session_pool"]
                        if hasattr(pool_mod, "pool") and pool_mod.pool:
                            if hasattr(pool_mod.pool, "_llm_service") and pool_mod.pool._llm_service:
                                workspace_dir = getattr(pool_mod.pool._llm_service, "_current_workspace_dir", None)
                            if not workspace_dir and hasattr(pool_mod.pool, "list_all"):
                                active_sessions = pool_mod.pool.list_all()
                                if active_sessions:
                                    for s in active_sessions:
                                        if hasattr(s, "workspace_dir") and s.workspace_dir:
                                            workspace_dir = s.workspace_dir
                                            break
                except Exception:
                    pass

        self.workspace_dir = workspace_dir or os.getcwd()
        self.PROJECT_CONFIG_DIR = Path(self.workspace_dir) / ".kogniterm"
        self.PROJECT_CONFIG_FILE = self.PROJECT_CONFIG_DIR / "config.json"
        self._ensure_global_dir_exists()

    def _ensure_global_dir_exists(self):
        """Ensures the global configuration directory exists."""
        if not self.GLOBAL_CONFIG_DIR.exists():
            self.GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _ensure_project_dir_exists(self):
        """Ensures the project configuration directory exists."""
        if not self.PROJECT_CONFIG_DIR.exists():
            self.PROJECT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Loads a JSON file, returning an empty dict if it doesn't exist or is invalid."""
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_json(self, path: Path, data: Dict[str, Any]):
        """Saves a dictionary to a JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def load_global_config(self) -> Dict[str, Any]:
        """Loads the global configuration."""
        return self._load_json(self.GLOBAL_CONFIG_FILE)

    def load_project_config(self) -> Dict[str, Any]:
        """Loads the project-specific configuration."""
        return self._load_json(self.PROJECT_CONFIG_FILE)

    def get_config(self, key: Optional[str] = None) -> Any:
        """
        Retrieves a configuration value.
        If key is None, returns the merged configuration (project overrides global).
        """
        global_config = self.load_global_config()
        project_config = self.load_project_config()

        # Merge configs: project overrides global
        merged_config = {**global_config, **project_config}

        if key is None:
            return merged_config

        return merged_config.get(key)

    def set_global_config(self, key: str, value: Any):
        """Sets a value in the global configuration."""
        config = self.load_global_config()
        config[key] = value
        self._save_json(self.GLOBAL_CONFIG_FILE, config)
        
        # Si la carpeta del proyecto (.kogniterm) existe, también guardamos allí para evitar
        # que el valor de proyecto anterior sobreescriba/enmascare nuestro cambio.
        if self.PROJECT_CONFIG_FILE.exists() or self.PROJECT_CONFIG_DIR.exists():
            project_config = self.load_project_config()
            # Si la llave ya existe en el proyecto, o si es una de las llaves del LLM/modelo/proveedor,
            # sincronizarla también en el proyecto para que persista.
            if key in project_config or key in ("default_model", "summary_model", "reasoning_effort", "embeddings_provider", "embeddings_model", "custom_openai_api_base", "ollama_api_base", "ollama_provider_target"):
                project_config[key] = value
                self._save_json(self.PROJECT_CONFIG_FILE, project_config)

    def set_project_config(self, key: str, value: Any):
        """Sets a value in the project-specific configuration."""
        self._ensure_project_dir_exists()
        config = self.load_project_config()
        config[key] = value
        self._save_json(self.PROJECT_CONFIG_FILE, config)

    def get_all_config(self) -> Dict[str, Any]:
        """Returns the complete merged configuration."""
        return self.get_config()

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Obtiene la API key para un provider (ej: 'google', 'openai', 'anthropic', etc.)
        Busca primero en config del proyecto, luego en global. Si no existe, retorna None.
        """
        key_name = f"api_key_{provider.lower()}"
        # Merge config: project > global
        merged = self.get_config()
        return merged.get(key_name)

    def set_api_key(self, provider: str, key: str, scope: str = "project"):
        """
        Guarda la API key para un provider en el config.json (por defecto en el workspace).
        scope: 'project' o 'global'.
        """
        key_name = f"api_key_{provider.lower()}"
        if scope == "global":
            self.set_global_config(key_name, key)
        else:
            self.set_project_config(key_name, key)