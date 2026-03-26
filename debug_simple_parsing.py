#!/usr/bin/env python3

import json
import re

def extract_args(args_str):
    """Extract arguments from args string."""
    if not args_str:
        return {}
    
    # Intentar JSON primero
    try:
        return json.loads(args_str)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Intentar argumentos key=value
    kv_pattern = r'(\w+)\s*[:=]\s*([\w"\'\[\{].*?)(?:[,}]|$)'
    kv_matches = re.findall(kv_pattern, args_str)
    if kv_matches:
        result = {}
        for key, value in kv_matches:
            try:
                # Intentar convertir a número
                if value.isdigit():
                    result[key] = int(value)
                elif value.replace('.', '').isdigit():
                    result[key] = float(value)
                elif value.lower() in ['true', 'false']:
                    result[key] = value.lower() == 'true'
                elif value.startswith('[') and value.endswith(']'):
                    # Lista simple
                    result[key] = [v.strip().strip('"\'\'') for v in value[1:-1].split(',')]
                else:
                    # Cadena
                    result[key] = value.strip('"\'\'')
            except:
                result[key] = value.strip('"\'\'')
        return result
    
    # Fallback: argumentos vacíos
    return {}

def _extract_balanced_content(text, start_pos):
    """
    Extrae contenido balanceado entre paréntesis desde una posición dada.
    Maneja paréntesis anidados correctamente.
    """
    if start_pos >= len(text) or text[start_pos] != '(':
        return ''
    
    depth = 0
    content = ''
    in_string = False
    string_char = None
    i = start_pos
    
    while i < len(text):
        char = text[i]
        
        # Manejar strings
        if char in ['"', "'"]:
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char and (i == 0 or text[i-1] != '\\'):
                in_string = False
                string_char = None
        
        # Solo contar paréntesis fuera de strings
        if not in_string:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    # Paréntesis de cierre encontrado, terminar
                    break
        
        content += char
        i += 1
    
    # Remover el paréntesis de apertura y cierre
    if content.startswith('(') and content.endswith(')'):
        content = content[1:-1]
    
    return content.strip()

def _parse_tool_calls_from_text(text):
    """Parse tool calls from text - simplified version."""
    tool_calls = []
    
    # Normalizar texto
    normalized_text = re.sub(r'\s+', ' ', text.strip())
    
    print(f"Normalized text length: {len(normalized_text)}")
    print(f"First 200 chars: {normalized_text[:200]}")
    
    # PATRÓN 3.1: Python function calls con parámetros específicos
    # Usar un enfoque que maneja correctamente los paréntesis anidados
    python_func_patterns = [
        r'\b(call_agent|invoke_agent|execute_agent|run_agent)\s*\(',
        r'\b(llamar_agent|ejecutar_funcion|usar_funcion)\s*\('
    ]
    
    for i, pattern in enumerate(python_func_patterns):
        print(f"\nTesting pattern {i+1}: {pattern}")
        matches = re.findall(pattern, normalized_text, re.IGNORECASE)
        print(f"  Matches found: {len(matches)}")
        
        for func_name in matches:
            # Encontrar la posición del match
            start_pos = normalized_text.lower().find(func_name.lower())
            if start_pos == -1:
                continue
                
            # Buscar el paréntesis de apertura
            paren_start = normalized_text.find('(', start_pos)
            if paren_start == -1:
                continue
                
            # Extraer el contenido entre paréntesis balanceados
            args_str = _extract_balanced_content(normalized_text, paren_start)
            print(f"  Function: '{func_name}', Raw args: '{args_str}'")
            
            # Extraer argumentos específicos de funciones de agentes
            agent_args = {}
            
            # Buscar agent_name o agent
            agent_match = re.search(r'(?:agent_name|agent)\s*=\s*["\']([^"\']+)["\']', args_str)
            if agent_match:
                agent_args['agent_name'] = agent_match.group(1)
                print(f"    agent_name: '{agent_args['agent_name']}'")
            else:
                print("    agent_name: NOT FOUND")
            
            # Buscar task (el parámetro correcto del call_agent tool) - enfoque más simple y robusto
            # Buscar desde task= hasta el final del string o hasta el siguiente parámetro
            task_pattern = r'(?:task)\s*=\s*["\'](.*?)(?:["\']\s*(?:,|\)|$))'
            task_match = re.search(task_pattern, args_str, re.DOTALL)
            if not task_match:
                # Fallback: también buscar task_description para compatibilidad
                task_pattern = r'(?:task_description)\s*=\s*["\'](.*?)(?:["\']\s*(?:,|\)|$))'
                task_match = re.search(task_pattern, args_str, re.DOTALL)
            if task_match:
                agent_args['task'] = task_match.group(1)  # Usar 'task' no 'task_description'
                print(f"    task: '{agent_args['task'][:50]}...'")
            else:
                print("    task: NOT FOUND")
            
            # Buscar context o parameters
            context_match = re.search(r'(?:context|parameters)\s*=\s*(\{[^}]*\})', args_str)
            if context_match:
                try:
                    agent_args['context'] = json.loads(context_match.group(1))
                    print(f"    context: {agent_args['context']}")
                except:
                    agent_args['context'] = context_match.group(1)
                    print(f"    context: {agent_args['context']}")
            else:
                print("    context: NOT FOUND")
            
            # Si no se encontraron argumentos específicos, usar el parser general
            if not agent_args:
                agent_args = extract_args(args_str)
                print(f"    Using general parser: {agent_args}")
            
            tool_calls.append({
                "id": "debug_id",
                "name": func_name,
                "args": agent_args
            })
    
    return tool_calls

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
    
    # Test the parsing
    print("\n=== Testing _parse_tool_calls_from_text ===")
    try:
        parsed_calls = _parse_tool_calls_from_text(test_input)
        print(f"\n=== FINAL RESULT ===")
        print(f"Parsed tool calls: {len(parsed_calls)}")
        
        for i, tc in enumerate(parsed_calls):
            print(f"  {i+1}. Name: '{tc['name']}', Args: {tc['args']}")
    except Exception as e:
        print(f"ERROR in parsing: {e}")
        import traceback
        traceback.print_exc()
    
    # Test step by step the specific call_agent pattern
    print("\n=== Testing simple call_agent pattern ===")
    
    # Test the exact pattern we expect
    simple_test = 'call_agent(agent_name="researcher_agent", task_description="Test task")'
    print(f"Simple test input: {simple_test}")
    
    parsed_simple = _parse_tool_calls_from_text(simple_test)
    print(f"Simple test result: {len(parsed_simple)} calls")
    for i, tc in enumerate(parsed_simple):
        print(f"  {i+1}. Name: '{tc['name']}', Args: {tc['args']}")

if __name__ == "__main__":
    debug_call_agent_parsing()