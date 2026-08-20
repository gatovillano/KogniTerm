import pytest
from pathlib import Path
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.mcp.config import MCPServerConfig

def test_config_manager_mcp_servers(tmp_path, monkeypatch):
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_DIR", tmp_path / "global")
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_FILE", tmp_path / "global" / "config.json")
    monkeypatch.setattr(ConfigManager, "PROJECT_CONFIG_DIR", tmp_path / "project")
    monkeypatch.setattr(ConfigManager, "PROJECT_CONFIG_FILE", tmp_path / "project" / "config.json")
    
    cm = ConfigManager()
    server_data = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "env": {"TEST": "1"},
        "disabled": False,
        "transport": "stdio"
    }
    cm.set_mcp_server("filesystem", server_data, scope="project")
    
    servers = cm.get_mcp_servers()
    assert "filesystem" in servers
    assert servers["filesystem"]["command"] == "npx"
    
    cm.delete_mcp_server("filesystem", scope="project")
    assert "filesystem" not in cm.get_mcp_servers()
