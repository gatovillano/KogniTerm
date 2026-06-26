---
name: call-agents-parallel
version: 2.0.0
description: Invoca N agentes especializados en paralelo con visualización en pestañas
---

Esta herramienta permite lanzar **múltiples agentes especializados simultáneamente**, cada uno trabajando en su propia tarea de forma independiente.

La TUI crea dinámicamente una pestaña por agente en el panel inferior para visualizar el streaming de razonamiento y output de cada uno en tiempo real.

### Tipos de agente disponibles

| type | Descripción |
|------|-------------|
| `code_agent` | Motor de desarrollo profundo (DeepCoder): escribe, edita y valida código |
| `researcher_agent` | Motor de investigación profunda (DeepResearcher): lee archivos, busca contexto |
| cualquier string | Agente dinámico genérico — usar con `system_prompt` personalizado |

### Ejemplo de uso (2 agentes predefinidos)
```json
{
  "agents": [
    { "name": "Desarrollador", "task": "Implementar la función X en utils.py", "type": "code_agent" },
    { "name": "Investigador",  "task": "Analizar el contexto del módulo Y",     "type": "researcher_agent" }
  ]
}
```

### Ejemplo de uso (3 agentes, uno dinámico)
```json
{
  "agents": [
    { "name": "Tester",       "task": "Escribir tests para el módulo Z",    "type": "tester",           "system_prompt": "Eres un experto en testing con pytest." },
    { "name": "Refactorizador","task": "Limpiar y optimizar el módulo Z",   "type": "code_agent" },
    { "name": "Documentador",  "task": "Generar docstrings para el módulo Z","type": "researcher_agent" }
  ]
}
```

### Notas
- Mínimo 1 agente, máximo 8 agentes simultáneos.
- Los agentes son autónomos y no solicitan autorización para ejecutar comandos.
- Al finalizar, el resumen de cada agente se muestra en el chat principal.
