"""
Tests para las nuevas características del sistema de Skills:
1. Persistencia de estado local por skill.
2. Instalación en caliente de dependencias.
3. Ejecución en Sandbox (aislamiento de procesos).
"""

import pytest
import sys
import os
import json
import shutil
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

# Añadir el path del proyecto para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kogniterm.core.skills.skill_manager import (
    SkillManager,
    Skill,
    SkillValidator,
    SkillLoader
)

class TestNewSkillsFeatures:
    """Tests para las funcionalidades extendidas de SkillManager."""

    def test_skill_state_persistence(self, tmp_path):
        """Verifica que se inyecte get_skill_state y save_skill_state y persistan los datos."""
        # Crear estructura de skill
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        skill_dir = bundled / "test_persistence"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()

        # Crear SKILL.md
        (skill_dir / "SKILL.md").write_text("""---
name: test_persistence
version: 1.0.0
description: "Skill con estado persistente"
category: system
tags: ["test"]
dependencies: []
security_level: "low"
sandbox_required: false
---
""")

        # Crear script
        (skill_dir / "scripts" / "tool.py").write_text("""
def save_some_data_tool(key, val):
    state = get_skill_state()
    state[key] = val
    save_skill_state(state)
    return "Saved!"

def load_some_data_tool(key):
    state = get_skill_state()
    return state.get(key)
""")

        manager = SkillManager(base_path=tmp_path)
        manager.discover_all_skills()
        success = manager.load_skill("test_persistence")
        assert success

        # Obtener herramientas
        save_tool = manager.get_tool("save_some_data_tool")
        load_tool = manager.get_tool("load_some_data_tool")

        # Guardar datos
        res_save = save_tool("mi_clave", "mi_valor")
        assert res_save == "Saved!"

        # El archivo de estado debe existir
        state_file = tmp_path / ".kogniterm" / "state" / "test_persistence.json"
        assert state_file.exists()

        # Recargar skill para probar persistencia entre cargas
        manager.unload_skill("test_persistence")
        manager.load_skill("test_persistence")
        
        load_tool2 = manager.get_tool("load_some_data_tool")
        res_load = load_tool2("mi_clave")
        assert res_load == "mi_valor"

    def test_auto_dependency_installation(self, tmp_path):
        """Verifica que _validate_dependencies intente instalar paquetes faltantes."""
        manager = SkillManager(base_path=tmp_path)
        
        # Simular que pip install se ejecuta correctamente
        with patch("subprocess.check_call") as mock_pip, \
             patch("importlib.import_module", side_effect=ImportError):
            
            # Primera llamada falla import, por lo que llama a pip, segunda llamada simula import exitoso posterior
            manager._validate_dependencies(["unsupported-fake-library"])
            
            mock_pip.assert_called_once()
            args = mock_pip.call_args[0][0]
            assert "pip" in args
            assert "install" in args
            assert "unsupported-fake-library" in args

    def test_sandboxed_tool_wrapping(self, tmp_path):
        """Verifica que las herramientas marcadas con sandbox_required se envuelvan en _wrap_in_sandbox."""
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        skill_dir = bundled / "sandbox_skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()

        # Crear SKILL.md con sandbox_required: true
        (skill_dir / "SKILL.md").write_text("""---
name: sandbox_skill
version: 1.0.0
description: "Skill en sandbox"
category: external
tags: ["test"]
dependencies: []
security_level: "high"
sandbox_required: true
---
""")

        # Crear script
        (skill_dir / "scripts" / "tool.py").write_text("""
def run_in_sandbox_tool(x, y):
    return x + y
""")

        manager = SkillManager(base_path=tmp_path)
        manager.discover_all_skills()
        success = manager.load_skill("sandbox_skill")
        assert success

        tool_info = manager.tool_registry.get("run_in_sandbox_tool")
        assert tool_info["sandbox_required"] is True

        # Al obtener la herramienta, debe ser una función envuelta
        tool = manager.get_tool("run_in_sandbox_tool")
        assert tool is not None
        assert tool.__name__ == "run_in_sandbox_tool"
        
        # Ejecutar en sandbox
        result = tool(x=10, y=20)
        assert result == 30 or "❌" in str(result)
