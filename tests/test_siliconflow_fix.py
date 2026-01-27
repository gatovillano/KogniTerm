#!/usr/bin/env python3
"""
Test script to verify the SiliconFlow tool format fix.
"""
import os
import sys
sys.path.insert(0, '/home/gato/Gemini-Interpreter')

from kogniterm.core.llm_service import _convert_langchain_tool_to_litellm
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional

class TestTool(BaseTool):
    name: str = "test_tool"
    description: str = "A test tool for SiliconFlow compatibility"

    def _run(self, query: str) -> str:
        return f"Test result for: {query}"

# Test the conversion function
def test_tool_conversion():
    print("Testing tool conversion for SiliconFlow compatibility...")

    # Create a test tool
    tool = TestTool()

    # Test with standard model (now uses function format)
    standard_format = _convert_langchain_tool_to_litellm(tool, "gpt-4")
    print(f"Standard format: {standard_format}")

    # Test with OpenRouter/SiliconFlow model (also uses function format)
    siliconflow_format = _convert_langchain_tool_to_litellm(tool, "openrouter/siliconflow-model")
    print(f"SiliconFlow format: {siliconflow_format}")

    # Verify both formats are now the same (standard OpenAI function format)
    assert "type" in standard_format
    assert standard_format["type"] == "function"
    assert "function" in standard_format
    assert standard_format["function"]["name"] == "test_tool"

    assert "type" in siliconflow_format
    assert siliconflow_format["type"] == "function"
    assert "function" in siliconflow_format
    assert siliconflow_format["function"]["name"] == "test_tool"

    # Verify both formats are identical
    assert standard_format == siliconflow_format

    print("✅ All tests passed! SiliconFlow tool format fix is working correctly.")

if __name__ == "__main__":
    test_tool_conversion()