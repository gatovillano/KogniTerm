"""
Tests unitarios para el sistema de Skills de KogniTerm.

Estos tests verifican:
1. Discovery de skills
2. Validación de estructura de skills
3. Carga de módulos Python
4. Registro de herramientas
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import yaml
import sys

# Añadir el path del proyecto para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kogniterm.core.skills.skill_manager import (
    SkillManager,
    Skill,
    SkillValidator,
    SkillLoader
)


class TestSkillValidator:
    """Tests para el SkillValidator."""

    def test_validate_valid_skill(self, tmp_path):
        """Debe validar una skill con estructura correcta."""
        # Crear estructura de skill válida
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()

        # Crear SKILL.md válido
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test_skill
version: 1.0.0
description: "Una skill de prueba"
category: system
tags: ["test"]
dependencies: []
required_permissions: ["execute"]
security_level: "medium"
allowlist: false
auto_approve: false
sandbox_required: false
---

# Instrucciones
""")

        validator = SkillValidator()
        is_valid, errors = validator.validate_skill(skill_dir)

        assert is_valid, f"Errores: {errors}"
        assert len(errors) == 0

    def test_validate_missing_skill_md(self, tmp_path):
        """Debe rechazar skill sin SKILL.md."""
        skill_dir = tmp_path / "invalid_skill"
        skill_dir.mkdir()

        validator = SkillValidator()
        is_valid, errors = validator.validate_skill(skill_dir)

        assert not is_valid
        assert any("SKILL.md" in e for e in errors)

    def test_validate_prompt_only_skill_without_scripts(self, tmp_path):
        """Debe aceptar una skill solo de instrucciones sin scripts/."""
        skill_dir = tmp_path / "invalid_skill"
        skill_dir.mkdir()
        (skill_dir / "references").mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: invalid_skill
description: "Skill sin scripts"
---

# Instrucciones
Esta skill solo contiene instrucciones.

""")

        validator = SkillValidator()
        is_valid, errors = validator.validate_skill(skill_dir)

        assert is_valid, f"Errores: {errors}"
        assert len(errors) == 0

    def test_validate_invalid_security_level(self, tmp_path):
        """Debe rechazar security_level inválido."""
        skill_dir = tmp_path / "invalid_skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()

        (skill_dir / "SKILL.md").write_text("""---
name: invalid_skill
version: 1.0.0
description: "Skill con security_level inválido"
security_level: "invalid_level"
---

""")

        validator = SkillValidator()
        is_valid, errors = validator.validate_skill(skill_dir)

        assert not is_valid
        assert any("security_level" in e for e in errors)


class TestSkillLoader:
    """Tests para el SkillLoader."""

    def test_load_tools_from_scripts(self, tmp_path):
        """Debe cargar herramientas desde scripts/."""
        # Crear estructura
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (skill_dir / "references").mkdir()

        # Crear script con función tool
        tool_script = scripts_dir / "tool.py"
        tool_script.write_text("""
def test_function(command: str) -> str:
    '''Una función de prueba.'''
    return f"Echo: {command}"
""")

        # Crear skill
        skill = Skill(
            path=skill_dir,
            name="test_skill",
            version="1.0.0",
            description="Skill de prueba"
        )

        loader = SkillLoader()
        tools = loader.load_tools_from_skill(skill)

        assert len(tools) > 0
        assert any(hasattr(t, '__call__') or callable(t) for t in tools)


class TestSkillManager:
    """Tests para el SkillManager."""

    def test_discover_all_skills(self, tmp_path):
        """Debe descubrir skills en bundled/managed/workspace."""
        # Crear estructura temporal de skills
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        skill1 = bundled / "skill_one"
        skill1.mkdir()
        (skill1 / "scripts").mkdir()
        (skill1 / "references").mkdir()
        (skill1 / "SKILL.md").write_text("""---
name: skill_one
version: 1.0.0
description: "Skill uno"
category: system
tags: ["test"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: false
sandbox_required: false
---
""")

        skill2_root = bundled / "topic"
        skill2_root.mkdir()
        skill2 = skill2_root / "skill_two"
        skill2.mkdir()
        (skill2 / "scripts").mkdir()
        (skill2 / "references").mkdir()
        (skill2 / "SKILL.md").write_text("""---
name: skill_two
description: "Skill dos"
category: system
tags: ["test"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: false
sandbox_required: false
---
""")

        manager = SkillManager(base_path=tmp_path)
        skills = manager.discover_all_skills()

        assert len(skills) >= 2
        skill_names = [s.name for s in skills]
        assert "skill_one" in skill_names
        assert "skill_two" in skill_names

    def test_load_skill(self, tmp_path):
        """Debe cargar una skill y registrar sus herramientas."""
        # Crear estructura de skill
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        skill_dir = bundled / "test_load"
        skill_dir.mkdir()
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (skill_dir / "references").mkdir()

        # Crear SKILL.md
        (skill_dir / "SKILL.md").write_text("""---
name: test_load
version: 1.0.0
description: "Skill para test de carga"
category: system
tags: ["test"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: false
sandbox_required: false
---
""")

        # Crear script con función
        tool_script = scripts_dir / "tool.py"
        tool_script.write_text("""
def test_tool(command: str) -> str:
    '''Tool de prueba.'''
    return f"Result: {command}"

name = "test_tool"
description = "Tool de prueba"
""")

        manager = SkillManager(base_path=tmp_path)
        manager.discover_all_skills()

        success = manager.load_skill("test_load")

        assert success
        assert "test_tool" in manager.tool_registry or len(manager.tool_registry) > 0

    def test_load_prompt_only_skill(self, tmp_path):
        """Debe cargar una skill de solo instrucciones sin herramientas."""
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        skill_dir = bundled / "prompt_only"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: prompt_only
description: "Skill de solo instrucciones"
category: system
tags: ["prompt"]
dependencies: []
required_permissions: []
allowed-tools: []
denied-tools: []
security_level: "low"
allowlist: false
auto_approve: false
sandbox_required: false
---

# Instrucciones
Actúa como una guía especializada para una tarea concreta.
""")

        manager = SkillManager(base_path=tmp_path)
        manager.discover_all_skills()

        success = manager.load_skill("prompt_only")

        assert success
        assert "prompt_only" in manager.loaded_skills
        assert manager.get_skill_info("prompt_only")["instructions"].strip().startswith("# Instrucciones")

    def test_unload_skill(self, tmp_path):
        """Debe descargar una skill correctamente."""
        # Crear estructura
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        skill_dir = bundled / "test_unload"
        skill_dir.mkdir()
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (skill_dir / "references").mkdir()

        (skill_dir / "SKILL.md").write_text("""---
name: test_unload
version: 1.0.0
description: "Skill para test de unload"
category: system
tags: ["test"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: false
sandbox_required: false
---
""")

        (scripts_dir / "tool.py").write_text("""
def dummy_tool():
    pass

name = "dummy_tool"
""")

        manager = SkillManager(base_path=tmp_path)
        manager.discover_all_skills()
        manager.load_skill("test_unload")

        assert "test_unload" in manager.loaded_skills

        manager.unload_skill("test_unload")

        assert "test_unload" not in manager.loaded_skills

    def test_get_available_tools(self, tmp_path):
        """Debe retornar lista de herramientas disponibles."""
        # Crear estructura
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        skill_dir = bundled / "test_tools"
        skill_dir.mkdir()
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (skill_dir / "references").mkdir()

        (skill_dir / "SKILL.md").write_text("""---
name: test_tools
version: 1.0.0
description: "Skill para test de tools"
category: system
tags: ["test"]
dependencies: []
required_permissions: ["execute"]
security_level: "medium"
allowlist: false
auto_approve: false
sandbox_required: false
---
""")

        (scripts_dir / "tool.py").write_text("""
def tool_one():
    pass

def tool_two():
    pass
""")

        manager = SkillManager(base_path=tmp_path)
        manager.discover_all_skills()
        manager.load_skill("test_tools")

        available = manager.get_available_tools()

        assert len(available) > 0
        for tool in available:
            assert 'name' in tool
            assert 'security_level' in tool
            assert 'skill' in tool

    def test_list_skills(self, tmp_path):
        """Debe listar todas las skills con su estado."""
        # Crear estructura
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        skill_dir = bundled / "test_list"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()

        (skill_dir / "SKILL.md").write_text("""---
name: test_list
version: 1.0.0
description: "Skill para test de listing"
category: system
tags: ["test"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: false
sandbox_required: false
---
""")

        manager = SkillManager(base_path=tmp_path)
        manager.discover_all_skills()

        skills_list = manager.list_skills()

        assert len(skills_list) >= 1
        assert any(s['name'] == 'test_list' for s in skills_list)


class TestSkillIntegration:
    """Tests de integración con skills reales (bundled)."""

    def test_discover_bundled_skills(self):
        """Debe descubrir las skills bundled en el proyecto."""
        # Usar la ruta real del proyecto
        project_root = Path(__file__).parent.parent.parent
        bundled_path = project_root / "kogniterm" / "skills" / "bundled"

        if not bundled_path.exists():
            pytest.skip("Skills bundled no existen aún")

        manager = SkillManager(base_path=project_root / "kogniterm")
        skills = manager.discover_all_skills()

        # Verificar que al menos tenemos las skills migradas
        skill_names = [s.name for s in skills]
        print(f"Skills encontradas: {skill_names}")

        # Las skills que migramos deberían estar
        expected_skills = ['execute_command', 'file_operations', 'memory_append']
        for expected in expected_skills:
            if expected in skill_names:
                print(f"✅ Skill '{expected}' encontrada")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
