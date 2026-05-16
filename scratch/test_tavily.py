import os
from kogniterm.skills.bundled.web_tools.scripts.tavily_search import tavily_search_sync

# Necesitamos TAVILY_API_KEY
api_key = os.getenv("TAVILY_API_KEY")
print(f"API KEY: {'Configurada' if api_key else 'NO CONFIGURADA'}")

if api_key:
    query = "Hermes Agent memory management repository"
    print(f"Buscando: {query}...")
    try:
        result = tavily_search_sync(query)
        print(f"RESULTADO (primeros 500 chars):\n{result[:500]}")
        if not result:
            print("¡EL RESULTADO ESTÁ VACÍO!")
    except Exception as e:
        print(f"ERROR: {e}")
else:
    print("Por favor, configura TAVILY_API_KEY")
