---
name: code_tools
version: 1.0.0
author: "KogniTerm Core"
description: "Colección unificada de herramientas para análisis de código y búsqueda semántica en la base de datos vectorial del proyecto"
category: "code"
tags: ["code", "analysis", "search", "semantic", "complexity", "linting", "codebase"]
dependencies: ["radon", "pylint", "langchain", "numpy", "beautifulsoup4"]
required_permissions: ["filesystem"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM - Code Tools

Esta skill unifica diversas herramientas para analizar y navegar por la base de código del proyecto.

## Herramientas disponibles:

### 1. codebase_search
Realiza búsquedas semánticas de snippets de código en la base de datos vectorial del proyecto. Utiliza embeddings para encontrar código relevante basado en el significado de la consulta.
- **Parámetros:** `query` (string), `k` (int, default: 5), `file_path_filter` (string, opcional), `language_filter` (string, opcional)

### 2. code_analysis
Realiza análisis estático de código Python utilizando la librería 'radon'. Proporciona métricas de calidad de código, complejidad ciclomática, índice de mantenibilidad y capacidades de linting.
- **Parámetros:** `analysis_type` (string: 'lint', 'complexity', 'maintainability', 'raw', 'halstead'), `path` (string), `recursive` (boolean, default: false)

## Flujo de trabajo recomendado:

1. **Exploración Semántica**: Usa `codebase_search` para encontrar código relacionado con funcionalidades específicas que no sabes dónde están ubicadas.
2. **Análisis de Calidad**: Una vez ubicado el código, usa `code_analysis` con `complexity` o `maintainability` para identificar áreas que necesitan refactorización.
3. **Validación**: Usa `code_analysis` con `lint` para verificar errores de sintaxis o estilo antes de proceder con una edición.

## Consideraciones de seguridad:
- El análisis se realiza de forma local y no requiere acceso a red externo una vez instaladas las dependencias.
- El análisis lint puede tardar en bases de código muy extensas si se usa de forma recursiva.
- Para `codebase_search`, el proyecto debe estar indexado previamente.
