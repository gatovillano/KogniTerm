# Task 2 Report: Config-driven Agents (Agentes Declarativos por Configuración)

## What was implemented

We implemented declarative, config-driven agent definitions loaded from YAML or Markdown files. This allows specifying the agent's role, allowed tools, and system prompt in a modular, declarative way without hardcoding them in the tool scripts.

Key changes:
1. Created `AgentConfigManager` in `kogniterm/core/agents/config_manager.py` which searches for agent definition files (under `.agents/`, `~/.kogniterm/agents/`, and default configurations packaged with the app) and parses them.
2. Parsed Frontmatter YAML from `.md` files or full `.yaml`/`.yml` documents.
3. Created default configuration files:
   - `kogniterm/core/agents/config/code_agent.yaml`
   - `kogniterm/core/agents/config/researcher_agent.yaml`
4. Integrated `AgentConfigManager` into the delegation pipeline in:
   - `kogniterm/skills/bundled/call-agent/scripts/tool.py` (resolving role, allowed tools, system prompt)
   - `kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py` (resolving role and system prompt, and blocking non-allowed tools)

---

## TDD Evidence

### RED State
We wrote the unit tests first in `tests/unit/test_agent_config_manager.py` and ran them before implementing the config manager.

**Command:**
```bash
venv/bin/pytest tests/unit/test_agent_config_manager.py -v
```

**Output:**
```
___________ ERROR collecting tests/unit/test_agent_config_manager.py ___________
ImportError while importing test module '/home/gato/Proyectos/Gemini-Interpreter/tests/unit/test_agent_config_manager.py'.
...
E   ModuleNotFoundError: No module named 'kogniterm.core.agents.config_manager'
```

**Why the failure was expected:** The config manager module had not yet been created, leading to a standard `ModuleNotFoundError`.

### GREEN State
We implemented the config manager and resolved the missing dependencies and tests.

**Command:**
```bash
venv/bin/pytest tests/unit/test_agent_config_manager.py -v
```

**Output:**
```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.1.1, pluggy-1.6.0
collected 3 items

tests/unit/test_agent_config_manager.py::test_agent_config_loading PASSED [ 33%]
tests/unit/test_agent_config_manager.py::test_call_agent_skill_loads_declarative_config PASSED [ 66%]
tests/unit/test_agent_config_manager.py::test_call_agents_parallel_loads_declarative_config PASSED [100%]

============================== 3 passed in 3.26s ===============================
```

---

## What was tested and test results

We ran the focused test suite for `AgentConfigManager` as well as the unit tests for `delegation.py` and `parallel_agent_completion.py`.

- `tests/unit/test_agent_config_manager.py`: 3/3 passed.
- `tests/unit/test_delegation.py`: 7/7 passed.
- `tests/unit/test_parallel_agent_completion.py`: 5/5 passed.

---

## Files changed

- **Created:**
  - `kogniterm/core/agents/config_manager.py` (AgentConfigManager class)
  - `kogniterm/core/agents/config/code_agent.yaml` (Default code agent config)
  - `kogniterm/core/agents/config/researcher_agent.yaml` (Default researcher agent config)
  - `tests/unit/test_agent_config_manager.py` (Unit tests)
- **Modified:**
  - `kogniterm/skills/bundled/call-agent/scripts/tool.py` (Integrated config manager)
  - `kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py` (Integrated config manager)
  - `tests/unit/test_delegation.py` (Fixed test mocks and assertions to match new/existing delegation behavior)
  - `kogniterm/terminal/tui/tui_app.py` (Fixed a syntax error from a missing except block in a try-except structure)

---

## Self-review findings

- **Spec Completeness:** Fully completed according to the task brief.
- **Naming Clear and Accurate:** Names like `AgentConfigManager` and its methods match standard conventions.
- **Code Cleanliness:** Used clear, readable imports and exception handling for YAML parsing. Added dynamic module loading (`importlib`) in tests to handle the module path containing a dash (`call-agent`).
- **Tests Verify Behavior:** Tests verify loading YAML/Markdown configs, and checking that the loaded settings are correctly propagated during both simple and parallel agent delegation.

---

## Issues or Concerns

No remaining issues. All tests are passing cleanly.
