import sys
import os
import queue
sys.path.append(os.path.abspath("."))
import logging
logging.basicConfig(level=logging.INFO)

from kogniterm.skills.bundled.call_agents_parallel.scripts.tool import call_agents_parallel
from kogniterm.core.llm_service import LLMService

def run_test():
    print("Iniciando prueba de agentes paralelos...")
    llm = LLMService(use_multi_provider=False)
    
    # Proveemos una queue falsa para interrupt_queue
    iq = queue.Queue()
    
    # Creamos un dummy UI si es necesario, o pasamos None
    class DummyUI:
        is_tui = False
        def print_stream(self, *args, **kwargs): pass
        def write_stream_to_chat(self, *args, **kwargs): pass
        def update_live(self, *args, **kwargs): print(f"UI LIVE UPDATE: {args}")

    ui = DummyUI()

    try:
        # Llamar a la herramienta
        result = call_agents_parallel(
            task_coder="Escribe una función lambda simple en python.",
            task_researcher="Investiga brevemente quién descubrió América.",
            terminal_ui=ui,
            llm_service=llm,
            interrupt_queue=iq
        )
        print("======== RESULTADO ========")
        print(result)
        print("===========================")
    except Exception as e:
        print(f"Prueba falló: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
