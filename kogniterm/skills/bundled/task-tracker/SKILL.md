---
name: task-tracker
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

## ⚠️ REGLAS OBLIGATORIAS (incumplirlas causa fallos)

1. **SIEMPRE** inicializa el plan en el PRIMER turno de una tarea compleja, antes de cualquier otra acción.
2. **SIEMPRE** usa el mismo `agent_name` dentro de una misma sesión de trabajo.
3. **SIEMPRE** marca `in-progress` la tarea actual antes de ejecutar la acción principal.
4. **SIEMPRE** marca `done` la tarea inmediatamente después de completarla.
5. **SIEMPRE** consulta el estado con `get` si pierdes el hilo de qué tarea sigue.

## Formato de llamada

```json
{
  "tool": "task_tracker",
  "args": {
    "action": "init|update|get|show",
    "agent_name": "NombreAgente",
    "plan": ["tarea1", "tarea2"],
    "task_index": 0,
    "status": "pending|in-progress|done"
  }
}
```

## Acciones permitidas

### init
- **Requerido**: `agent_name`, `plan`
- **Efecto**: Crea/reinicia el plan de tareas para el agente
- **Ejemplo**:
```json
{"action": "init", "agent_name": "BashAgent", "plan": ["Analizar logs", "Generar reporte"]}
```

### update
- **Requerido**: `action`, `agent_name`, `task_index`, `status`
- **Efecto**: Actualiza el estado de una tarea específica
- **Ejemplo**:
```json
{"action": "update", "agent_name": "BashAgent", "task_index": 0, "status": "in-progress"}
```

### get
- **Requerido**: `action`, `agent_name`
- **Efecto**: Muestra el estado actual del plan
- **Ejemplo**:
```json
{"action": "get", "agent_name": "BashAgent"}
```

### show
- **Requerido**: `action`, `agent_name`
- **Efecto**: Fuerza la actualización del panel visual
- **Ejemplo**:
```json
{"action": "show", "agent_name": "BashAgent"}
```

## Valores válidos

- **action**: `init`, `update`, `get`, `show`
- **status**: `pending`, `in-progress`, `done`
- **task_index**: entero >= 0 (0-indexed)

## Errores comunes a evitar

1. ❌ Olvidar `agent_name` en la llamada
2. ❌ Usar `task_index` fuera de rango
3. ❌ No actualizar el estado después de `init`
4. ❌ Mezclar agentes con diferentes `agent_name`
5. ❌ Usar `show` sin antes haber hecho `init`

## Flujo recomendado

1. `init` con lista de tareas
2. Por cada tarea:
   - `update` a `in-progress` antes de empezar
   - Ejecutar la acción
   - `update` a `done` al terminar
3. `get` para verificar estado final
