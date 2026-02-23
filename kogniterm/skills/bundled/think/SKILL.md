---
name: think
version: 1.0.0
author: "KogniTerm Core"
description: "Herramienta de razonamiento y planificación para procesos de pensamiento profundo"
category: "thinking"
tags: ["reasoning", "planning", "analysis", "thinking", "decision-making", "cognitive"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill proporciona capacidades de razonamiento y planificación para procesos de pensamiento profundo. Permite al sistema analizar situaciones, planificar acciones y tomar decisiones informadas antes de ejecutar otras herramientas.

## Herramientas disponibles:

### think

Realiza razonamiento detallado y análisis antes de tomar decisiones o ejecutar acciones.

**Parámetros:**
- `thought` (string, requerido): El razonamiento detallado o análisis antes de realizar una acción

**Ejemplo:**
```json
{
  "tool": "think",
  "args": {
    "thought": "Necesito analizar el problema actual. El usuario quiere migrar herramientas al formato skill. Primero debo revisar las herramientas existentes, luego crear la estructura de directorios, migrar la lógica y finalmente probar la funcionalidad. Es importante mantener la compatibilidad con el sistema existente."
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: low** - No requiere aprobación
- **Permisos requeridos:** ninguno
- **Requiere allowlisting:** false
- **Auto-aprobado:** true
- **Requiere sandbox:** false

## Requisitos:

- No requiere dependencias externas
- Funciona en cualquier entorno
- No requiere permisos especiales
- Es segura para uso en cualquier contexto

## Uso recomendado:

1. Usa esta herramienta antes de ejecutar acciones complejas o importantes
2. Ideal para planificación de tareas y análisis de problemas
3. Útil para documentar el proceso de pensamiento
4. Ayuda a tomar decisiones informadas
5. Facilita la depuración y comprensión de la lógica del sistema
6. Es obligatoria para procesos de pensamiento profundo
7. Puede usarse para validar suposiciones antes de ejecutar código
8. Útil para explicar el razonamiento detrás de decisiones complejas