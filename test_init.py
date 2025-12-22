
import os
import sys
from kogniterm.core.llm_service import LLMService

try:
    print("Iniciando instancia de LLMService...")
    llm = LLMService()
    print("LLMService instanciado correctamente.")
except Exception as e:
    print(f"Error al instanciar LLMService: {e}")
    import traceback
    traceback.print_exc()
