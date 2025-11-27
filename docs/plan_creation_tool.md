# 📋 Plan Creation Tool - Documentación

## 🎯 Descripción General

La herramienta `PlanCreationTool` permite al agente generar planes detallados paso a paso para tareas complejas que requieren múltiples acciones. El plan se presenta al usuario en un panel Rich con formato Markdown, y el usuario puede aprobar o rechazar el plan antes de que el agente proceda con su ejecución.

## ✨ Características

- **Generación Automática de Planes**: Utiliza el LLM para crear planes estructurados basados en la descripción de la tarea
- **Interfaz Visual Rica**: Presenta el plan en un panel con formato Markdown y colores temáticos
- **Aprobación Interactiva**: Solicita confirmación del usuario (s/n) antes de proceder
- **Integración con CommandApprovalHandler**: Se integra perfectamente con el sistema de aprobación existente
- **Formato JSON Estructurado**: Retorna datos en formato JSON para fácil procesamiento

## 🔧 Uso

### Desde el Agente

El agente puede invocar la herramienta cuando detecta que una tarea requiere múltiples pasos:

```python
# El agente detecta una tarea compleja
task_description = "Crear una aplicación web con React, configurar el backend con FastAPI y desplegar en Docker"

# Invoca la herramienta
result = plan_creation_tool._run(task_description=task_description)
```

### Formato de Salida

La herramienta retorna un JSON string con el siguiente formato:

```json
{
  "status": "requires_confirmation",
  "operation": "plan_creation",
  "plan_title": "Plan para Crear Aplicación Web Full-Stack",
  "plan_steps": [
    {
      "step": 1,
      "description": "Crear estructura del proyecto React con create-react-app"
    },
    {
      "step": 2,
      "description": "Configurar FastAPI backend con estructura de carpetas"
    },
    {
      "step": 3,
      "description": "Crear Dockerfile para containerización"
    }
  ],
  "message": "Se ha generado un plan para: Crear una aplicación web...",
  "task_description": "Crear una aplicación web con React..."
}
```

## 🎨 Interfaz de Usuario

Cuando el usuario recibe el plan, ve algo como esto:

```
╭─ Confirmación de Plan: Plan para Crear Aplicación Web Full-Stack ─╮
│                                                                     │
│ Tarea: Crear una aplicación web con React, configurar el backend   │
│ con FastAPI y desplegar en Docker                                  │
│                                                                     │
│ ───────────────────────────────────────────────────────────────    │
│                                                                     │
│ 1. Crear estructura del proyecto React con create-react-app        │
│                                                                     │
│ 2. Configurar FastAPI backend con estructura de carpetas           │
│                                                                     │
│ 3. Crear Dockerfile para containerización                          │
│                                                                     │
╰─────────────────────────────────────────────────────────────────────╯

¿Deseas ejecutar esta acción? (s/n):
```

## 🔄 Flujo de Aprobación

1. **Generación**: El agente invoca `plan_creation_tool` con una descripción de la tarea
2. **Presentación**: El plan se muestra en un panel Rich con formato Markdown
3. **Confirmación**: El usuario responde 's' (aprobar) o 'n' (rechazar)
4. **Respuesta**:
   - Si se aprueba: El agente recibe confirmación y procede con los pasos
   - Si se rechaza: El agente recibe denegación y puede ajustar su estrategia

## 🛠️ Integración con el Sistema

### CommandApprovalHandler

El `CommandApprovalHandler` detecta automáticamente cuando una herramienta retorna:

```json
{
  "status": "requires_confirmation",
  "operation": "plan_creation",
  ...
}
```

Y maneja la presentación y aprobación del plan.

### BashAgent

El `bash_agent.py` detecta cualquier herramienta que retorne `status: "requires_confirmation"` y detiene la ejecución para solicitar aprobación del usuario.

## 📝 Ejemplo Completo

### Solicitud del Usuario

```
Usuario: Necesito crear un sistema de autenticación completo para mi aplicación
```

### Respuesta del Agente

```
🤖 Entendido! Voy a crear un plan detallado para implementar un sistema de autenticación completo.

[Invoca plan_creation_tool]
```

### Plan Generado

```
╭─ Confirmación de Plan: Sistema de Autenticación Completo ─╮
│                                                             │
│ 1. Configurar base de datos con tabla de usuarios          │
│ 2. Implementar hash de contraseñas con bcrypt              │
│ 3. Crear endpoints de registro y login                     │
│ 4. Implementar JWT para sesiones                           │
│ 5. Añadir middleware de autenticación                      │
│ 6. Crear tests unitarios para el sistema                   │
│                                                             │
╰─────────────────────────────────────────────────────────────╯

¿Aceptas este plan? (s/n):
```

### Si el Usuario Aprueba

```
✅ Plan 'Sistema de Autenticación Completo' aprobado. ¡A trabajar! 🚀

[El agente procede a ejecutar cada paso del plan]
```

## 🧪 Testing

Para verificar que la herramienta funciona correctamente:

```bash
python3 test_plan_tool_integration.py
```

## 🔍 Detalles Técnicos

### Schema

```python
class PlanCreationToolSchema(BaseModel):
    task_description: str = Field(
        description="A detailed description of the complex task for which a plan needs to be created."
    )
```

### Método Principal

```python
def _run(self, task_description: str) -> str:
    """
    Generates a plan for a given task description using the LLM.
    Returns a JSON string with status "requires_confirmation" for the approval handler.
    """
```

### Prompt del LLM

La herramienta utiliza un prompt especializado que instruye al LLM para generar planes en formato JSON estructurado:

```
Eres un experto planificador de tareas. Genera un plan detallado y paso a paso...
Formato de salida (JSON):
{
  "plan_title": "Título del Plan",
  "steps": [
    {"step": 1, "description": "Descripción del paso 1"},
    ...
  ]
}
```

## 🎯 Casos de Uso

1. **Proyectos Nuevos**: Crear estructura completa de un proyecto
2. **Refactorización**: Planificar cambios grandes en el código
3. **Debugging Complejo**: Estrategia paso a paso para resolver bugs
4. **Despliegue**: Plan de deployment con múltiples etapas
5. **Migraciones**: Migración de tecnologías o versiones

## ⚙️ Configuración

La herramienta está registrada automáticamente en el `ToolManager` y está disponible para el agente sin configuración adicional.

## 🐛 Troubleshooting

### El plan no se muestra

- Verificar que `terminal_ui` está correctamente inicializado
- Revisar logs para errores de parsing JSON

### El LLM no genera JSON válido

- La herramienta incluye manejo de errores para extraer JSON de bloques de código
- Si falla, retorna un error descriptivo

## 📚 Referencias

- `kogniterm/core/tools/plan_creation_tool.py` - Implementación de la herramienta
- `kogniterm/terminal/command_approval_handler.py` - Manejo de aprobación
- `kogniterm/core/agents/bash_agent.py` - Integración con el agente
