---
name: set-llm-instructions
version: 1.0.0
author: "KogniTerm Core"
description: "Permite establecer instrucciones o reglas personalizadas para el LLM, modificando su comportamiento en las interacciones futuras"
category: "llm"
tags: ["llm", "instructions", "behavior", "customization", "settings"]
dependencies: []
required_permissions: []
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite establecer instrucciones o reglas personalizadas para el LLM, modificando su comportamiento en las interacciones futuras.

## Herramientas disponibles:

### set_llm_instructions

Establece instrucciones o reglas personalizadas para el LLM.

**Parámetros:**
- `instructions` (string, requerido): Las instrucciones o reglas que se deben dar al LLM para guiar su comportamiento

**Ejemplo:**
```json
{
  "tool": "set_llm_instructions",
  "args": {
    "instructions": "Responde siempre de forma formal y profesional. Usa lenguaje técnico cuando sea apropiado. Proporciona ejemplos concretos para ilustrar tus puntos."
  }
}
```

## Uso recomendado:

1. Usa esta herramienta para personalizar el comportamiento del LLM
2. Ideal para definir el tono, el formato de respuesta, o cualquier directriz específica
3. Las instrucciones afectan todas las interacciones futuras con el LLM
4. Útil para mantener consistencia en el estilo de comunicación
5. Permite adaptar el comportamiento del LLM a diferentes contextos

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** Ninguno
- **Requiere allowlisting:** false
- **Auto-aprobado:** true
- **Requiere sandbox:** false

## Requisitos:

- No requiere dependencias externas
- Las instrucciones se almacenan en memoria durante la sesión
- Las instrucciones personalizadas se aplican a todas las llamadas futuras al LLM
- Las instrucciones pueden ser modificadas en cualquier momento

## Formato de instrucciones:

Las instrucciones pueden incluir:

### Estilo de comunicación
- Tono (formal, informal, amigable, técnico)
- Nivel de detalle (conciso, detallado)
- Uso de emojis o lenguaje coloquial

### Formato de respuesta
- Estructura de respuestas (listas, tablas, párrafos)
- Formato de código (bloques, inline)
- Longitud de respuestas

### Contenido preferido
- Temas a enfatizar o evitar
- Nivel de technicalidad
- Enfoque en aspectos prácticos o teóricos

### Restricciones
- Límites de longitud
- Temas prohibidos
- Formatos no permitidos

## Limitaciones:

- Las instrucciones solo afectan al LLM actual
- No persisten entre sesiones diferentes
- Las instrucciones muy complejas pueden no ser interpretadas correctamente
- El LLM puede ignorar instrucciones que entren en conflicto con sus capacidades fundamentales