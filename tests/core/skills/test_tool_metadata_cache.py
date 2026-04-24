from pathlib import Path

from kogniterm.core.skills.skill_manager import Skill, SkillLoader


def test_skill_loader_caches_callable_injection_metadata(tmp_path):
    skill_dir = tmp_path / "cached_skill"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (skill_dir / "references").mkdir()

    (scripts_dir / "tool.py").write_text(
        """
def cached_tool(value: str, llm_service=None, approval_handler=None) -> str:
    return value

name = "cached_tool"
description = "Tool de prueba"
""".strip(),
        encoding="utf-8",
    )

    skill = Skill(
        path=skill_dir,
        name="cached_skill",
        version="1.0.0",
        description="Skill de prueba",
    )

    loader = SkillLoader()
    tools = loader.load_tools_from_skill(skill)

    assert len(tools) == 1
    assert getattr(tools[0], "_kogniterm_injection_params") == {
        "llm_service": True,
        "approval_handler": True,
    }
