from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import os
import tomllib


class ProjectMemoryBuilder:
    """Genera una memoria de alto nivel del proyecto para %init."""

    DEFAULT_MEMORY_FILE = "llm_context.md"

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def build_markdown(self) -> str:
        existing_instructions = self._read_text(
            self.root_dir / ".github" / "copilot-instructions.md",
            max_chars=50000,
        )
        if existing_instructions.strip():
            return self._normalize_existing_instructions(existing_instructions)
        return self._build_fallback_markdown()

    def write_memory_file(
        self, content: str, file_path: str = DEFAULT_MEMORY_FILE
    ) -> Path:
        kogniterm_dir = self.root_dir / ".kogniterm"
        kogniterm_dir.mkdir(parents=True, exist_ok=True)
        full_path = kogniterm_dir / Path(file_path).name
        full_path.write_text(content.strip() + "\n", encoding="utf-8")
        return full_path

    def _normalize_existing_instructions(self, content: str) -> str:
        lines = content.strip().splitlines()
        if lines and lines[0].lstrip().startswith("# "):
            lines = lines[1:]

        body = "\n".join(lines).strip()
        if not body:
            return self._build_fallback_markdown()

        return "# Memoria Contextual del Proyecto\n\n" + body

    def _build_fallback_markdown(self) -> str:
        commands = self._build_commands_section()
        architecture = self._build_architecture_section()
        conventions = self._build_conventions_section()

        sections = [
            "# Memoria Contextual del Proyecto",
            "",
            "## Build, test, and lint commands",
            "",
            *commands,
            "",
            "## High-level architecture",
            "",
            *architecture,
            "",
            "## Key conventions",
            "",
            *conventions,
        ]
        return "\n".join(sections).strip()

    def _build_commands_section(self) -> List[str]:
        lines: List[str] = ["```bash"]

        if (self.root_dir / "pyproject.toml").exists() or (self.root_dir / "setup.py").exists():
            lines.append("python -m pip install -e .")

        if (self.root_dir / "kogniterm" / "terminal" / "terminal.py").exists():
            lines.append("python -m kogniterm.terminal.terminal")
            lines.append("kogniterm")
            lines.append("kogniterm --cli")

        if (self.root_dir / "tests").exists():
            lines.append("python -m pytest tests/")
            if (self.root_dir / "run_tests.py").exists():
                lines.append("python run_tests.py")
                lines.append(
                    'python -c "import run_tests; run_tests.run_unit_tests()"'
                )
                lines.append(
                    'python -c "import run_tests; run_tests.run_integration_tests()"'
                )

            single_test = self._pick_single_test_target()
            if single_test:
                lines.append(f"python -m pytest {single_test}")
                if single_test == "tests/test_basic.py":
                    lines.append(
                        "python -m pytest tests/test_basic.py::test_logger_setup"
                    )

        lint_note = self._infer_lint_note()
        if lint_note:
            lines.append(lint_note)

        lines.append("```")
        return lines

    def _pick_single_test_target(self) -> Optional[str]:
        preferred = self.root_dir / "tests" / "test_basic.py"
        if preferred.exists():
            return "tests/test_basic.py"

        for path in sorted((self.root_dir / "tests").rglob("test_*.py")):
            rel = path.relative_to(self.root_dir).as_posix()
            if "__pycache__" not in rel:
                return rel
        return None

    def _infer_lint_note(self) -> Optional[str]:
        contributing = self._read_text(self.root_dir / "CONTRIBUTING.md", max_chars=12000)
        mentions_black = "`black`" in contributing or "black " in contributing
        mentions_isort = "`isort`" in contributing or "isort " in contributing
        if mentions_black and mentions_isort:
            return "# no lint task is wired in CI; CONTRIBUTING.md recommends black . && isort ."
        return None

    def _build_architecture_section(self) -> List[str]:
        bullets: List[str] = []

        if (self.root_dir / "kogniterm" / "terminal" / "terminal.py").exists():
            bullets.append(
                "- `kogniterm/terminal/terminal.py` is the real entrypoint. It chooses between CLI commands in `terminal/cli.py`, Rich-only `--cli`, and the default Textual TUI."
            )

        if (self.root_dir / "kogniterm" / "core" / "llm_service.py").exists():
            bullets.append(
                "- `kogniterm/core/llm_service.py` is the runtime orchestrator: provider/model selection, fallback routing, tool wiring, workspace context, vector DB access, and conversation history all meet there."
            )

        if all(
            (self.root_dir / "kogniterm" / "core" / part).exists()
            for part in ("agent_state.py", "message_manager.py", "history_manager.py")
        ):
            bullets.append(
                "- Conversation state is split intentionally: `AgentState` carries runtime flags, `MessageManager` handles rewind/sync semantics, and `HistoryManager` persists the LangChain message history."
            )

        if (self.root_dir / "kogniterm" / "core" / "command_executor.py").exists():
            bullets.append(
                "- Shell execution uses `kogniterm/core/command_executor.py`, which keeps a persistent PTY-backed bash session instead of spawning a fresh shell for every command."
            )

        if (self.root_dir / "kogniterm" / "core" / "context" / "codebase_indexer.py").exists():
            bullets.append(
                "- Repo understanding lives under `kogniterm/core/context/`: the indexer scans files, respects ignore rules, chunks code, and persists embeddings in `.kogniterm/vector_db`."
            )

        if (self.root_dir / "kogniterm" / "core" / "skills" / "skill_manager.py").exists():
            bullets.append(
                "- Skills are discovered dynamically from `kogniterm/skills/bundled`, `~/.kogniterm/skills/managed`, and `kogniterm/skills/workspace`."
            )

        if not bullets:
            bullets.append("- Review the repo docs and the top-level package modules first; this repository does not expose its architecture from a single file.")

        return bullets

    def _build_conventions_section(self) -> List[str]:
        bullets: List[str] = []
        main_py = self._read_text(self.root_dir / "kogniterm" / "main.py", max_chars=1000)
        if "ya no es el punto de entrada principal" in main_py:
            bullets.append(
                "- Do not route new startup behavior through `kogniterm/main.py`; it is kept only as an obsolete stub."
            )

        if (self.root_dir / "kogniterm" / "terminal" / "config_manager.py").exists():
            bullets.append(
                "- Configuration is layered: `~/.kogniterm/config.json` is global and `.kogniterm/config.json` in the workspace overrides it."
            )

        if (self.root_dir / "kogniterm" / "core" / "skills" / "skill_manager.py").exists():
            bullets.append(
                "- Skills follow the open `SKILL.md` folder format: `SKILL.md` is required, while `scripts/`, `references/`, `assets/`, and `resources/` are optional depending on whether the skill is prompt-only or executable."
            )

        terminal_py = self._read_text(
            self.root_dir / "kogniterm" / "terminal" / "terminal.py",
            max_chars=6000,
        )
        if "lazy dependency loading" in terminal_py or "Heavy imports moved inside functions" in terminal_py:
            bullets.append(
                "- Startup code favors lazy imports to keep launch time down; preserve that pattern when adding new integrations."
            )

        if (self.root_dir / ".kogniterm").exists() or (self.root_dir / "kogniterm").exists():
            bullets.append(
                "- Project-local runtime state lives under `.kogniterm/` in the workspace, including history, logs, sessions, vector DB data, and memory files."
            )

        readme = self._read_text(self.root_dir / "README.md", max_chars=12000)
        if any(token in readme for token in (" es ", " tu ", " asistente ", "terminal inteligente")):
            bullets.append(
                "- Much of the documentation and user-facing text is in Spanish; match the language already used in the file you are editing."
            )

        return bullets

    def _read_text(self, path: Path, max_chars: int) -> str:
        if not path.exists() or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        except OSError:
            return ""

    def _load_pyproject(self) -> dict:
        pyproject_path = self.root_dir / "pyproject.toml"
        if not pyproject_path.exists():
            return {}
        try:
            with pyproject_path.open("rb") as f:
                return tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            return {}
