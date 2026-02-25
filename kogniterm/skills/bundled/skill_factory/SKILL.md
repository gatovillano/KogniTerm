---
name: skill_factory
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
    \"\"\"Docstring acá.\"\"\"
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

- `skill_name` (string, requerido): Nombre técnico de la skill (ej. `image_optimizer`). Debe ser snake_case.
- `description` (string, requerido): Una descripción clara de qué hace la nueva skill.
- `tool_code` (string, requerido): El código Python completo para `scripts/tool.py`. Debe incluir los schemas de Pydantic si es posible.
- `instructions` (string, requerido): El contenido markdown para el archivo `SKILL.md` (sin el frontmatter YAML, este se genera solo).

## Ejemplo de uso

```json
{
  "action": "create_skill",
  "skill_name": "text_summarizer",
  "description": "Una herramienta para resumir textos largos usando algoritmos locales.",
  "tool_code": "...",
  "instructions": "# Resumidor...\nUsa esta herramienta para..."
}
```

> [!IMPORTANT]
> Las nuevas skills se guardan en el directorio `workspace`, lo que significa que son persistentes entre sesiones a menos que se borren manualmente.
