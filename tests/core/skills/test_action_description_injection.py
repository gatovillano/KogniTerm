from pathlib import Path
import sys
import os

# Añadir el path del proyecto para imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from kogniterm.core.skills.skill_manager import SkillManager, Skill, SkillLoader

def test_action_description_injection(tmp_path):
    """Verifica que SkillLoader inyecta get_action_description si existe en el módulo."""
    # 1. Crear estructura de skill temporal
    skill_dir = tmp_path / "test_desc_skill"
    skill_dir.mkdir()
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    
    # 2. Crear SKILL.md
    (skill_dir / "SKILL.md").write_text("""---
name: test_desc_skill
version: 1.0.0
description: "Skill para test de descripción"
---
""")

    # 3. Crear script con función y get_action_description
    tool_script = scripts_dir / "tool.py"
    tool_script.write_text("""
def my_tool(arg1: str):
    return f"Done {arg1}"

def get_action_description(arg1: str, **kwargs):
    return f"Acting on {arg1}"

name = "my_tool"
""")

    # 4. Cargar la skill
    skill = Skill(path=skill_dir, name="test_desc_skill")
    loader = SkillLoader()
    tools = loader.load_tools_from_skill(skill)
    
    assert len(tools) == 1
    tool = tools[0]
    
    # 5. Verificar inyección
    assert hasattr(tool, 'get_action_description')
    assert tool.get_action_description(arg1="test") == "Acting on test"
    print("✅ Inyección de get_action_description verificada con éxito.")

if __name__ == "__main__":
    # Simular tmp_path para ejecución directa si es necesario
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_action_description_injection(Path(tmp))
