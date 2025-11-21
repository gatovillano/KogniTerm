import os
import re
import sys

# Mock TerminalUI
class MockTerminalUI:
    def print_message(self, message, style=None):
        print(f"[MockUI] {message}")

# Standalone function for testing (replicating the logic added to KogniTermApp)
def _process_file_tags(text: str, terminal_ui) -> str:
    pattern = r'@(?P<path>[^\s]+)'
    
    def replace_match(match):
        file_path = match.group('path')
        full_path = os.path.abspath(os.path.join(os.getcwd(), file_path))
        
        if os.path.isfile(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                terminal_ui.print_message(f"  📄 Inyectando contenido de: {file_path}", style="dim")
                return f"\n\n--- CONTENIDO DEL ARCHIVO: {file_path} ---\n{content}\n--- FIN DEL ARCHIVO ---\n\n"
            except Exception as e:
                terminal_ui.print_message(f"  ⚠️ Error al leer '{file_path}': {e}", style="red")
                return match.group(0)
        else:
            return match.group(0)

    return re.sub(pattern, replace_match, text)

# Create a dummy file
with open("test_tag.txt", "w") as f:
    f.write("Hello from tagged file!")

# Test
ui = MockTerminalUI()
input_text = "Please analyze @test_tag.txt for me."
output_text = _process_file_tags(input_text, ui)

print(f"Input: {input_text}")
print(f"Output: {output_text}")

expected_content = "Hello from tagged file!"
if expected_content in output_text and "--- CONTENIDO DEL ARCHIVO: test_tag.txt ---" in output_text:
    print("SUCCESS: File content injected.")
else:
    print("FAILURE: File content NOT injected.")

# Clean up
os.remove("test_tag.txt")
