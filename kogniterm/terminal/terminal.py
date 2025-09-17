import sys
import os
from dotenv import load_dotenv # Importar load_dotenv
from prompt_toolkit.completion import Completer, Completion
from rich.text import Text
from rich.syntax import Syntax
import re

load_dotenv() # Cargar variables de entorno al inicio

# New helper function
def _format_text_with_basic_markdown(text: str) -> Text:
    """Applies basic Markdown-like formatting to a string using rich.Text."""
    formatted_text = Text()
    
    lines = text.split('\n')
    
    in_code_block = False
    code_block_lang = ""
    code_block_content = []

    for line in lines:
        code_block_match = re.match(r"```(\w*)", line)
        if code_block_match:
            if in_code_block: # End of code block
                in_code_block = False
                if code_block_content:
                    code_str = "\n".join(code_block_content)
                    lexer = code_block_lang if code_block_lang else "plaintext"
                    formatted_text.append(Text.from_ansi(str(Syntax(code_str, lexer, theme="monokai", line_numbers=False))))
                    code_block_content = []
                formatted_text.append("\n")
            else: # Start of code block
                in_code_block = True
                code_block_lang = code_block_match.group(1) if code_block_match.group(1) else ""
                formatted_text.append("\n")
        elif in_code_block:
            code_block_content.append(line)
        else:
            # Apply inline formatting (bold)
            parts = re.split(r"(\*\*.*?\*\*)", line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    formatted_text.append(part[2:-2], style="bold")
                else:
                    formatted_text.append(part)
            formatted_text.append("\n")

    if in_code_block and code_block_content:
        code_str = "\n".join(code_block_content)
        lexer = code_block_lang if code_block_lang else "plaintext"
        formatted_text.append(Text.from_ansi(str(Syntax(code_str, lexer, theme="monokai", line_numbers=False))))

    return formatted_text

# --- Importar KogniTermApp ---
from kogniterm.terminal.kogniterm_app import KogniTermApp
from kogniterm.core.llm_service import LLMService # Importar la CLASE LLMService
from kogniterm.core.tools.file_operations_tool import FileOperationsTool # Importar FileOperationsTool para acceder a glob

class FileCompleter(Completer):
    def __init__(self, file_operations_tool, show_indicator: bool = True):
        self.file_operations_tool = file_operations_tool
        self.show_indicator = show_indicator

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        
        if '@' not in text_before_cursor:
            return # No estamos en modo de autocompletado de archivos

        current_input_part = text_before_cursor.split('@')[-1]
        
        base_path = os.getcwd()

        include_hidden = current_input_part.startswith('.')

        try:
            all_relative_items = self.file_operations_tool._list_directory(
                path=base_path,
                recursive=True,
                include_hidden=include_hidden,
                silent_mode=not self.show_indicator
            )
            
            suggestions = []
            for relative_item_path in all_relative_items:
                absolute_item_path = os.path.join(base_path, relative_item_path)
                
                display_item = relative_item_path
                if os.path.isdir(absolute_item_path):
                    display_item += '/'

                if current_input_part.lower() in display_item.lower():
                    suggestions.append(display_item)
            
            suggestions.sort()

            for suggestion in suggestions:
                start_position = -len(current_input_part)
                yield Completion(suggestion, start_position=start_position)

        except Exception as e:
            print(f"Error en FileCompleter: {e}", file=sys.stderr)


def main():
    """Función principal para iniciar la terminal de KogniTerm."""
    app = KogniTermApp()
    app.run()

if __name__ == "__main__":
    main()
