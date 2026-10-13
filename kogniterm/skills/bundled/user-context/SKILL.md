---
name: user-context
version: 1.0.0
author: "KogniTerm Core"
description: "Use when the user shares durable personal information (name, location, work preferences, tech stack, active projects) that should be remembered across ALL projects, or when you need to recall the user's global profile. Manages ~/.kogniterm/user_context.md."
category: "memory"
tags: ["memory", "user", "profile", "context", "global", "preferences"]
dependencies: []
required_permissions: ["memory"]
security_level: "low"
allowlist: false
auto_approve: true
sandbox_required: false
---

# User Context — Memoria Global de Usuario

## Overview

Esta skill gestiona el **contexto global de usuario**: un archivo Markdown persistente
en `~/.kogniterm/user_context.md` que almacena información duradera sobre el usuario y
se inyecta automáticamente en el system prompt de KogniTerm en **todos** los proyectos.

Es distinto de la memoria de proyecto (`llm_context.md`), que vive por workspace.
Usa esta skill SOLO para información que debe recordarse siempre, en cualquier proyecto.

## When to Use

Usa `user_context_*` cuando:
- El usuario revele su nombre, ubicación, zona horaria o idioma preferido.
- El usuario exprese una preferencia de trabajo duradera ("prefiero respuestas concisas",
  "no uses emojis", "siempre en español").
- El usuario mencione su stack tecnológico o herramientas que usa habitualmente.
- El usuario hable de un proyecto activo o a largo plazo que deberías recordar.
- Necesites consultar el perfil global del usuario antes de responder.

NO la uses para detalles puntuales de la tarea actual (eso va en `llm_context.md`
del proyecto vía `memory_append`).

## Core Pattern / Instrucciones

### Herramientas disponibles

1. **`user_context_read_tool()`** — Lee el contexto global completo.
   - Úsalo al inicio si necesitas conocer el perfil del usuario.

2. **`user_context_update_field_tool(field_label, value)`** — Crea/actualiza un campo.
   - Para datos estructurados clave: Nombre, Ubicación, Idioma preferido, etc.
   - Ejemplo: `user_context_update_field_tool("Nombre", "Sebastián")`

3. **`user_context_append_note_tool(section, note)`** — Añade una nota a una sección.
   - Para listas: Proyectos Activos, Stack y Herramientas, Preferencias, Notas.
   - Si la sección no existe, se crea automáticamente.
   - Ejemplo: `user_context_append_note_tool("Proyectos Activos", "KognitoAI - plataforma de agentes IA")`

### Secciones estándar del archivo

- **Identidad**: Nombre, Ubicación/Zona horaria, Idioma preferido.
- **Preferencias de Trabajo**: estilo de respuesta, formato, nivel de detalle.
- **Stack y Herramientas**: lenguajes, frameworks, software que usa.
- **Proyectos Activos**: proyectos a largo plazo y su descripción breve.
- **Notas y Contexto Relevante**: cualquier otro dato persistente.

### Proactividad

Escribe en el contexto global de forma **proactiva** cuando el usuario comparta
información duradera. No esperes a que te lo pida explícitamente. Pero NUNCA
sobrescribas información existente sin confirmar si hay ambigüedad.

## Quick Reference / Ejemplos

```
# Usuario dice: "Me llamo Sebastián y estoy en Santiago de Chile"
user_context_update_field_tool("Nombre", "Sebastián")
user_context_update_field_tool("Ubicación / Zona horaria", "Ñuñoa, Santiago de Chile (GMT-3/-4)")

# Usuario dice: "Estoy trabajando en KognitoAI y Cuerpo Libre"
user_context_append_note_tool("Proyectos Activos", "KognitoAI - plataforma de agentes IA")
user_context_append_note_tool("Proyectos Activos", "Cuerpo Libre Fotografía (cuerpolibre.cl)")

# Usuario dice: "Prefiero respuestas directas sin rodeos"
user_context_append_note_tool("Preferencias de Trabajo", "Prefiere respuestas directas y concisas")
```

## Common Mistakes / Red Flags

- ❌ Usar esta skill para detalles de la tarea actual → usa `memory_append` (proyecto).
- ❌ Escribir secretos, contraseñas o tokens en el contexto global.
- ❌ Duplicar información que ya existe (lee primero con `user_context_read`).
- ❌ Inventar datos que el usuario no ha compartido.
