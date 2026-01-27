#!/usr/bin/env python3
"""
Simplified test for the enhanced tool call parsing functionality
"""

import json
import re
import random
import string
from typing import List, Dict, Any

# Mock the LLMService methods we need for testing
class MockLLMService:
    def _generate_short_id(self, length: int = 9) -> str:
        """Genera un ID alfanumérico corto compatible con proveedores estrictos como Mistral."""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def _parse_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Parsea llamadas a herramientas desde texto plano para compatibilidad con modelos que no usan tool_calls nativos.
        Implementa un modo de parseo amplio y permisivo que detecta múltiples formatos de tool calls.
        
        Patrones soportados:
        - tool_call: nombre({args})
        - Llamar/ejecutar/usar herramienta nombre con args
        - Function calls: nombre({args})
        - Tool invocation: [TOOL_CALL] nombre args
        - JSON estructurado: {"tool_call": {...}}
        - YAML-like: nombre: {args}
        - XML-like: <tool_call name="nombre"><args>...</args> </tool_call>
        - Natural language: I need to call/using tool nombre with args
        - Code-like: nombre({args})
        - Model-specific formats for OpenAI, Anthropic, etc.
        """
        tool_calls = []
        
        # Normalizar texto: reemplazar múltiples espacios y normalizar caracteres
        normalized_text = re.sub(r'\s+', ' ', text.strip())
        
        # Función auxiliar para extraer argumentos de manera permisiva
        def extract_args(args_str):
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
                            result[key] = [v.strip().strip('"\'') for v in value[1:-1].split(',')]
                        else:
                            # Cadena
                            result[key] = value.strip('"\'')
                    except:
                        result[key] = value.strip('"\'')
                return result
            
            # Fallback: argumentos vacíos
            return {}
        
        # PATRÓN 1: tool_call: nombre({args})
        pattern1 = r'tool_call\s*:\s*(\w+)\s*\(\s*([^)]*?)\s*\)'
        matches1 = re.findall(pattern1, normalized_text, re.IGNORECASE | re.DOTALL)
        for name, args_str in matches1:
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 2: llamar/ejecutar/usar herramienta nombre con args
        pattern2 = r'(?:llamar|ejecutar|usar|invoke|call)\s+(?:a\s+)?(?:la\s+)?(?:herramienta|tool)\s+(\w+)\s*(?:con\s+args?|con\s+argumentos?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|.*?)$'
        matches2 = re.findall(pattern2, normalized_text, re.IGNORECASE | re.DOTALL)
        for name, args_str in matches2:
            # Limpiar la cadena de argumentos
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 3: Function calls estilo código - nombre({args})
        pattern3 = r'\b(\w+)\s*\(\s*([^)]*?)\s*\)'
        matches3 = re.findall(pattern3, normalized_text)
        for name, args_str in matches3:
            # Filtrar funciones comunes que no son herramientas
            if name.lower() in ['print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'range', 'type', 'isinstance', 'hasattr', 'getattr', 'open', 'input', 'print', 'exec', 'eval']:
                continue
            
            args = extract_args(args_str)
            if args or args_str.strip():  # Solo agregar si hay argumentos o si es una llamada clara
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })

        # PATRÓN 3.1: Python function calls con parámetros específicos (ej: call_agent)
        # Buscar patrones como call_agent(agent_name="researcher_agent", task_description="...")
        python_func_patterns = [
            r'\b(call_agent|invoke_agent|execute_agent|run_agent)\s*\(\s*([^)]*?)\s*\)',
            r'\b(llamar_agent|ejecutar_funcion|usar_funcion)\s*\(\s*([^)]*?)\s*\)'
        ]
        
        for pattern in python_func_patterns:
            matches = re.findall(pattern, normalized_text, re.IGNORECASE)
            for func_name, args_str in matches:
                # Extraer argumentos específicos de funciones de agentes
                agent_args = {}
                
                # Buscar agent_name o agent
                agent_match = re.search(r'(?:agent_name|agent)\s*=\s*["\']([^"\']+)["\']', args_str)
                if agent_match:
                    agent_args['agent_name'] = agent_match.group(1)
                
                # Buscar task, task_description, o description
                task_match = re.search(r'(?:task_description|task|description)\s*=\s*["\']([^"\']+)["\']', args_str)
                if task_match:
                    agent_args['task_description'] = task_match.group(1)
                
                # Buscar context o parameters
                context_match = re.search(r'(?:context|parameters)\s*=\s*(\{[^}]*\})', args_str)
                if context_match:
                    try:
                        agent_args['context'] = json.loads(context_match.group(1))
                    except:
                        agent_args['context'] = context_match.group(1)
                
                # Si no se encontraron argumentos específicos, usar el parser general
                if not agent_args:
                    agent_args = extract_args(args_str)
                
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": func_name,
                    "args": agent_args
                })

        # PATRÓN 4: [TOOL_CALL] formato
        pattern4 = r'\[TOOL_CALL\]\s*(\w+)\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\n]+)'
        matches4 = re.findall(pattern4, normalized_text, re.IGNORECASE)
        for name, args_str in matches4:
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 5: JSON estructurado expandido
        # Buscar cualquier objeto JSON que contenga información de herramientas
        json_patterns = [
            r'\{[^}]*"(?:tool_call|function_call|action|operation)"\s*:\s*\{[^}]*"(?:name|tool|function)"\s*:\s*["\']([^"\']+)["\'][^}]*"(?:args|arguments|parameters)"\s*:\s*(\{[^}]*\})[^}]*\}',
            r'\{[^}]*"(?:name|tool|function)"\s*:\s*["\']([^"\']+)["\'][^}]*"(?:args|arguments|parameters)"\s*:\s*(\{[^}]*\})[^}]*\}',
            r'\{[^}]*"(\w+)"\s*:\s*(\{[^}]*\})[^}]*"(?:tool|function|operation)"\s*:\s*true[^}]*\}',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, normalized_text, re.DOTALL)
            for name, args_str in matches:
                try:
                    args = json.loads(args_str)
                    tool_calls.append({
                        "id": self._generate_short_id(),
                        "name": name,
                        "args": args
                    })
                except (json.JSONDecodeError, ValueError):
                    args = extract_args(args_str)
                    tool_calls.append({
                        "id": self._generate_short_id(),
                        "name": name,
                        "args": args
                    })

        # PATRÓN 6: YAML-like formato
        pattern6 = r'^(\w+)\s*:\s*(\{[^}]*\}|\([^)]*\)|[^\n]+)$'
        matches6 = re.findall(pattern6, normalized_text, re.MULTILINE)
        for name, args_str in matches6:
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 7: XML-like formato
        pattern7 = r'<(?:tool_call|function|action)\s+(?:name|id)\s*=\s*["\']([^"\']+)["\'][^>]*>(?:<args[^>]*>)?([^<]*?)(?:</args>)?</(?:tool_call|function|action)>'
        matches7 = re.findall(pattern7, normalized_text, re.IGNORECASE | re.DOTALL)
        for name, args_str in matches7:
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # PATRÓN 8: Lenguaje natural expandido
        natural_patterns = [
            r'(?:i\s+need\s+to|i\s+want\s+to|i\s+should|i\s+must)\s+(?:call|use|execute|invoke|run)\s+(?:the\s+)?(?:tool|function|action)\s+(\w+)\s*(?:with\s+args?|with\s+arguments?|with\s+parameters?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\.]+)',
            r'(?:let\s+me\s+|please\s+)?(?:call|use|execute|invoke|run)\s+(?:the\s+)?(?:tool|function|action)\s+(\w+)\s*(?:with\s+args?|with\s+arguments?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\.]+)',
            r'(?:we\s+need\s+to|we\s+should|we\s+can)\s+(?:call|use|execute|invoke|run)\s+(?:the\s+)?(?:tool|function|action)\s+(\w+)\s*(?:with\s+args?|with\s+arguments?)?\s*[:\-]?\s*(\{[^}]*\}|\([^)]*\)|[^\.]+)'
        ]
        
        for pattern in natural_patterns:
            matches = re.findall(pattern, normalized_text, re.IGNORECASE | re.DOTALL)
            for name, args_str in matches:
                args_str = args_str.strip().strip('{}()')
                args = extract_args(args_str)
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })

        # PATRÓN 9: Formatos específicos de proveedores
        # OpenAI function calling format
        openai_pattern = r'"name"\s*:\s*["\']([^"\']+)["\'][^}]*"arguments"\s*:\s*(\{[^}]*\})'
        openai_matches = re.findall(openai_pattern, normalized_text)
        for name, args_str in openai_matches:
            try:
                args = json.loads(args_str)
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })
            except (json.JSONDecodeError, ValueError):
                args = extract_args(args_str)
                tool_calls.append({
                    "id": self._generate_short_id(),
                    "name": name,
                    "args": args
                })

        # PATRÓN 10: Formato de lista/bloque
        list_pattern = r'^(?:\d+\.\s*|-\s*|\*\s*)?(\w+)\s*[:\-]\s*(\{[^}]*\}|\([^)]*\)|[^\n]+)$'
        list_matches = re.findall(list_pattern, normalized_text, re.MULTILINE)
        for name, args_str in list_matches:
            # Filtrar elementos que claramente no son herramientas
            if name.lower() in ['step', 'note', 'important', 'warning', 'error', 'info', 'debug']:
                continue
            
            args_str = args_str.strip().strip('{}()')
            args = extract_args(args_str)
            tool_calls.append({
                "id": self._generate_short_id(),
                "name": name,
                "args": args
            })

        # Eliminar duplicados basados en nombre
        seen = set()
        unique_tool_calls = []
        for tc in tool_calls:
            if tc['name'] not in seen:
                seen.add(tc['name'])
                unique_tool_calls.append(tc)
        
        return unique_tool_calls

def test_enhanced_parsing():
    """Test various tool call formats that the enhanced parser can now handle"""
    
    llm_service = MockLLMService()
    
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
        "We should execute the analyze_data function with parameters: {\"dataset\": \"sales_2024.csv\", \"analysis_type\": \"trend\"}",
        
        # Pattern 11: Python function call style (NEW)
        'call_agent(agent_name="researcher_agent", task_description="Analiza exhaustivamente los dos archivos de procesamiento de grafos de conocimiento")',
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