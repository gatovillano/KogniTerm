# 📋 Especificación de Migración: Tools → Skills

**Versión:** 1.0  
**Fecha:** 2025-01-20  
**Estado:** Borrador  
**Autor:** Researcher Agent

---

## 🎯 Objetivo

Documentar el proceso de migración de las herramientas tradicionales (tools) al nuevo formato de habilidades modulares (skills) en KogniTerm.

---

## 📊 Estado Actual de Migración

### ✅ Skills Migradas (30+)

#### Bundled Skills (29 skills)
| Skill | Categoría | Estado |
|-------|-----------|--------|
| `task_tracker` | workflow | ✅ Migrado |
| `think` | thinking | ✅ Migrado |
| `execute_command` | system | ✅ Migrado |
| `sophisticated_editor_tool` | filesystem | ✅ Migrado |
| `bash_agent` | agents | ✅ Migrado |
| `call_agent` | agents | ✅ Migrado |
| `code_analysis` | code | ✅ Migrado |
| `code_tools` | code | ✅ Migrado |
| `codebase_search` | code | ✅ Migrado |
| `web_tools` | web | ✅ Migrado |
| `github` | web | ✅ Migrado |
| `tavily_search` | web | ✅ Migrado |
| `web_fetch` | web | ✅ Migrado |
| `web_scraping` | web | ✅ Migrado |
| `python_executor` | code | ✅ Migrado |
| `plan_creation` | planning | ✅ Migrado |
| `memory_append` | memory | ✅ Migrado |
| `memory_read` | memory | ✅ Migrado |
| `memory_init` | memory | ✅ Migrado |
| `memory_summarize` | memory | ✅ Migrado |
| `search_memory` | memory | ✅ Migrado |
| `file_operations` | filesystem | ✅ Migrado |
| `file_read_directory` | filesystem | ✅ Migrado |
| `file_update` | filesystem | ✅ Migrado |
| `call_agents_parallel` | agents | ✅ Migrado |
| `refresh_tools` | meta | ✅ Migrado |
| `set_llm_instructions` | llm | ✅ Migrado |
| `skill_factory` | meta | ✅ Migrado |
| `task_complete` | workflow | ✅ Migrado |

#### Workspace Skills (9 skills en desarrollo)
| Skill | Categoría | Estado |
|-------|-----------|--------|
| `project_analyzer` | autonomous | 🔄 En desarrollo |
| `safe_cleanup` | autonomous | 🔄 En desarrollo |
| `parse_iso_mirrors_from_html` | autonomous | 🔄 En desarrollo |
| `photo_organizer` | autonomous | 🔄 En desarrollo |
| `photo_organizer_tool` | autonomous | 🔄 En desarrollo |
| `native_photo_organizer` | autonomous | 🔄 En desarrollo |
| `evolution_test_skill` | general | 🔄 En desarrollo |
| `email_manager` | general | 🔄 En desarrollo |
| `reddit_cli_skill` | general | 🔄 En desarrollo |

### ⏳ Skills Pendientes de Migración

Basado en el análisis del código y la documentación, las siguientes herramientas podrían necesitar migración:

1. **`file_search`** - Búsqueda de archivos
2. **`web_tools`** (partes no migradas) - Herramientas web adicionales
3. **`code_tools`** (partes no migradas) - Herramientas de código adicionales
4. **`advanced_file_editor`** - Editor de archivos avanzado

---

## 🔄 Diferencias entre Tools y Skills

### Tools Tradicionales

**Características:**
- Implementación directa en Python
- Registro estático en `tool_manager.py`
- Llamadas síncronas
- Menos estructura de metadatos
- Difícil de extender/organizar

**Ejemplo:**
```python
def get_tool(name):
    tools = {
        "execute_command": execute_command_tool,
        "file_operations": file_operations_tool,
    }
    return tools.get(name)
```

### Skills Nuevo Formato

**Características:**
- Estructura de directorio estandarizada
- `SKILL.md` con metadatos YAML
- `scripts/tool.py` con función principal y schema
- Discovery automático
- Soporte para diferentes niveles de seguridad
- Documentación integrada

**Estructura:**
```
skill_name/
├── SKILL.md              # Metadatos y documentación
├── scripts/
│   └── tool.py           # Implementación con schema
└── references/           # Documentación adicional
```

---

## 📋 Guía de Migración Paso a Paso

### Paso 1: Análisis de la Tool Existente

1. Identificar la función principal
2. Mapear parámetros de entrada
3. Documentar comportamiento esperado
4. Identificar nivel de seguridad necesario

### Paso 2: Crear Estructura de Directorio

```bash
mkdir -p skills/workspace/nombre_skill/scripts
mkdir -p skills/workspace/nombre_skill/references
```

### Paso 3: Crear SKILL.md

```yaml
---
name: nombre_skill
version: 1.0.0
description: "Descripción clara de la habilidad"
category: categoria
tags: ["tag1", "tag2"]
dependencies: []
required_permissions: ["execute", "filesystem"]
security_level: "standard"
allowlist: false
auto_approve: false
sandbox_required: false
---

# Instrucciones

Explicación detallada de cómo usar la habilidad.
```

### Paso 4: Implementar tool.py

**Plantilla obligatoria:**

```python
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 1. Función principal con parámetros fuertemente tipados
def nombre_skill(parametro1: str, parametro2: bool = False) -> str:
    """Docstring explicativo."""
    try:
        # Lógica de la herramienta
        return f"Resultado: {parametro1}"
    except Exception as e:
        return f"Error: {e}"

# 2. Esquema CRÍTICO para el parser de llamadas a herramientas
parameters_schema = {
    "type": "object",
    "properties": {
        "parametro1": {
            "type": "string",
            "description": "Descripción del parámetro"
        },
        "parametro2": {
            "type": "boolean",
            "description": "Otra descripción"
        }
    },
    "required": ["parametro1"]
}
```

### Paso 5: Validar y Probar

1. Verificar estructura con `SkillValidator`
2. Probar carga con `SkillManager`
3. Ejecutar tests unitarios
4. Verificar documentación

### Paso 6: Registrar

1. Ejecutar `refresh_tools` para recargar el sistema
2. Verificar que aparece en lista de skills
3. Probar invocación

---

## 📊 Comparación de Métricas

| Aspecto | Tools Tradicionales | Skills |
|---------|-------------------|--------|
| Estructura | Monolítica | Modular |
| Descubrimiento | Estático | Automático (JIT) |
| Metadatos | Mínimos | Completos (YAML) |
| Seguridad | Básica | Nivelada (low/standard/high/elevated) |
| Documentación | Separada | Integrada (SKILL.md) |
| Extensibilidad | Difícil | Fácil |
| Testing | Limitado | Mejorado |
| Mantenimiento | Complejo | Modular |

---

## 🎯 Recomendaciones

### Prioridad Alta
1. Completar migración de `project_analyzer`
2. Migrar `safe_cleanup` al formato skill
3. Documentar `parse_iso_mirrors_from_html`

### Prioridad Media
1. Consolidar skills en `workspace/`
2. Crear tests para skills migradas
3. Optimizar documentación SKILL.md

### Prioridad Baja
1. Revisar dependencias de skills
2. Crear template de skill para nuevos casos
3. Documentar casos de uso avanzados

---

## 📚 Referencias

- `docs/SKILL.md` - Guía oficial de creación de skills
- `docs/migracion_sistema_skills.md` - Detalles de migración
- `tests/test_skill_manager.py` - Tests de validación
- `kogniterm/core/skills/skill_manager.py` - Implementación del manager