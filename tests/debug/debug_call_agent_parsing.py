#!/usr/bin/env python3

import sys
import os
import json
import re

# Add the kogniterm directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'kogniterm'))

from core.llm_service import LLMService

def debug_call_agent_parsing():
    """Debug the specific call_agent parsing to identify the issue."""
    
    print("=== DEBUG call_agent PARSING ===")
    
    # Test the exact format the user is trying to use
    test_input = '''call_agent(agent_name="researcher_agent", task="Analiza exhaustivamente los dos archivos de procesamiento de grafos de conocimiento:
      knowledge_graph/conceptual_graph_processor.py y knowledge_graph/hybrid_graph_processor.py.

Tu análisis debe cubrir:

1. **Arquitectura y Diseño**: Comparar las filosofías de ambos procesadores, responsabilidades, pipeline de procesamiento y modelos utilizados

2. **Flujos de Trabajo Detallados**: Mapear cada fase del procesamiento, desde extracción hasta generación de relaciones, identificando:
   - Estrategias de extracción (LLM, spaCy, GLiNER, embeddings)
   - Métodos de deduplicación y filtrado
   - Algoritmos de generación de relaciones
   - Mecanismos de caching y optimización

3. **Técnicas de Optimización Actuales**: Identificar todas las optimizaciones ya implementadas:
   - Procesamiento paralelo (asyncio, batches)
   - Caching multi-nivel
   - Modelos fast_llm vs main_llm
   - Gestión de memoria y límites
   - Estrategias de fallback

4. **Cuellos de Botella Potenciales**: Detectar posibles problemas de rendimiento:
   - Límites de modelos (GLiNER 384 chars, chunking)
   - Cálculos intensivos (embeddings, similitudes)
   - Gestión de caché y memoria
   - Procesamiento de grandes volúmenes

5. **Oportunidades de Mejora**: Proponer áreas específicas de optimización:
   - Técnicas de pre-filtrado y priorización
   - Optimización de embeddings y similitudes
   - Mejora de estrategias de caching
   - Balanceo de carga y paralelización inteligente
   - Reducción de llamadas a LLM
   - Gestión eficiente de memoria

Genera un informe detallado en formato Markdown que incluya diagramas conceptuales, tablas comparativas y recomendaciones específicas con justificación técnica.")'''
    
    print(f"Input text length: {len(test_input)}")
    print(f"First 100 chars: {test_input[:100]}")
    print(f"Last 100 chars: {test_input[-100:]}")
    
    # Initialize LLMService to access the parsing method
    llm_service = LLMService()
    
    # Test the parsing
    print("\n=== Testing _parse_tool_calls_from_text ===")
    try:
        parsed_calls = llm_service._parse_tool_calls_from_text(test_input)
        print(f"Parsed tool calls: {len(parsed_calls)}")
        
        for i, tc in enumerate(parsed_calls):
            print(f"  {i+1}. Name: '{tc['name']}', Args: {tc['args']}")
    except Exception as e:
        print(f"ERROR in parsing: {e}")
        import traceback
        traceback.print_exc()
    
    # Test step by step the specific call_agent pattern
    print("\n=== Testing specific call_agent pattern ===")
    
    # Test the exact pattern we expect
    simple_test = 'call_agent(agent_name="researcher_agent", task_description="Test task")'
    print(f"Simple test input: {simple_test}")
    
    parsed_simple = llm_service._parse_tool_calls_from_text(simple_test)
    print(f"Simple test result: {len(parsed_simple)} calls")
    for i, tc in enumerate(parsed_simple):
        print(f"  {i+1}. Name: '{tc['name']}', Args: {tc['args']}")
    
    # Test just the Python function pattern
    print("\n=== Testing Python function pattern ===")
    
    # Pattern 3.1: Python function calls
    python_func_patterns = [
        r'\b(call_agent|invoke_agent|execute_agent|run_agent)\s*\(\s*([^)]*?)\s*\)',
        r'\b(llamar_agent|ejecutar_funcion|usar_funcion)\s*\(\s*([^)]*?)\s*\)'
    ]
    
    for i, pattern in enumerate(python_func_patterns):
        print(f"\nPattern {i+1}: {pattern}")
        matches = re.findall(pattern, test_input, re.IGNORECASE)
        print(f"  Matches found: {len(matches)}")
        for j, (func_name, args_str) in enumerate(matches):
            print(f"    {j+1}. Function: '{func_name}', Args: '{args_str}'")
    
    # Test argument extraction for call_agent
    print("\n=== Testing argument extraction ===")
    
    test_args_str = 'agent_name="researcher_agent", task="Analiza exhaustivamente los dos archivos..."'
    print(f"Test args string: {test_args_str}")
    
    # Test agent_name extraction
    agent_match = re.search(r'(?:agent_name|agent)\s*=\s*["\']([^"\']+)["\']', test_args_str)
    if agent_match:
        print(f"  agent_name found: '{agent_match.group(1)}'")
    else:
        print("  agent_name NOT found")
    
    # Test task extraction  
    task_match = re.search(r'(?:task_description|task|description)\s*=\s*["\']([^"\']+)["\']', test_args_str)
    if task_match:
        print(f"  task found: '{task_match.group(1)[:50]}...'")
    else:
        print("  task NOT found")
    
    print("\n=== Debug complete ===")

if __name__ == "__main__":
    debug_call_agent_parsing()