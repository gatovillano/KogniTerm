import pytest
from pathlib import Path
from kogniterm.core.skills.jit_skill_manager import JITSkillManager

def test_jit_skill_manager_header_extraction(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: test-skill
description: Use when testing JIT skill loading.
---
# Test Skill
Full body instructions here.
""")
    
    manager = JITSkillManager(skills_dirs=[tmp_path])
    headers = manager.get_compact_headers()
    assert "- test-skill: Use when testing JIT skill loading." in headers
    assert "Full body instructions here." not in headers

def test_jit_skill_manager_body_expansion(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: test-skill
description: Use when testing JIT skill loading.
---
# Test Skill
Full body instructions here.
""")
    
    manager = JITSkillManager(skills_dirs=[tmp_path])
    body = manager.resolve_and_expand_skill("test-skill")
    assert "Full body instructions here." in body
