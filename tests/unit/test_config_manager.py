import os
import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
import sys

from kogniterm.terminal.config_manager import ConfigManager

def test_config_manager_workspace_dir_manual(tmp_path):
    # If workspace_dir is passed manually, it should use it
    cm = ConfigManager(workspace_dir=str(tmp_path))
    assert cm.workspace_dir == str(tmp_path)
    assert cm.PROJECT_CONFIG_DIR == tmp_path / ".kogniterm"
    assert cm.PROJECT_CONFIG_FILE == tmp_path / ".kogniterm" / "config.json"

def test_config_manager_workspace_dir_context_var(tmp_path):
    # Mock LLMService module-level structure to simulate an active workspace context
    mock_module = MagicMock()
    mock_module.LLMService._context_current_workspace_dir.get.return_value = str(tmp_path)
    
    with patch.dict(sys.modules, {"kogniterm.core.llm_service": mock_module}):
        cm = ConfigManager()
        assert cm.workspace_dir == str(tmp_path)

def test_config_manager_workspace_dir_session_pool(tmp_path):
    # Mock session pool to simulate an active session
    mock_pool_mod = MagicMock()
    mock_pool_mod.pool.list_all.return_value = [
        MagicMock(workspace_dir=str(tmp_path))
    ]
    mock_pool_mod.pool._llm_service = None
    
    with patch.dict(sys.modules, {
        "kogniterm.core.llm_service": None,
        "kogniterm.server.session_pool": mock_pool_mod
    }):
        cm = ConfigManager()
        assert cm.workspace_dir == str(tmp_path)

def test_set_global_config_syncs_to_project_config(tmp_path):
    # Arrange: Setup global and project configs
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".kogniterm").mkdir()  # Create the .kogniterm project config folder
    
    with patch.object(ConfigManager, "GLOBAL_CONFIG_DIR", global_dir), \
         patch.object(ConfigManager, "GLOBAL_CONFIG_FILE", global_dir / "config.json"):
         
        cm = ConfigManager(workspace_dir=str(project_dir))
        
        # Create global config file
        cm._save_json(cm.GLOBAL_CONFIG_FILE, {"theme": "default"})
        
        # Scenario 1: Project config folder exists, but config file does not exist yet.
        # Calling set_global_config on standard keys like default_model should create the project config file.
        cm.set_global_config("default_model", "openai/gpt-4o")
        
        assert cm.load_global_config().get("default_model") == "openai/gpt-4o"
        assert cm.load_project_config().get("default_model") == "openai/gpt-4o"
        
        # Scenario 2: Project config file exists with a key, we change it globally.
        # It should update the project config file as well.
        cm.set_global_config("default_model", "google/gemini-1.5-flash")
        assert cm.load_project_config().get("default_model") == "google/gemini-1.5-flash"
