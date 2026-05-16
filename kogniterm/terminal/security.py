import re
from typing import Any

def scrub_secrets(text: Any) -> Any:
    """
    Escanea un texto (o estructura) y enmascara posibles secretos como API Keys, 
    Tokens, Passwords y credenciales en URLs.
    """
    if not isinstance(text, str):
        return text
        
    # 1. Enmascarar API Keys y Tokens (formatos comunes)
    # Patrón: KEY="sk-..." o KEY: "sk-..." o TOKEN: sk-...
    # Buscamos palabras clave seguidas de delimitadores y una cadena de al menos 8 caracteres
    text = re.sub(r'(?i)(api[-_]?key|token|password|secret|pass|auth_token|access_key|access_token|credentials|private_key|secret_key)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{8,})["\']?', 
                  lambda m: f"{m.group(1)}: {m.group(2)[:4]}****{m.group(2)[-4:]}" if len(m.group(2)) > 8 else f"{m.group(1)}: ****", 
                  text)
    
    # 2. Enmascarar credenciales en URLs (http://user:pass@host)
    # Patrón: protocolo://usuario:password@host
    text = re.sub(r'([a-z]+://)([^:/@\s]+):([^:/@\s]+)@', r'\1****:****@', text)
    
    # 3. Enmascarar posibles llaves de Ollama/OpenRouter que no tengan prefijo claro pero parezcan llaves
    # sk-or-v1-... (OpenRouter)
    text = re.sub(r'\bsk-or-v1-[a-zA-Z0-9]{32,}\b', lambda m: f"{m.group(0)[:12]}****{m.group(0)[-4:]}", text)
    
    # gspread / google keys
    text = re.sub(r'\bAIzaSy[a-zA-Z0-9_-]{33}\b', lambda m: f"AIzaSy****{m.group(0)[-4:]}", text)

    return text

def mask_url_credentials(url: str) -> str:
    """Enmascara específicamente credenciales en una URL."""
    if not url or not isinstance(url, str):
        return url
    return re.sub(r'([a-z]+://)([^:/@\s]+):([^:/@\s]+)@', r'\1****:****@', url)
