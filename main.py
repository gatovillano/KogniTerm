import sys
import asyncio
from kogniterm.terminal.terminal import start_terminal_interface

if __name__ == "__main__":
    # Comprobar si la bandera -y o --yes está presente
    auto_approve = '-y' in sys.argv or '--yes' in sys.argv
    
    # Ejecutar la interfaz de terminal asíncrona
    try:
        asyncio.run(start_terminal_interface(auto_approve=auto_approve))
    except KeyboardInterrupt:
        print("\nSaliendo de KogniTerm.")