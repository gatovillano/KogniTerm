---
allowlist: false
author: KogniTerm AI (Autonomous Generation)
auto_approve: true
category: autonomous
dependencies: []
description: "Analiza un directorio de proyectos y resume informaci\xF3n clave leyendo\
  \ README.md, package.json, requirements.txt, Dockerfile y otros archivos de configuraci\xF3\
  n"
name: project_analyzer
required_permissions:
- filesystem
sandbox_required: false
security_level: standard
tags:
- autonomous
- generated
version: 1.0.0
---

# Project Analyzer Skill

Esta skill analiza un directorio de proyectos y extrae información clave leyendo archivos de configuración comunes.

## Uso

```python
project_analyzer(
    project_path="/ruta/al/proyecto"
)
```

## Parámetros

- **project_path** (string, requerido): Ruta al directorio del proyecto que se desea analizar

## Retorna

La skill devuelve un diccionario con la siguiente estructura:

```json
{
  "project_name": "nombre_del_directorio",
  "project_path": "/ruta/completa/al/proyecto",
  "files_found": {
    "README": ["README.md"],
    "package_json": ["package.json"],
    "requirements": ["requirements.txt"],
    "docker": ["Dockerfile", "docker-compose.yml"]
  },
  "summary": "Descripción legible del proyecto",
  "readme_preview": "Primeros 200 caracteres del README",
  "package_info": {/* contenido de package.json si existe */},
  "requirements_preview": "Primeros 300 caracteres de requirements.txt"
}
```

## Ejemplos

### Analizar un proyecto Node.js
```python
result = project_analyzer(project_path="/home/gato/Proyectos/ClubGriego")
# Detectará package.json y generará un resumen
```

### Analizar un proyecto Python
```python
result = project_analyzer(project_path="/home/gato/Proyectos/Fito")
# Detectará requirements.txt y otros archivos de configuración
```

### Manejo de errores
Si el path no existe o no es un directorio, la skill devolverá:
```json
{"error": "Mensaje descriptivo del error"}
```

## Notas

- La skill busca archivos comunes como README.md, package.json, requirements.txt, Dockerfile, etc.
- Lee y muestra previews de los contenidos para dar contexto
- Funciona con proyectos de cualquier tipo, enfocándose en los archivos de configuración estándar
- Útil para hacer inventario rápido de proyectos en un directorio