import sys
import os
sys.path.append('/home/gato/Proyectos/Gemini-Interpreter')

from kogniterm.core.llm_service import LLMService

def test_actual_parser():
    llm = LLMService()
    # Hypothetical Flash output with tool calls
    test_text = """
He decidido listar los archivos.
```python
execute_command(command="ls -la")
```
Y luego veré el contenido.
"""
    print(f"Testing text:\n{test_text}")
    calls = llm._parse_tool_calls_from_text(test_text)
    print(f"\nParsed calls: {calls}")

if __name__ == "__main__":
    test_actual_parser()
