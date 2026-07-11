# KogniTerm Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement five key evolution recommendations in KogniTerm: configuration-driven agents, real async delegation with `AgentPool`, granular command regex permissions, decoupling `AgentInteractionManager`, and session telemetry.

**Architecture:** Create modular classes under the `core` layer (`config_manager`, `agent_pool`, `command_rules`, `telemetry`, `agent_interaction`) and integrate them into existing tools/handlers while decoupling core imports from UI.

**Tech Stack:** Python 3.10+, asyncio, Pydantic, LangChain, LangGraph, pytest.

## Global Constraints
- Do not import `kogniterm.terminal.*` or `kogniterm.server.*` directly in `kogniterm/core/` unless explicitly managed by lazy registries.
- Ensure terminal compatibility with ECHO-less environments: always verify that command markers (`##KOGNITERM_DONE_MARKER##`) are not stripped or confused with command echoes.
- Persist telemetry files locally under the active session workspace at `.kogniterm/telemetry/session_<id>.json`.

---

### Task 1: Reducción de Acoplamiento (Aislamiento de `AgentInteractionManager`)

**Files:**
- Create: `kogniterm/core/agent_interaction.py`
- Modify: `kogniterm/terminal/agent_interaction_manager.py`
- Modify: `kogniterm/server/session_pool.py:70-75`, `645-655`
- Create Test: `tests/unit/test_decoupling.py`

**Interfaces:**
- Consumes: None
- Produces: `BaseAgentInteractionManager` (Abstract base class) and `AgentInteractionRegistry` (Factory registry)

- [ ] **Step 1: Write the failing test**
  Create `tests/unit/test_decoupling.py`:
  ```python
  import pytest
  from kogniterm.core.agent_interaction import BaseAgentInteractionManager, AgentInteractionRegistry

  def test_registry_raises_unregistered():
      with pytest.raises(RuntimeError, match="La factory de AgentInteractionManager no ha sido registrada"):
          AgentInteractionRegistry.create()

  def test_registry_instantiates_registered():
      class DummyManager(BaseAgentInteractionManager):
          def __init__(self, x):
              self.x = x
          def invoke_agent(self, user_input):
              return {"status": "ok", "x": self.x}

      AgentInteractionRegistry.register_factory(DummyManager)
      manager = AgentInteractionRegistry.create(x=10)
      assert isinstance(manager, BaseAgentInteractionManager)
      assert manager.invoke_agent("test") == {"status": "ok", "x": 10}
      # Cleanup registry
      AgentInteractionRegistry._factory = None
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/unit/test_decoupling.py -v`
  Expected: FAIL with `ModuleNotFoundError` for `kogniterm.core.agent_interaction`

- [ ] **Step 3: Write minimal implementation**
  Create `kogniterm/core/agent_interaction.py`:
  ```python
  from abc import ABC, abstractmethod
  from typing import Dict, Any, Optional

  class BaseAgentInteractionManager(ABC):
      @abstractmethod
      def invoke_agent(self, user_input: Optional[str]) -> Dict[str, Any]:
          pass

  class AgentInteractionRegistry:
      _factory = None

      @classmethod
      def register_factory(cls, factory):
          cls._factory = factory

      @classmethod
      def create(cls, *args, **kwargs) -> BaseAgentInteractionManager:
          if cls._factory is None:
              raise RuntimeError(
                  "Error de Arquitectura: La factory de AgentInteractionManager no ha sido registrada. "
                  "Asegúrate de que la capa de UI/Terminal la registre al inicio."
              )
          return cls._factory(*args, **kwargs)
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/unit/test_decoupling.py -v`
  Expected: PASS

- [ ] **Step 5: Inherit from interface and register in terminal**
  Modify `kogniterm/terminal/agent_interaction_manager.py` to inherit and register at module load time:
  ```python
  # at the top
  from kogniterm.core.agent_interaction import BaseAgentInteractionManager, AgentInteractionRegistry

  # class definition
  class AgentInteractionManager(BaseAgentInteractionManager):
      # ... (keep existing implementation)

  # at the end of the file
  AgentInteractionRegistry.register_factory(AgentInteractionManager)
  ```

- [ ] **Step 6: Update server to use registry**
  Modify `kogniterm/server/session_pool.py`:
  Replace the import `from kogniterm.terminal.agent_interaction_manager import AgentInteractionManager` with:
  ```python
  from kogniterm.core.agent_interaction import AgentInteractionRegistry
  ```
  Replace lines 648-655 where `AgentInteractionManager` was instantiated:
  ```python
  # Gestor de interacción (crea el grafo LangGraph)
  self.manager = AgentInteractionRegistry.create(
      llm_service=llm_service,
      agent_state=self.agent_state,
      terminal_ui=self.ui,
      interrupt_queue=self.interrupt_queue,
      command_approval_handler=self.command_approval_handler,
  )
  ```

- [ ] **Step 7: Verify all existing tests still pass**
  Run: `pytest tests/unit/ -v`
  Expected: PASS (especially `tests/unit/test_server_stop.py` or other server tests)

- [ ] **Step 8: Commit**
  ```bash
  git add kogniterm/core/agent_interaction.py kogniterm/terminal/agent_interaction_manager.py kogniterm/server/session_pool.py tests/unit/test_decoupling.py
  git commit -m "feat: decouple AgentInteractionManager using registry interface"
  ```

---

### Task 2: Config-driven Agents (Agentes Declarativos por Configuración)

**Files:**
- Create: `kogniterm/core/agents/config_manager.py`
- Create Default Configs:
  - `kogniterm/core/agents/config/code_agent.yaml`
  - `kogniterm/core/agents/config/researcher_agent.yaml`
- Modify: `kogniterm/skills/bundled/call-agent/scripts/tool.py`
- Modify: `kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py`
- Create Test: `tests/unit/test_agent_config_manager.py`

**Interfaces:**
- Consumes: None
- Produces: `AgentConfigManager` class exposing `get_agent_config(agent_name)`

- [ ] **Step 1: Write the failing test**
  Create `tests/unit/test_agent_config_manager.py`:
  ```python
  import os
  import shutil
  import pytest
  from pathlib import Path
  from kogniterm.core.agents.config_manager import AgentConfigManager

  @pytest.fixture
  def temp_config_dir(tmp_path):
      workspace_dir = tmp_path / "workspace"
      workspace_dir.mkdir()
      agents_dir = workspace_dir / ".agents"
      agents_dir.mkdir()
      
      # Write a markdown agent file
      md_content = """---
name: test_md_agent
description: "Test agent description"
role: leaf
allowed_tools:
  - file_operations
---
System prompt from markdown body.
"""
      with open(agents_dir / "test_md_agent.md", "w") as f:
          f.write(md_content)
          
      # Write a yaml agent file
      yaml_content = """
name: test_yaml_agent
description: "Test yaml agent"
role: orchestrator
allowed_tools:
  - execute_command
system_prompt: "System prompt from yaml key."
"""
      with open(agents_dir / "test_yaml_agent.yaml", "w") as f:
          f.write(yaml_content)
          
      return workspace_dir

  def test_agent_config_loading(temp_config_dir):
      manager = AgentConfigManager(workspace_dir=str(temp_config_dir))
      manager.discover_configs()
      
      # Test Markdown Agent
      md_config = manager.get_agent_config("test_md_agent")
      assert md_config is not None
      assert md_config["name"] == "test_md_agent"
      assert md_config["role"] == "leaf"
      assert md_config["allowed_tools"] == ["file_operations"]
      assert "System prompt from markdown body." in md_config["system_prompt"]
      
      # Test YAML Agent
      yaml_config = manager.get_agent_config("test_yaml_agent")
      assert yaml_config is not None
      assert yaml_config["name"] == "test_yaml_agent"
      assert yaml_config["role"] == "orchestrator"
      assert yaml_config["allowed_tools"] == ["execute_command"]
      assert yaml_config["system_prompt"] == "System prompt from yaml key."
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/unit/test_agent_config_manager.py -v`
  Expected: FAIL with `ModuleNotFoundError` for `kogniterm.core.agents.config_manager`

- [ ] **Step 3: Write AgentConfigManager implementation**
  Create `kogniterm/core/agents/config_manager.py`:
  ```python
  import os
  import yaml
  from pathlib import Path
  from typing import Dict, Any, Optional

  class AgentConfigManager:
      def __init__(self, workspace_dir: Optional[str] = None):
          self.workspace_dir = workspace_dir or os.getcwd()
          self.configs: Dict[str, Dict[str, Any]] = {}
          
      def discover_configs(self):
          self.configs.clear()
          
          # Paths to search (ordered by priority: project -> user -> default)
          paths = [
              Path(self.workspace_dir) / ".agents",
              Path.home() / ".kogniterm" / "agents",
              Path(__file__).parent / "config"
          ]
          
          for path in paths:
              if not path.exists() or not path.is_dir():
                  continue
              for file_path in path.glob("*"):
                  if file_path.name == "AGENTS.md":  # Skip system rules file
                      continue
                  if file_path.suffix in (".yaml", ".yml", ".md"):
                      try:
                          self._parse_file(file_path)
                      except Exception as e:
                          import logging
                          logging.getLogger(__name__).warning(f"Error parsing agent config {file_path}: {e}")

      def _parse_file(self, file_path: Path):
          content = file_path.read_text(encoding="utf-8")
          config = {}
          
          if file_path.suffix == ".md":
              if content.startswith("---"):
                  end_idx = content.find("---", 3)
                  if end_idx != -1:
                      yaml_content = content[3:end_idx].strip()
                      body = content[end_idx + 3:].strip()
                      config = yaml.safe_load(yaml_content) or {}
                      if "system_prompt" not in config:
                          config["system_prompt"] = body
          else:
              config = yaml.safe_load(content) or {}
              
          if "name" in config:
              name = config["name"]
              # Only set if not already set by a higher priority directory
              if name not in self.configs:
                  self.configs[name] = config

      def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
          if not self.configs:
              self.discover_configs()
          return self.configs.get(agent_name)
  ```

- [ ] **Step 4: Create default YAML config files**
  Create directory `kogniterm/core/agents/config/` and default configuration files.
  Create `kogniterm/core/agents/config/code_agent.yaml`:
  ```yaml
  name: code_agent
  description: "Desarrollador profundo de software (DeepCoder)"
  role: leaf
  allowed_tools:
    - file_operations
    - execute_command
  system_prompt: |
    Eres el DeepCoder de KogniTerm. Escribe, edita y valida código basándote en la tarea asignada.
  ```
  Create `kogniterm/core/agents/config/researcher_agent.yaml`:
  ```yaml
  name: researcher_agent
  description: "Investigador profundo de código y web (DeepResearcher)"
  role: leaf
  allowed_tools:
    - codebase_search_tool
    - file_read_directory
    - web_search
  system_prompt: |
    Eres el DeepResearcher de KogniTerm. Realiza un análisis exhaustivo del código, lee archivos y busca en la web para encontrar respuestas precisas.
  ```

- [ ] **Step 5: Run test to verify it passes**
  Run: `pytest tests/unit/test_agent_config_manager.py -v`
  Expected: PASS

- [ ] **Step 6: Integrate AgentConfigManager into call_agent tool**
  Modify `kogniterm/skills/bundled/call-agent/scripts/tool.py` at line 225 inside `call_agent_skill`:
  ```python
      # --- Resolver la configuración del agente declarativamente ---
      from kogniterm.core.agents.config_manager import AgentConfigManager
      config_mgr = AgentConfigManager(workspace_dir=getattr(llm_service, "current_workspace_dir", None))
      config_mgr.discover_configs()
      agent_config = config_mgr.get_agent_config(agent_name)
      
      if agent_config:
          # Usar los valores del archivo de configuración
          role_str = agent_config.get("role", "leaf").lower()
          role = AgentRole.ORCHESTRATOR if role_str == "orchestrator" else AgentRole.LEAF
          if allowed_tools is None:
              allowed_tools = agent_config.get("allowed_tools")
          if custom_system_prompt is None:
              custom_system_prompt = agent_config.get("system_prompt")
  ```

- [ ] **Step 7: Integrate AgentConfigManager into call_agents_parallel tool**
  Modify `kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py` at line 433 inside `run_agent_async`:
  ```python
          # --- Resolver la configuración del agente declarativamente ---
          from kogniterm.core.agents.config_manager import AgentConfigManager
          config_mgr = AgentConfigManager(workspace_dir=getattr(llm_service, "current_workspace_dir", None))
          config_mgr.discover_configs()
          agent_config = config_mgr.get_agent_config(agent_type) or config_mgr.get_agent_config(name)
          
          if agent_config:
              role_str = agent_config.get("role", "leaf").lower()
              role = AgentRole.ORCHESTRATOR if role_str == "orchestrator" else AgentRole.LEAF
              if not system_prompt:
                  system_prompt = agent_config.get("system_prompt")
  ```

- [ ] **Step 8: Run all unit tests to check for regressions**
  Run: `pytest tests/unit/ -v`
  Expected: PASS

- [ ] **Step 9: Commit**
  ```bash
  git add kogniterm/core/agents/config_manager.py kogniterm/core/agents/config/ kogniterm/skills/bundled/call-agent/scripts/tool.py kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py tests/unit/test_agent_config_manager.py
  git commit -m "feat: implement config-driven agents loading YAML/Markdown configs"
  ```

---

### Task 3: Permisos Granulares por Comando (allow/ask/deny)

**Files:**
- Create: `kogniterm/core/delegation/command_rules.py`
- Modify: `kogniterm/terminal/command_approval_handler.py:265-320`, `425-443`, `500-525`
- Create Test: `tests/unit/test_command_rules.py`

**Interfaces:**
- Consumes: None
- Produces: `CommandRulesResolver` class matching command strings to actions (`allow`, `ask`, `deny`).

- [ ] **Step 1: Write the failing test**
  Create `tests/unit/test_command_rules.py`:
  ```python
  import pytest
  from pathlib import Path
  from kogniterm.core.delegation.command_rules import CommandRulesResolver

  @pytest.fixture
  def temp_rules_file(tmp_path):
      rules_content = """
rules:
  - pattern: "^git status$"
    action: "allow"
  - pattern: "^rm -rf .*$"
    action: "deny"
  - pattern: "^sudo .*$"
    action: "deny"
  - pattern: "^pip install .*$"
    action: "ask"
"""
      rules_file = tmp_path / "command_rules.yaml"
      rules_file.write_text(rules_content)
      return rules_file

  def test_rules_resolution(temp_rules_file):
      resolver = CommandRulesResolver(rules_file_path=str(temp_rules_file))
      resolver.load_rules()
      
      assert resolver.resolve("git status") == "allow"
      assert resolver.resolve("rm -rf /") == "deny"
      assert resolver.resolve("sudo apt get install") == "deny"
      assert resolver.resolve("pip install flask") == "ask"
      assert resolver.resolve("cat README.md") == "ask"  # default action
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/unit/test_command_rules.py -v`
  Expected: FAIL with `ModuleNotFoundError` for `kogniterm.core.delegation.command_rules`

- [ ] **Step 3: Write CommandRulesResolver implementation**
  Create `kogniterm/core/delegation/command_rules.py`:
  ```python
  import os
  import re
  import yaml
  from typing import List, Dict, Any, Optional

  class CommandRulesResolver:
      def __init__(self, rules_file_path: Optional[str] = None):
          self.rules_file_path = rules_file_path
          self.rules: List[Dict[str, str]] = []
          
      def load_rules(self):
          self.rules.clear()
          
          # Default rules
          self.rules = [
              {"pattern": r"^git status$", "action": "allow"},
              {"pattern": r"^git diff$", "action": "allow"},
              {"pattern": r"^git log.*$", "action": "allow"},
              {"pattern": r"^ls(\s+.*)?$", "action": "allow"},
              {"pattern": r"^pwd$", "action": "allow"},
              {"pattern": r"^whoami$", "action": "allow"},
              {"pattern": r"^date$", "action": "allow"},
              {"pattern": r"^rm\s+-rf\s+.*$", "action": "deny"},
              {"pattern": r"^sudo\s+.*$", "action": "deny"},
          ]
          
          # Determine path to user rules
          path_candidates = []
          if self.rules_file_path:
              path_candidates.append(self.rules_file_path)
          else:
              # Workspace and global candidates
              path_candidates.extend([
                  os.path.join(os.getcwd(), ".agents", "command_rules.yaml"),
                  os.path.join(os.path.expanduser("~"), ".kogniterm", "command_rules.yaml")
              ])
              
          for path in path_candidates:
              if os.path.exists(path):
                  try:
                      with open(path, "r", encoding="utf-8") as f:
                          data = yaml.safe_load(f) or {}
                          user_rules = data.get("rules", [])
                          if user_rules:
                              # Put user rules at the beginning of the list to take precedence
                              self.rules = user_rules + self.rules
                              break
                  except Exception as e:
                      import logging
                      logging.getLogger(__name__).warning(f"Error loading command rules from {path}: {e}")

      def resolve(self, command: str) -> str:
          if not self.rules:
              self.load_rules()
              
          cmd_stripped = command.strip()
          for rule in self.rules:
              pattern = rule.get("pattern")
              action = rule.get("action")
              if pattern and action:
                  try:
                      if re.match(pattern, cmd_stripped):
                          return action
                  except re.error:
                      pass
                      
          return "ask"  # default fallback action
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/unit/test_command_rules.py -v`
  Expected: PASS

- [ ] **Step 5: Integrate resolved rules into CommandApprovalHandler**
  Modify `kogniterm/terminal/command_approval_handler.py`:
  Import the resolver at the top:
  ```python
  from kogniterm.core.delegation.command_rules import CommandRulesResolver
  ```
  Initialize `self.rules_resolver` inside `CommandApprovalHandler.__init__`:
  ```python
  self.rules_resolver = CommandRulesResolver()
  self.rules_resolver.load_rules()
  ```
  Modify the `handle_command_approval` method. At the start of validation check:
  ```python
          # --- Resolver la acción por comando declarativo (allow/ask/deny) ---
          resolved_action = "ask"
          if command_to_execute:
              resolved_action = self.rules_resolver.resolve(command_to_execute)
              logger.info(f"CommandRulesResolver: '{command_to_execute}' -> {resolved_action}")
              
          if resolved_action == "deny":
              # Retornar denegado de forma inmediata
              tool_message_content = "Error: El comando fue denegado por las políticas de seguridad."
              self.terminal_ui.print_error_box("Comando denegado por la directiva de seguridad.", "Seguridad KogniTerm")
              self.agent_state.messages.append(AIMessage(content=tool_message_content))
              self.llm_service._save_history(self.agent_state.messages)
              return {
                  "messages": self.agent_state.messages,
                  "tool_message_content": tool_message_content,
                  "approved": False,
                  "command_output": ""
              }
              
          if resolved_action == "allow":
              auto_approve = True
  ```

- [ ] **Step 6: Run existing tests to ensure no breakages**
  Run: `pytest tests/unit/test_delegation.py -v`
  Expected: PASS (ensuring default agent roles/permissions work fine)

- [ ] **Step 7: Commit**
  ```bash
  git add kogniterm/core/delegation/command_rules.py kogniterm/terminal/command_approval_handler.py tests/unit/test_command_rules.py
  git commit -m "feat: implement granular command permissions with regex matching rules"
  ```

---

### Task 4: Delegación Asíncrona Real (`AgentPool`)

**Files:**
- Create: `kogniterm/core/delegation/agent_pool.py`
- Modify: `kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py:590-636`
- Create Test: `tests/unit/test_agent_pool.py`

**Interfaces:**
- Consumes: `create_dynamic_agent` from `kogniterm/core/agents/dynamic_agent.py`
- Produces: `AgentPool` class executing graphs concurrently via `ainvoke`

- [ ] **Step 1: Write the failing test**
  Create `tests/unit/test_agent_pool.py`:
  ```python
  import pytest
  import asyncio
  from kogniterm.core.delegation.agent_pool import AgentPool

  @pytest.mark.asyncio
  async def test_agent_pool_execution():
      pool = AgentPool(max_concurrent=2)
      
      # Mock graphs
      class DummyGraph:
          def __init__(self, val):
              self.val = val
          async def ainvoke(self, state, config=None):
              await asyncio.sleep(0.1)
              return {"messages": ["done_" + self.val]}
              
      agents_to_run = [
          {"id": "a1", "graph": DummyGraph("1"), "initial_state": {}, "recursion_limit": 100},
          {"id": "a2", "graph": DummyGraph("2"), "initial_state": {}, "recursion_limit": 100}
      ]
      
      results = await pool.execute_parallel(agents_to_run)
      
      assert len(results) == 2
      assert results[0] == {"messages": ["done_1"]}
      assert results[1] == {"messages": ["done_2"]}
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/unit/test_agent_pool.py -v`
  Expected: FAIL with `ModuleNotFoundError` for `kogniterm.core.delegation.agent_pool`

- [ ] **Step 3: Write AgentPool implementation**
  Create `kogniterm/core/delegation/agent_pool.py`:
  ```python
  import asyncio
  import logging
  from typing import List, Dict, Any, Optional

  logger = logging.getLogger(__name__)

  class AgentPool:
      """
      Administra la ejecución paralela y asíncrona de múltiples subagentes.
      Encapsula el paralelismo verdadero usando asyncio.Semaphore.
      """
      def __init__(self, max_concurrent: int = 5):
          self.semaphore = asyncio.Semaphore(max_concurrent)
          self.active_tasks: Dict[str, asyncio.Task] = {}

      async def execute_agent(self, agent_id: str, agent_graph: Any, initial_state: Any, recursion_limit: int) -> Any:
          async with self.semaphore:
              logger.info(f"AgentPool: Iniciando ejecución de subagente {agent_id}")
              try:
                  return await agent_graph.ainvoke(
                      initial_state,
                      config={"recursion_limit": recursion_limit}
                  )
              except Exception as e:
                  logger.exception(f"AgentPool: Error en subagente {agent_id}: {e}")
                  raise e

      async def execute_parallel(self, agents_to_run: List[Dict[str, Any]]) -> List[Any]:
          tasks = []
          for spec in agents_to_run:
              agent_id = spec["id"]
              graph = spec["graph"]
              initial_state = spec["initial_state"]
              limit = spec.get("recursion_limit", 1000)
              
              task = asyncio.create_task(
                  self.execute_agent(agent_id, graph, initial_state, limit)
              )
              self.active_tasks[agent_id] = task
              tasks.append(task)
              
          try:
              results = await asyncio.gather(*tasks, return_exceptions=True)
              return results
          finally:
              for spec in agents_to_run:
                  self.active_tasks.pop(spec["id"], None)
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/unit/test_agent_pool.py -v`
  Expected: PASS

- [ ] **Step 5: Integrate AgentPool into call_agents_parallel**
  Modify `kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py`:
  Import `AgentPool`:
  ```python
  from kogniterm.core.delegation.agent_pool import AgentPool
  ```
  Replace the async method `_run_all_parallel` inside `call_agents_parallel`:
  ```python
      async def _run_all_parallel():
          pool = AgentPool(max_concurrent=len(authorized))
          
          agents_specs = []
          for spec, agent_ui, pid in zip(authorized, agent_uis, panel_ids):
              # Configurar el subagente
              name = spec.get("name", "Agente")
              task = spec.get("task", "")
              agent_type = spec.get("type") or spec.get("name", "dynamic_agent")
              system_prompt = spec.get("system_prompt")
              
              # Resolve default instructions
              task_message = (
                  f"{task}\n\n"
                  "---\n"
                  "⚠️ **REGLAS CRÍTICAS DE SUB-AGENTE AUTÓNOMO** ⚠️\n"
                  "1. **NO INTERACTÚAS CON EL USUARIO**: Toma decisiones de forma autónoma.\n"
                  "2. **task_tracker**: Inicializa y actualiza la herramienta task_tracker.\n"
                  "3. 🏁 **FINALIZACIÓN COMPLETA CON `complete_task`**."
              )
              if system_prompt:
                  system_prompt = f"{system_prompt}\n\n🏁 **IMPORTANTE**: Eres un subagente autónomo. Usa complete_task al finalizar."
                  
              agent_graph = _build_agent_graph(
                  agent_type, system_prompt, llm_service, agent_ui, interrupt_queue
              )
              initial_state = AgentState(
                  messages=[_HumanMessage(content=task_message)],
                  autonomous_approvals=True,
              )
              
              # Obtener y setear contextos de delegación
              import uuid
              from kogniterm.core.delegation import AgentRole
              child_id = f"child_{name}_{uuid.uuid4().hex[:8]}"
              child_ctx = None
              if llm_service and hasattr(llm_service, "delegation_manager") and llm_service.delegation_manager:
                  child_ctx = llm_service.delegation_manager.register_agent(
                      agent_id=child_id, parent_id="parallel_orchestrator", role=AgentRole.LEAF
                  )
              if child_ctx:
                  initial_state.delegation_context = child_ctx
                  
              agents_specs.append({
                  "id": child_id,
                  "graph": agent_graph,
                  "initial_state": initial_state,
                  "recursion_limit": AGENT_RECURSION_LIMIT,
                  "name": name,
                  "pid": pid,
                  "child_ctx": child_ctx
              })

          # Lanzar todo asíncronamente vía AgentPool
          pool_specs = [{"id": a["id"], "graph": a["graph"], "initial_state": a["initial_state"], "recursion_limit": a["recursion_limit"]} for a in agents_specs]
          results = await pool.execute_parallel(pool_specs)
          
          # Desregistrar agentes y limpiar
          final_results = []
          for i, res in enumerate(results):
              spec = agents_specs[i]
              child_id = spec["id"]
              child_ctx = spec["child_ctx"]
              pid = spec["pid"]
              name = spec["name"]
              
              if isinstance(res, Exception):
                  logger.error(f"Error en ejecución del subagente {name}: {res}")
                  final_results.append(res)
              else:
                  # Extraer el resultado del complete_task
                  status_emoji = "🏁"
                  if child_ctx and child_ctx.metadata.get("completed"):
                      result_str = child_ctx.metadata.get("result", "Sin respuesta")
                      status_emoji = "✅"
                  else:
                      msgs = res.get("messages", [])
                      result_str = "Sin respuesta"
                      if msgs:
                          for m in reversed(msgs):
                              content_str = str(getattr(m, "content", "") or "").strip()
                              if content_str and len(content_str) > 5:
                                  result_str = content_str
                                  break
                  
                  if terminal_ui and hasattr(terminal_ui, "print_message"):
                      terminal_ui.print_message(f"🏁 **Agente ({name}) completó su tarea.**")
                  final_results.append((name, result_str))
                  
              # Cleanup
              if llm_service and hasattr(llm_service, "delegation_manager") and llm_service.delegation_manager:
                  llm_service.delegation_manager.unregister_agent(child_id)
                  
          try:
              _deactivate_parallel_container(
                  panel_ids, terminal_ui, server_mode, is_tui_local, target_app
              )
          except Exception as e:
              logger.exception("Error al desactivar el contenedor de agentes: %s", e)
              
          return final_results
  ```

- [ ] **Step 6: Run parallel agent unit tests to ensure compatibility**
  Run: `pytest tests/unit/test_parallel_agent_completion.py -v`
  Expected: PASS

- [ ] **Step 7: Commit**
  ```bash
  git add kogniterm/core/delegation/agent_pool.py kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py tests/unit/test_agent_pool.py
  git commit -m "feat: implement AgentPool for true async delegation using ainvoke"
  ```

---

### Task 5: Telemetría de Sesión (`KiloSession`-like)

**Files:**
- Create: `kogniterm/core/delegation/telemetry.py`
- Modify: `kogniterm/core/llm_service.py`
- Modify: `kogniterm/skills/bundled/call-agent/scripts/tool.py`
- Modify: `kogniterm/skills/bundled/call-agents-parallel/scripts/tool.py`
- Modify: `kogniterm/server/session_pool.py`
- Create Test: `tests/unit/test_telemetry.py`

**Interfaces:**
- Consumes: None
- Produces: `TelemetryTracker` class recording traces and calculating API costs per session.

- [ ] **Step 1: Write the failing test**
  Create `tests/unit/test_telemetry.py`:
  ```python
  import os
  import json
  import pytest
  from kogniterm.core.delegation.telemetry import TelemetryTracker

  def test_telemetry_recording(tmp_path):
      tracker = TelemetryTracker(session_id="test_session", workspace_dir=str(tmp_path))
      
      tracker.record_llm_call(model="gemini-1.5-pro", input_tokens=1000, output_tokens=500, cost=0.015)
      tracker.record_delegation(
          subagent_id="child_1",
          subagent_name="tester",
          task="write unit tests",
          depth=1,
          status="success",
          duration=2.5,
          summary="All tests passed"
      )
      
      # Verify saved JSON trace
      trace_file = tmp_path / ".kogniterm" / "telemetry" / "session_test_session.json"
      assert trace_file.exists()
      
      with open(trace_file, "r") as f:
          data = json.load(f)
          
      assert data["session_id"] == "test_session"
      assert data["total_cost"] == 0.015
      assert data["total_input_tokens"] == 1000
      assert len(data["llm_calls"]) == 1
      assert len(data["delegations"]) == 1
      assert data["delegations"][0]["subagent_name"] == "tester"
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/unit/test_telemetry.py -v`
  Expected: FAIL with `ModuleNotFoundError` for `kogniterm.core.delegation.telemetry`

- [ ] **Step 3: Write TelemetryTracker implementation**
  Create `kogniterm/core/delegation/telemetry.py`:
  ```python
  import json
  import os
  import time
  from dataclasses import dataclass, field, asdict
  from typing import List, Dict, Any, Optional

  @dataclass
  class LLMCallTrace:
      model: str
      input_tokens: int
      output_tokens: int
      cost: float
      timestamp: float = field(default_factory=time.time)

  @dataclass
  class DelegationTrace:
      subagent_id: str
      subagent_name: str
      task: str
      depth: int
      status: str
      duration: float
      summary: str
      timestamp: float = field(default_factory=time.time)

  class TelemetryTracker:
      def __init__(self, session_id: str, workspace_dir: str):
          self.session_id = session_id
          self.workspace_dir = workspace_dir
          self.start_time = time.time()
          self.llm_calls: List[LLMCallTrace] = []
          self.delegations: List[DelegationTrace] = []
          self.total_cost = 0.0
          self.total_input_tokens = 0
          self.total_output_tokens = 0

      def record_llm_call(self, model: str, input_tokens: int, output_tokens: int, cost: float):
          trace = LLMCallTrace(model, input_tokens, output_tokens, cost)
          self.llm_calls.append(trace)
          self.total_cost += cost
          self.total_input_tokens += input_tokens
          self.total_output_tokens += output_tokens
          self.save_trace()

      def record_delegation(self, subagent_id: str, subagent_name: str, task: str, depth: int, status: str, duration: float, summary: str):
          trace = DelegationTrace(subagent_id, subagent_name, task, depth, status, duration, summary)
          self.delegations.append(trace)
          self.save_trace()

      def save_trace(self):
          telemetry_dir = os.path.join(self.workspace_dir, ".kogniterm", "telemetry")
          os.makedirs(telemetry_dir, exist_ok=True)
          file_path = os.path.join(telemetry_dir, f"session_{self.session_id}.json")
          
          data = {
              "session_id": self.session_id,
              "start_time": self.start_time,
              "end_time": time.time(),
              "total_duration": time.time() - self.start_time,
              "total_cost": self.total_cost,
              "total_input_tokens": self.total_input_tokens,
              "total_output_tokens": self.total_output_tokens,
              "llm_calls": [asdict(c) for c in self.llm_calls],
              "delegations": [asdict(d) for d in self.delegations],
          }
          with open(file_path, "w", encoding="utf-8") as f:
              json.dump(data, f, ensure_ascii=False, indent=2)
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/unit/test_telemetry.py -v`
  Expected: PASS

- [ ] **Step 5: Instantiate and track TelemetryTracker in AgentSession**
  Modify `kogniterm/server/session_pool.py`:
  Import `TelemetryTracker`:
  ```python
  from kogniterm.core.delegation.telemetry import TelemetryTracker
  ```
  In `AgentSession.__init__`, instantiate the tracker:
  ```python
  self.telemetry_tracker = TelemetryTracker(session_id=session_id, workspace_dir=self.workspace_dir)
  llm_service.telemetry_tracker = self.telemetry_tracker
  ```

- [ ] **Step 6: Log token usage and cost in LLMService**
  Modify `kogniterm/core/llm_service.py` to record telemetry after invoking the LLM model.
  Define cost estimation logic using token rates inside `LLMService`:
  ```python
      def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
          # Standard pricing reference (per 1M tokens)
          rates = {
              "gemini-1.5-pro": (7.0, 21.0),
              "gemini-1.5-flash": (0.075, 0.3),
              "claude-3-5-sonnet": (3.0, 15.0),
              "gpt-4o": (5.0, 15.0),
              "gpt-4o-mini": (0.15, 0.6)
          }
          # Default fallback rates if model not found
          rate_in, rate_out = rates.get(model.lower(), (1.0, 3.0))
          return ((input_tokens / 1_000_000) * rate_in) + ((output_tokens / 1_000_000) * rate_out)
  ```
  After getting the final chunk in `LLMService.invoke` (or in LLM call completion logic), parse token counts from provider metadata and record to `self.telemetry_tracker`:
  ```python
          # (Assuming input_tokens and output_tokens are extracted from LLM metadata/response)
          if hasattr(self, "telemetry_tracker") and self.telemetry_tracker:
              # Simple fallback count estimation if provider metadata is not populated
              in_tokens = len(str(history)) // 4
              out_tokens = len(str(full_response)) // 4
              cost = self._estimate_cost(self.model_name or "gemini-1.5-flash", in_tokens, out_tokens)
              self.telemetry_tracker.record_llm_call(
                  model=self.model_name or "gemini-1.5-flash",
                  input_tokens=in_tokens,
                  output_tokens=out_tokens,
                  cost=cost
              )
  ```

- [ ] **Step 7: Log delegation metrics in call_agent & call_agents_parallel tools**
  Modify `call_agent_skill` in `kogniterm/skills/bundled/call-agent/scripts/tool.py` to calculate subagent execution duration and log it:
  ```python
      import time
      t0 = time.time()
      status = "success"
      result_str = ""
      try:
          # ... (run agent code)
          result_str = "..."
      except Exception as e:
          status = "failed"
          result_str = f"Error: {e}"
          raise e
      finally:
          if llm_service and hasattr(llm_service, "telemetry_tracker") and llm_service.telemetry_tracker:
              duration = time.time() - t0
              summary = result_str[:200] + "..." if len(result_str) > 200 else result_str
              llm_service.telemetry_tracker.record_delegation(
                  subagent_id=child_id,
                  subagent_name=agent_name,
                  task=task,
                  depth=getattr(child_ctx, "depth", 1),
                  status=status,
                  duration=duration,
                  summary=summary
              )
  ```

- [ ] **Step 8: Run all tests to verify everything compiles and passes**
  Run: `pytest tests/unit/ -v`
  Expected: PASS

- [ ] **Step 9: Commit**
  ```bash
  git add kogniterm/core/delegation/telemetry.py kogniterm/core/llm_service.py kogniterm/skills/bundled/call-agent/scripts/tool.py kogniterm/server/session_pool.py tests/unit/test_telemetry.py
  git commit -m "feat: integrate KiloSession-like session telemetry costing and delegation traces"
  ```
