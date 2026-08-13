---
name: python-executor
version: 1.0.0
author: "KogniTerm Core"
description: "Use when executing interactive Python code requiring Jupyter kernel state persistence"
category: "code"
tags: ["python", "execution", "jupyter", "interactive", "sandbox", "code-runner"]
dependencies: ["jupyter_client", "ipykernel"]
required_permissions: ["execution"]
security_level: "high"
allowlist: false
auto_approve: false
---

# Instrucciones para el LLM

Esta skill permite ejecutar código Python de forma interactiva utilizando un kernel de Jupyter. Mantiene el estado entre ejecuciones y soporta múltiples tipos de salida incluyendo texto, errores y resultados estructurados.

## Herramientas disponibles:

### python_executor

Ejecuta código Python de forma interactiva en un kernel de Jupyter.

**Parámetros:**
- `code` (string, requerido): El código Python a ejecutar

**Ejemplo:**
```json
{
  "tool": "python_executor",
  "args": {
    "code": "print('Hola, mundo!')\nresult = 2 + 2\nprint(f'El resultado es: {result}')"
  }
}
```

## Consideraciones de seguridad:

- **Nivel de seguridad: high** - Requiere aprobación manual
- **Permisos requeridos:** execution
- **Requiere allowlisting:** false
- **Auto-aprobado:** false
- **Requiere sandbox:** true

## Requisitos:

- Se necesitan las librerías `jupyter_client` e `ipykernel` instaladas: `pip install jupyter_client ipykernel`
- Se recomienda tener un entorno virtual configurado
- El kernel se inicia automáticamente al primer uso
- El estado se mantiene entre ejecuciones en la misma sesión

## Uso recomendado:

1. Usa esta skill para ejecutar código Python de forma interactiva
2. Ideal para prototipado rápido y pruebas de algoritmos
3. Mantiene variables entre ejecuciones (estado persistente)
4. Soporta múltiples tipos de salida:
   - Salida estándar (stdout)
   - Errores con traceback completo
   - Resultados estructurados (variables, objetos)
   - Contenido HTML y PNG generados
5. Para código que requiere mucho tiempo, considera dividirlo en bloques más pequeños
6. Siempre verifica los resultados antes de usarlos en otras operaciones
7. Usa esta skill con precaución debido a su nivel de seguridad alto