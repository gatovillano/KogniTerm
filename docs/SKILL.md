# 🧩 Sistema de Skills de KogniTerm

## 📋 Índice

1. [Introducción](#introducción)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Creación de Skills Personalizadas](#creación-de-skills-personalizadas)
4. [Ejemplos Prácticos](#ejemplos-prácticos)
5. [Mejores Prácticas](#mejores-prácticas)
6. [Debugging y Testing](#debugging-y-testing)
7. [Referencia de API](#referencia-de-api)

---

## 🎯 Introducción

El **SkillManager** de KogniTerm es un framework modular que permite extender las capacidades del asistente mediante **habilidades** (skills) auto-descritas y validadas. Cada skill es una función Python con un esquema de parámetros JSON que define su interfaz pública.

### Características Clave

- **Carga dinámica JIT**: Las skills se cargan solo cuando se usan por primera vez
- **Validación estricta**: Esquemas JSON para tipos, requerimientos y descripciones
- **Registro automático**: Integración instantánea con el sistema de herramientas
- **Documentación integrada**: Cada skill genera su propia documentación Markdown
- **27 skills bundled**: Incluye `file_operations`, `execute_command`, `code_analysis`, etc.

---

## 🏗 Arquitectura del Sistema

### Componentes Principales

```
SkillManager (642 líneas)
├── SkillLoader: Carga dinámica desde módulos Python
├── SkillValidator: Valida esquemas parameters_schema
├── SkillRegistry: Registro central de todas las skills disponibles
├── SkillExecutor: Ejecuta skills con inyección de kwargs
└── SkillDocumentation: Genera SKILL.md automáticamente
```

### Flujo de Ejecución

1. **Usuario** pide acción → `BashAgent` interpreta intención
2. **LLM** decide qué skill usar → envía nombre de skill + parámetros
3. **SkillManager** busca skill en registro → si no está, la carga (JIT)
4. **Validador** comprueba esquema → rechaza si parámetros inválidos
5. **Ejecutor** invoca función → pasa kwargs extraídos
6. **Resultado** → devuelto al agente → mostrado al usuario

### Esquema de una Skill

Toda skill **debe** definir:

```python
def mi_skill(**kwargs):
    """
    Descripción de lo que hace la skill.
    """
    param1 = kwargs.get('param1')  # Obligatorio si está en required
    param2 = kwargs.get('param2', 'default')  # Opcional con default
    # Lógica de la skill
    return f"Resultado: {param1}, {param2}"

# Esquema JSON obligatorio
parameters_schema = {
    "type": "object",
    "properties": {
        "param1": {
            "type": "string",
            "description": "Descripción del parámetro 1"
        },
        "param2": {
            "type": "integer",
            "description": "Descripción del parámetro 2",
            "default": 42
        }
    },
    "required": ["param1"]  # Lista de parámetros obligatorios
}
```

---

## 🛠 Creación de Skills Personalizadas

### Método 1: `skill_factory` (Recomendado)

La función `skill_factory` crea e integra automáticamente una nueva skill:

```python
from kogniterm.core.skill_factory import skill_factory

skill_factory(
    skill_name="mi_herramienta",
    description="Mi skill personalizada que hace algo útil",
    tool_code="""
def mi_herramienta(**kwargs):
    '''
    Implementación concreta de la skill.
    '''
    archivo = kwargs.get('archivo')
    linea = kwargs.get('linea', 0)

    # Lógica personalizada
    with open(archivo, 'r') as f:
        contenido = f.readlines()

    if linea > 0:
        return contenido[linea-1]
    return ''.join(contenido)

parameters_schema = {
    "type": "object",
    "properties": {
        "archivo": {
            "type": "string",
            "description": "Ruta al archivo a leer"
        },
        "linea": {
            "type": "integer",
            "description": "Número de línea (1-indexado, opcional)",
            "minimum": 1,
            "default": 0
        }
    },
    "required": ["archivo"]
}
""",
    instructions="""
## Instrucciones de Uso

Esta skill lee archivos de texto. Ejemplos:

- `mi_herramienta(archivo="/tmp/test.txt")` → contenido completo
- `mi_herramienta(archivo="/tmp/test.txt", linea=5)` → línea 5 específica
"""
)
```

**Parámetros de `skill_factory`**:

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `skill_name` | str | Nombre único en snake_case (sin espacios) |
| `description` | str | Breve descripción de la skill |
| `tool_code` | str | Código Python completo con función + `parameters_schema` |
| `instructions` | str | Documentación Markdown para usuarios |
| `version` | str (opcional) | Versión de la skill (default: "1.0.0") |

### Método 2: Módulo Independiente

Puedes crear un archivo Python en `~/.config/kogniterm/skills/` o en el directorio `scripts/` del proyecto:

```python
# ~/.config/kogniterm/skills/mi_skill.py

def mi_skill(**kwargs):
    # Implementación
    pass

parameters_schema = {
    "type": "object",
    "properties": {...},
    "required": [...]
}

# Metadatos opcionales
skill_metadata = {
    "name": "mi_skill",
    "description": "Descripción breve",
    "version": "1.0.0",
    "author": "Tu Nombre"
}
```

El `SkillManager` detectará automáticamente el módulo al primer uso y lo cargará.

---

## 📚 Ejemplos Prácticos

### Ejemplo 1: Skill de Sistema (Ejecutar Comando)

```python
skill_factory(
    skill_name="execute_command",
    description="Ejecuta un comando en la shell y devuelve la salida",
    tool_code="""
import subprocess

def execute_command(**kwargs):
    '''
    Ejecuta un comando del sistema.
    '''
    command = kwargs.get('command')
    timeout = kwargs.get('timeout', 30)

    if not command:
        return {"error": "El parámetro 'command' es requerido"}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Comando excedió timeout de {timeout} segundos"}
    except Exception as e:
        return {"error": str(e)}

parameters_schema = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Comando a ejecutar en la shell"
        },
        "timeout": {
            "type": "integer",
            "description": "Tiempo máximo de ejecución en segundos",
            "minimum": 1,
            "maximum": 300,
            "default": 30
        }
    },
    "required": ["command"]
}
""",
    instructions="""
## execute_command

Ejecuta comandos del sistema operativo.

### Parámetros
- `command` (string, requerido): Comando a ejecutar
- `timeout` (integer, opcional): Timeout en segundos (1-300, default: 30)

### Ejemplos
```
execute_command(command="ls -la")
execute_command(command="find . -name "*.py"", timeout=60)
```
"""
)
```

### Ejemplo 2: Skill de Análisis de Código

```python
skill_factory(
    skill_name="code_analysis",
    description="Analiza un archivo Python y reporta métricas de calidad",
    tool_code="""
import ast
from pathlib import Path

def code_analysis(**kwargs):
    '''
    Analiza código Python usando AST.
    '''
    file_path = kwargs.get('file_path')

    if not file_path or not Path(file_path).exists():
        return {"error": "Archivo no encontrado"}

    with open(file_path, 'r') as f:
        source = f.read()

    try:
        tree = ast.parse(source)
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

        return {
            "file": file_path,
            "lines": len(source.splitlines()),
            "functions": len(functions),
            "classes": len(classes),
            "function_names": functions,
            "class_names": classes
        }
    except SyntaxError as e:
        return {"error": f"Error de sintaxis: {e}"}

parameters_schema = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Ruta al archivo Python a analizar"
        }
    },
    "required": ["file_path"]
}
""",
    instructions="""
## code_analysis

Analiza archivos Python extrayendo métricas básicas.

### Parámetros
- `file_path` (string, requerido): Ruta al archivo .py

### Retorna
- `lines`: Número total de líneas
- `functions`: Cantidad de funciones
- `classes`: Cantidad de clases
- `function_names`: Lista de nombres de funciones
- `class_names`: Lista de nombres de clases
"""
)
```

---

## ✅ Mejores Prácticas

### 1. **Nombres Descriptivos**
```python
# ❌ Mal
skill_name="tool1"

# ✅ Bien
skill_name="list_directory_contents"
```

### 2. **Esquemas Completos**
```python
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Ruta absoluta o relativa al directorio",
            "pattern": "^[a-zA-Z0-9_./-]+$"  # Validación con regex
        },
        "recursive": {
            "type": "boolean",
            "description": "Si True, lista recursivamente",
            "default": False
        }
    },
    "required": ["path"],
    "additionalProperties": False  # Rechazar parámetros no definidos
}
```

### 3. **Manejo de Errores**
```python
def mi_skill(**kwargs):
    try:
        # Lógica principal
        return {"success": True, "data": resultado}
    except FileNotFoundError:
        return {"success": False, "error": "Archivo no existe"}
    except PermissionError:
        return {"success": False, "error": "Sin permisos de lectura"}
    except Exception as e:
        return {"success": False, "error": f"Error inesperado: {str(e)}"}
```

### 4. **Docstrings Claros**
```python
def mi_skill(**kwargs):
    """
    Descripción concisa de la skill.

    Explicación más detallada del comportamiento,
    efectos secundarios y consideraciones.

    Args:
        **kwargs: Parámetros definidos en parameters_schema

    Returns:
        dict: Diccionario con 'success' (bool) y 'data' o 'error'
    """
```

### 5. **Timeouts y Límites**
```python
def mi_skill(**kwargs):
    max_items = kwargs.get('max_items', 100)
    if max_items > 1000:
        return {"error": "max_items no puede superar 1000"}

    # Procesamiento con límite
    items = obtener_items()[:max_items]
    return {"items": items}
```

---

## 🐛 Debugging y Testing

### Testing Unitario

```python
# test_mi_skill.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.mi_skill import mi_skill

def test_mi_skill_success():
    result = mi_skill(archivo="/tmp/test.txt")
    assert "success" in result
    assert result["success"] is True

def test_mi_skill_missing_param():
    result = mi_skill()  # Falta 'archivo'
    assert result["success"] is False
    assert "requerido" in result["error"].lower()

if __name__ == "__main__":
    test_mi_skill_success()
    test_mi_skill_missing_param()
    print("✅ Todos los tests pasaron")
```

### Debugging en Producción

```python
def mi_skill(**kwargs):
    import logging
    logger = logging.getLogger(__name__)

    logger.debug(f"mi_skill llamada con kwargs: {kwargs}")

    try:
        # Lógica
        pass
    except Exception as e:
        logger.exception(f"Error en mi_skill: {e}")
        return {"error": str(e)}
```

### Verificación de Esquema

```python
from jsonschema import validate, ValidationError

def verificar_esquema():
    schema = {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
    test_params = {"param1": "valor", "param2": 123}
    try:
        validate(instance=test_params, schema=schema)
        print("✅ Esquema válido")
    except ValidationError as e:
        print(f"❌ Error de validación: {e}")
```

---

## 📖 Referencia de API

### `skill_factory`

```python
skill_factory(
    skill_name: str,
    description: str,
    tool_code: str,
    instructions: str,
    version: str = "1.0.0"
) -> dict
```

**Descripción**: Crea e integra una nueva skill en el sistema.

**Retorna**: Diccionario con estado de registro:
```json
{
  "status": "success",
  "skill_name": "mi_skill",
  "registered_at": "2025-10-09T..."
}
```

### `parameters_schema`

Esquema JSON compatible con [JSON Schema Draft 7](https://json-schema.org/).

**Campos obligatorios**:
- `type`: Siempre `"object"`
- `properties`: Diccionario de parámetros
- `required`: Lista de nombres de parámetros obligatorios

**Campos por parámetro**:
- `type`: `"string"`, `"integer"`, `"boolean"`, `"number"`, `"array"`, `"object"`
- `description`: Texto descriptivo (requerido)
- `default`: Valor por defecto (opcional)
- `minimum`/`maximum`: Límites numéricos
- `pattern`: Regex para strings
- `items`: Para arrays (esquema de elementos)
- `enum`: Lista de valores permitidos

---

## 🔄 Ciclo de Vida de una Skill

```
1. Definición: Escribes código + esquema
2. Registro: skill_factory() integra la skill
3. Discovery: SkillManager la detecta en el registro
4. Validación: Cada llamada valida parámetros contra el esquema
5. Ejecución: Se llama a la función con kwargs
6. Resultado: Retorna dict (éxito/error) que el agente interpreta
7. Documentación: SKILL.md se genera/actualiza automáticamente
```

---

## 🎯 Casos de Uso Comunes

| Caso de Uso | Skill Recomendada | Ejemplo |
|-------------|-------------------|---------|
| Leer archivos | `file_operations` (read_file) | `read_file(path="/etc/passwd")` |
| Escribir archivos | `file_operations` (write_file) | `write_file(path="output.txt", content="Hola")` |
| Ejecutar comandos | `execute_command` | `execute_command(command="git status")` |
| Análisis estático | `code_analysis` | `code_analysis(path="main.py")` |
| Búsqueda en código | `search_in_files` | `search_in_files(pattern="def.*test", path="tests/")` |
| Indexación RAG | `index_codebase` | `index_codebase(path=".")` |

---

## 🚀 Próximos Pasos

1. **Explora skills existentes**: Revisa `kogniterm/skills/` para ver implementaciones de referencia
2. **Crea tu primera skill**: Usa `skill_factory` con el ejemplo mínimo
3. **Añade tests**: Valida tu skill con casos de éxito y error
4. **Documenta bien**: Instrucciones claras en Markdown
5. **Comparte**: Si la skill es general, considera enviar un PR al repositorio principal

---

## 📚 Recursos Adicionales

- [Especificación de Esquemas](skill_schema_specification.md): Detalles técnicos de `parameters_schema`
- [Guía de Contribución](../CONTRIBUTING.md): Cómo contribuir skills al proyecto
- [API Reference](../docs/api/): Documentación generada automáticamente

---

*Última actualización: 2025-10-09*