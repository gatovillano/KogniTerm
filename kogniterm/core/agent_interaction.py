from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAgentInteractionManager(ABC):
    @abstractmethod
    def invoke_agent(self, user_input: Optional[str]) -> Dict[str, Any]:
        pass

class AgentInteractionRegistry:
    _factory = None

    @classmethod
    def register_factory(cls, factory):
        cls._factory = factory

    @classmethod
    def create(cls, *args, **kwargs) -> BaseAgentInteractionManager:
        if cls._factory is None:
            raise RuntimeError(
                "Error de Arquitectura: La factory de AgentInteractionManager no ha sido registrada. "
                "Asegúrate de que la capa de UI/Terminal la registre al inicio."
            )
        return cls._factory(*args, **kwargs)
