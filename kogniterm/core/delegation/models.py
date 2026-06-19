from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, FrozenSet
import time
from .agent_roles import AgentRole

@dataclass(frozen=True)
class DelegationLimits:
    max_depth: int = 2
    max_concurrent_children: int = 3
    child_timeout: float = 300.0  # 5 minutos

@dataclass
class DelegationContext:
    agent_id: str
    parent_id: Optional[str]
    role: AgentRole
    depth: int
    toolsets: List[str] = field(default_factory=list)
    blocked_tools: FrozenSet[str] = field(default_factory=frozenset)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DelegationResult:
    agent_id: str
    status: str  # "success", "failed", "timeout", "killed"
    summary: str
    duration: float
    api_calls: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    error: Optional[str] = None
