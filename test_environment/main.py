import os
from researcher_crew import ResearcherCrew
# Asumimos que el entorno ya tiene configuradas las variables para el LLM 
# que usa KogniTerm (ej. OpenAI, Anthropic, etc.)
from langchain_openai import ChatOpenAI 

def run_test():
    print("🚀 Iniciando prueba del nuevo ResearcherAgent Multi-Agente...")
    
    # 1. Configurar el LLM (usando los estándares de la app)
    # Por defecto CrewAI busca OPENAI_API_KEY, pero aquí lo explicitamos
    llm = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL_NAME", "gpt-4-turbo-preview"),
        temperature=0.2
    )

    # 2. Instanciar la Crew
    crew_orchestrator = ResearcherCrew(llm)

    # 3. Definir una consulta de prueba técnica
    query = "Analizar la estructura actual de los agentes en el directorio \'agents/\' y proponer mejoras de modularidad."

    print(f"🔍 Investigando: {query}\n")
    
    # 4. Ejecutar el proceso
    result = crew_orchestrator.run(query)

    # 5. Guardar el resultado
    output_file = "test_environment/final_report.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"\n✅ Prueba completada con éxito!")
    print(f"📄 Informe generado en: {output_file}")

if __name__ == "__main__":
    run_test()
