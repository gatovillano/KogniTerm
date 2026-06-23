---
name: call-agent
version: 1.0.0
author: "KogniTerm Core"
description: "Invoca agentes especializados para realizar tareas complejas como desarrollo de código e investigación profunda"
category: "agents"
tags: ["agent", "code", "research", "delegation", "specialized"]
dependencies: ["langchain-core", "rich"]
required_permissions: ["network", "filesystem"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite invocar agentes especializados para realizar tareas complejas que requieren capacidades específicas.

## Herramientas disponibles:

### call_agent

Invoca a un agente especializado para realizar tareas complejas.

**Parámetros:**
- `agent_name` (string, requerido): El nombre del agente a invocar: 'code_agent' o 'researcher_agent'
- `task` (string, requerido): La tarea específica que el agente debe realizar

**Ejemplo:**
```json
{
  "tool": "call_agent",
  "args": {
    "agent_name": "code_agent",
    "task": "Crea un script Python para procesar datos CSV y generar un informe"
  }
}
```

## Agentes disponibles:

### Code Agent
- **Propósito**: Desarrollo de código, edición de archivos, tareas técnicas
- **Capacidades**: Escribir, modificar y analizar código en múltiples lenguajes
- **Ideal para**: Scripts, aplicaciones, refactorización, análisis de código

### Research Agent
- **Propósito**: Investigación profunda, análisis complejo, búsqueda de información
- **Capacidades**: Realizar investigaciones exhaustivas, analizar documentos, resumir información
- **Ideal para**: Investigación de mercado, análisis de documentos, búsqueda de información técnica

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** network, filesystem
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Requisitos:

- Se necesita acceso a los módulos de agentes del sistema
- Los agentes tienen límites de recursión configurables (100 por defecto)
- Los resultados se muestran en formato amigable con Rich

## Uso recomendado:

1. Usa esta herramienta para tareas que requieren especialización profunda
2. Ideal cuando la tarea excede las capacidades del agente principal
3. Los agentes especializados tienen su propio contexto y memoria
4. Los resultados incluyen visualización enriquecida con formato Markdown
5. Los agentes pueden manejar tareas complejas con múltiples pasos