# Copilot instructions for KogniTerm

-Siempre debes hacer tu proceso de razonamiento en español.


## Build, test, and lint commands

```bash
# install in editable mode
python -m pip install -e .

# run the app (preferred entrypoint)
python -m kogniterm.terminal.terminal

# equivalent console entrypoint from pyproject.toml
kogniterm

# Rich-only CLI mode instead of the default Textual TUI
kogniterm --cli

# full pytest suite
python -m pytest tests/

# unit / integration subsets via the checked-in helper
python run_tests.py          # full suite
python -c "import run_tests; run_tests.run_unit_tests()"
python -c "import run_tests; run_tests.run_integration_tests()"

# single test file
python -m pytest tests/test_basic.py

# single test function
python -m pytest tests/test_basic.py::test_logger_setup

# smoke test used by the GitHub Actions workflow
python -m pytest tests/test_basic.py
```

There is no repo-managed lint task in `pyproject.toml` or CI. `CONTRIBUTING.md` only recommends `black` for formatting and `isort` for imports when you need them.

## High-level architecture

- The real application entrypoint is `kogniterm/terminal/terminal.py`. `kogniterm/main.py` is explicitly marked obsolete and should not be used as the execution path.
- `terminal/terminal.py` decides between three surfaces: lightweight command handlers in `terminal/cli.py` (`config`, `index`, `models`, `keys`), a Rich-only `--cli` mode, and the default Textual TUI.
- `LLMService` in `kogniterm/core/llm_service.py` is the main runtime orchestrator. It wires together provider/model selection, multi-provider fallback, rate limiting, embeddings/vector DB access, skill loading, tool synchronization, workspace context, and conversation history.
- Conversation state is split across `AgentState`, `MessageManager`, and `HistoryManager`. That split matters: `AgentState` carries runtime flags and pending confirmations, `MessageManager` owns rewind/sync behavior between UI history and API history, and `HistoryManager` persists LangChain messages to `.kogniterm/history.json`.
- Shell execution is not fire-and-forget. `kogniterm/core/command_executor.py` runs commands through a persistent PTY-backed bash session so shell state survives across commands and interactive input can be forwarded.
- Local codebase understanding lives under `kogniterm/core/context/`. `CodebaseIndexer` walks the repo, respects `.gitignore` and `.kognitermignore`, chunks files, and stores embeddings in `.kogniterm/vector_db`. The indexing flow is exposed both from `kogniterm index refresh` and from the TUI.
- Skills are a first-class extension mechanism, not just helper scripts. `kogniterm/core/skills/skill_manager.py` discovers skills from three roots: bundled repo skills (`kogniterm/skills/bundled`), user-managed skills (`~/.kogniterm/skills/managed`), and workspace skills (`kogniterm/skills/workspace`).

## Key conventions

- Prefer editing `kogniterm/terminal/terminal.py` for startup behavior. Do not route new runtime behavior through `kogniterm/main.py`.
- Project-local runtime state is stored in `.kogniterm/` inside the workspace (`history.json`, `config.json`, `vector_db`, sessions, logs, persisted instructions). Many features depend on those files existing in the current working directory, so changes that affect paths or startup should preserve that assumption.
- Config resolution is layered: `~/.kogniterm/config.json` is global, `.kogniterm/config.json` in the repo is project-specific, and project config overrides global config.
- Skill definitions follow a strict layout: each skill directory needs `SKILL.md` with YAML frontmatter plus a `scripts/` directory containing Python tool implementations. Optional reference material lives in `references/`. If you add or change skills, keep that structure intact or the loader will skip/flag them.
- The codebase relies heavily on lazy imports in entrypoint code to keep startup responsive and avoid loading heavy dependencies before the UI mode is chosen. Follow that pattern when adding new startup-time integrations.
- Message/history code uses LangChain message objects (`HumanMessage`, `AIMessage`, `ToolMessage`, `SystemMessage`) as the canonical conversation model. Preserve that representation instead of introducing parallel ad hoc message structures.
- The codebase is bilingual, but user-facing docs and many inline comments are in Spanish. Match the surrounding file instead of normalizing everything to English.
- CI is currently a smoke test, not a full confidence suite: `.github/workflows/tests.yml` installs the package and only runs `tests/test_basic.py`. For risky changes, check targeted tests under `tests/unit`, `tests/integration`, or the specific `tests/test_*.py` module you are touching.
