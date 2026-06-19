# 📊 Comparativa y Propuesta de Mejoras: KogniTerm vs Hermes-agent

Este documento detalla la comparación arquitectónica entre **KogniTerm** y **Hermes-agent**, junto con una propuesta de mejoras para KogniTerm inspiradas en las fortalezas de Hermes-agent.

---

## 🏗️ 1. Comparación Arquitectónica

| Aspecto | Hermes-agent | KogniTerm |
|---------|-------------|-----------|
| **Modelo** | Agente único con delegación dinámica | Multi-agente con orquestador central |
| **Paradigma** | Delegación bajo demanda (freelancers) | Agentes especializados predefinidos |
| **Orquestación** | El modelo decide cuándo delegar | El orquestador decide qué agente invocar |
| **Extensibilidad** | Toolsets y herramientas fijas | Skills dinámicas + agentes especializados |
| **Paralelismo** | ThreadPoolExecutor con `max_concurrent_children` | `call_agents_parallel` (máximo 2 agentes fijos) |
| **Comunicación** | Aislamiento estricto, solo resúmenes | Memoria compartida + retorno de strings |
| **Memoria** | No compartida entre agentes | `llm_context.md` compartido globalmente |
| **Seguridad** | Alta (aislamiento y bloqueo de herramientas) | Media (confianza entre agentes, aprobaciones) |

---

## 🚀 2. Propuesta de Mejoras para KogniTerm

A continuación se detallan las mejoras propuestas para robustecer la arquitectura de KogniTerm basándose en los patrones de diseño de Hermes-agent.

### 2.1. Delegación Dinámica con Aislamiento
Permite al orquestador principal crear subagentes "hijos" al vuelo para resolver tareas específicas de forma aislada, en lugar de depender únicamente de agentes estáticos predefinidos.

```python
# kogniterm/core/delegation_manager.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, FrozenSet
from enum import Enum
import uuid
import time
import threading

class AgentRole(Enum):
    LEAF = "leaf"           # No puede delegar
    ORCHESTRATOR = "orchestrator"  # Puede spawnear hijos

@dataclass
class DelegationContext:
    """Contexto aislado para un subagente"""
    agent_id: str
    parent_id: Optional[str]
    role: AgentRole
    depth: int
    toolsets: List[str]
    blocked_tools: FrozenSet[str]
    conversation: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    timeout: Optional[float] = None

class DelegationManager:
    """Gestor de delegación dinámica inspirado en Hermes-agent"""
    
    def __init__(self, max_depth: int = 1, max_concurrent: int = 3):
        self.max_depth = max_depth
        self.max_concurrent = max_concurrent
        self.active_agents: Dict[str, DelegationContext] = {}
        self.lock = threading.Lock()
    
    def can_delegate(self, agent_id: str) -> bool:
        with self.lock:
            if agent_id not in self.active_agents:
                return False
            ctx = self.active_agents[agent_id]
            if ctx.role != AgentRole.ORCHESTRATOR:
                return False
            if ctx.depth >= self.max_depth:
                return False
            children_count = sum(1 for a in self.active_agents.values() 
                               if a.parent_id == agent_id)
            return children_count < self.max_concurrent
```

### 2.2. Roles con Permisos Granulares (RBAC)
Evita que los agentes hijos hereden herramientas peligrosas o realicen acciones destructivas.

| Rol | Puede Delegar | Puede Borrar Archivos | Acceso a Memoria Padre | Herramientas Bloqueadas |
|-----|--------------|---------------------|----------------------|-------------------------|
| **LEAF** | ❌ No | ❌ No | ❌ No (Aislado) | `delegate_task`, `execute_command`, `file_delete` |
| **ORCHESTRATOR** | ✅ Sí | ❌ No | ✅ Sí | Ninguna |

### 2.3. Timeouts y Límites de Profundidad
Previene bucles infinitos y consumo excesivo de recursos mediante límites estrictos.

```python
class DelegationLimits:
    def __init__(self, max_depth: int = 1, max_concurrent: int = 3, child_timeout: float = 300):
        self.max_depth = max_depth
        self.max_concurrent = max_concurrent
        self.child_timeout = child_timeout
```

### 2.4. Heartbeat y Detección de Estancamiento
Un monitor en segundo plano que detecta si un agente ha dejado de reportar progreso o se encuentra en un ciclo repetitivo.

```python
class HeartbeatMonitor:
    def is_stalled(self, agent_id: str, timeout: float = 60) -> bool:
        # Si el progreso no varía en un lapso de tiempo, marcar como estancado.
        pass
```

### 2.5. Comunicación basada en Resúmenes (Metadatos)
En lugar de pasar todo el output de texto (que puede consumir miles de tokens y contaminar el contexto), los agentes devuelven un objeto estructurado con un resumen ejecutivo y los artefactos generados.

```python
@dataclass
class DelegationResult:
    agent_id: str
    summary: str                    # Resumen ejecutivo
    status: str                     # "success", "error", "timeout"
    api_calls: List[Dict]           # Herramientas utilizadas
    duration: float                 # Tiempo de ejecución
    artifacts: List[str]            # Archivos generados
    error: Optional[str] = None
```

### 2.6. AgentPool para Paralelismo Real
Sustituir el acoplamiento rígido de `call_agents_parallel` por un pool de hilos (`ThreadPoolExecutor`) que permita ejecutar $N$ tareas independientes en paralelo.

---

## 📋 Plan de Implementación Sugerido

1. **Fase 1: Core de Delegación**
   - Crear `kogniterm/core/delegation/`
   - Implementar `delegation_manager.py` y `agent_roles.py`.
2. **Fase 2: Aislamiento e Interfaz**
   - Adaptar los agentes base para recibir contextos aislados.
   - Implementar `DelegationResult` para la comunicación.
3. **Fase 3: Robustez y Seguridad**
   - Integrar `HeartbeatMonitor` y `DelegationLimits`.
   - Configurar el control de acceso en las Skills (`SkillAccess`).
