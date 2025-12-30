# Flujo de Trabajo del Nuevo ResearcherAgent con CrewAI

## Diagrama de Flujo

```mermaid
graph TD
    A[Usuario] --> B[Planificador]
    B --> C[Agentes Investigadores]
    C --> D[Sintetizador]
    D --> E[Generador de Informes]
    E --> F[Usuario: Informe en Markdown]

    subgraph Agentes Investigadores
        C1[Internet]
        C2[GitHub]
        C3[Código Base]
        C4[Análisis de Código]
    end

    C --> C1
    C --> C2
    C --> C3
    C --> C4
```

## Descripción del Flujo

1. **Usuario**: Envía una consulta o solicitud de investigación.
2. **Planificador**: Decide qué agentes investigadores son necesarios para responder a la consulta.
3. **Agentes Investigadores**: Cada agente realiza su tarea específica:
   - **Internet**: Busca información en la web.
   - **GitHub**: Investiga repositorios y código en GitHub.
   - **Código Base**: Analiza el código local.
   - **Análisis de Código**: Realiza análisis estático y métricas.
4. **Sintetizador**: Recopila los resultados de los investigadores y genera un JSON estructurado.
5. **Generador de Informes**: Convierte el JSON en un informe en Markdown para el usuario.
