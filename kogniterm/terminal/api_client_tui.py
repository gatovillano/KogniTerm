import os
import httpx

API_BASE_URL = "http://127.0.0.1:8765"  # Sin /api, para coincidir con el backend real

async def send_chat_message(message: str, workspace_id: str = None, session_id: str = None, thread_id: str = None):
    """
    Envía un mensaje de chat al backend centralizado y retorna la respuesta.
    """
    from kogniterm.terminal.tui.tui_app import _DEFAULT_SESSION_ID
    sid = session_id or _DEFAULT_SESSION_ID
    payload = {"message": message, "session_id": sid}
    if workspace_id:
        payload["workspace_id"] = workspace_id
    if thread_id:
        payload["thread_id"] = thread_id
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{API_BASE_URL}/chat/{sid}", json=payload)
        resp.raise_for_status()
        return resp.json()

async def get_available_models():
    """
    Consulta la lista de modelos y proveedores disponibles desde el backend.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE_URL}/models/available")
        resp.raise_for_status()
        return resp.json()

async def get_llm_config():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE_URL}/config/llm")
        resp.raise_for_status()
        return resp.json()

async def set_llm_config(model_name: str = None, provider: str = None, api_key: str = None):
    payload = {}
    if model_name:
        payload["model"] = model_name
    if provider:
        payload["provider"] = provider
    if api_key:
        payload["api_key"] = api_key
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API_BASE_URL}/config/llm", json=payload)
        resp.raise_for_status()
        return resp.json()
