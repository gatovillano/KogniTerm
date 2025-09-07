from dotenv import load_dotenv
load_dotenv() # Cargar variables de entorno desde .env

import sys
from kogniterm.terminal.terminal import start_terminal_interface
from kogniterm.core.llm_service import LLMService # Importar LLMService

def run_kogniterm():
    """
    Función de punto de entrada para KogniTerm.
    Carga variables de entorno, inicializa el LLMService
    y lanza la interfaz de la terminal.
    """
    auto_approve = '-y' in sys.argv or '--yes' in sys.argv
    llm_service_instance = LLMService()
    start_terminal_interface(llm_service=llm_service_instance, auto_approve=auto_approve)

if __name__ == "__main__":
    run_kogniterm()
