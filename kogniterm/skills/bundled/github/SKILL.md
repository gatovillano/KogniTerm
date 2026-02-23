---
name: github
version: 1.0.0
author: "KogniTerm Core"
description: "Herramienta unificada para interactuar con repositorios de GitHub: obtener información, listar contenidos, leer archivos y directorios"
category: "development"
tags: ["github", "repository", "code", "development", "api"]
dependencies: ["PyGithub"]
required_permissions: ["network"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite interactuar con repositorios de GitHub de manera unificada, obteniendo información, listando contenidos y leyendo archivos.

## Herramientas disponibles

### github

Herramienta unificada para interactuar con repositorios de GitHub.

**Parámetros:**

- `action` (string, requerido): La acción a realizar
- `repo_name` (string, opcional): El nombre completo del repositorio de GitHub (ej. 'octocat/Spoon-Knife'). Requerido para acciones que no son de búsqueda global.
- `path` (string, opcional): La ruta del archivo o directorio dentro del repositorio (por defecto la raíz)
- `query` (string, opcional): La consulta de búsqueda para 'search_repositories' o 'search_code' (búsqueda global si no hay repo_name)
- `github_token` (string, opcional): Token de GitHub para autenticación

**Acciones disponibles:**

- `get_repo_info`: Obtener información del repositorio
- `list_contents`: Listar contenidos de un directorio
- `read_file`: Leer un archivo específico
- `read_directory`: Leer un directorio (no recursivo)
- `read_recursive_directory`: Leer un directorio recursivamente
- `search_repositories`: Buscar repositorios
- `search_code`: Buscar código en un repositorio

**Ejemplo:**

```json
{
  "tool": "github",
  "args": {
    "action": "get_repo_info",
    "repo_name": "octocat/Spoon-Knife"
  }
}
```

## Consideraciones de seguridad

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** network
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Requisitos

- Se necesita la variable de entorno `GITHUB_TOKEN` para autenticación (opcional)
- Para repositorios privados se requiere autenticación
- El contenido de archivos se limita a 100,000 caracteres
- Los archivos binarios no muestran su contenido

## Uso recomendado

1. Usa `get_repo_info` para obtener información general de un repositorio
2. Usa `list_contents` para explorar la estructura de directorios
3. Usa `read_file` para ver el contenido de archivos específicos
4. Usa `read_recursive_directory` para obtener una vista completa del código
5. Usa `search_repositories` para encontrar repositorios relevantes
6. Usa `search_code` para buscar código específico en un repositorio

## Limitaciones

- Los archivos binarios no muestran su contenido
- El contenido de archivos se trunca a 100,000 caracteres
- Las búsquedas están limitadas a los primeros 10 resultados
- Se requiere conexión a internet para todas las operaciones
