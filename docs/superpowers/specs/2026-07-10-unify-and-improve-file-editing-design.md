# Especificación de Diseño: Unificación y Mejora de Edición de Archivos en KogniTerm

**Fecha:** 2026-07-10  
**Estado:** Aprobado  
**Autor:** Antigravity  

---

## 1. Contexto y Objetivos

KogniTerm cuenta actualmente con múltiples herramientas y alias para modificar archivos (`file_update_tool`, `file_operations`, `advanced_file_editor`, `sophisticated_editor_tool`, etc.). Esta redundancia causa confusión en el LLM sobre cuál elegir. Además, el motor de coincidencia actual (`FlexibleMatcher`) sufre de problemas de precisión que resultan en ediciones erráticas:
- **Sobre-matching en Fuzzy**: La búsqueda difusa (`fuzzy=True`) asume saltos de línea opcionales, permitiendo coincidencias que abarcan decenas de líneas no deseadas.
- **Conflictos con Saltos de Línea**: Coincidencias exactas fallan en entornos con archivos en Windows/CRLF si el LLM envía caracteres de salto de línea Unix (`\n`).
- **Desambiguación Ineficaz**: `context_hint` usa una ventana estática que genera falsos positivos en archivos pequeños.
- **Inserciones con Saltos Duplicados**: `insert_after_match` genera líneas vacías adicionales innecesarias.
- **Copias de Números de Línea**: El LLM copia accidentalmente el prefijo de número de línea (`  12 | `) devuelto por `read_file_tool`, rompiendo los patrones de búsqueda.
- **Aprobaciones Rotas**: El flujo de confirmación en `bash_agent.py` ejecuta todas las aprobaciones del editor avanzado como `full_replacement`, perdiendo los parámetros de la operación original.

**Objetivo:** Implementar un único motor de edición premium unificado en `advanced_file_editor` con precisión quirúrgica, corrección automática de errores comunes del LLM y robustez en la desambiguación y la confirmación.

---

## 2. Cambios Propuestos

### 2.1 Unificación de la Interfaz de Herramientas
- **Punto Único**: Consolidar la edición en `advanced_file_editor` (skill `advanced-file-editor`).
- **Deprecación Activa**: Modificar `file_update_tool` y `file_operations` para que redirijan internamente a `advanced_file_editor` (con `action="full_replacement"` para sobrescritura total). Se eliminarán de los esquemas declarados a los nuevos agentes para que solo utilicen `advanced_file_editor`.

### 2.2 Endurecimiento de `FlexibleMatcher` y `file_editor.py`

#### A. Pipeline de Limpieza e Inspección JIT de Entradas
Antes de procesar, limpiaremos `target_content`, `replacement_content`, `content` y `regex_pattern`:
1. **Remoción de Prefijos de Lectura**: Detectar si las líneas empiezan con el formato `^\s*\d+\s*\|\s?` y remover dicho prefijo para extraer el código crudo.
2. **Normalización de Salto de Línea**: Reemplazar temporalmente todos los `\r\n` por `\n` durante el análisis y el cálculo de diferencias. Al escribir a disco, restaurar los saltos originales detectados en el archivo.

#### B. Coincidencia Difusa Restringida a Línea (Fuzzy Line Match)
- Modificar el comportamiento de `fuzzy=True` en `FlexibleMatcher.find_match` para que reemplace los espacios horizontales del target con `[ \t]*` en lugar de `\s*` (que incluía `\n`).
- La coincidencia difusa será útil para variaciones de espaciado e indentación dentro de la misma línea, pero **nunca cruzará saltos de línea**.

#### C. Desambiguación por Proximidad Real
- Modificar `FlexibleMatcher.find_unique`.
- En caso de detectar múltiples coincidencias de `target_content`, se buscarán las ocurrencias de `context_hint`.
- Se calculará la distancia absoluta en líneas entre cada ocurrencia de `target_content` y la ocurrencia de `context_hint` más cercana.
- Se elegirá el match de `target_content` que minimice esta distancia (siempre que esté dentro de un rango razonable, ej. ±20 líneas). Si no hay un ganador único absoluto o la distancia es excesiva, se arrojará `MultipleMatchesError`.

#### D. Auto-Indentación Adaptativa
- Durante la sustitución de bloques en `replace_block`, `insert_after_match` o `insert_before_match`, detectaremos la diferencia de indentación entre la coincidencia encontrada en el archivo y la especificada por el LLM.
- Aplicaremos este offset al bloque de reemplazo para que encaje perfectamente con el estilo del archivo del usuario.

#### E. Prevención de Saltos de Línea Duplicados
- En `insert_after_match` e `insert_before_match`, validar la presencia de saltos de línea tanto en el punto de anclaje como en el contenido a insertar para evitar la inyección indeseada de líneas en blanco adicionales.

---

## 3. Flujo de Confirmación en Agentes
- Modificar `kogniterm/core/agents/bash_agent.py` (y cualquier otro agente relevante que maneje aprobaciones) para que, al procesar la confirmación aprobada por el usuario de `advanced_file_editor`, ejecute la herramienta con el diccionario de argumentos original (`original_tool_args`) y `confirm=True`, en lugar de forzar un reemplazo total (`full_replacement`) en base a un argumento de contenido incompleto.

---

## 4. Plan de Verificación

### 4.1 Pruebas Unitarias Automáticas
Ejecutaremos el conjunto de pruebas unitarias existente en `tests/unit/test_file_editor.py` e incorporaremos nuevas aserciones para validar:
1. **Auto-remoción de números de línea** en el target.
2. **Normalización y conservación de CRLF**.
3. **Auto-indentación adaptativa** en `replace_block`.
4. **Búsqueda por proximidad** con `context_hint` en archivos pequeños.
5. **No cruce de saltos de línea** en fuzzy.
6. **Inserciones limpias** en `insert_after_match` sin saltos duplicados.

### 4.2 Comando de Verificación
```bash
pytest tests/unit/test_file_editor.py
```
Todos los tests deben pasar exitosamente.
