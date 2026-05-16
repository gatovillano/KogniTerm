from pathlib import Path

from kogniterm.core.context.project_memory_builder import ProjectMemoryBuilder


def test_build_markdown_prefers_existing_copilot_instructions(tmp_path):
    repo = tmp_path
    (repo / ".github").mkdir()
    (repo / ".github" / "copilot-instructions.md").write_text(
        "# Copilot instructions for Demo\n\n## Build, test, and lint commands\n\n```bash\npytest\n```",
        encoding="utf-8",
    )

    builder = ProjectMemoryBuilder(str(repo))
    content = builder.build_markdown()

    assert content.startswith("# Memoria Contextual del Proyecto")
    assert "## Build, test, and lint commands" in content
    assert "pytest" in content
    assert "Copilot instructions for Demo" not in content


def test_write_memory_file_uses_dot_kogniterm_directory(tmp_path):
    builder = ProjectMemoryBuilder(str(tmp_path))

    full_path = builder.write_memory_file("contenido", file_path="custom.md")

    assert full_path == tmp_path / ".kogniterm" / "custom.md"
    assert full_path.read_text(encoding="utf-8") == "contenido\n"


def test_fallback_markdown_infers_commands_and_architecture(tmp_path):
    repo = tmp_path
    (repo / "kogniterm" / "terminal").mkdir(parents=True)
    (repo / "kogniterm" / "core" / "context").mkdir(parents=True)
    (repo / "kogniterm" / "core" / "skills").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        """
[project]
name = "demo"

[project.scripts]
demo = "demo:main"
""".strip(),
        encoding="utf-8",
    )
    (repo / "CONTRIBUTING.md").write_text(
        "Usa black para formatear y isort para imports.",
        encoding="utf-8",
    )
    (repo / "README.md").write_text(
        "Este proyecto es tu agente evolutivo de terminal inteligente.",
        encoding="utf-8",
    )
    (repo / "run_tests.py").write_text("print('ok')", encoding="utf-8")
    (repo / "tests" / "test_basic.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "kogniterm" / "terminal" / "terminal.py").write_text(
        "# Heavy imports moved inside functions\n",
        encoding="utf-8",
    )
    (repo / "kogniterm" / "main.py").write_text(
        "# Este archivo ya no es el punto de entrada principal de KogniTerm.\n",
        encoding="utf-8",
    )
    (repo / "kogniterm" / "terminal" / "config_manager.py").write_text("CONFIG = True\n", encoding="utf-8")
    (repo / "kogniterm" / "core" / "llm_service.py").write_text("class LLMService: pass\n", encoding="utf-8")
    (repo / "kogniterm" / "core" / "agent_state.py").write_text("class AgentState: pass\n", encoding="utf-8")
    (repo / "kogniterm" / "core" / "message_manager.py").write_text("class MessageManager: pass\n", encoding="utf-8")
    (repo / "kogniterm" / "core" / "history_manager.py").write_text("class HistoryManager: pass\n", encoding="utf-8")
    (repo / "kogniterm" / "core" / "command_executor.py").write_text("class CommandExecutor: pass\n", encoding="utf-8")
    (repo / "kogniterm" / "core" / "context" / "codebase_indexer.py").write_text("class CodebaseIndexer: pass\n", encoding="utf-8")
    (repo / "kogniterm" / "core" / "skills" / "skill_manager.py").write_text("class SkillManager: pass\n", encoding="utf-8")

    builder = ProjectMemoryBuilder(str(repo))
    content = builder.build_markdown()

    assert "python -m pip install -e ." in content
    assert "python -m kogniterm.terminal.terminal" in content
    assert "python -m pytest tests/test_basic.py::test_logger_setup" in content
    assert "`kogniterm/terminal/terminal.py` is the real entrypoint" in content
    assert "Do not route new startup behavior through `kogniterm/main.py`" in content
