import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

class ConfigManager:
    """
    Manages configuration for KogniTerm, handling both global and project-specific settings.
    Project settings override global settings.
    """

    GLOBAL_CONFIG_DIR = Path.home() / ".kogniterm"
    GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"
    PROJECT_CONFIG_DIR = Path(".kogniterm")
    PROJECT_CONFIG_FILE = PROJECT_CONFIG_DIR / "config.json"

    def __init__(self):
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

    def set_project_config(self, key: str, value: Any):
        """Sets a value in the project-specific configuration."""
        self._ensure_project_dir_exists()
        config = self.load_project_config()
        config[key] = value
        self._save_json(self.PROJECT_CONFIG_FILE, config)

    def get_all_config(self) -> Dict[str, Any]:
        """Returns the complete merged configuration."""
        return self.get_config()
