---
name: ask_question
version: 1.0.0
author: "KogniTerm Core"
description: "Permite al agente consultar algo al usuario mostrando un panel interactivo con opciones seleccionables y una opción libre para respuesta personalizada"
category: "interaction"
tags: ["user-interaction", "question", "prompt", "dialog", "confirmation"]
dependencies: []
required_permissions: []
security_level: "low"
allowlist: false
auto_approve: true
---

# Instrucciones para el LLM

Esta skill te permite **hacer preguntas directamente al usuario** en momentos donde necesitas su opinión, preferencia o aprobación antes de continuar.

## Cuándo usar esta herramienta

Usa `ask_question` cuando:
- Necesitas que el usuario elija entre varias opciones de implementación
- Hay ambigüedad en el requerimiento y necesitas aclaración
- Antes de una acción importante que requiere elección del usuario
- Quieres confirmar una dirección antes de proceder

## Herramientas disponibles:

### ask_question

Muestra un panel interactivo al usuario con la pregunta y una lista de opciones numeradas. El usuario puede seleccionar una opción por número o escribir una respuesta libre.

**Parámetros:**
- `question` (string, requerido): La pregunta clara y concisa a hacer al usuario
- `options` (array de strings, requerido): Lista de 2 a 10 opciones predefinidas que el usuario puede seleccionar
- `title` (string, opcional): Título del panel (default: "Consulta del Agente")
- `allow_freeform` (boolean, opcional): Permite al usuario escribir una respuesta personalizada además de las opciones (default: true)

**Ejemplo:**
```json
{
  "tool": "ask_question",
  "args": {
    "question": "¿Cómo prefieres que se implemente el sistema de caché?",
    "options": [
      "En memoria con TTL configurable",
      "En disco usando SQLite",
      "Redis para soporte distribuido"
    ],
    "title": "Decisión de Arquitectura"
  }
}
```

**Respuesta:** Retorna un string con la respuesta del usuario (texto de la opción seleccionada o respuesta libre).

## Buenas prácticas

- Formula preguntas claras y específicas
- Ofrece opciones mutuamente excluyentes cuando sea posible
- Limita las opciones a las realmente relevantes (2-6 es ideal)
- Incluye siempre una opción para "continuar como estaba" si aplica
