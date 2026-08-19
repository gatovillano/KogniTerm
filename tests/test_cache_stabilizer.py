import pytest
from kogniterm.core.context.cache_stabilizer import CacheStabilizer

def test_cache_stabilizer_ordering():
    stabilizer = CacheStabilizer()
    sys_prompt = "You are KogniTerm agent."
    dyn_context = "Active Skill: test-skill"
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"}
    ]
    
    formatted = stabilizer.format_cacheable_messages(sys_prompt, dyn_context, history)
    assert formatted[0]["role"] == "system"
    assert sys_prompt in formatted[0]["content"]
    assert dyn_context in formatted[0]["content"]
    assert len(formatted) == 3

def test_cache_stabilizer_truncation():
    stabilizer = CacheStabilizer(max_output_chars=100)
    long_output = "a" * 500
    truncated = stabilizer.truncate_tool_output(long_output)
    assert len(truncated) < 500
    assert "TRUNCATED" in truncated
