import re
import json
import random
import string
from typing import List, Dict, Any, Optional

def generate_short_id(length: int = 9) -> str:
    """Genera un ID alfanum\u00e9rico corto compatible con proveedores estrictos como Mistral."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def extract_balanced_content(text: str, start_pos: int) -> Optional[str]:
    """Extrae contenido balanceado entre {}, [] o () manejando anidamiento y strings."""
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
    """Extrae argumentos de una cadena de texto de forma permisiva."""
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
            if value and value.isdigit(): 
                try: value = int(value)
                except ValueError: pass
            result[key] = value
        return result

def parse_tool_calls_from_text(text: str, tool_names: List[str], id_generator=None) -> List[Dict[str, Any]]:
    """
    Analiza el texto para encontrar llamadas a herramientas usando m\u00faltiples estrategias.
    """
    if not text:
        return []
    
    if id_generator is None:
        id_generator = generate_short_id

    tool_calls = []
    seen_combinations = set()
    valid_tool_calls = []
    
    # 1. Limpieza inicial: Quitar caracteres de control invisibles
    clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    # ESTRATEGIA A: Patrones expl\u00edcitos
    explicit_patterns = [
        r'LLAMADA_A_HERRAMIENTA:\s*(\w+)',
        r'Herramienta:\s*(\w+)',
        r'\[TOOL_CALL\]\s*(\w+)',
        r'Tool:\s*(\w+)'
    ]
    for pat in explicit_patterns:
        for match in re.finditer(pat, clean_text, re.IGNORECASE):
            tool_name = match.group(1).strip()
            real_name = next((k for k in tool_names if k.lower() == tool_name.lower()), None)
            if real_name:
                search_start = match.end()
                json_start = clean_text.find('{', search_start)
                if json_start != -1 and (json_start - search_start) < 200:
                    args_str = extract_balanced_content(clean_text, json_start)
                    if args_str:
                        args = extract_args(args_str)
                        tool_calls.append({"id": id_generator(), "name": real_name, "args": args})

    # ESTRATEGIA B: Lenguaje natural con JSON inline - patrones amplios
    # Captura: "usa search con {...}", "usa 'search' con {...}", "usa \"search\" con {...}"
    nl_patterns = [
        r'(?:usa|usar|utiliza|usamos|usando|use)\s+(?:la\s+)?["\']?(\w+)["\']?\s*(?:,?\s*(?:luego\s+)?(?:con\s+(?:los\s+)?argumentos?|con\s+args?)\s*)?\s*(\{[^}]+\})',
        r'(?:llama?r?|llamamos)\s+(?:a\s+)?["\']?(\w+)["\']?\s*(?:con\s+(?:argumentos?|args?)\s*)?\s*(\{[^}]+\})',
        r'(?:vamos\s+a\s+)?(?:usar|llamar)\s+["\']?(\w+)["\']?\s*(?:con\s+(?:argumentos?|args?)\s*)?\s*(\{[^}]+\})',
        r'(?:usa|usar|utiliza)\s+(\w+)\s*(?:con\s+(?:argumentos?|args?)\s*)?\s*(\{[^}]+\})',
        r'(\w+)\s*con\s+(?:argumentos?|args?)\s*(\{[^}]+\})',
        r'(?:usa|usamos)\s+(\w+)\s*\(\s*(\{[^}]+\})\s*\)',
    ]
    for pat in nl_patterns:
        for match in re.finditer(pat, clean_text, re.IGNORECASE):
            tool_name = match.group(1).strip()
            args_str = match.group(2).strip()
            real_name = next((k for k in tool_names if k.lower() == tool_name.lower()), None)
            if real_name:
                args_str_balanced = extract_balanced_content(clean_text, match.start(2))
                if args_str_balanced:
                    args = extract_args(args_str_balanced)
                else:
                    args = extract_args(args_str)
                tool_calls.append({"id": id_generator(), "name": real_name, "args": args})

    # ESTRATEGIA C: Bloques JSON estructurados
    for i in range(len(clean_text)):
        if clean_text[i] == '{':
            json_str = extract_balanced_content(clean_text, i)
            if json_str:
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict) and data:
                        name = data.get("name") or data.get("tool") or data.get("function")
                        args = data.get("args") or data.get("arguments") or data.get("parameters") or {}
                        
                        if name:
                            real_name = next((k for k in tool_names if k.lower() == str(name).lower()), None)
                            if real_name:
                                tool_calls.append({"id": id_generator(), "name": real_name, "args": args})
                        
                        elif len(data) == 1:
                            potential_name = list(data.keys())[0]
                            if str(potential_name).lower() in [k.lower() for k in tool_names]:
                                real_name = next(k for k in tool_names if k.lower() == str(potential_name).lower())
                                tool_calls.append({"id": id_generator(), "name": real_name, "args": data[potential_name]})
                        
                        elif not any(k in data for k in ["name", "tool", "function"]):
                            lookback = clean_text[max(0, i-300):i].lower()
                            for tname in tool_names:
                                if tname.lower() in lookback:
                                    tool_calls.append({"id": id_generator(), "name": tname, "args": data})
                                    break
                except:
                    continue

    # ESTRATEGIA D: Formatos Legacy tipo Codigo "name({args})"
    legacy_pattern = r'(\w+)\s*\(([\{].*?[\}])\)'
    for match in re.finditer(legacy_pattern, clean_text, re.DOTALL):
        name, args_str = match.groups()
        real_name = next((k for k in tool_names if k.lower() == name.lower()), None)
        if real_name:
            args = extract_args(args_str)
            tool_calls.append({"id": id_generator(), "name": real_name, "args": args})

    # Filtrar duplicados y consolidar
    for tc in tool_calls:
        try:
            args_json = json.dumps(tc['args'], sort_keys=True)
            key = f"{tc['name']}:{args_json}"
            if key not in seen_combinations:
                seen_combinations.add(key)
                valid_tool_calls.append(tc)
        except:
            if tc not in valid_tool_calls: 
                valid_tool_calls.append(tc)

    return valid_tool_calls
