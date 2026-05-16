---
name: task_tracker
version: 1.0.0
author: "KogniTerm Core"
description: "Gestiona y trackea el progreso de tareas en un plan de trabajo complejo"
category: "utility"
tags: ["tasks", "tracking", "workflow", "management", "plan"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite gestionar una lista de tareas dinámica para mantener el foco en misiones complejas.

## Herramientas disponibles:

### task_tracker

Permite inicializar un plan, actualizar el estado de las tareas y obtener el resumen del progreso.

**Parámetros:**
- `action` (string, requerido): Acción a realizar: 'init', 'update', 'get'.
- `plan` (array de strings, opcional): Lista de tareas para inicializar (solo para 'init').
- `task_index` (integer, opcional): Índice de la tarea a actualizar (0-indexed, solo para 'update').
- `status` (string, opcional): Nuevo estado de la tarea: 'pending', 'in-progress', 'done' (solo para 'update').

**Ejemplos:**

1. Inicializar plan:
```json
{
  "action": "init",
  "plan": ["Investigar bug", "Implementar fix", "Validar con tests"]
}
```

2. Marcar tarea en progreso:
```json
{
  "action": "update",
  "task_index": 0,
  "status": "in-progress"
}
```

3. Obtener estado:
```json
{
  "action": "get"
}
```

## Uso recomendado:

1. **SIEMPRE** inicializa un plan al comienzo de una tarea compleja.
2. Actualiza el estado a `in-progress` al empezar una tarea y a `done` al terminarla.
3. Consulta el estado periódicamente para no perder el contexto.
