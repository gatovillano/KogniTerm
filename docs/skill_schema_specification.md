# 📐 Especificación de Esquemas para Skills

## 📋 Índice

1. [Introducción](#introducción)
2. [Formato Básico](#formato-básico)
3. [Tipos de Datos Soportados](#tipos-de-datos-soportados)
4. [Validaciones Avanzadas](#validaciones-avanzadas)
5. [Metadatos de Skill](#metadatos-de-skill)
6. [Ejemplos Completos](#ejemplos-completos)
7. [Errores Comunes](#errores-comunes)
8. [Checklist de Validación](#checklist-de-validación)

---

## 🎯 Introducción

Toda skill de KogniTerm **debe** definir una variable global `parameters_schema` que siga la especificación [JSON Schema Draft 7](https://json-schema.org/). Este esquema es utilizado por el `SkillManager` para:

- Validar parámetros antes de ejecutar la skill
- Generar documentación automática
- Proporcionar autocompletado inteligente al usuario
- Detectar errores de uso temprano

### Estructura Mínima

```python
parameters_schema = {
    "type": "object",
    "properties": {
        # Definición de parámetros
    },
    "required": []  # Lista de parámetros obligatorios
}
```

---

## 📦 Formato Básico

### Esquema de Nivel Superior

```python
{
    "type": "object",                    # ✅ Siempre "object"
    "properties": {                      # Diccionario de parámetros
        "param_name": {
            "type": "string",            # Tipo del parámetro
            "description": "Texto..."    # Descripción (requerido)
        }
    },
    "required": ["param_name"],          # Lista de parámetros obligatorios
    "additionalProperties": false,       # (Opcional) Rechazar params extra
    "definitions": {                     # (Opcional) Definiciones reutilizables
        "mi_tipo": {...}
    }
}
```

### Ejemplo Mínimo Válido

```python
parameters_schema = {
    "type": "object",
    "properties": {
        "archivo": {
            "type": "string",
            "description": "Ruta al archivo"
        }
    },
    "required": ["archivo"]
}
```

---

## 🔤 Tipos de Datos Soportados

| Tipo JSON | Tipo Python | Descripción |
|-----------|-------------|-------------|
| `string` | `str` | Texto |
| `integer` | `int` | Números enteros |
| `number` | `float` | Números decimales |
| `boolean` | `bool` | Valores `true`/`false` |
| `array` | `list` | Listas/arrays |
| `object` | `dict` | Objetos anidados |
| `null` | `None` | Valor nulo |

### Ejemplos por Tipo

```python
parameters_schema = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string", "description": "Nombre de usuario"},
        "edad": {"type": "integer", "description": "Edad en años", "minimum": 0},
        "precio": {"type": "number", "description": "Precio en USD", "minimum": 0.0},
        "activo": {"type": "boolean", "description": "Si está activo"},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lista de etiquetas"
        },
        "config": {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "default": 30}
            },
            "required": ["timeout"]
        },
        "valor_nulo": {"type": "null", "description": "Puede ser None"}
    },
    "required": ["nombre", "edad"]
}
```

---

## ✅ Validaciones Avanzadas

### Restricciones Numéricas

```python
"edad": {
    "type": "integer",
    "minimum": 0,           # Valor mínimo (inclusive)
    "maximum": 150,         # Valor máximo (inclusive)
    "exclusiveMinimum": 1,  # Valor mínimo (exclusivo)
    "exclusiveMaximum": 18, # Valor máximo (exclusivo)
    "multipleOf": 5         # Debe ser múltiplo de 5
}
```

### Restricciones de String

```python
"email": {
    "type": "string",
    "minLength": 5,         # Longitud mínima
    "maxLength": 254,       # Longitud máxima
    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"  # Regex
}

"ruta": {
    "type": "string",
    "format": "file-path"   # Formatos especiales (ver abajo)
}
```

### Formatos Especiales (Date, Email, etc.)

```python
"fecha": {"type": "string", "format": "date-time"}  # ISO 8601
"email": {"type": "string", "format": "email"}
"uri": {"type": "string", "format": "uri"}
"hostname": {"type": "string", "format": "hostname"}
"ipv4": {"type": "string", "format": "ipv4"}
"ipv6": {"type": "string", "format": "ipv6"}
```

> **Nota**: KogniTerm usa `jsonschema` que soporta estos formatos estándar.

### Arrays y Objetos

```python
"lista_numeros": {
    "type": "array",
    "items": {"type": "integer", "minimum": 0},
    "minItems": 1,          # Mínimo de elementos
    "maxItems": 100,        # Máximo de elementos
    "uniqueItems": True     # No duplicados
}

"configuracion": {
    "type": "object",
    "properties": {...},
    "required": ["clave"],
    "additionalProperties": False  # No permitir claves extra
}
```

### Valores por Defecto (Default)

```python
"timeout": {
    "type": "integer",
    "description": "Timeout en segundos",
    "default": 30,          # Valor si no se proporciona
    "minimum": 1,
    "maximum": 300
}

"modo": {
    "type": "string",
    "enum": ["fast", "safe", "debug"],  # Valores permitidos
    "default": "safe"
}
```

---

## 🏷 Metadatos de Skill

Además de `parameters_schema`, puedes definir metadatos opcionales:

```python
# Metadatos (opcional)
skill_metadata = {
    "name": "mi_skill",
    "description": "Descripción corta para el registro",
    "version": "1.2.0",
    "author": "Tu Nombre <email@ejemplo.com>",
    "tags": ["file", "read", "text"],
    "category": "file_operations",
    "deprecated": False,  # o fecha de deprecación
    "experimental": False
}
```

---

## 📚 Ejemplos Completos

### Ejemplo 1: Skill de Lectura de Archivos

```python
def read_file(**kwargs):
    """
    Lee el contenido completo de un archivo.
    """
    path = kwargs.get('path')
    encoding = kwargs.get('encoding', 'utf-8')

    if not path:
        return {"error": "El parámetro 'path' es requerido"}

    try:
        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
        return {"content": content, "path": path}
    except FileNotFoundError:
        return {"error": f"Archivo no encontrado: {path}"}
    except UnicodeDecodeError:
        return {"error": f"Error de codificación: {encoding}"}
    except Exception as e:
        return {"error": str(e)}

parameters_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Ruta absoluta o relativa al archivo",
            "minLength": 1
        },
        "encoding": {
            "type": "string",
            "description": "Codificación del archivo",
            "default": "utf-8",
            "enum": ["utf-8", "latin-1", "ascii", "utf-16"]
        }
    },
    "required": ["path"],
    "additionalProperties": False
}

skill_metadata = {
    "name": "read_file",
    "description": "Lee archivos de texto",
    "version": "1.0.0",
    "category": "file_operations"
}
```

### Ejemplo 2: Skill con Múltiples Parámetros y Validaciones

```python
def search_files(**kwargs):
    """
    Busca archivos que coincidan con un patrón.
    """
    pattern = kwargs.get('pattern')
    path = kwargs.get('path', '.')
    recursive = kwargs.get('recursive', False)
    max_results = kwargs.get('max_results', 100)

    if not pattern:
        return {"error": "El parámetro 'pattern' es requerido"}

    # Lógica de búsqueda...
    results = []

    return {
        "pattern": pattern,
        "path": path,
        "recursive": recursive,
        "results": results[:max_results],
        "total_found": len(results)
    }

parameters_schema = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Patrón glob (ej: '*.py', '**/*.txt')",
            "minLength": 1,
            "pattern": "^[a-zA-Z0-9_*./\\-]+$"
        },
        "path": {
            "type": "string",
            "description": "Directorio donde buscar",
            "default": "."
        },
        "recursive": {
            "type": "boolean",
            "description": "Si True, busca en subdirectorios",
            "default": False
        },
        "max_results": {
            "type": "integer",
            "description": "Máximo número de resultados",
            "minimum": 1,
            "maximum": 10000,
            "default": 100
        }
    },
    "required": ["pattern"],
    "additionalProperties": False
}
```

### Ejemplo 3: Skill con Objeto Anidado

```python
def create_project(**kwargs):
    """
    Crea un nuevo proyecto con estructura de directorios.
    """
    config = kwargs.get('config', {})

    project_name = config.get('name')
    project_type = config.get('type', 'python')

    if not project_name:
        return {"error": "config.name es requerido"}

    # Crear proyecto...
    return {"status": "created", "name": project_name, "type": project_type}

parameters_schema = {
    "type": "object",
    "properties": {
        "config": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del proyecto",
                    "minLength": 1
                },
                "type": {
                    "type": "string",
                    "description": "Tipo de proyecto",
                    "enum": ["python", "javascript", "rust", "go"],
                    "default": "python"
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de dependencias",
                    "default": []
                }
            },
            "required": ["name"],
            "additionalProperties": False
        }
    },
    "required": ["config"],
    "additionalProperties": False
}
```

---

## 🐛 Errores Comunes

### 1. Olvidar `parameters_schema`

```python
# ❌ MAL
def mi_skill(**kwargs):
    return "OK"
# Falta parameters_schema

# ✅ BIEN
def mi_skill(**kwargs):
    return "OK"

parameters_schema = {
    "type": "object",
    "properties": {},
    "required": []
}
```

### 2. `required` con Parámetros No Definidos

```python
# ❌ MAL
parameters_schema = {
    "properties": {"param1": {"type": "string"}},
    "required": ["param1", "param2"]  # param2 no existe en properties
}

# ✅ BIEN
parameters_schema = {
    "properties": {
        "param1": {"type": "string"},
        "param2": {"type": "integer"}
    },
    "required": ["param1", "param2"]
}
```

### 3. Tipos Incorrectos

```python
# ❌ MAL
parameters_schema = {
    "properties": {
        "count": {"type": "int"}  # Tipo incorrecto
    }
}

# ✅ BIEN
parameters_schema = {
    "properties": {
        "count": {"type": "integer"}
    }
}
```

### 4. Falta `description` en Parámetros

```python
# ❌ MAL
parameters_schema = {
    "properties": {
        "path": {"type": "string"}  # Sin description
    }
}

# ✅ BIEN
parameters_schema = {
    "properties": {
        "path": {"type": "string", "description": "Ruta al archivo"}
    }
}
```

### 5. Usar `additionalProperties: true` por Omisión

```python
# ❌ MAL (permite parámetros no definidos)
parameters_schema = {
    "type": "object",
    "properties": {"param1": {"type": "string"}},
    "required": []
    # falta additionalProperties → default true
}

# ✅ BIEN (rechaza parámetros inesperados)
parameters_schema = {
    "type": "object",
    "properties": {"param1": {"type": "string"}},
    "required": [],
    "additionalProperties": False
}
```

---

## ✅ Checklist de Validación

Antes de registrar una skill, verifica:

- [ ] `parameters_schema` está definido como variable global
- [ ] `parameters_schema["type"] == "object"`
- [ ] Todos los parámetros en `required` existen en `properties`
- [ ] Cada parámetro en `properties` tiene `type` y `description`
- [ ] Los tipos son válidos (`string`, `integer`, `number`, `boolean`, `array`, `object`)
- [ ] Si usas `enum`, todos los valores son del tipo correcto
- [ ] Si usas `pattern`, es un regex válido
- [ ] Considera `additionalProperties: false` para evitar parámetros extra
- [ ] La función usa `**kwargs` y extrae parámetros con `kwargs.get('nombre', default)`
- [ ] La función retorna un diccionario con `success`/`error` o similar
- [ ] La documentación (docstring + `instructions`) es clara y con ejemplos

### Validación Automática

```python
from jsonschema import validate, ValidationError

def validar_esquema(schema):
    # Esquema mínimo válido
    base_schema = {
        "type": "object",
        "properties": {},
        "required": []
    }

    # Verificar estructura
    try:
        validate(instance=schema, schema=base_schema)
        print("✅ Esquema válido")
    except ValidationError as e:
        print(f"❌ Error: {e.message}")
        return False

    # Verificar que todos los required existen
    for req in schema.get("required", []):
        if req not in schema["properties"]:
            print(f"❌ '{req}' en required pero no en properties")
            return False

    # Verificar que cada propiedad tiene description
    for name, prop in schema["properties"].items():
        if "description" not in prop:
            print(f"⚠️  '{name}' no tiene description")

    return True

# Uso
validar_esquema(parameters_schema)
```

---

## 🔗 Referencias

- [JSON Schema Draft 7](https://json-schema.org/specification-links.html#draft-7)
- [jsonschema library](https://python-jsonschema.readthedocs.io/)
- [KogniTerm SkillManager docs](../SKILL.md)

---

*Última actualización: 2025-10-09*