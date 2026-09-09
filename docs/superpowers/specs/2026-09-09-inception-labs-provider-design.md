# Especificación de Diseño: Proveedor Inception Labs

**Fecha:** 2026-09-09  
**Estado:** Aprobado por el usuario  
**Endpoint:** `https://api.inceptionlabs.ai/v1/chat/completions`

---

## 1. Contexto y Objetivos

Integrar **Inception Labs** (`https://api.inceptionlabs.ai/v1`) como proveedor oficial de modelos LLM en KogniTerm.
Inception Labs ofrece modelos basados en difusión (familia *Mercury*) exponiendo una interfaz compatible con OpenAI en `/v1/chat/completions`.
Los requerimientos clave son:
1. Nombre del proveedor: `inception` (con soporte para alias `inceptionlabs`).
2. Variable de entorno principal: `INCEPTION_API_KEY` (con fallback a `INCEPTIONLABS_API_KEY` o `ConfigManager`).
3. Carga dinámica de modelos consultando directamente `GET https://api.inceptionlabs.ai/v1/models`.
4. Soporte completo en:
   - `MultiProviderManager` y fallback automático.
   - `LLMService` (detección de modelos con prefijo `inception/*`, configuración de base URL y credenciales).
   - `meta_command_processor.py` (comandos `/provider`, `/model`, `/keys`).
   - `server/app.py` (FastAPI / Desktop API para sincronización de modelos remotos).
   - `kogniterm_config.py` (asistente interactivo de configuración).

---

## 2. Arquitectura de Integración

### 2.1 Configuración del Proveedor (`core/multi_provider_manager.py`)
- Se define un nuevo `ProviderConfig`:
  ```python
  ProviderConfig(
      name="inception",
      model_prefix="openai",
      api_key_env="INCEPTION_API_KEY",
      api_base="https://api.inceptionlabs.ai/v1",
      api_base_env="INCEPTION_API_BASE",
      priority=80,
      fallback_on_error_codes=["429", "503", "timeout"]
  )
  ```
- En `ProviderConfig.get_api_key()`:
  - Mapear `"inception"` y `"inceptionlabs"` a `ConfigManager.get_api_key("inception")`.
  - Fallback a `os.getenv("INCEPTION_API_KEY")` o `os.getenv("INCEPTIONLABS_API_KEY")`.
- En `MultiProviderManager._parse_model_name()`:
  - Mapear los prefijos `"inception"` e `"inceptionlabs"` a `"inception"`.
- En `MultiProviderManager._resolve_model_for_provider()`:
  - Si el proveedor destino es `inception`: remover el prefijo de namespace (ej. `inception/mercury` -> `mercury`) para la llamada a LiteLLM.
- En `MultiProviderManager._determine_ideal_provider()`:
  - Detectar prefijos `inception/` o `inceptionlabs/` o nombres de modelos que contengan `mercury`.
- En `MultiProviderManager.execute()`:
  - Si `provider.name == "inception"`, inyectar `custom_llm_provider = "openai"` y `api_base = "https://api.inceptionlabs.ai/v1"`.

### 2.2 Servicio LLM Principal (`core/llm_service.py`)
- En `set_model()`:
  - Si `model_lower` contiene `"inception"` o `"mercury"`, asignar `provider = "inception"`.
  - Configurar `self.api_key`, `os.environ["LITELLM_API_KEY"]` y `litellm.api_base = "https://api.inceptionlabs.ai/v1"`.
- En `get_model_context_window()`:
  - Definir ventana por defecto (ej. 32768 / 120000 tokens para modelos Mercury).
- En la llamada de completion:
  - Si `self.model_name` contiene `inception` o el `api_base` contiene `inceptionlabs.ai`, establecer `custom_llm_provider = "openai"`.

### 2.3 Carga Dinámica de Modelos (`terminal/meta_command_processor.py` y `server/app.py`)
- Función asíncrona `_fetch_inception_models()`:
  - Llama a `GET https://api.inceptionlabs.ai/v1/models` usando cabecera `Bearer <INCEPTION_API_KEY>`.
  - Formatea los modelos como `inception/<id>` para visualización y selección.
  - Ordena alfabéticamente los modelos.
- En `/provider`:
  - Agregar opción `("inception", "⚡ Inception Labs (Diffusion LLMs)")`.
  - Modelo por defecto inicial: `inception/mercury` o el primer modelo devuelto por la API.
- En `/keys`:
  - Agregar `INCEPTION_API_KEY` a la lista de variables clave.

### 2.4 Servidor KogniTerm (`server/app.py`)
- En `/api/llm/providers-models`:
  - Crear tarea `fetch_inception()` para consultar la lista de modelos de Inception Labs si existe API key.
  - Registrar el proveedor `inception` con su lista de modelos en la respuesta.
- En `set_llm_config`:
  - Detección de proveedor `inception` para guardar la llave en `ConfigManager`.

---

## 3. Pruebas y Validación
- Pruebas unitarias en `tests/test_multi_provider_manager.py`:
  - Test de configuración de `ProviderConfig` para Inception Labs.
  - Test de `_parse_model_name()` con `inception/mercury`.
  - Test de resolución de nombre de modelo con `_resolve_model_for_provider()`.
- Verificación sintáctica y ejecución de test suite existente con `pytest`.
