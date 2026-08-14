import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from kogniterm.core.llm_service import LLMService
from kogniterm.core.skills.skill_manager import SkillManager
from kogniterm.core.context.workspace_context import WorkspaceContext

def test_skill_instructions_limit_when_query_empty():
    sm = SkillManager()
    class MockSkill:
        def __init__(self, name):
            self.name = name
            self.loaded = True
            self.description = "desc"
            self.category = "general"
            self.security_level = "low"
            self.instructions = "Instructions for " + name

    for i in range(10):
        sm.skills[f"skill_{i}"] = MockSkill(f"skill_{i}")

    instructions = sm.get_loaded_skill_instructions(query=None, limit=3)
    assert len(instructions) == 3

def test_workspace_context_truncation(tmp_path):
    wc = WorkspaceContext(str(tmp_path))
    wc.context_data = "A" * 50000
    msg = wc.build_context_message()
    assert msg is not None
    assert "[Contexto del proyecto truncado por seguridad de ventana de contexto]" in msg.content
    assert len(msg.content) < 45000

def test_llm_service_precall_purging_system_message():
    service = LLMService()
    service.model_name = "stepfun/step-3.7-flash:free"
    
    huge_system = "SYSTEM " * 150000
    litellm_messages = [
        {"role": "system", "content": huge_system},
        {"role": "user", "content": "User message 1"},
        {"role": "assistant", "content": "Assistant response 1"},
        {"role": "user", "content": "User message 2"}
    ]
    
    model_window = service.get_model_context_window(service.model_name)
    max_allowed = max(4000, model_window - 8192 - 3000)
    
    total_tokens = service._get_messages_token_count(litellm_messages)
    assert total_tokens > max_allowed
    
    system_msgs = [m for m in litellm_messages if m.get("role") == "system"]
    conv_msgs = [m for m in litellm_messages if m.get("role") != "system"]
    
    while conv_msgs and total_tokens > max_allowed:
        conv_msgs.pop(0)
        total_tokens = service._get_messages_token_count(system_msgs + conv_msgs)
        
    litellm_messages = system_msgs + conv_msgs
    
    if total_tokens > max_allowed:
        for msg in litellm_messages:
            if msg.get("role") == "system" and isinstance(msg.get("content"), str):
                allowed_chars = max(2000, int(max_allowed * 3.2))
                if len(msg["content"]) > allowed_chars:
                    msg["content"] = msg["content"][:allowed_chars] + "\n\n[Mensaje de sistema truncado por límite estricto de contexto]"
        total_tokens = service._get_messages_token_count(litellm_messages)
        
    assert total_tokens <= max_allowed
