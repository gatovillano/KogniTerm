import re

file_path = '/home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py'

with open(file_path, 'rb') as f:
    content = f.read().decode('utf-8', errors='replace')

# Look for the broken section - the regex needs to match Strategy C
# In the corrupted file it looks like:
#        i = 0
#        while i < len(clean_text):
#            # Buscar algo que parezca un nombre de funciM-CM-3n seguido de (
#                # Solo aceptar funciones que estM-CM-)n en el tool_map o sean comandos conocidos
# ...
#            i += 1

# I'll use a more specific regex to find the corrupted block
pattern = re.compile(r'        i = 0\n        while i < len\(clean_text\):\n            # Buscar algo que parezca.*?i \+= 1', re.DOTALL)

new_code = r"""        i = 0
        while i < len(clean_text):
            # Buscar algo que parezca un nombre de funcion seguido de (
            match = re.search(r'\b(\w+)\s*\(', clean_text[i:])
            if match:
                name = match.group(1)
                
                # Solo aceptar funciones que esten en el tool_map o sean comandos conocidos
                if name not in self.tool_map and name.lower() not in self.tool_map and name not in ['call_agent', 'think', 'execute_command']:
                    i += match.end(0)
                    continue
                    
                # Evitar funciones comunes de Python que no son herramientas
                if name.lower() in ['print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'range', 'open', 'with', 'if', 'for', 'while', 'def', 'class']:
                    i += match.end(0)
                    continue
                    
                start_paren = i + match.start(0) + match.end(0) - match.start(0) - 1
                content = self._extract_balanced_content(clean_text, start_paren)
                if content:
                    # Quitar los parentesis exteriores
                    args_str = content[1:-1].strip()
                    
                    # Si el contenido empieza con { o [, es probable que sea JSON o lista
                    # Si no, es probable que sea Python-style arguments key=value
                    args = self.extract_args(args_str)
                    if args or args_str.strip():
                        tool_calls.append({"id": self._generate_short_id(), "name": name, "args": args})
                    
                    i = start_paren + len(content)
                    continue
            i += 1"""

# Use lambda to avoid backslash issues in sub
updated_content = pattern.sub(lambda m: new_code, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(updated_content)

print("File updated successfully")
