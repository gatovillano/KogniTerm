import re, json

def extract_balanced_content(text, start_pos):
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

text = 'Voy a usar la herramienta "search" con argumentos {"query": "test"}'
clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
print('Clean:', repr(clean_text))

for i in range(len(clean_text)):
    if clean_text[i] == '{':
        json_str = extract_balanced_content(clean_text, i)
        print('JSON str:', json_str)
        if json_str:
            data = json.loads(json_str)
            print('Data:', data)
            print('len:', len(data))
            print('Has name/tool/function?', any(k in data for k in ['name','tool','function']))
            if not any(k in data for k in ['name','tool','function']):
                lookback = clean_text[max(0,i-300):i].lower()
                print('Lookback:', repr(lookback))
                for tname in ['search','read_file']:
                    if tname.lower() in lookback:
                        print('Found tool:', tname)
        break
