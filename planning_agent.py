from kogniterm.tools import codebase_search_tool, plan_creation_tool, call_agent
from kogniterm.core.agent_state import AgentState
from typing import List, Dict, Any

class PlanningAgent:
    def __init__(self, state: AgentState):
        self.state = state
        self.tools = {
            "codebase_search": codebase_search_tool,
            "plan_creation": plan_creation_tool,
            "call_agent": call_agent
        }

    def analyze_task(self, task: str) -> Dict[str, Any]:
        """Analiza la tarea principal y busca código relevante."""
        search_results = self.tools["codebase_search"](query=task, k=5)
        return {
            "task": task,
            "relevant_code": search_results
        }

    def create_plan(self, task_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Genera un plan detallado de subtareas."""
        plan = self.tools["plan_creation"](task_description=task_analysis["task"])
        return plan

    def assign_subtasks(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Asigna subtareas a otros agentes."""
        results = []
        for subtask in plan:
            result = self.tools["call_agent"](
                agent_name="researcher_agent",
                task=subtask["description"]
            )
            results.append({
                "subtask": subtask["description"],
                "result": result
            })
        return results

    def execute(self, task: str) -> Dict[str, Any]:
        """Ejecuta el flujo completo del Agente Planificador."""
        task_analysis = self.analyze_task(task)
        plan = self.create_plan(task_analysis)
        subtask_results = self.assign_subtasks(plan)

        return {
            "task": task,
            "plan": plan,
            "subtask_results": subtask_results
        }