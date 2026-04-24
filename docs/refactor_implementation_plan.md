# Refactorization Plan: KogniTerm Structural Improvements

This plan outlines the steps to address the architectural issues and technical debt identified in the master audit report.

## 1. LLMService Decomposition
`LLMService` (currently ~1,781 lines) will be split into a core orchestrator and several specialized modules in `kogniterm/core/llm/`.

### Modules to create:
- `kogniterm/core/llm/provider_config.py`: APIs, credentials, and model initialization logic.
- `kogniterm/core/llm/message_converter.py`: LangChain ↔ LiteLLM message conversion.
- `kogniterm/core/llm/tool_parser.py`: Parsing tool calls from raw text.
- `kogniterm/core/llm/streaming_executor.py`: Streaming logic, handling chunks, and timeouts.
- `kogniterm/core/llm/fallback_handler.py`: Model/provider fallback logic.
- `kogniterm/core/llm/rate_limiter.py`: Rate limiting and token tracking.

### Orchestrator update:
- Modify `kogniterm/core/llm_service.py` to use these modules, reducing its size significantly.

## 2. Eliminate Code Duplication in Agents
Extract shared logic from agents into a common base.

### Steps:
- Create `kogniterm/core/agents/base_agent.py` containing `BaseAgentNode`.
- Move `create_call_model_node` and shared utilities (`execute_single_tool`, `handle_tool_confirmation`, `should_continue`) to `BaseAgentNode`.
- Refactor `bash_agent.py`, `code_agent.py`, `researcher_agent.py`, and `deep_researcher.py` to inherit from or use `BaseAgentNode`.

## 3. Tool Executor Consolidation
Create a dedicated tool executor.
- Create `kogniterm/core/agents/tool_executor.py`.
- Consolidate the 3 versions of `execute_single_tool`.

## 4. Thread Safety and Concurrency
Address potential race conditions and corruption.
- Add resource grouping to `ThreadPoolExecutor` in `bash_agent.py` / `tool_executor.py`.
- Implement locking in `HistoryManager` and `KogniTermKernel`.

## 5. Cleanup
- Remove legacy `ToolManager` (`kogniterm/core/tools/tool_manager.py`).
- Fix `docker-compose.yml` (remove WordPress config).
- Update `pyproject.toml` with correct dependencies.

---
**Status:** In Progress
**Priority:** 1 (Structural Refactor)
