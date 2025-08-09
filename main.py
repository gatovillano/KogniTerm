import sys
from gemini_interpreter.terminal.terminal import start_terminal_interface

if __name__ == "__main__":
    # Comprobar si la bandera -y o --yes está presente
    auto_approve = '-y' in sys.argv or '--yes' in sys.argv
    
    start_terminal_interface(auto_approve=auto_approve)