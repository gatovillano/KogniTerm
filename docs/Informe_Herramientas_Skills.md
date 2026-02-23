# Informe: Herramientas y Skills en KogniTerm 🛠️🧠

Este informe detalla el funcionamiento, la arquitectura y los mecanismos de seguridad del sistema de herramientas y *skills* de KogniTerm.

## 1. Introducción 🌟

KogniTerm utiliza un sistema híbrido para extender las capacidades de sus agentes:

- **Herramientas (Core Tools)**: Componentes integrados que realizan tareas específicas.
- **Skills**: Módulos dinámicos que agrupan herramientas y documentación, permitiendo una expansión modular y personalizada sin modificar el núcleo del sistema.

## 2. Arquitectura: Legacy vs. Modular 🏗️

El sistema ha evolucionado de un modelo monolítico a uno basado en *plugins*:

### Herramientas Legacy

Ubicadas en `kogniterm/core/tools/`, son clases de Python que heredan de estructuras básicas y están registradas de forma permanente en el `ToolManager`.

### Sistema de Skills

Ubicado en `kogniterm/skills/`, permite cargar herramientas de forma dinámica ("Just-In-Time"). Está gestionado por el `SkillManager`, que separa la definición de la lógica.

---

## 3. Funcionamiento del SkillManager 🔄

El `SkillManager` (`kogniterm/core/skills/skill_manager.py`) es el corazón del sistema modular:

1. **Discovery (Descubrimiento)**: Busca skills en tres ubicaciones prioritarias:
    - `bundled`: Skills integradas en el sistema.
    - `managed`: Skills instaladas por el usuario.
    - `workspace`: Skills específicas del proyecto actual.
2. **Validación**: Verifica que cada skill tenga un `SKILL.md` válido y una carpeta `scripts/` con archivos Python.
3. **Carga JIT (Just-In-Time)**: Importa los módulos de Python solo cuando son necesarios, ahorrando recursos.
4. **Registro**: Inyecta las herramientas descubiertas en el `ToolManager` para que el LLM pueda verlas.

---

## 4. Anatomía de una Skill 📂

Cada skill sigue una estructura estándar para asegurar la compatibilidad:

- `SKILL.md`: Contiene los metadatos (nombre, versión, permisos) e instrucciones detalladas para el LLM en formato YAML frontmatter y Markdown.
- `scripts/`: Contiene la lógica en archivos `.py`. El sistema detecta automáticamente funciones y clases exportables.
- `references/` (Opcional): Documentación adicional o ejemplos de uso.

---

## 5. Gestión y Ejecución: ToolManager 🛠️

El `ToolManager` (`kogniterm/core/tools/tool_manager.py`) actúa como el puente entre el cerebro del agente (LLM) y las capacidades del sistema:

- **Consolidación**: Une las herramientas legacy y las provenientes de skills en un solo registro.
- **Formateado para el LLM**: Traduce las descripciones y esquemas de parámetros al formato que el modelo de lenguaje entiende (JSON Schema).
- **Inyección de Estado**: Pasa el `agent_state` a las herramientas para que mantengan el contexto de la tarea actual.

---

## 6. Seguridad y Validación 🛡️

El sistema implementa varios niveles de protección:

### Validación de Race Conditions

Utiliza el `RaceConditionGuard` para asegurar que un archivo no haya cambiado entre el momento en que el agente decide editarlo y el momento en que aplica el cambio.

### Confirmación del Usuario

Las herramientas críticas (como `advanced_file_editor`) no aplican cambios directamente. En su lugar, generan un **diff** (diferencia visual) y solicitan aprobación explícita.

### Niveles de Seguridad

Cada skill define su `security_level` (low, medium, high). Esto permite configurar automáticamente qué acciones requieren supervisión humana constante.

---

## 7. Conclusión ✨

La arquitectura de KogniTerm está diseñada para ser flexible y segura. El sistema de *skills* no solo permite a los desarrolladores añadir nuevas capacidades fácilmente, sino que garantiza que los agentes operen bajo un marco riguroso de seguridad y transparencia para el usuario final.
