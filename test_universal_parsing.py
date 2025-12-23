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
    """Extrae contenido balanceado entre paréntesis desde una posición dada."""
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
                    break
        
        content += char
        i += 1
    
    # Remover el paréntesis de apertura y cierre
    if content.startswith('(') and content.endswith(')'):
        content = content[1:-1]
    
    return content.strip()

def parse_tool_calls_universal(text):
    """Test universal tool call parsing for all tools."""
    tool_calls = []
    normalized_text = re.sub(r'\s+', ' ', text.strip())
    
    print(f"=== UNIVERSAL TOOL PARSING TEST ===")
    print(f"Input: {text[:100]}...")
    
    # PATRÓN 3.1: Python function calls con parámetros específicos (ej: call_agent)
    python_func_patterns = [
        r'\b(call_agent|invoke_agent|execute_agent|run_agent)\s*\(',
        r'\b(llamar_agent|ejecutar_funcion|usar_funcion)\s*\('
    ]
    
    for pattern in python_func_patterns:
        matches = re.findall(pattern, normalized_text, re.IGNORECASE)
        for func_name in matches:
            start_pos = normalized_text.lower().find(func_name.lower())
            if start_pos == -1:
                continue
                
            paren_start = normalized_text.find('(', start_pos)
            if paren_start == -1:
                continue
                
            args_str = _extract_balanced_content(normalized_text, paren_start)
            
            # Extraer argumentos específicos para call_agent
            agent_args = {}
            
            # Buscar agent_name o agent
            agent_match = re.search(r'(?:agent_name|agent)\s*=\s*["\']([^"\']+)["\']', args_str)
            if agent_match:
                agent_args['agent_name'] = agent_match.group(1)
            
            # Buscar task (el parámetro correcto del call_agent tool)
            task_pattern = r'(?:task)\s*=\s*["\'](.*?)(?:["\']\s*(?:,|\)|$))'
            task_match = re.search(task_pattern, args_str, re.DOTALL)
            if not task_match:
                task_pattern = r'(?:task_description)\s*=\s*["\'](.*?)(?:["\']\s*(?:,|\)|$))'
                task_match = re.search(task_pattern, args_str, re.DOTALL)
            if task_match:
                agent_args['task'] = task_match.group(1)
            
            # Si no se encontraron argumentos específicos, usar el parser general
            if not agent_args:
                agent_args = extract_args(args_str)
            
            tool_calls.append({
                "id": "test_id",
                "name": func_name,
                "args": agent_args
            })
    
    # PATRÓN 3: Function calls estilo código - nombre({args})
    pattern3 = r'\b(\w+)\s*\(\s*([^)]*?)\s*\)'
    matches3 = re.findall(pattern3, normalized_text)
    for name, args_str in matches3:
        # Filtrar funciones comunes que no son herramientas
        if name.lower() in ['print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'range', 'type', 'isinstance', 'hasattr', 'getattr', 'open', 'input', 'print', 'exec', 'eval']:
            continue
        
        # Evitar duplicados (ya procesados en Pattern 3.1)
        if any(tc['name'] == name for tc in tool_calls):
            continue
        
        args = extract_args(args_str)
        if args or args_str.strip():
            tool_calls.append({
                "id": "test_id",
                "name": name,
                "args": args
            })
    
    return tool_calls

def test_all_tools():
    """Test parsing for various tools with different parameter structures."""
    
    test_cases = [
        # 1. call_agent (complex parameters)
        {
            "name": "call_agent",
            "input": 'call_agent(agent_name="researcher_agent", task="Analiza el código con mucho contenido que incluye paréntesis (ejemplo) y comillas "dobles"")',
            "expected_tool": "call_agent",
            "expected_params": ["agent_name", "task"]
        },
        
        # 2. execute_command (simple parameter)
        {
            "name": "execute_command", 
            "input": 'execute_command(command="ls -la /tmp/test")',
            "expected_tool": "execute_command",
            "expected_params": ["command"]
        },
        
        # 3. file_operations (complex multi-parameter)
        {
            "name": "file_operations",
            "input": 'file_operations(operation="read_file", path="/home/user/test.txt")',
            "expected_tool": "file_operations", 
            "expected_params": ["operation", "path"]
        },
        
        # 4. web_fetch (different parameters)
        {
            "name": "web_fetch",
            "input": 'web_fetch(url="https://example.com", method="GET", timeout=30)',
            "expected_tool": "web_fetch",
            "expected_params": ["url", "method", "timeout"]
        },
        
        # 5. memory_read (list parameters)
        {
            "name": "memory_read",
            "input": 'memory_read(query="test", limit=10)',
            "expected_tool": "memory_read",
            "expected_params": ["query", "limit"]
        },
        
        # 6. Standard format
        {
            "name": "standard_format",
            "input": 'tool_call: file_search({"path": "/home/user", "recursive": true})',
            "expected_tool": "file_search",
            "expected_params": ["path", "recursive"]
        },
        
        # 7. Natural language
        {
            "name": "natural_language", 
            "input": 'I need to call the file_operations tool with args {"operation": "write_file", "path": "/tmp/test.txt", "content": "Hello World"}',
            "expected_tool": "file_operations",
            "expected_params": ["operation", "path", "content"]
        }
    ]
    
    print("Testing Universal Tool Call Parsing for All Tools")
    print("=" * 60)
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print(f"Input: {test_case['input']}")
        
        try:
            parsed = parse_tool_calls_universal(test_case['input'])
            
            if not parsed:
                print("❌ FAILED: No tool calls parsed")
                all_passed = False
                continue
            
            # Verificar que encontramos la herramienta esperada
            expected_tool = test_case['expected_tool']
            found_tool = None
            for tc in parsed:
                if expected_tool.lower() in tc['name'].lower():
                    found_tool = tc
                    break
            
            if not found_tool:
                print(f"❌ FAILED: Expected tool '{expected_tool}' not found")
                print(f"   Found tools: {[tc['name'] for tc in parsed]}")
                all_passed = False
                continue
            
            # Verificar parámetros
            expected_params = set(test_case['expected_params'])
            found_params = set(found_tool['args'].keys())
            
            missing_params = expected_params - found_params
            extra_params = found_params - expected_params
            
            if missing_params:
                print(f"❌ FAILED: Missing parameters: {missing_params}")
                all_passed = False
            elif extra_params:
                print(f"⚠️  WARNING: Extra parameters: {extra_params}")
                print(f"✅ PASSED: {found_tool['name']} with params: {found_tool['args']}")
            else:
                print(f"✅ PASSED: {found_tool['name']} with params: {found_tool['args']}")
                
        except Exception as e:
            print(f"❌ FAILED: Exception occurred: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Universal parsing works for all tools!")
    else:
        print("⚠️  Some tests failed. Review the results above.")
    
    return all_passed

if __name__ == "__main__":
    test_all_tools()