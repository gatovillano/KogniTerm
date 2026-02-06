from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import os
import logging
from dotenv import set_key

router = APIRouter()
logger = logging.getLogger(__name__)

class LLMSettings(BaseModel):
    provider: str
    model: str
    api_key: str
    
    # Opcionales para futuro
    temperature: Optional[float] = 0.7

@router.get("/config/llm")
async def get_llm_config():
    """Devuelve la configuración actual del LLM (enmascarando keys)."""
    model = os.environ.get("LITELLM_MODEL", "google/gemini-1.5-flash")
    
    # Detectar proveedor basado en el modelo o variables
    provider = "google"
    if "openrouter" in model:
        provider = "openrouter"
    elif "gpt" in model:
        provider = "openai"
    elif "claude" in model:
        provider = "anthropic"
        
    # Obtener key actual (enmascarada)
    key = ""
    if provider == "google":
        raw_key = os.environ.get("GOOGLE_API_KEY", "")
    elif provider == "openrouter":
        raw_key = os.environ.get("OPENROUTER_API_KEY", "")
    else:
        raw_key = os.environ.get("OPENAI_API_KEY", "") # Fallback genérico
        
    masked_key = f"{raw_key[:4]}...{raw_key[-4:]}" if len(raw_key) > 8 else "********"
    
    return {
        "provider": provider,
        "model": model,
        "api_key_masked": masked_key,
        "has_key": bool(raw_key)
    }

@router.post("/config/llm")
async def update_llm_config(settings: LLMSettings):
    """Actualiza la configuración del LLM y persiste en .env."""
    try:
        # 1. Actualizar entorno actual
        if settings.provider == "google":
            os.environ["GOOGLE_API_KEY"] = settings.api_key
            # Gemini a veces usa LITELLM_API_KEY también en este proyecto
            os.environ["LITELLM_API_KEY"] = settings.api_key 
            
            # Formatear modelo si no viene completo
            if not settings.model.startswith("gemini/"):
                full_model = f"gemini/{settings.model}"
            else:
                full_model = settings.model
                
            os.environ["LITELLM_MODEL"] = full_model
            os.environ["GEMINI_MODEL"] = full_model.replace("gemini/", "")
            
            # Persistir
            set_key(".env", "GOOGLE_API_KEY", settings.api_key)
            set_key(".env", "GEMINI_MODEL", full_model.replace("gemini/", ""))
            set_key(".env", "LITELLM_MODEL", full_model)
            
        elif settings.provider == "openrouter":
            os.environ["OPENROUTER_API_KEY"] = settings.api_key
            
            if not settings.model.startswith("openrouter/"):
                full_model = f"openrouter/{settings.model}"
            else:
                full_model = settings.model
            
            os.environ["LITELLM_MODEL"] = full_model
            
            # Persistir
            set_key(".env", "OPENROUTER_API_KEY", settings.api_key)
            set_key(".env", "LITELLM_MODEL", full_model)
            
        else:
            # Genérico (OpenAI, etc)
            os.environ["OPENAI_API_KEY"] = settings.api_key
            os.environ["LITELLM_MODEL"] = settings.model
            set_key(".env", "OPENAI_API_KEY", settings.api_key)
            set_key(".env", "LITELLM_MODEL", settings.model)
            
        logger.info(f"Configuración LLM actualizada: {settings.provider} / {settings.model}")
        return {"status": "success", "message": "Configuración actualizada. Reinicia el chat para aplicar cambios."}
        
    except Exception as e:
        logger.error(f"Error actualizando config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
