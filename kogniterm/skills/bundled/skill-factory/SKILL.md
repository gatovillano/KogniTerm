---
name: skill-factory
version: 1.0.0
author: "KogniTerm Core"
description: "Permite al agente autogenerar y registrar nuevas skills en tiempo de ejecución para evolucionar sus capacidades."
category: "meta"
tags: ["meta", "evolution", "automation", "skills", "factory"]
dependencies: []
required_permissions: ["filesystem", "logic"]
security_level: "high"
allowlist: true
auto_approve: false
sandbox_required: false
---

# Instrucciones para el LLM

Esta es una **Meta-Skill**. Te permite crear nuevas habilidades para ti mismo de forma permanente o temporal. Úsala cuando identifiques un patrón de tarea complejo o repetitivo que se beneficiaría de tener una herramienta dedicada.

## Cómo usar esta herramienta

1. **Diseña la lógica**: Define qué parámetros necesita la nueva herramienta y qué debe hacer.
2. **Escribe el código**: Proporciona el código Python robusto que implemente la lógica.
3. **Define las instrucciones**: Escribe el contenido del `SKILL.md` para que tú mismo sepas usarla en el futuro.

Al ejecutar esta herramienta, se creará una nueva carpeta en `skills/workspace/` y se registrará automáticamente en tu arsenal. **Podrás usar la nueva herramienta en tu siguiente turno.**

## FORMATO OBLIGATORIO DE `SKILL.MD`

Toda skill creada con `skill_factory` DEBE cumplir con la especificación estándar de formato de Agent Skills:

### 1. Parámetro `description` (Frontmatter YAML)
- **OBLIGATORIO**: Debe comenzar siempre con `"Use when..."` en tercera persona.
- Describe únicamente las **condiciones de activación** (síntomas, disparadores, contextos).
- **NUNCA** debes resumir el flujo o procedimiento interno de la skill en la descripción.

### 2. Parámetro `instructions` (Cuerpo Markdown del `SKILL.md`)
El markdown debe estructurarse en las siguientes secciones obligatorias:

```markdown
# Nombre de la Skill

## Overview
Principio fundamental o propósito central en 1-2 oraciones.

## When to Use
- Síntomas y condiciones de activación concretas.
- Cuándo NOT a usar esta habilidad.

## Core Pattern / Instrucciones
Explicación paso a paso de la lógica, flujo de trabajo, comparaciones antes/después o patrones de implementación.

## Quick Reference / Ejemplos
Tablas de referencia rápida, comandos o snippets de código reutilizables.

## Common Mistakes / Red Flags
Errores comunes, trampas y cómo evitarlos.
```

## REGLAS CRÍTICAS PARA EL CÓDIGO DE LA HERRAMIENTA (`tool_code`)

Para evitar el error `'str' object has no attribute 'get'` o problemas de parseo:

1. **Definición de Función**: Tu función principal DEBE recibir los parámetros explícitamente (ej. `def mi_tool(ruta: str):`). **NUNCA** uses `def mi_tool(args):` esperando un diccionario y luego `args.get()`.
2. **Esquema de Parámetros**: DEBES incluir una variable global llamada `parameters_schema` que contenga el esquema JSON Schema de tus parámetros. Esto instruye al parser sobre cómo decodificar los argumentos antes de inyectarlos en la función.
3. **Retorno**: Siempre devuelve un solo valor de tipo `str` o un diccionario (`dict`) serializable.

### Plantilla Obligatoria para `scripts/tool.py`

```python
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 1. Función principal con parámetros fuertemente tipados
def mi_nueva_skill(ruta: str, opcion_extra: bool = False) -> str: # Puede retornar str o dict
    """Docstring acá."""
    try:
        # TU LÓGICA AQUÍ
        return f"Éxito procesando {ruta}"
    except Exception as e:
        return f"Error: {e}"

# 2. Esquema MUY IMPORTANTE para el parser de llamadas a herramientas
parameters_schema = {
    "type": "object",
    "properties": {
        "ruta": {
            "type": "string",
            "description": "Descripción clara para el LLM"
        },
        "opcion_extra": {
            "type": "boolean",
            "description": "Otra descripción"
        }
    },
    "required": ["ruta"]
}
```

## Parámetros

- `skill_name` (string, requerido): Nombre técnico de la skill (ej. `image_optimizer`). Debe ser snake_case o hyphen-case.
- `description` (string, requerido): Descripción de cuándo debe activarse la skill. DEBE empezar con `"Use when..."` indicando solo disparadores.
- `tool_code` (string, requerido): El código Python completo para `scripts/tool.py`. Debe incluir `parameters_schema`.
- `instructions` (string, requerido): El contenido markdown estructurado para el archivo `SKILL.md` (con `# Titulo`, `## Overview`, `## When to Use`, etc.).

## Ejemplo de uso

```json
{
  "skill_name": "text_summarizer",
  "description": "Use when long text files or logs need to be summarized into structured bullet points.",
  "tool_code": "...",
  "instructions": "# Text Summarizer\n\n## Overview\nSummarizes long text...\n\n## When to Use\n..."
}
```

> [!IMPORTANT]
> Las nuevas skills se guardan en el directorio `workspace`, lo que significa que son persistentes entre sesiones a menos que se borren manualmente.

