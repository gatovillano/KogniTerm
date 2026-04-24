import sys
import os
sys.path.append("/home/gato/Proyectos/Gemini-Interpreter")

from kogniterm.core.llm.tool_parser import parse_tool_calls_from_text

text = """{"name": "list_directory_tool", "arguments": {"path": "/dir1"}}
Tool Calls: [ { "id": "nWpLsTqRv", "type": "function", "function": { "name": "list_directory_tool", "arguments": {"path": "/dir2"} } } ]
Tool Calls: [ { "id": "oxqMtUrSw", "type": "function", "function": { "name": "list_directory_tool", "arguments": {"path": "/dir3"} } } ]"""

tools = ["list_directory_tool", "project_analyzer"]
print("Resultados con argumentos diferentes:")
print(parse_tool_calls_from_text(text, tools))
