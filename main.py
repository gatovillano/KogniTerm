from dotenv import load_dotenv
load_dotenv() # Cargar variables de entorno desde .env

import sys
from kogniterm.terminal.terminal import start_terminal_interface
from kogniterm.core.llm_service import LLMService # Importar LLMService

if __name__ == "__main__":
    # Comprobar si la bandera -y o --yes está presente
    auto_approve = '-y' in sys.argv or '--yes' in sys.argv
    
    # Crear una única instancia de LLMService
    llm_service_instance = LLMService()

    start_terminal_interface(auto_approve=auto_approve)
