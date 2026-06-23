---
name: plan-creation
version: 1.0.0
author: "KogniTerm Core"
description: "Genera planes detallados y paso a paso para tareas complejas, presentándolos para confirmación antes de ejecución"
category: "planning"
tags: ["planning", "strategy", "workflow", "task_management", "complex_tasks"]
dependencies: ["langchain-core"]
required_permissions: ["network"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill genera planes detallados y paso a paso para tareas complejas, presentándolos al usuario para confirmación antes de la ejecución.

## Herramientas disponibles:

### plan_creation

Genera un plan detallado y paso a paso para tareas complejas.

**Parámetros:**
- `task_description` (string, requerido): Una descripción detallada de la tarea compleja para la cual se necesita crear un plan

**Ejemplo:**
```json
{
  "tool": "plan_creation",
  "args": {
    "task_description": "Crear una aplicación web completa con frontend, backend y base de datos"
  }
}
```

## Formato de salida:

La herramienta devuelve un JSON con la siguiente estructura:

```json
{
  "status": "requires_confirmation",
  "operation": "plan_creation",
  "plan_title": "Título del Plan",
  "plan_steps": [
    {
      "step": 1,
      "description": "Descripción del paso 1"
    },
    {
      "step": 2,
      "description": "Descripción del paso 2"
    }
  ],
  "message": "Se ha generado un plan para: [tarea]",
  "task_description": "[tarea]"
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** network
- **Requiere allowlisting:** false
- **Auto-aprobado:** true
- **Requiere sandbox:** false

## Requisitos:

- Se necesita acceso al servicio LLM para generar el plan
- El plan se genera en formato JSON estructurado
- Los planes requieren confirmación del usuario antes de ejecución
- Cada paso debe ser una acción específica que el agente pueda ejecutar

## Uso recomendado:

1. Usa esta herramienta cuando una tarea involucra múltiples pasos
2. Ideal para tareas estratégicas que requieren un enfoque estructurado
3. El plan se presenta al usuario para confirmación
4. Cada paso debe ser claro, conciso y ejecutable
5. El formato JSON permite procesamiento automático del plan

## Características:

- **Planificación estructurada**: Los planes se generan como listas numeradas de acciones
- **Formato JSON**: Salida estructurada para fácil procesamiento
- **Confirmación requerida**: Los planes deben ser aprobados por el usuario
- **Pasos ejecutables**: Cada paso es una acción específica que el agente puede realizar
- **Flexibilidad**: Adapta el plan según la complejidad de la tarea

## Limitaciones:

- Requiere acceso a un servicio LLM funcional
- La calidad del plan depende del modelo de lenguaje utilizado
- Los planes generados son sugerencias y pueden requerir ajustes
- No garantiza que todos los pasos sean exitosos al ejecutarse