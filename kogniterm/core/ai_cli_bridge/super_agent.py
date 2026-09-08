from typing import Any, AsyncGenerator, Dict, List, Optional

from kogniterm.core.ai_cli_bridge.llm_bridge import LLMBridge


class SuperAgent:
    """Agente maestro simplificado con acceso completo a herramientas."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model
        self.llm_bridge = LLMBridge(model=self.model)

    async def execute_stream(
        self,
        task: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 25,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if messages is None:
            messages = []

        default_system = "Eres KogniTerm en modo fast path. Responde claro, breve y ejecuta tools cuando ayuden."
        sys_content = system_prompt or default_system

        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": sys_content})
        elif system_prompt:
            messages[0]["content"] = system_prompt

        if task:
            messages.append({"role": "user", "content": task})

        tools_used: List[str] = []
        full_content: List[str] = []
        error_msg: Optional[str] = None

        async for event in self.llm_bridge.chat(messages=messages, max_steps=max_steps):
            ev_type = event.get("type")
            if ev_type in ("content", "chunk"):
                text = event.get("text", "")
                if text:
                    full_content.append(text)
                    yield {"type": "chunk", "text": text}
            elif ev_type == "reasoning":
                yield {"type": "reasoning", "text": event.get("text", "")}
            elif ev_type == "tool_start":
                name = event.get("name", "")
                if name and name not in tools_used:
                    tools_used.append(name)
                yield {"type": "tool_start", "name": name, "args": event.get("args", {})}
            elif ev_type == "tool_result":
                yield {"type": "tool_result", "name": event.get("name", ""), "result": event.get("result")}
            elif ev_type == "error":
                error_msg = event.get("message")
                yield {"type": "error", "message": error_msg}
            elif ev_type == "done":
                content = event.get("content", "")
                if content and not full_content:
                    full_content.append(content)

        output_text = "".join(full_content).strip()
        success = error_msg is None

        if error_msg:
            output_text = f"{output_text}\n\n[Respuesta interrumpida debido a un error: {error_msg}]" if output_text else f"[Error: {error_msg}]"

        yield {
            "type": "done",
            "output": output_text or "Tarea completada.",
            "tools_used": tools_used,
            "success": success,
            "error": error_msg,
        }

    async def run(
        self,
        task: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 25,
    ) -> Dict[str, Any]:
        """Ejecuta una tarea y devuelve el resultado final consolidado."""
        output_text = ""
        tools_used: List[str] = []
        error_msg: Optional[str] = None
        success = True

        async for event in self.execute_stream(
            task=task,
            messages=messages,
            system_prompt=system_prompt,
            max_steps=max_steps,
        ):
            ev_type = event.get("type")
            if ev_type in ("content", "chunk"):
                output_text += event.get("text", "")
            elif ev_type == "tool_start":
                tools_used.append(event.get("name", ""))
            elif ev_type == "error":
                error_msg = event.get("message")
                success = False
            elif ev_type == "done":
                output_text = event.get("output", output_text)
                tools_used = event.get("tools_used", tools_used)
                success = event.get("success", success)
                error_msg = event.get("error", error_msg)

        return {
            "output": output_text.strip(),
            "tools_used": tools_used,
            "success": success,
            "error": error_msg,
        }
