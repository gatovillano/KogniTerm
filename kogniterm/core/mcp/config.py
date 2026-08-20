from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field

class MCPServerConfig(BaseModel):
    transport: Literal["stdio", "sse"] = "stdio"
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    disabled: bool = False
    scope: Literal["global", "project"] = "project"
