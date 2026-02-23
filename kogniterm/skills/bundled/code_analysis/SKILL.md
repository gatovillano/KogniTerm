---
name: code_analysis
version: 1.0.0
author: "KogniTerm Core"
description: "Análisis estático de código Python con métricas de complejidad, mantenibilidad y linting"
category: "code"
tags: ["analysis", "python", "complexity", "maintainability", "linting", "code-quality"]
dependencies: ["radon", "pylint"]
required_permissions: ["filesystem"]
security_level: "standard"
allowlist: false
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Esta skill permite realizar análisis estático de código Python utilizando la librería 'radon'. Proporciona métricas de calidad de código, complejidad ciclomática, índice de mantenibilidad y capacidades de linting.

## Herramientas disponibles:

### code_analysis

Realiza análisis estático de código Python con diferentes tipos de análisis.

**Parámetros:**
- `analysis_type` (string, requerido): Tipo de análisis: 'lint' (pylint/eslint), 'complexity' (ciclomática), 'maintainability' (índice MI), 'raw' (líneas, comentarios, etc.), 'halstead' (métricas Halstead)
- `path` (string, requerido): Ruta al archivo o directorio a analizar
- `recursive` (boolean, opcional, default: false): Si es True y path es un directorio, busca archivos recursivamente

**Ejemplo:**
```json
{
  "tool": "code_analysis",
  "args": {
    "analysis_type": "complexity",
    "path": "./src/main.py",
    "recursive": true
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: standard** - No requiere aprobación
- **Permisos requeridos:** filesystem
- **Requiere allowlisting:** false
- **Auto-aprobado:** true

## Requisitos:

- Se necesita la librería `radon` instalada: `pip install radon`
- Para análisis linting se necesita `pylint` para Python: `pip install pylint`
- Para análisis linting de JavaScript/TypeScript se necesita `eslint`: `npm install -g eslint`

## Uso recomendado:

1. Usa `complexity` para analizar la complejidad ciclomática del código
2. Usa `maintainability` para obtener el índice de mantenibilidad
3. Usa `raw` para métricas básicas (líneas de código, comentarios, etc.)
4. Usa `halstead` para métricas avanzadas de complejidad
5. Usa `lint` para validación de código con pylint/eslint
6. Para directorios, usa `recursive: true` para analizar todos los archivos hijos
7. Los resultados se muestran por archivo con detalles específicos por tipo de análisis