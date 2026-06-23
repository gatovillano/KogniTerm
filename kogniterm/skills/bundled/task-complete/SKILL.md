---
name: task-complete
version: 1.0.0
author: "KogniTerm Core"
description: "Señala que la tarea actual está completada y proporciona un resumen de las acciones del LLM durante la tarea"
category: "workflow"
tags: ["completion", "summary", "workflow", "end_task", "finalization"]
dependencies: ["rich"]
required_permissions: []
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill señala que la tarea actual está completada y proporciona un resumen amigable de las acciones del LLM durante la tarea.

## Herramientas disponibles:

### task_complete

Señala que la tarea actual está completada y proporciona un resumen de las acciones del LLM.

**Parámetros:**
- No requiere parámetros, ya que lee el historial del agente para generar el resumen

**Ejemplo:**
```json
{
  "tool": "task_complete",
  "args": {}
}
```

## Funcionamiento:

1. **Generación de resumen**: La herramienta analiza el historial de acciones del agente
2. **Creación de contenido**: Invoca al LLM para generar un resumen amigable y humano
3. **Visualización**: Muestra el resumen en un panel enriquecido con Rich
4. **Finalización**: Devuelve un estado de éxito con el mensaje generado

## Formato de resumen:

El resumen generado incluye:

### Características del resumen
- **Lenguaje natural y amigable**: Usa un tono cercano y accesible
- **Destacar hitos principales**: Resalta los logros más importantes
- **Valor entregado**: Enfatiza el beneficio para el usuario
- **Emojis moderados**: Usa emojis de forma decorativa para dar calidez
- **Conciso pero completo**: Máximo 2 o 3 párrafos
- **Sin detalles técnicos**: Omite IDs de llamadas a funciones o logs internos
- **Cierre positivo**: Termina con un mensaje de cierre alentador

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** Ninguno
- **Requiere allowlisting:** false
- **Auto-aprobado:** true
- **Requiere sandbox:** false

## Requisitos:

- Se necesita el servicio LLM para generar el resumen
- Se requiere la librería Rich para la visualización enriquecida
- El resumen se genera sin guardar este paso en el historial principal
- En caso de error, se proporciona un resumen por defecto

## Uso recomendado:

1. Usa esta herramienta cuando creas que la solicitud del usuario ha sido completamente abordada
2. Ideal para finalizar interacciones largas o complejas
3. Proporciona una experiencia de usuario satisfactoria con el resumen visual
4. Útil para dar cierre a sesiones de trabajo
5. Ayuda a que el usuario entienda lo que se ha logrado

## Limitaciones:

- Requiere acceso a un servicio LLM funcional
- En caso de error en la generación del resumen, se proporciona un mensaje por defecto
- El resumen no incluye detalles técnicos internos del sistema
- La calidad del resumen depende del modelo de lenguaje utilizado