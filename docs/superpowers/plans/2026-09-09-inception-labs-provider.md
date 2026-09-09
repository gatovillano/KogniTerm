# Inception Labs Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar el proveedor Inception Labs (`https://api.inceptionlabs.ai/v1/chat/completions`) en KogniTerm con carga dinámica de modelos desde la API (`/v1/models`).

**Architecture:** Se añade Inception Labs como proveedor OpenAI-compatible en `MultiProviderManager` y `LLMService`, con resolución de claves mediante `INCEPTION_API_KEY`, consulta dinámica de modelos vía `httpx`, y registro en la interfaz de comandos TUI/CLI y el servidor FastAPI.

**Tech Stack:** Python 3.12+, LiteLLM, httpx, prompt_toolkit, pytest.

## Global Constraints
- Nombres de proveedor: `inception` (alias secundario `inceptionlabs`).
- Variables de entorno: `INCEPTION_API_KEY` (fallback a `INCEPTIONLABS_API_KEY`).
- Endpoint base: `https://api.inceptionlabs.ai/v1` (OpenAI-compatible).
- Endpoint de modelos: `https://api.inceptionlabs.ai/v1/models`.
- Los modelos se nombran con prefijo `inception/<model_id>` en UI/configuración.

---

### Task 1: MultiProviderManager Core Configuration & Unit Tests

**Files:**
- Modify: `kogniterm/core/multi_provider_manager.py`
- Test: `tests/test_multi_provider_manager.py`

**Interfaces:**
- Consumes: `ProviderConfig`, `MultiProviderManager`
- Produces: `DEFAULT_PROVIDERS` con entrada `inception`, soporte de `_parse_model_name("inception/mercury") -> ("inception", "mercury")`, `_resolve_model_for_provider()`.

- [ ] **Step 1: Write the failing tests**
Add test cases in `tests/test_multi_provider_manager.py`:
```python
def test_inception_provider_configuration(monkeypatch):
    from kogniterm.core.multi_provider_manager import DEFAULT_PROVIDERS, MultiProviderManager
    inception = next((p for p in DEFAULT_PROVIDERS if p.name == "inception"), None)
    assert inception is not None
    assert inception.api_base == "https://api.inceptionlabs.ai/v1"
    assert inception.api_key_env == "INCEPTION_API_KEY"

    monkeypatch.setenv("INCEPTION_API_KEY", "test-key-123")
    assert inception.get_api_key() == "test-key-123"
    assert inception.is_configured() is True

def test_parse_model_name_inception():
    from kogniterm.core.multi_provider_manager import MultiProviderManager
    owner, pure = MultiProviderManager._parse_model_name("inception/mercury")
    assert owner == "inception"
    assert pure == "mercury"

    owner_alias, pure_alias = MultiProviderManager._parse_model_name("inceptionlabs/mercury-coder")
    assert owner_alias == "inception"
    assert pure_alias == "mercury-coder"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_multi_provider_manager.py::test_inception_provider_configuration -v`
Expected: FAIL (assertion error because `inception` not in `DEFAULT_PROVIDERS`).

- [ ] **Step 3: Implement minimal code in `kogniterm/core/multi_provider_manager.py`**
1. Add `inception` entry to `DEFAULT_PROVIDERS`:
```python
    ProviderConfig(
        name="inception",
        model_prefix="openai",
        api_key_env="INCEPTION_API_KEY",
        api_base="https://api.inceptionlabs.ai/v1",
        api_base_env="INCEPTION_API_BASE",
        priority=80,
        fallback_on_error_codes=["429", "503", "timeout"]
    ),
```
2. In `ProviderConfig.get_api_key()`:
Add `"inception": "inception"` and support `os.getenv("INCEPTIONLABS_API_KEY")`.
3. In `_parse_model_name()`:
Add `"inception": "inception"` and `"inceptionlabs": "inception"` to `prefix_map`.
4. In `_resolve_model_for_provider()`:
If `provider.name == "inception"`: return `pure_model`.
5. In `_determine_ideal_provider()`:
Support `prefix in ("inception", "inceptionlabs")` and `if "mercury" in lower_model`.
6. In `execute()`:
If `provider.name == "inception"`: set `completion_kwargs["custom_llm_provider"] = "openai"`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_multi_provider_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add kogniterm/core/multi_provider_manager.py tests/test_multi_provider_manager.py
git commit -m "feat(core): add inception labs provider to multi_provider_manager"
```

---

### Task 2: LLMService Provider Support

**Files:**
- Modify: `kogniterm/core/llm_service.py`

**Interfaces:**
- Consumes: `MultiProviderManager`
- Produces: Auto-configures `inception` provider in `set_model()` and completion requests.

- [ ] **Step 1: Write test for LLMService model setting with Inception**
Add test to `tests/unit/test_model_switching.py` (or execute via pytest):
```python
def test_set_model_inception(monkeypatch):
    from kogniterm.core.llm_service import LLMService
    monkeypatch.setenv("INCEPTION_API_KEY", "test-key-inception")
    service = LLMService()
    service.set_model("inception/mercury")
    assert service.api_key == "test-key-inception"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_model_switching.py -v`

- [ ] **Step 3: Implement Inception handling in `kogniterm/core/llm_service.py`**
1. In `get_model_context_window()`:
Include `"inception"` and `"mercury"` in token window calculation (default 120000 tokens).
2. In `set_model()`:
Detect `elif "inception" in model_lower or "mercury" in model_lower: provider = "inception"`.
Set:
```python
key = cm.get_api_key("inception") or os.environ.get("INCEPTION_API_KEY") or os.environ.get("INCEPTIONLABS_API_KEY") or os.environ.get("LITELLM_API_KEY")
if key:
    self.api_key = key
    os.environ["LITELLM_API_KEY"] = key
    os.environ["INCEPTION_API_KEY"] = key

litellm.api_base = os.environ.get("LITELLM_API_BASE") or "https://api.inceptionlabs.ai/v1"
litellm.headers = {}
logger.info(f"🤖 Cambiado a Inception Labs: {model_name}")
```
3. In completion call / `execute_with_fallback`:
Inject `custom_llm_provider = "openai"` if `"inception"` in `self.model_name.lower()` or `"inceptionlabs.ai"` in `self.api_base`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_model_switching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add kogniterm/core/llm_service.py
git commit -m "feat(core): add inception provider detection and setup in llm_service"
```

---

### Task 3: Dynamic Model Fetching & CLI/TUI Integration

**Files:**
- Modify: `kogniterm/terminal/meta_command_processor.py`
- Modify: `kogniterm/terminal/tui/command_processor.py`
- Modify: `kogniterm_config.py`

**Interfaces:**
- Consumes: `https://api.inceptionlabs.ai/v1/models`
- Produces: `_fetch_inception_models()`, `/provider` selection option, `/keys` management.

- [ ] **Step 1: Implement `_fetch_inception_models()` and `/model` support in `meta_command_processor.py`**
1. Implement `_fetch_inception_models()`:
```python
async def _fetch_inception_models():
    try:
        api_key = os.getenv("INCEPTION_API_KEY") or os.getenv("INCEPTIONLABS_API_KEY")
        if not api_key:
            from kogniterm.terminal.config_manager import ConfigManager
            api_key = ConfigManager().get_api_key("inception")
        if not api_key:
            self.terminal_ui.print_message("⚠️ No se encontró INCEPTION_API_KEY en el entorno ni en configuración.", style="yellow")
            return []

        self.terminal_ui.print_message("⏳ Consultando modelos desde Inception Labs...", style="dim")
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.inceptionlabs.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=20.0
            )
            if response.status_code == 200:
                data = response.json()
                models = []
                model_list = data if isinstance(data, list) else data.get("data", data.get("models", []))
                for m in model_list:
                    model_id = m.get("id", m.get("model", ""))
                    if not model_id.startswith("inception/"):
                        model_id = f"inception/{model_id}"
                    label = m.get("name", model_id)
                    models.append((model_id, label))
                models.sort(key=lambda x: x[1])
                return models
            else:
                self.terminal_ui.print_message(f"⚠️ Error al consultar modelos de Inception Labs: {response.status_code}", style="yellow")
                return []
    except Exception as e:
        self.terminal_ui.print_message(f"⚠️ Excepción al conectar con Inception Labs: {e}", style="red")
        return []
```
2. In model listing logic:
Detect `elif "inception" in current_model:` and call `target_list = await _fetch_inception_models()`.
If empty, provide fallback options: `[("inception/mercury", "Mercury (Inception Labs)"), ("inception/mercury-coder", "Mercury Coder")]`.
3. In `/provider` list:
Add `("inception", "⚡ Inception Labs (Diffusion LLMs)")`.
In `default_models`: `"inception": "inception/mercury"`.
4. In `/keys` list:
Add `"INCEPTION_API_KEY"` to `common_keys` and map `"INCEPTION_API_KEY": "inception"`.

- [ ] **Step 2: Update `kogniterm/terminal/tui/command_processor.py` and `kogniterm_config.py`**
1. In `command_processor.py`:
Add `("inception", "Inception Labs")` to `_handle_provider()` and `("inception", "INCEPTION_API_KEY")` to `_handle_keys()`.
2. In `kogniterm_config.py`:
Add `"8": ("inception", "Inception Labs")` and `"inception": "INCEPTION_API_KEY"` to `key_mapping`.

- [ ] **Step 3: Verification**
Run python syntax check:
`python -m py_compile kogniterm/terminal/meta_command_processor.py kogniterm/terminal/tui/command_processor.py kogniterm_config.py`

- [ ] **Step 4: Commit**
```bash
git add kogniterm/terminal/meta_command_processor.py kogniterm/terminal/tui/command_processor.py kogniterm_config.py
git commit -m "feat(ui): add dynamic model fetching and provider configuration for inception labs"
```

---

### Task 4: Server API Integration in `kogniterm/server/app.py`

**Files:**
- Modify: `kogniterm/server/app.py`

**Interfaces:**
- Consumes: `https://api.inceptionlabs.ai/v1/models`
- Produces: Inception models in `/api/llm/providers-models` endpoint and support in `set_llm_config`.

- [ ] **Step 1: Implement `fetch_inception()` in `providers_models` endpoint**
Add `inception_models` with dynamic fetch from `https://api.inceptionlabs.ai/v1/models`.
Register `"id": "inception"`, `"name": "Inception Labs"`, `"models": inception_models`.
In `set_llm_config`: handle `provider == "inception"` and default model `"inception/mercury"`.

- [ ] **Step 2: Verification**
Run syntax check and server tests:
`python -m py_compile kogniterm/server/app.py`
`pytest tests/test_multi_provider_manager.py`

- [ ] **Step 3: Commit**
```bash
git add kogniterm/server/app.py
git commit -m "feat(server): support inception labs in providers-models endpoint"
```
