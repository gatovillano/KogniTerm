# Design Spec: KogniTerm Desktop Dynamic Provider & Model Preloading

## 1. Overview & Goals
KogniTerm Desktop currently relies on OpenCode-compatible backend endpoints (`GET /api/provider`, `GET /api/model`, `GET /api/model/default`). Previously, these endpoints returned static hardcoded dummy data for Google Gemini.

The goal of this feature is to seamlessly integrate KogniTerm's centralized `get_available_models()` engine—the exact same engine powering the KogniTerm TUI—into the Desktop interface.

### Key Objectives
1. **Preloaded Providers**: Automatically make available all LLM providers supported by KogniTerm (`google`, `openrouter`, `openai`, `anthropic`, `ollama`, `ollama_cloud`, `antigravity`, `kilocode`, `inception`).
2. **Direct API Model Fetching**: For each configured provider, fetch its available model list directly from the provider's upstream REST API in parallel using saved API keys from `ConfigManager` / environment variables.
3. **OpenCode Desktop Schema Compatibility**: Format the response into the exact schema expected by the SolidJS desktop frontend (`NormalizedProviderListResponse`).
4. **Performance & Caching**: Cache fetched model lists in memory with a 60-second TTL to guarantee instantaneous 0ms responses in the UI while keeping model rosters fresh.

---

## 2. Architecture & Data Flow

```
+-------------------------------------------------------------------+
|                        KogniTerm Desktop                          |
|                     (SolidJS / Electron UI)                       |
+---------------------------------+---------------------------------+
                                  |
                                  | HTTP GET /api/provider, /api/model, /api/model/default
                                  v
+---------------------------------+---------------------------------+
|                        FastAPI Backend                            |
|                   (kogniterm/server/app.py)                       |
+---------------------------------+---------------------------------+
                                  |
                                  | Reads ConfigManager (~/.kogniterm/kogniterm.json)
                                  | & Environment Variables
                                  v
+---------------------------------+---------------------------------+
|                   Centralized get_available_models()              |
|                     (In-memory TTL Cache: 60s)                    |
+---------------------------------+---------------------------------+
                                  |
               +------------------+------------------+
               | (Async parallel API queries via HTTP)
               v                                     v
   +-----------------------+             +-----------------------+
   | Google AI Studio API  |             |  OpenRouter API       |
   | OpenAI API            |             |  Ollama Local Daemon  |
   | Anthropic API         |             |  KiloCode API         |
   | Inception Labs API    |             |  Ollama Cloud API     |
   | Antigravity OAuth     |             +-----------------------+
   +-----------------------+
```

---

## 3. Supported Providers & Upstream API Endpoints

| Provider ID | Provider Name | Credential Source | Upstream Endpoint |
|---|---|---|---|
| `google` | Google AI Studio | `api_key_google` / `GOOGLE_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/models?key={key}` |
| `openrouter` | OpenRouter | `api_key_openrouter` / `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1/models` |
| `openai` | OpenAI | `api_key_openai` / `OPENAI_API_KEY` | `https://api.openai.com/v1/models` |
| `anthropic` | Anthropic | `api_key_anthropic` / `ANTHROPIC_API_KEY` | Model roster curated + API verification |
| `ollama` | Ollama Local | `ollama_api_base` (`default: http://127.0.0.1:11434`) | `{base}/api/tags` |
| `ollama_cloud`| Ollama Cloud | `api_key_ollama_cloud` / `OLLAMA_CLOUD_API_KEY` | `{base}/models` |
| `antigravity`| Google Antigravity | `~/.gemini/antigravity-cli/antigravity-oauth-token` | `AntigravityClient.fetch_available_models()` |
| `kilocode` | KiloCode Gateway | `api_key_kilocode` / `KILOCODE_API_KEY` | `https://api.kilo.ai/api/gateway/models` |
| `inception` | Inception Labs | `api_key_inception` / `INCEPTION_API_KEY` | `https://api.inceptionlabs.ai/v1/models` |

---

## 4. OpenCode Compatibility Schema Mapping

The SolidJS Desktop application expects responses formatted for `@opencode-ai/sdk` and `@opencode-ai/session-ui`.

### 4.1 `GET /api/provider` and `GET /provider`
Returns the list of providers with a nested `models` object dictionary:
```json
[
  {
    "id": "google",
    "name": "Google AI Studio",
    "models": {
      "gemini-2.0-flash": {
        "id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash"
      },
      "gemini-1.5-pro": {
        "id": "gemini-1.5-pro",
        "name": "Gemini 1.5 Pro"
      }
    }
  },
  {
    "id": "openrouter",
    "name": "OpenRouter",
    "models": {
      "google/gemini-2.0-flash-exp:free": {
        "id": "google/gemini-2.0-flash-exp:free",
        "name": "google/gemini-2.0-flash-exp:free"
      }
    }
  }
]
```
Note: If the request URL starts with `/api/`, the payload is wrapped in `{"data": [...]}` as required by `@opencode-ai/sdk` v2.

### 4.2 `GET /api/model` and `GET /model`
Returns a flattened list of all models with `providerID`:
```json
[
  { "id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "providerID": "google" },
  { "id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "providerID": "google" },
  { "id": "google/gemini-2.0-flash-exp:free", "name": "google/gemini-2.0-flash-exp:free", "providerID": "openrouter" }
]
```
Wrapped in `{"data": [...]}` for `/api/model`.

### 4.3 `GET /api/model/default` and `GET /model/default`
Returns the user's currently configured active model:
```json
{
  "id": "gemini-2.0-flash",
  "name": "Gemini 2.0 Flash",
  "providerID": "google"
}
```
Wrapped in `{"data": {...}}` for `/api/model/default`.

---

## 5. Caching & Fault Tolerance

1. **TTL Cache (60s)**:
   - Queries to `get_available_models()` take ~1-2s when hitting all external APIs in parallel.
   - Cache results in memory: `_cached_models_data` and `_cached_models_time`.
   - If `time.time() - _cached_models_time < 60.0`, return the cached results immediately.
2. **Explicit Cache Invalidation**:
   - When keys or configuration change (e.g. `POST /config`, `handle_keys`), clear the cache so the next call fetches fresh models.
3. **Resilience & Timeouts**:
   - Each upstream HTTP call has a strict 2.0s - 3.0s timeout.
   - If an API query fails or times out, the provider falls back to its default curated model list without failing the entire request.
   - `asyncio.gather(..., return_exceptions=True)` ensures isolated failures do not affect other providers.

---

## 6. Verification Plan

1. **Backend Unit / Integration Check**:
   - Query `http://127.0.0.1:8765/api/provider` and verify all providers are returned with their dynamic models.
   - Query `http://127.0.0.1:8765/api/model` and verify flattened list with `providerID`.
   - Query `http://127.0.0.1:8765/api/model/default` and verify default model object.
2. **Desktop UI Verification**:
   - Inspect desktop window via CDP (`ws://127.0.0.1:9222`).
   - Open model selector menu in UI and verify models from active providers are selectable.
3. **TUI Parity Check**:
   - Run `/models` in KogniTerm terminal/TUI and verify the list matches the desktop model selector.
