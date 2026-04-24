import sys
sys.path.append("/home/gato/Proyectos/Gemini-Interpreter")
from kogniterm.core.llm.tool_parser import parse_tool_calls_from_text

text = """[ { "id": "call_12345", "type": "function", "function": { "name": "list_directory_tool", "arguments": {"path": "/dir2"} } } ]"""

print(parse_tool_calls_from_text(text, ["list_directory_tool"]))
