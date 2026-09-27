# KogniTerm Desktop Dynamic Provider & Model Preloading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate KogniTerm's centralized dynamic model fetching engine (`get_available_models()`) into the OpenCode-compatible Desktop endpoints (`/api/provider`, `/api/model`, `/api/model/default`) with a 60-second in-memory TTL cache, so all supported providers (`google`, `openrouter`, `openai`, `anthropic`, `ollama`, `ollama_cloud`, `antigravity`, `kilocode`, `inception`) are preloaded and populated directly from their respective APIs.

**Architecture:** Connect FastAPI routes `/api/provider`, `/api/model`, `/api/model/default` in `kogniterm/server/app.py` to `get_available_models()`. Implement TTL caching to prevent repeated slow external API queries. Transform models into the OpenCode `NormalizedProviderListResponse` structure expected by the SolidJS desktop frontend.

**Tech Stack:** Python 3.12+, FastAPI, HTTPX, SolidJS, Electron.

## Global Constraints
- NEVER edit, delete, or touch `/home/gato/.kogniterm/repo`. All development MUST remain strictly inside `/home/gato/Proyectos/Gemini-Interpreter`.
- Do not break existing CLI or TUI endpoints. `/models` and `/api/models` must remain fully backward-compatible.
- All OpenCode endpoints must support both v1 (direct list `[...]`) and v2 (wrapped `{"data": [...]}`) depending on whether `/api/` prefix is present in the path.

---

### Task 1: Implement TTL Caching & OpenCode Provider/Model Formatting in Backend

**Files:**
- Modify: `kogniterm/server/app.py:434-750` and `1550-1590`
- Test: `tests/test_opencode_providers.py`

**Interfaces:**
- Consumes: `get_available_models()` in `kogniterm/server/app.py`
- Produces:
  - `cached_get_available_models(ttl_seconds: float = 60.0) -> dict`
  - `GET /api/provider` returning `{"data": [{"id": str, "name": str, "models": {id: {id, name}}}]}`
  - `GET /api/model` returning `{"data": [{"id": str, "name": str, "providerID": str}]}`
  - `GET /api/model/default` returning `{"data": {"id": str, "name": str, "providerID": str}}`

- [ ] **Step 1: Write the failing unit tests for OpenCode provider & model endpoints**

```python
# tests/test_opencode_providers.py
import pytest
from httpx import AsyncClient, ASGITransport
from kogniterm.server.app import create_app

@pytest.mark.asyncio
async def test_opencode_provider_list():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test v2 (/api/provider)
        resp = await client.get("/api/provider")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        providers = data["data"]
        assert isinstance(providers, list)
        provider_ids = [p["id"] for p in providers]
        assert "google" in provider_ids
        # Check provider structure
        google_p = next(p for p in providers if p["id"] == "google")
        assert "models" in google_p
        assert isinstance(google_p["models"], dict)

        # Test v1 (/provider)
        resp_v1 = await client.get("/provider")
        assert resp_v1.status_code == 200
        v1_data = resp_v1.json()
        assert isinstance(v1_data, list)

@pytest.mark.asyncio
async def test_opencode_model_list():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/model")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        models = data["data"]
        assert isinstance(models, list)
        assert len(models) > 0
        first = models[0]
        assert "id" in first
        assert "name" in first
        assert "providerID" in first

@pytest.mark.asyncio
async def test_opencode_default_model():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/model/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        model = data["data"]
        assert "id" in model
        assert "providerID" in model
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_opencode_providers.py -v`
Expected: FAIL because `/api/provider` currently returns `models` as a `list` instead of `dict` and has only hardcoded google entries.

- [ ] **Step 3: Implement TTL Caching & Dynamic OpenCode Model Provider Endpoints**

In `kogniterm/server/app.py`:
1. Add `_cached_models_data = None` and `_cached_models_time = 0.0` at app level.
2. In `get_available_models()`, wrap in `cached_get_available_models(ttl_seconds=60.0)`.
3. Update `opencode_list_providers`, `opencode_list_models`, and `opencode_default_model` to:
   - Call `await cached_get_available_models()`.
   - Format each provider into `{ "id": p["id"], "name": p["name"], "models": { clean_id: {"id": clean_id, "name": clean_name} } }`.
   - Format `opencode_list_models` into `[{ "id": clean_id, "name": clean_name, "providerID": p["id"] }]`.
   - Format `opencode_default_model` using active config from `ConfigManager` (`current_model` and `current_provider`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_opencode_providers.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add tests/test_opencode_providers.py kogniterm/server/app.py
git commit -m "feat(server): dynamic model preloading and TTL caching for OpenCode desktop endpoints"
git push origin main
```

---

### Task 2: End-to-End Desktop Verification

**Files:**
- Test / Verify: `kogniterm-desktop/packages/desktop/src/main/windows.ts` and Chrome DevTools Protocol (`http://127.0.0.1:9222`)

- [ ] **Step 1: Start backend server and probe API endpoints directly**

Run:
```bash
curl -s http://127.0.0.1:8765/api/provider | jq .data[].id
curl -s http://127.0.0.1:8765/api/model/default | jq .
```
Expected: All configured providers (`google`, `openrouter`, `openai`, `anthropic`, `ollama`, `kilocode`, etc.) listed, and default model returned.

- [ ] **Step 2: Verify in Desktop UI via CDP**

Run desktop with `./start.sh` or daemon:
Query via Chrome DevTools Protocol (`http://127.0.0.1:9222`):
Verify that the model dropdown in the SolidJS UI displays the preloaded providers and dynamically loaded models from their APIs.

- [ ] **Step 3: Commit and push any finishing adjustments**

```bash
git push origin main
```
