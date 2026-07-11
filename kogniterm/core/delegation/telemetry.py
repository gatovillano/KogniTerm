import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class LLMCallTrace:
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class DelegationTrace:
    subagent_id: str
    subagent_name: str
    task: str
    depth: int
    status: str
    duration: float
    summary: str
    timestamp: float = field(default_factory=time.time)


class TelemetryTracker:
    """
    Rastrea costes y trazas de ejecución por sesión (KiloSession-like).
    Persiste los datos en .kogniterm/telemetry/session_<id>.json.
    """

    def __init__(self, session_id: str, workspace_dir: str):
        self.session_id = session_id
        self.workspace_dir = workspace_dir
        self.start_time = time.time()
        self.llm_calls: List[LLMCallTrace] = []
        self.delegations: List[DelegationTrace] = []
        self.total_cost: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        trace = LLMCallTrace(model, input_tokens, output_tokens, cost)
        self.llm_calls.append(trace)
        self.total_cost += cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.save_trace()

    def record_delegation(
        self,
        subagent_id: str,
        subagent_name: str,
        task: str,
        depth: int,
        status: str,
        duration: float,
        summary: str,
    ) -> None:
        trace = DelegationTrace(
            subagent_id=subagent_id,
            subagent_name=subagent_name,
            task=task,
            depth=depth,
            status=status,
            duration=duration,
            summary=summary,
        )
        self.delegations.append(trace)
        self.save_trace()

    def save_trace(self) -> None:
        telemetry_dir = os.path.join(self.workspace_dir, ".kogniterm", "telemetry")
        os.makedirs(telemetry_dir, exist_ok=True)
        file_path = os.path.join(telemetry_dir, f"session_{self.session_id}.json")

        now = time.time()
        data = {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": now,
            "total_duration": now - self.start_time,
            "total_cost": self.total_cost,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "llm_calls": [asdict(c) for c in self.llm_calls],
            "delegations": [asdict(d) for d in self.delegations],
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
