# Refactorización del Flujo del Agente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactorizar la ejecución de herramientas, carga de skills y estructuración de contexto en KogniTerm para reducir drásticamente la latencia y acelerar la inferencia (3-5x más veloz).

**Architecture:** Implementación de tres módulos desacoplados: JIT Skill Manager (metadatos compactos en system prompt + expansión diferida), Parallel Tool Dispatcher (clasificación de herramientas y dispatch asíncrono concurrente con `asyncio.gather`) y Cache Stabilizer (estabilización de prefijo en contexto para 100% Prompt Caching).

**Tech Stack:** Python 3.10+, asyncio, pytest, LangChain / KogniTerm core message system.

## Global Constraints
- Preservar 100% compatibilidad con la especificación oficial de Agent Skills (`SKILL.md`).
- Mantener la integridad de los mensajes duales en `MessageManager` (`history_for_api` y `messages`).
- Garantizar que las operaciones mutantes (`run_command`, `replace_file_content`) se ejecuten de forma estrictamente secuencial y segura.

---

### Task 1: JIT Skill Manager (`kogniterm/core/skills/jit_skill_manager.py`)

**Files:**
- Create: `kogniterm/core/skills/jit_skill_manager.py`
- Test: `tests/test_jit_skill_manager.py`

**Interfaces:**
- Produces: `JITSkillManager` con métodos `get_compact_headers() -> str`, `resolve_and_expand_skill(skill_name: str) -> str`, `is_skill_active(skill_name: str) -> bool`.

- [ ] **Step 1: Write the failing unit tests for JIT Skill Manager**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jit_skill_manager.py -v`  
Expected: FAIL with "ModuleNotFoundError: No module named 'kogniterm.core.skills.jit_skill_manager'"

- [ ] **Step 3: Implement JITSkillManager**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jit_skill_manager.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kogniterm/core/skills/jit_skill_manager.py tests/test_jit_skill_manager.py
git commit -m "feat: add JITSkillManager for dynamic token-efficient skill loading"
```

---

### Task 2: Parallel Tool Dispatcher (`kogniterm/core/agents/parallel_tool_dispatcher.py`)

**Files:**
- Create: `kogniterm/core/agents/parallel_tool_dispatcher.py`
- Test: `tests/test_parallel_tool_dispatcher.py`

**Interfaces:**
- Consumes: `tool_calls: List[Dict]`, `tool_executor_func: Callable`
- Produces: `ParallelToolDispatcher.execute_tool_calls_parallel(tool_calls, executor_map) -> List[ToolResult]`

- [ ] **Step 1: Write the failing unit tests for Parallel Tool Dispatcher**

```python
import pytest
import asyncio
import time
from kogniterm.core.agents.parallel_tool_dispatcher import ParallelToolDispatcher, ToolCallItem

@pytest.mark.asyncio
async def test_parallel_tool_execution_speed():
    dispatcher = ParallelToolDispatcher()
    
    async def mock_read_file(args):
        await asyncio.sleep(0.1)
        return f"read:{args['path']}"
    
    async def mock_write_file(args):
        await asyncio.sleep(0.1)
        return f"write:{args['path']}"
    
    tool_calls = [
        ToolCallItem(id="1", name="read_file", args={"path": "a.py"}),
        ToolCallItem(id="2", name="read_file", args={"path": "b.py"}),
        ToolCallItem(id="3", name="read_file", args={"path": "c.py"}),
        ToolCallItem(id="4", name="write_to_file", args={"path": "d.py"}),
    ]
    
    executors = {
        "read_file": mock_read_file,
        "write_to_file": mock_write_file,
    }
    
    start = time.time()
    results = await dispatcher.execute_batch(tool_calls, executors)
    elapsed = time.time() - start
    
    # 3 reads in parallel (0.1s total) + 1 write serial (0.1s) -> total ~0.2s, not 0.4s
    assert elapsed < 0.3
    assert len(results) == 4
    assert results[0].output == "read:a.py"
    assert results[1].output == "read:b.py"
    assert results[2].output == "read:c.py"
    assert results[3].output == "write:d.py"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parallel_tool_dispatcher.py -v`  
Expected: FAIL with "ModuleNotFoundError: No module named 'kogniterm.core.agents.parallel_tool_dispatcher'"

- [ ] **Step 3: Implement ParallelToolDispatcher**

```python
import asyncio
import inspect
from typing import List, Dict, Any, Callable, NamedTuple
from dataclasses import dataclass

READ_ONLY_TOOLS = {
    "read_file", "view_file", "list_dir", "grep_search", "search_web", 
    "read_url_content", "get_file_info", "read_resource"
}

@dataclass
class ToolCallItem:
    id: str
    name: str
    args: Dict[str, Any]

@dataclass
class ToolResult:
    call_id: str
    name: str
    output: Any
    error: bool = False

class ParallelToolDispatcher:
    """Dispatches tool calls concurrently for read-only ops and sequentially for stateful ops."""

    def __init__(self, read_only_tools: set = READ_ONLY_TOOLS):
        self.read_only_tools = read_only_tools

    def is_read_only(self, tool_name: str) -> bool:
        return tool_name in self.read_only_tools

    async def _execute_single(self, item: ToolCallItem, executor: Callable) -> ToolResult:
        try:
            if inspect.iscoroutinefunction(executor):
                res = await executor(item.args)
            else:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(None, executor, item.args)
            return ToolResult(call_id=item.id, name=item.name, output=res, error=False)
        except Exception as e:
            return ToolResult(call_id=item.id, name=item.name, output=str(e), error=True)

    async def execute_batch(self, tool_calls: List[ToolCallItem], executors: Dict[str, Callable]) -> List[ToolResult]:
        results: Dict[str, ToolResult] = {}
        
        # Group adjacent read-only tools into batches for parallel execution
        i = 0
        n = len(tool_calls)
        while i < n:
            item = tool_calls[i]
            executor = executors.get(item.name)
            if not executor:
                results[item.id] = ToolResult(
                    call_id=item.id, name=item.name, output=f"Unknown tool: {item.name}", error=True
                )
                i += 1
                continue

            if self.is_read_only(item.name):
                # Gather all consecutive read-only tool calls
                parallel_batch = []
                while i < n and self.is_read_only(tool_calls[i].name) and tool_calls[i].name in executors:
                    parallel_batch.append(tool_calls[i])
                    i += 1
                
                tasks = [self._execute_single(call, executors[call.name]) for call in parallel_batch]
                batch_results = await asyncio.gather(*tasks)
                for res in batch_results:
                    results[res.call_id] = res
            else:
                # Execute mutating tool sequentially
                res = await self._execute_single(item, executor)
                results[res.call_id] = res
                i += 1

        # Preserve original order of tool calls
        return [results[item.id] for item in tool_calls if item.id in results]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_parallel_tool_dispatcher.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kogniterm/core/agents/parallel_tool_dispatcher.py tests/test_parallel_tool_dispatcher.py
git commit -m "feat: add ParallelToolDispatcher for concurrent read-only tool execution"
```

---

### Task 3: Cache Stabilizer (`kogniterm/core/context/cache_stabilizer.py`)

**Files:**
- Create: `kogniterm/core/context/cache_stabilizer.py`
- Test: `tests/test_cache_stabilizer.py`

**Interfaces:**
- Produces: `CacheStabilizer.format_cacheable_messages(system_prompt, dynamic_context, history) -> List[Dict]`

- [ ] **Step 1: Write failing unit test for Cache Stabilizer**

```python
import pytest
from kogniterm.core.context.cache_stabilizer import CacheStabilizer

def test_cache_stabilizer_ordering():
    stabilizer = CacheStabilizer()
    sys_prompt = "You are KogniTerm agent."
    dyn_context = "Active Skill: test-skill"
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"}
    ]
    
    formatted = stabilizer.format_cacheable_messages(sys_prompt, dyn_context, history)
    assert formatted[0]["role"] == "system"
    assert sys_prompt in formatted[0]["content"]
    assert dyn_context in formatted[0]["content"]
    assert len(formatted) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cache_stabilizer.py -v`  
Expected: FAIL with "ModuleNotFoundError: No module named 'kogniterm.core.context.cache_stabilizer'"

- [ ] **Step 3: Implement CacheStabilizer**

```python
from typing import List, Dict, Any

class CacheStabilizer:
    """Structures context buffers to maximize LLM Prompt Cache hit rates."""

    def __init__(self, max_output_chars: int = 20000):
        self.max_output_chars = max_output_chars

    def truncate_tool_output(self, content: str) -> str:
        """Truncates excessively large outputs to preserve context space."""
        if not isinstance(content, str):
            content = str(content)
        if len(content) <= self.max_output_chars:
            return content
        half = self.max_output_chars // 2
        return (
            f"{content[:half]}\n\n"
            f"... [TRUNCATED {len(content) - self.max_output_chars} CHARACTERS FOR SPEED] ...\n\n"
            f"{content[-half:]}"
        )

    def format_cacheable_messages(
        self, system_prompt: str, dynamic_context: str, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        combined_sys = system_prompt
        if dynamic_context:
            combined_sys = f"{system_prompt}\n\n--- DYNAMIC CONTEXT ---\n{dynamic_context}"

        messages = [{"role": "system", "content": combined_sys}]
        
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "tool":
                content = self.truncate_tool_output(content)
            messages.append({"role": role, "content": content})
            
        return messages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cache_stabilizer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kogniterm/core/context/cache_stabilizer.py tests/test_cache_stabilizer.py
git commit -m "feat: add CacheStabilizer for prompt caching optimization and output truncation"
```

---

### Task 4: Integration into ToolExecutor & LLM Core (`kogniterm/core/agents/tool_executor.py`)

**Files:**
- Modify: `kogniterm/core/agents/tool_executor.py`
- Test: `tests/test_tool_executor_integration.py`

- [ ] **Step 1: Write integration test**

```python
import pytest
import asyncio
from kogniterm.core.agents.tool_executor import ToolExecutor
from kogniterm.core.agents.parallel_tool_dispatcher import ToolCallItem

@pytest.mark.asyncio
async def test_tool_executor_integration_parallel():
    executor = ToolExecutor()
    calls = [
        ToolCallItem(id="c1", name="list_dir", args={"DirectoryPath": "."}),
        ToolCallItem(id="c2", name="list_dir", args={"DirectoryPath": "."})
    ]
    results = await executor.execute_calls(calls)
    assert len(results) == 2
    assert not results[0].error
```

- [ ] **Step 2: Update ToolExecutor to leverage ParallelToolDispatcher & JITSkillManager**

- [ ] **Step 3: Run integration test and existing test suite**

Run: `pytest -v`  
Expected: All tests PASS

- [ ] **Step 4: Commit integration changes**

```bash
git add kogniterm/core/agents/tool_executor.py tests/test_tool_executor_integration.py
git commit -m "refactor: integrate ParallelToolDispatcher and JIT Skill loading into core ToolExecutor"
```
