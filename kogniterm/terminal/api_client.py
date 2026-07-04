import os
import requests

def _get_api_base_url() -> str:
    server_url = os.environ.get("KOGNITERM_SERVER_URL")
    if server_url:
        if server_url.startswith("wss://"):
            return server_url.replace("wss://", "https://", 1)
        elif server_url.startswith("ws://"):
            return server_url.replace("ws://", "http://", 1)
        return server_url
    return "http://localhost:8765"

API_BASE_URL = _get_api_base_url()  # Ajusta si el backend corre en otro puerto o dirección

def get_llm_config():
    """Obtiene la configuración LLM centralizada desde el backend."""
    resp = requests.get(f"{API_BASE_URL}/config/llm")
    resp.raise_for_status()
    return resp.json()

def set_llm_config(model_name: str = None, provider: str = None, api_key: str = None):
    """Actualiza la configuración LLM centralizada en el backend."""
    payload = {}
    if model_name:
        payload["model"] = model_name
    if provider:
        payload["provider"] = provider
    if api_key:
        payload["api_key"] = api_key
    resp = requests.post(f"{API_BASE_URL}/config/llm", json=payload)
    resp.raise_for_status()
    return resp.json()
