import pytest
from unittest.mock import MagicMock
from prompt_toolkit.document import Document
from kogniterm.terminal.file_completer import FileCompleter
from kogniterm.core.utils.prompt_processor import process_prompt_references


class TestSkillPromptCompletion:

    def test_file_completer_hash_trigger(self, tmp_path):
        """Verifica que el FileCompleter despliegue las skills procedimentales al usar '#'."""
        mock_skills = [
            {"name": "a11y-debugging", "description": "DevTools accessibility debugging", "loaded": True, "is_procedural": True},
            {"name": "antigravity-guide", "description": "Google Antigravity SDK guide", "loaded": False, "is_procedural": True},
            {"name": "brainstorming", "description": "Design before implementation", "loaded": True, "is_procedural": True},
        ]
        mock_skill_manager = MagicMock()
        mock_skill_manager.list_skills.return_value = mock_skills
        mock_skill_manager.get_procedural_skills.return_value = mock_skills

        completer = FileCompleter(skill_manager=mock_skill_manager, workspace_directory=str(tmp_path))

        # 1. Al escribir '#' debe listar todas las skills coincidentes
        doc = Document("#", cursor_position=1)
        completions = list(completer.get_completions(doc, None))
        completion_texts = [c.text for c in completions]

        assert "a11y-debugging" in completion_texts
        assert "antigravity-guide" in completion_texts
        assert "brainstorming" in completion_texts

        # 2. Al escribir '#anti' debe filtrar por 'antigravity-guide'
        doc_filter = Document("#anti", cursor_position=5)
        completions_filter = list(completer.get_completions(doc_filter, None))
        filter_texts = [c.text for c in completions_filter]

        assert filter_texts == ["antigravity-guide"]
        assert "Google Antigravity SDK guide" in str(completions_filter[0].display_meta)

    def test_process_prompt_references_valid_skill(self, tmp_path):
        """Verifica que #nombre_skill se reemplace por las instrucciones de la skill."""
        mock_skill_manager = MagicMock()
        mock_skill_manager.get_skill_instructions.side_effect = lambda name: (
            "Instrucciones de a11y-debugging" if name == "a11y-debugging" else None
        )

        prompt = "Analizar la interfaz siguiendo #a11y-debugging por favor."
        result = process_prompt_references(prompt, workspace_directory=str(tmp_path), skill_manager=mock_skill_manager)

        assert "### INSTRUCCIONES DE LA SKILL 'a11y-debugging' ###" in result
        assert "Instrucciones de a11y-debugging" in result

    def test_process_prompt_references_non_skill_hash(self, tmp_path):
        """Verifica que etiquetas o encabezados # que no son skills permanezcan intactos."""
        mock_skill_manager = MagicMock()
        mock_skill_manager.get_skill_instructions.return_value = None

        prompt = "# Título principal\nRevisar la tarea #123 y el color #ffffff"
        result = process_prompt_references(prompt, workspace_directory=str(tmp_path), skill_manager=mock_skill_manager)

        assert result == prompt

    def test_is_procedural_identification(self, tmp_path):
        """Verifica que una skill sin scripts Python sea clasificada como is_procedural=True."""
        from pathlib import Path
        from kogniterm.core.skills.skill_manager import Skill, SkillManager

        # Skill procedimental (sin scripts python)
        proc_dir = tmp_path / "proc_skill"
        proc_dir.mkdir()
        (proc_dir / "SKILL.md").write_text("---\nname: proc_skill\ndescription: Procedural skill\n---\nBody")
        proc_skill = Skill(path=proc_dir, name="proc_skill", description="Procedural skill")

        # Skill con scripts python (herramienta)
        tool_dir = tmp_path / "tool_skill"
        scripts_dir = tool_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (tool_dir / "SKILL.md").write_text("---\nname: tool_skill\ndescription: Tool skill\n---\nBody")
        (scripts_dir / "tool.py").write_text("def run(): pass")
        tool_skill = Skill(path=tool_dir, name="tool_skill", description="Tool skill")

        assert proc_skill.is_procedural is True
        assert tool_skill.is_procedural is False

        sm = SkillManager(base_path=tmp_path)
        sm.skills = {"proc_skill": proc_skill, "tool_skill": tool_skill}

        procedural_list = sm.get_procedural_skills()
        names = [s["name"] for s in procedural_list]
        assert "proc_skill" in names
        assert "tool_skill" not in names

