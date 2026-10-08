"""Descubrimiento de modelos para gateways OpenAI-compatible (KiloCode, Inception, OpenCode Zen).

Estos proveedores no exponen un catálogo estático: la lista real de modelos
depende de la key y cambia con el tiempo, así que hay que consultarla.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

GATEWAY_MODEL_ENDPOINTS: Dict[str, str] = {
    "kilocode": "https://api.kilo.ai/api/gateway/models",
    "inception": "https://api.inceptionlabs.ai/v1/models",
    "opencode": "https://opencode.ai/zen/v1/models",
}

GATEWAY_API_KEY_ENVS: Dict[str, Tuple[str, ...]] = {
    "kilocode": ("KILOCODE_API_KEY",),
    "inception": ("INCEPTION_API_KEY", "INCEPTIONLABS_API_KEY"),
    "opencode": ("OPENCODE_API_KEY",),
}

GATEWAY_FALLBACK_MODELS: Dict[str, List[Tuple[str, str]]] = {
    "kilocode": [
        ("kilocode/kilo/auto", "Kilo Auto (Smart Routing)"),
        ("kilocode/anthropic/claude-sonnet-4", "Claude Sonnet 4"),
        ("kilocode/openai/gpt-4o", "GPT-4o"),
    ],
    "inception": [
        ("inception/mercury-2", "Mercury 2"),
        ("inception/mercury-2.5", "Mercury 2.5"),
    ],
    "opencode": [
        ("opencode/claude-sonnet-4-5", "Claude Sonnet 4.5"),
        ("opencode/gpt-5.5", "GPT-5.5"),
        ("opencode/gemini-3-flash", "Gemini 3 Flash"),
        ("opencode/deepseek-v4-pro", "DeepSeek V4 Pro"),
    ],
}

GATEWAY_DISPLAY_NAMES: Dict[str, str] = {
    "kilocode": "KiloCode Gateway",
    "inception": "Inception Labs",
    "opencode": "OpenCode Zen",
}


def resolve_gateway_api_key(provider: str) -> Optional[str]:
    """Resuelve la API key del gateway: ConfigManager -> entorno."""
    try:
        from kogniterm.terminal.config_manager import ConfigManager

        key = ConfigManager().get_api_key(provider)
        if key:
            return key
    except Exception as e:
        logger.debug("No se pudo leer la key de %s desde ConfigManager: %s", provider, e)

    for env_name in GATEWAY_API_KEY_ENVS.get(provider, ()):
        key = os.getenv(env_name)
        if key:
            return key
    return None


def _format_label(model_id: str, entry: Dict) -> str:
    label = entry.get("name") or model_id
    pricing = entry.get("pricing") or {}
    if pricing:
        try:
            prompt = float(pricing.get("prompt", 0) or 0) * 1_000_000
            completion = float(pricing.get("completion", 0) or 0) * 1_000_000
            label += f" [${prompt:.2f}/M in, ${completion:.2f}/M out]"
        except (TypeError, ValueError):
            pass
    return label


async def fetch_gateway_models(provider: str) -> List[Tuple[str, str]]:
    """Descarga la lista de modelos desde la API del gateway.

    Devuelve [] si no hay key, si la petición falla o si la respuesta no es
    utilizable, para que el llamante aplique su lista de respaldo.
    """
    url = GATEWAY_MODEL_ENDPOINTS.get(provider)
    if not url:
        return []

    api_key = resolve_gateway_api_key(provider)
    if not api_key:
        logger.debug("Sin API key para %s; se usará la lista local de respaldo.", provider)
        return []

    try:
        import httpx
    except ImportError:
        logger.warning("httpx no disponible; no se puede consultar la API de %s", provider)
        return []

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                logger.warning("El gateway de %s respondió %s", provider, resp.status_code)
                return []
            data = resp.json()
    except Exception as e:
        logger.warning("Error consultando modelos de %s: %s", provider, e)
        return []

    if isinstance(data, list):
        model_list = data
    else:
        model_list = data.get("models") or data.get("data") or []

    models: List[Tuple[str, str]] = []
    for entry in model_list:
        if isinstance(entry, str):
            entry = {"id": entry}
        elif not isinstance(entry, dict):
            continue
        # Solo 'id'/'model' son ids válidos: 'name' es texto de presentación y
        # usarlo produciría ids inventados (ej: "kilocode/Claude Sonnet 4").
        raw_id = entry.get("id") or entry.get("model") or ""
        if not raw_id:
            continue
        model_id = raw_id if raw_id.startswith(f"{provider}/") else f"{provider}/{raw_id}"
        models.append((model_id, _format_label(raw_id, entry)))

    models.sort(key=lambda x: x[1])
    return models


async def get_gateway_models_with_fallback(provider: str) -> List[Tuple[str, str]]:
    """Modelos del gateway desde la API, o la lista local si no se pudo consultar."""
    models = await fetch_gateway_models(provider)
    if models:
        return models
    return list(GATEWAY_FALLBACK_MODELS.get(provider, []))