from typing import List, Dict, Any

class CacheStabilizer:
    """Structures context buffers to maximize LLM Prompt Cache hit rates."""

    def __init__(self, max_output_chars: int = 20000):
        self.max_output_chars = max_output_chars

    def truncate_tool_output(self, content: str) -> str:
        """Truncates excessively large outputs to preserve context space."""
        if not isinstance(content, str):
            content = str(content)
        if len(content) <= self.max_output_chars:
            return content
        half = self.max_output_chars // 2
        return (
            f"{content[:half]}\n\n"
            f"... [TRUNCATED {len(content) - self.max_output_chars} CHARACTERS FOR SPEED] ...\n\n"
            f"{content[-half:]}"
        )

    def format_cacheable_messages(
        self, system_prompt: str, dynamic_context: str, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        combined_sys = system_prompt
        if dynamic_context:
            combined_sys = f"{system_prompt}\n\n--- DYNAMIC CONTEXT ---\n{dynamic_context}"

        messages = [{"role": "system", "content": combined_sys}]
        
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "tool":
                content = self.truncate_tool_output(content)
            messages.append({"role": role, "content": content})
            
        return messages
