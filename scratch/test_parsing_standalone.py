import re
import json
import random
import string
from typing import List, Dict, Any, Optional

def _generate_short_id(length: int = 9) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def _extract_balanced_content(text: str, start_pos: int) -> Optional[str]:
    if start_pos >= len(text): return None
    chars = {'{': '}', '[': ']', '(': ')'}
    open_char = text[start_pos]
    if open_char not in chars: return None
    close_char = chars[open_char]
    
    depth = 0
    in_string = False
    string_char = None
    for i in range(start_pos, len(text)):
        char = text[i]
        if char in ['"', "'"] and (i == 0 or text[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
        
        if not in_string:
            if char == open_char: depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0: return text[start_pos : i + 1]
    return None

def extract_args(args_str: str) -> Dict[str, Any]:
    if not args_str: return {}
    args_str = args_str.strip()
    try:
        return json.loads(args_str)
    except:
        result = {}
        pair_pattern = r'(\w+)\s*[:=]\s*(?:"([^"]*)"|\'([^\']*)\'|(\d+)|([^\s,{}]+))'
        for m in re.finditer(pair_pattern, args_str):
            key = m.group(1)
            value = m.group(2) or m.group(3) or m.group(4) or m.group(5)
            if value and value.isdigit(): value = int(value)
            result[key] = value
        return result

def _parse_tool_calls_from_text(text: str, tool_map: Dict = None) -> List[Dict[str, Any]]:
    if not text:
        return []

    tool_calls = []
    seen_combinations = set()
    valid_tool_calls = []
    
    clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    explicit_patterns = [
        r'LLAMADA_A_HERRAMIENTA:\s*(\w+)',
        r'Herramienta:\s*(\w+)',
        r'\[TOOL_CALL\]\s*(\w+)',
        r'Tool:\s*(\w+)'
    ]
    for pat in explicit_patterns:
        for match in re.finditer(pat, clean_text, re.IGNORECASE):
            tool_name = match.group(1).strip()
            search_start = match.end()
            json_start = clean_text.find('{', search_start)
            if json_start != -1 and (json_start - search_start) < 200:
                args_str = _extract_balanced_content(clean_text, json_start)
                if args_str:
                    args = extract_args(args_str)
                    tool_calls.append({"id": _generate_short_id(), "name": tool_name, "args": args})

    i = 0
    while i < len(clean_text):
        if clean_text[i] == '{':
            json_str = _extract_balanced_content(clean_text, i)
            if json_str:
                tool_call_added = False
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict) and data:
                        name = data.get("name") or data.get("tool") or data.get("function")
                        args = data.get("args") or data.get("arguments") or data.get("parameters") or {}
                        
                        if name:
                            tool_calls.append({"id": _generate_short_id(), "name": str(name), "args": args})
                            tool_call_added = True
                        elif len(data) == 1:
                            potential_name = list(data.keys())[0]
                            potential_args = data[potential_name]
                            if isinstance(potential_args, dict):
                                tool_calls.append({"id": _generate_short_id(), "name": potential_name, "args": potential_args})
                                tool_call_added = True
                        
                        if not tool_call_added and tool_map:
                            lookback_start = max(0, i - 300)
                            lookback_text = clean_text[lookback_start:i]
                            for tool_name in tool_map.keys():
                                if re.search(r'\b' + re.escape(tool_name) + r'\b', lookback_text, re.IGNORECASE):
                                    tool_calls.append({"id": _generate_short_id(), "name": tool_name, "args": data})
                                    tool_call_added = True
                                    break
                except:
                    pass
                i += len(json_str)
                continue
        i += 1

    # ESTRATEGIA C: Formatos Legacy tipo Código "name({args})" o "name[{args}]"
    # O Python-style "name(arg=val, ...)"
    # Primero buscamos patrones de función: nombre(
    i = 0
    while i < len(clean_text):
        # Buscar algo que parezca un nombre de función seguido de (
        match = re.search(r'\b(\w+)\s*\(', clean_text[i:])
        if match:
            name = match.group(1)
            start_paren = i + match.start(0) + match.end(0) - match.start(0) - 1
            
            # Evitar funciones comunes de Python que no son herramientas
            if name.lower() in ['print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'range', 'open', 'with', 'if', 'for', 'while', 'def', 'class']:
                i += match.end(0)
                continue
                
            content = _extract_balanced_content(clean_text, start_paren)
            if content:
                # Quitar los paréntesis exteriores
                args_str = content[1:-1].strip()
                
                # Si el contenido empieza con { o [, es probable que sea JSON o lista
                # Si no, es probable que sea Python-style arguments key=value
                args = extract_args(args_str)
                if args or args_str.strip():
                    tool_calls.append({"id": _generate_short_id(), "name": name, "args": args})
                
                i += match.start(0) + len(content)
                continue
        i += 1

    for tc in tool_calls:
        try:
            args_json = json.dumps(tc['args'], sort_keys=True)
            key = f"{tc['name']}:{args_json}"
            if key not in seen_combinations:
                seen_combinations.add(key)
                valid_tool_calls.append(tc)
        except:
            if tc not in valid_tool_calls: valid_tool_calls.append(tc)

    return valid_tool_calls

def test_parsing():
    test_inputs = [
        'call_agent(task="investigar el codigo", agent_name="researcher")',
        'execute_command(command="ls -la")',
        'LLAMADA_A_HERRAMIENTA: execute_command {"command": "ls -la"}',
        '{"name": "execute_command", "args": {"command": "ls -la"}}',
        'He decidido usar la herramienta execute_command con el comando "ls -la". execute_command(command="ls -la")',
        'Mira esto: call_agent({"task": "test"})'
    ]
    
    for i, text in enumerate(test_inputs):
        print(f"\nTest {i+1}: {text}")
        calls = _parse_tool_calls_from_text(text)
        print(f"Result: {calls}")

if __name__ == "__main__":
    test_parsing()
