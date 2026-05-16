import sys
import os

# Añadir el path al proyecto para importar kogniterm
sys.path.append('/home/gato/Proyectos/Gemini-Interpreter')

from kogniterm.core.llm_service import LLMService

def test_parsing():
    service = LLMService()
    
    test_inputs = [
        'call_agent(task="investigar el codigo", agent_name="researcher")',
        'execute_command(command="ls -la")',
        'LLAMADA_A_HERRAMIENTA: execute_command {"command": "ls -la"}',
        '{"name": "execute_command", "args": {"command": "ls -la"}}'
    ]
    
    for i, text in enumerate(test_inputs):
        print(f"\nTest {i+1}: {text}")
        calls = service._parse_tool_calls_from_text(text)
        print(f"Result: {calls}")

if __name__ == "__main__":
    test_parsing()
