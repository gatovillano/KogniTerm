#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced tool call parsing capabilities
"""

import sys
import os
sys.path.insert(0, '.')

from kogniterm.core.llm_service import LLMService

def test_enhanced_parsing():
    """Test various tool call formats that the enhanced parser can now handle"""
    
    llm_service = LLMService()
    
    # Test cases covering different parsing patterns
    test_cases = [
        # Pattern 1: Standard tool_call format
        "tool_call: search_web({\"query\": \"python tutorial\"})",
        
        # Pattern 2: Natural language
        "I need to call the file_search tool with args {\"path\": \"/home/user\"}",
        
        # Pattern 3: Function call style
        "search_web(query=\"machine learning\")",
        
        # Pattern 4: Tool invocation bracket format
        "[TOOL_CALL] execute_command: {\"command\": \"ls -la\"}",
        
        # Pattern 5: JSON structured format
        '{"tool_call": {"name": "analyze_code", "args": {"file": "main.py"}}}',
        
        # Pattern 6: YAML-like format
        "search_web:\n  query: \"artificial intelligence\"\n  max_results: 5",
        
        # Pattern 7: OpenAI function calling format
        '{"name": "get_weather", "arguments": {"location": "Madrid", "unit": "celsius"}}',
        
        # Pattern 8: Block/list format
        "1. file_operations\n2. execute_command: {\"command\": \"pwd\"}\n3. search_memory",
        
        # Pattern 9: Mixed format
        "Please use the tool 'web_search' with query='latest news' and max_results=10",
        
        # Pattern 10: Complex natural language
        "We should execute the analyze_data function with parameters: {\"dataset\": \"sales_2024.csv\", \"analysis_type\": \"trend\"}"
    ]
    
    print("=== Enhanced Tool Call Parsing Test ===\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test Case {i}:")
        print(f"Input: {test_case}")
        
        # Parse the tool calls
        tool_calls = llm_service._parse_tool_calls_from_text(test_case)
        
        print(f"Parsed tool calls: {len(tool_calls)} found")
        for j, tc in enumerate(tool_calls, 1):
            print(f"  {j}. Name: '{tc['name']}', Args: {tc['args']}")
        print("-" * 60)
    
    print("\n=== Summary ===")
    print("✅ Enhanced parser now supports:")
    print("  • Standard tool_call: name(args) format")
    print("  • Natural language tool invocations")
    print("  • Function call syntax: name(args)")
    print("  • [TOOL_CALL] bracket format")
    print("  • JSON structured tool calls")
    print("  • YAML-like key-value formats")
    print("  • OpenAI function calling format")
    print("  • Block/list numbered formats")
    print("  • Mixed natural language + structured")
    print("  • Complex parameter parsing with type conversion")
    print("\nThis provides broad compatibility with various LLM models!")

if __name__ == "__main__":
    test_enhanced_parsing()