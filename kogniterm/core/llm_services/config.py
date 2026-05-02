"""
Configuración centralizada para servicios LLM.
"""
from typing import Dict, Any


class LLMConfig:
    """Configuración base para servicios LLM."""

    def __init__(
        self,
        model: str = "gemini-1.5-pro-latest",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.95,
        top_k: int = 40,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a diccionario."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfig":
        """Crea configuración desde diccionario."""
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})


# Configuraciones predefinidas
FAST_CONFIG = LLMConfig(
    model="gemini-1.5-flash-latest",
    temperature=0.5,
    max_tokens=2048,
)

DEEP_CONFIG = LLMConfig(
    model="gemini-1.5-pro-latest",
    temperature=0.7,
    max_tokens=8192,
)

TOOL_CONFIG = LLMConfig(
    model="gemini-1.5-pro-latest",
    temperature=0.3,
    max_tokens=4096,
)


DEFAULT_CONFIG = DEEP_CONFIG
