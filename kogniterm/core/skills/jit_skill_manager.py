import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class SkillHeader:
    name: str
    description: str
    file_path: Path

class JITSkillManager:
    """Manages skill discovery, compact prompt header generation, and JIT body loading."""

    def __init__(self, skills_dirs: List[Path]):
        self.skills_dirs = [Path(d) for d in skills_dirs]
        self._headers: Dict[str, SkillHeader] = {}
        self._active_skills: Dict[str, str] = {}
        self.index_skills()

    def index_skills(self) -> None:
        """Scan skills directories and index only YAML frontmatter headers."""
        self._headers.clear()
        for s_dir in self.skills_dirs:
            if not s_dir.exists():
                continue
            for item in s_dir.rglob("SKILL.md"):
                header = self._parse_frontmatter(item)
                if header:
                    self._headers[header.name] = header

    def _parse_frontmatter(self, filepath: Path) -> Optional[SkillHeader]:
        try:
            content = filepath.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return None
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None
            yaml_block = parts[1]
            name_match = re.search(r"^name:\s*(.+)$", yaml_block, re.MULTILINE)
            desc_match = re.search(r"^description:\s*(.+)$", yaml_block, re.MULTILINE)
            if name_match and desc_match:
                name = name_match.group(1).strip().strip('"\'')
                desc = desc_match.group(1).strip().strip('"\'')
                return SkillHeader(name=name, description=desc, file_path=filepath)
        except Exception:
            pass
        return None

    def get_compact_headers(self) -> str:
        """Generate a token-efficient summary list of available skills."""
        if not self._headers:
            return "No active skills loaded."
        lines = ["## Available Skills (JIT Loaded):"]
        for header in self._headers.values():
            lines.append(f"- {header.name}: {header.description}")
        return "\n".join(lines)

    def resolve_and_expand_skill(self, skill_name: str) -> Optional[str]:
        """Load and return the full SKILL.md body on demand."""
        if skill_name in self._active_skills:
            return self._active_skills[skill_name]
        if skill_name not in self._headers:
            return None
        header = self._headers[skill_name]
        try:
            content = header.file_path.read_text(encoding="utf-8")
            self._active_skills[skill_name] = content
            return content
        except Exception:
            return None

    def is_skill_active(self, skill_name: str) -> bool:
        return skill_name in self._active_skills
