# Auditoría de Código — KogniTerm

**Agente auditor:** BashAgent  
**Fecha:** 2026-06-10  
**Alcance:** módulos core del proyecto (`kogniterm/core/` y `kogniterm/terminal/`)  
**Estado:** Informe generado automáticamente a partir del análisis de métricas, code smells, seguridad y consistencia.

---

## 1. Métricas de complejidad y mantenibilidad

| Archivo | Líneas (aprox.) | Complejidad Ciclomática (CC) | Índice de Mantenibilidad (MI) | Comentario |
|---------|-----------------|------------------------------|-------------------------------|------------|
| `core/llm_service.py` | ~2400 | Alta en métodos de orquestación y streaming (varios bloques > 40) | Bajo-Moderado (~30–40 en zonas complejas) | Concentración de lógica en una sola clase |
| `core/history_manager.py` | ~980 | Moderada (~15–30 por método) | Moderado (~45–60) | Responsabilidad clara, pero con branching en truncado |
| `core/skills/skill_manager.py` | ~1140 | Moderada (~15–30) | Moderado (~45–60) | Estructura aceptable; riesgo por importaciones dinámicas |
| `terminal/cli.py` | ~670 | Baja-Moderada (~10–20) | Alto (~60–70) | Código más lineal y mantenible |

### Observaciones

- En `core/llm_service.py` se detectaron zonas de **alta densidad condicional** (múltiples ramas para proveedores, streaming, reintentos y parsing). Eso eleva la CC y reduce la mantenibilidad.
- Los archivos de `terminal/` son más pequeños y con menor complejidad relativa, lo que los hace candidatos a servir como referencia de estilo para refactorizaciones futuras en `core/`.

---

## 2. Code smells y patrones problemáticos

### 2.1 Excepciones genéricas (`except Exception`)

Se detectó un patrón recurrente de captura de excepciones muy amplias:

- `core/llm_service.py`: **19** capturas de `except Exception`
- `core/history_manager.py`: **8** capturas de `except Exception`
- `core/skills/skill_manager.py`: **10** capturas de `except Exception`

**Impacto:**  
Oculta errores específicos, hace difícil el debugging y puede enmascarar fallos de configuración, red o parseo de respuestas.

**Recomendación:**
- Reemplazar al menos las capturas más frecuentes por excepciones específicas (`json.JSONDecodeError`, `IOError`, errores de proveedor, etc.).
- Conservar solo un `except Exception` por módulo como último recurso, con logging explícito.

### 2.2 Importaciones dinámicas y rutas frágiles

En `terminal/cli.py` se observa código como:

```python
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "bundled" / "agent_skills_adapter" / "scripts"))
from tool import install_skill_pack_from_repo
```

**Impacto:**  
- Acopla la CLI a una estructura de carpetas concreta.
- Dificulta empaquetado, pruebas y refactorizaciones.

**Recomendación:**
- Extraer la lógica de instalación/búsqueda de skills a un servicio dedicado en `core/skills/`.
- Inyectar dependencias en vez de manipular `sys.path`.

### 2.3 Lógica de UI y reglas de negocio mezcladas

`terminal/command_approval_handler.py` combina:

- Validación de seguridad de comandos (`_is_command_safe`)
- Generación de explicaciones con LLM
- Ejecución de comandos y renderizado de diffs

**Impacto:**  
- Baja cohesión, difícil de testear.
- Cambios en aprobación de comandos afectan también a la presentación.

**Recomendación:**
- Separar `CommandSecurityPolicy`, `ExplanationGenerator` y `DiffRenderer`.
- El handler debería orquestar, no ejecutar toda la lógica.

### 2.4 Duplicación de manejo de configuración

- `terminal/config_manager.py` maneja configuración global y por proyecto.
- Varios comandos de CLI repiten patrones de lectura/escritura JSON y masking de secretos.

**Impacto:**  
- Duplicación de lógica de masking y validación.

**Recomendación:**
- Unificar helpers de masking/validación en un módulo compartido.
- Usar el `ConfigManager` como única fuente de verdad para defaults y validaciones.

---

## 3. Seguridad, manejo de errores y validaciones

### 3.1 Manejo de errores

- El exceso de `except Exception` dificulta distinguir entre errores de usuario, de red, de parseo o de configuración.
- En zonas sensibles (ej. manejo de aprobación de comandos), se debería diferenciar entre:
  - Errores recuperables (reintentar)
  - Errores de validación (mostrar mensaje claro)
  - Errores críticos (abortar con contexto)

### 3.2 Validaciones

- `_is_command_safe` en `command_approval_handler.py` realiza una validación simplificada basada en lista blanca.
- Limitaciones observadas:
  - No considera completamente operadores avanzados (`||`, `&&`, tuberías complejas).
  - No valida rutas absolutas, expansiones de variables ni redirecciones creativas.

**Recomendación:**
- Complementar la lista blanca con:
  - Parsing más preciso de la línea de comandos.
  - Validación de rutas y entornos.
  - Posible integración con `shlex.split` y análisis AST de comandos.

### 3.3 Exposición de secretos

- Se detectó masking en CLI (`_mask_secret`, `scrub_secrets`, `mask_url_credentials`), pero su uso no es uniforme en todos los flujos.
- En logs y mensajes de error podría filtrarse información sensible si no se aplica de forma consistente.

**Recomendación:**
- Centralizar el enmascaramiento en un único helper.
- Aplicarlo de forma obligatoria antes de imprimir o loguear valores de configuración.

---

## 4. Consistencia de estilo, documentación y arquitectura

### 4.1 Estilo de código

- Mezcla de docstrings tipo Google, comentarios cortos y bloques de explicación en línea.
- Uso inconsistente de mayúsculas en constantes y variables.
- Algunas funciones excesivamente largas en `core/llm_service.py`.

**Recomendación:**
- Definir una guía de estilo clara (PEP 8 + convenciones del proyecto).
- Aplicar formateo automático (`black`, `isort`) y linting (`ruff`, `flake8`) en CI.

### 4.2 Documentación

- Los módulos de `terminal/` están mejor documentados que algunos módulos de `core/`.
- Faltan:
  - Descripciones de parámetros en métodos clave.
  - Ejemplos de uso para integradores.
  - Diagramas de flujo para aprobación de comandos y ciclo de vida del historial.

**Recomendación:**
- Completar docstrings en métodos públicos.
- Mantener un `docs/` sincronizado con la arquitectura real.

### 4.3 Arquitectura

- El proyecto muestra una clara separación entre:
  - `core/` (lógica de dominio)
  - `terminal/` (interfaz CLI/TUI)
  - `server/` (API y canales)
- Sin embargo, hay fugas de dependencias:
  - `terminal/cli.py` accede directamente a estructuras de skills y rutas internas.
  - `command_approval_handler.py` conoce detalles de herramientas específicas (`file_update`, `advanced_file_editor`, etc.).

**Recomendación:**
- Establecer dependencias explícitas por capa.
- Introducir interfaces o abstracciones para herramientas de archivo y aprobación, evitando imports directos desde `terminal` a skills concretas.

---

## 5. Hallazgos prioritarios y plan de mejora

### Alta prioridad

1. **Reducir excepciones genéricas** en `core/llm_service.py`, `core/history_manager.py` y `core/skills/skill_manager.py`.  
   - Esfuerzo: medio.  
   - Impacto: alta (mejora debugging, robustez y observabilidad).

2. **Separar validación de seguridad de comandos** de la lógica de presentación.  
   - Esfuerzo: medio-alto.  
   - Impacto: alta (testabilidad, mantenibilidad).

3. **Centralizar manejo de secretos** y evitar fugas en logs/CLI.  
   - Esfuerzo: bajo-medio.  
   - Impacto: alta (seguridad).

### Media prioridad

4. **Reducir importaciones dinámicas** y manipulación de `sys.path` desde CLI.  
   - Esfuerzo: medio.  
   - Impacto: media.

5. **Mejorar documentación de módulos core** (parametrización, ejemplos, diagramas).  
   - Esfuerzo: bajo-medio.  
   - Impacto: media.

### Baja prioridad

6. **Normalizar estilo y formato** con herramientas automáticas.  
   - Esfuerzo: bajo.  
   - Impacto: baja-media (mejora legibilidad).

7. **Refactorizar métodos muy largos** en `core/llm_service.py` en unidades más pequeñas.  
   - Esfuerzo: alto.  
   - Impacto: media (mejora mantenibilidad a largo plazo).

---

## 6. Conclusión

El proyecto presenta una **base arquitectónica sólida**, con separación de capas y un modelo de skills bien estructurado. Los principales riesgos se concentran en:

- Manejo de errores demasiado genérico,
- Acoplamiento entre capas,
- Inconsistencias en validaciones y manejo de secretos.

Se recomienda abordar primero los ítems de **alta prioridad**, ya que mejoran tanto la robustez como la capacidad de evolucionar el código sin introducir regresiones.
