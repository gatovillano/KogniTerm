import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

class AgentConfigManager:
    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.getcwd()
        self.configs: Dict[str, Dict[str, Any]] = {}
        
    def discover_configs(self):
        self.configs.clear()
        
        # Paths to search (ordered by priority: project -> user -> default)
        paths = [
            Path(self.workspace_dir) / ".agents",
            Path.home() / ".kogniterm" / "agents",
            Path(__file__).parent / "config"
        ]
        
        for path in paths:
            if not path.exists() or not path.is_dir():
                continue
            for file_path in path.glob("*"):
                if file_path.name == "AGENTS.md":  # Skip system rules file
                    continue
                if file_path.suffix in (".yaml", ".yml", ".md"):
                    try:
                        self._parse_file(file_path)
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"Error parsing agent config {file_path}: {e}")

    def _parse_file(self, file_path: Path):
        content = file_path.read_text(encoding="utf-8")
        config = {}
        
        if file_path.suffix == ".md":
            if content.startswith("---"):
                end_idx = content.find("---", 3)
                if end_idx != -1:
                    yaml_content = content[3:end_idx].strip()
                    body = content[end_idx + 3:].strip()
                    config = yaml.safe_load(yaml_content) or {}
                    if "system_prompt" not in config:
                        config["system_prompt"] = body
        else:
            config = yaml.safe_load(content) or {}
            
        if "name" in config:
            name = config["name"]
            # Only set if not already set by a higher priority directory
            if name not in self.configs:
                self.configs[name] = config

    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        if not self.configs:
            self.discover_configs()
        return self.configs.get(agent_name)
