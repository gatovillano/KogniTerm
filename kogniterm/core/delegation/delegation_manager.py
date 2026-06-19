import threading
from typing import Dict, Optional, List
from .models import DelegationContext, DelegationLimits, AgentRole
from .agent_roles import DEFAULT_BLOCKED_TOOLS

class DelegationManager:
    """
    Gestor central de la delegación de subagentes en KogniTerm.
    Se encarga de verificar límites de profundidad, concurrencia por orquestador y
    resolver los permisos de herramientas (RBAC) correspondientes.
    """
    def __init__(self, limits: Optional[DelegationLimits] = None):
        self.limits = limits or DelegationLimits()
        self.active_agents: Dict[str, DelegationContext] = {}
        self._lock = threading.Lock()

    def register_agent(self, agent_id: str, parent_id: Optional[str], role: AgentRole) -> DelegationContext:
        """
        Registra un agente hijo calculando su profundidad y aplicando límites
        de profundidad y concurrencia. Retorna el contexto registrado.
        """
        with self._lock:
            # Calcular profundidad basándose en el padre
            depth = 0
            if parent_id:
                if parent_id not in self.active_agents:
                    raise ValueError(f"El agente padre '{parent_id}' no está registrado.")
                parent_ctx = self.active_agents[parent_id]
                depth = parent_ctx.depth + 1

            # Validar límite de profundidad
            if depth > self.limits.max_depth:
                raise ValueError(
                    f"Excedido límite de profundidad de delegación: {depth} > {self.limits.max_depth}"
                )

            # Validar concurrencia del padre
            if parent_id:
                children_count = sum(1 for a in self.active_agents.values() if a.parent_id == parent_id)
                if children_count >= self.limits.max_concurrent_children:
                    raise ValueError(
                        f"El agente padre '{parent_id}' ya tiene el número máximo de subagentes concurrentes: "
                        f"{children_count} >= {self.limits.max_concurrent_children}"
                    )

            # Resolver las herramientas bloqueadas para este rol
            blocked = DEFAULT_BLOCKED_TOOLS.get(role, frozenset())

            ctx = DelegationContext(
                agent_id=agent_id,
                parent_id=parent_id,
                role=role,
                depth=depth,
                blocked_tools=blocked
            )
            self.active_agents[agent_id] = ctx
            return ctx

    def unregister_agent(self, agent_id: str):
        """
        Elimina un agente del registro activo.
        """
        with self._lock:
            self.active_agents.pop(agent_id, None)

    def can_delegate(self, agent_id: str) -> bool:
        """
        Determina si un agente activo tiene permitido realizar delegaciones.
        """
        with self._lock:
            if agent_id not in self.active_agents:
                return False
            ctx = self.active_agents[agent_id]
            
            # Solo los orquestadores pueden delegar
            if ctx.role != AgentRole.ORCHESTRATOR:
                return False
                
            # No superar la profundidad máxima
            if ctx.depth >= self.limits.max_depth:
                return False
                
            # No superar el límite de hijos concurrentes
            children_count = sum(1 for a in self.active_agents.values() if a.parent_id == agent_id)
            return children_count < self.limits.max_concurrent_children

    def get_context(self, agent_id: str) -> Optional[DelegationContext]:
        """
        Retorna el contexto del agente registrado.
        """
        with self._lock:
            return self.active_agents.get(agent_id)
            
    def get_active_children(self, parent_id: str) -> List[DelegationContext]:
        """
        Retorna una lista de contextos de subagentes activos para un padre dado.
        """
        with self._lock:
            return [a for a in self.active_agents.values() if a.parent_id == parent_id]
