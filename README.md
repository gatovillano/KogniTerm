# 🤖 KogniTerm

![KogniTerm Banner](image.png)
<video controls src="kogniterm/kogniterm.mp4" title="KogniTerm Demo"></video>

**KogniTerm** es un asistente de terminal agéntico de última generación. Transforma tu línea de comandos en un entorno de desarrollo colaborativo donde **Agentes de IA Especializados** trabajan contigo para razonar, investigar, codificar y ejecutar tareas complejas.

A diferencia de otros asistentes, KogniTerm no depende de las capacidades nativas de "Tool Calling" de los modelos. Gracias a su **Motor de Parseo Universal**, es capaz de otorgar capacidades agénticas a prácticamente cualquier LLM (DeepSeek, Llama 3, Mistral, etc.), interpretando sus intenciones directamente desde el lenguaje natural.

## 🎯 Punto de Entrada

**⚠️ IMPORTANTE**: El punto de entrada principal del proyecto es `kogniterm/terminal/terminal.py` (404 líneas). El archivo `kogniterm/main.py` es una redirección obsoleta y no debe utilizarse para ejecución directa.

```bash
# Ejecución correcta
python -m kogniterm.terminal.terminal

# O usando el entry point configurado en pyproject.toml
kogniterm
```

## 🧠 Arquitectura Interna Profunda

KogniTerm implementa una arquitectura modular y escalable con los siguientes componentes centrales:

### 🔄 **AgentState** (170 líneas)
Sistema de estado global que orquesta toda la sesión:
- **MessageManager**: Gestión de mensajes entre agente y usuario, incluyendo formato y serialización
- **HistoryManager**: Persistencia de historial con soporte para compresión y recuperación
- **Detección de Race Conditions**: Sincronización para acceso concurrente a recursos compartidos
- **Interrupt Queue**: Sistema de prioridades para interrupciones y señales

### 🤖 **Agentes Especializados**

#### **BashAgent** (796 líneas) - Orquestador Principal
- **Streaming de respuestas**: Salida en tiempo real con renderizado progresivo
- **Detección de bucles**: Identifica y previene ciclos infinitos en comandos
- **Confirmaciones diferidas**: Permite postergar aprobaciones de acciones destructivas
- **Delegación inteligente**: Decide dinámicamente a qué especialista enviar cada tarea

#### **CodeAgent** (446 líneas) - Ingeniero de Software
- **Validación Markdown**: Asegura que el código generado esté en bloques代码 markdown
- **Verificación pre-edición**: Lee y valida archivos antes de modificarlos
- **Principios de calidad**: Prioriza robustez sobre velocidad
- **Contexto de archivos**: Capacidad para referenciar múltiples archivos simultáneamente

#### **ResearcherAgent** (El Detective)
- **Análisis estático**: Examina código sin ejecutarlo
- **Comprensión de arquitectura**: Identifica patrones y relaciones entre módulos
- **Explicaciones didácticas**: Traduce conceptos técnicos a lenguaje accesible

### ⚙️ **SkillManager** (642 líneas) - Framework de Habilidades
Sistema modular para extender funcionalidades:

- **Carga dinámica JIT**: Las skills se cargan solo cuando se necesitan por primera vez
- **Validación estricta**: Cada skill debe implementar un esquema de parámetros `parameters_schema`
- **27 skills bundled**: Incluyendo `file_operations`, `execute_command`, `code_analysis`, etc.
- **Registro automático**: Las skills creadas con `skill_factory` se integran automáticamente
- **Directorio `scripts/`**: Skills personalizadas pueden almacenarse como scripts externos
- **Documentación integrada**: Cada skill genera su propio `SKILL.md` automáticamente

Ejemplo de skill personalizada:
```python
skill_factory(
    skill_name="mi_tool",
    description="Mi herramienta personalizada",
    tool_code="""
def mi_tool(**kwargs):
    param1 = kwargs.get('param1')
    # Lógica personalizada
    return f"Resultado: {param1}"
parameters_schema = {
    "type": "object",
    "properties": {
        "param1": {"type": "string", "description": "Parámetro de ejemplo"}
    },
    "required": ["param1"]
}
""",
    instructions="Instrucciones detalladas en Markdown..."
)
```

### 🧠 **LLMService** (1648 líneas) - Motor de Lenguaje
- **MultiProviderManager**: Soporte unificado para múltiples proveedores
- **Soporte nativo**: OpenAI, Anthropic, Google Gemini
- **Soporte extendido**: DeepSeek, SiliconFlow, Nex-AGI, Ollama (modelos locales)
- **Text-to-Tool universal**: Convierte respuestas en texto plano (JSON, XML, YAML, lenguaje natural) en ejecuciones de herramientas
- **Rate limiting**: Control de cuota por proveedor
- **Conversión de herramientas**: Transforma el formato nativo de cada modelo al formato interno unificado

### 🗂 **RAG: Indexado de Código** (333 líneas)
Sistema de recuperación semántica para comprender la base de código completa:

- **CodebaseIndexer**: Indexador inteligente con chunking adaptativo
- **Exclusiones .gitignore**: Respeta automáticamente archivos ignorados
- **Embeddings vectoriales**: Almacena representaciones semánticas para búsqueda por similitud
- **Overlap inteligente**: Solapamiento configurable entre chunks para mantener contexto
- **Progreso visual**: Barra de progreso durante indexación masiva
- **Actualización incremental**: Re-indexa solo archivos modificados
- **Consultas contextuales**: Los agentes pueden preguntar "¿Cómo se relaciona X con Y?" cruzando archivos

Uso:
```bash
kogniterm index .          # Indexar directorio actual
kogniterm index --exclude "*.log"  # Exclusiones personalizadas
```

## 🛡 Seguridad Robusta

KogniTerm implementa múltiples capas de seguridad:

### **Human-in-the-Loop**
- **Confirmación explícita**: Antes de cualquier comando destructivo (`rm`, `dd`, etc.)
- **Edición atómica**: Los archivos se escriben completos, no línea por línea
- **Vista previa de diffs**: Revisa exactamente qué cambiará antes de aplicar
- **Modo `-y`**: Aprobación automática para automatización supervisada

### **Detección de Comportamientos Peligrosos**
- **Bucles infinitos**: BashAgent detecta patrones repetitivos en comandos
- **Race conditions**: AgentState sincroniza acceso a recursos compartidos
- **Campos de confirmación específicos**: Algunas acciones requieren escribir "CONFIRM" explícitamente
- **Límites de ejecución**: Timeout y restricciones de recursos en comandos

### **Validación de Entradas**
- **Esquemas JSON**: Todas las herramientas definen `parameters_schema` estricto
- **Sanitización**: Escape de caracteres especiales en argumentos
- **Permisos de archivos**: Verifica permisos antes de operaciones críticas

## ⚙️ Configuración Avanzada

### **Gestión de Proveedores Múltiples**
```bash
# Configurar múltiples API keys
kogniterm keys set openrouter sk-or-v1-...
kogniterm keys set google AIzaSy...
kogniterm keys set openai sk-...

# Cambiar modelo dinámicamente
kogniterm models use openrouter/deepseek/deepseek-chat
kogniterm models use google/gemini-2.0-flash-exp
kogniterm models current  # Ver modelo activo
```

### **Rate Limiting y Cuotas**
- Configuración por proveedor en `~/.config/kogniterm/config.yaml`
- Límites automáticos para evitar sobrecostos
- Retroceso exponencial en errores 429

### **Conversión Universal de Herramientas**
El sistema puede interpretar intenciones de cualquier modelo:
- **Modelos con Tool Calling**: Usan formato nativo (OpenAI, Anthropic)
- **Modelos sin Tool Calling**: Parsean JSON/XML/YAML o lenguaje natural
- **Fallback inteligente**: Si el parseo falla, se pide aclaración al usuario

## 🎮 Experiencia Interactiva

### **Comandos Mágicos (`%`)**
- **`%models`**: Menú interactivo para cambiar modelo en caliente
- **`%help`**: Panel de ayuda navegable
- **`%reset`**: Limpia contexto y comienza de cero
- **`%undo`**: Deshace la última acción
- **`%compress`**: Resume historial para ahorrar tokens

### **Referencias Inteligentes (`@`)**
```text
(kogniterm) › ¿Qué hace la función process en @core/logic.py?
```
Autocompletado de archivos al instante.

## 🗂 Estructura del Proyecto

```
kogniterm/
├── terminal/
│   └── terminal.py          # 🎯 Punto de entrada principal (404 líneas)
├── agents/
│   ├── bash_agent.py        # Orquestador (796 líneas)
│   ├── code_agent.py        # Desarrollador (446 líneas)
│   └── researcher_agent.py  # Detective
├── core/
│   ├── agent_state.py       # Estado global (170 líneas)
│   ├── skill_manager.py     # Framework de skills (642 líneas)
│   └── llm_service.py       # Motor LLM (1648 líneas)
├── rag/
│   └── codebase_indexer.py  # Indexador semántico (333 líneas)
├── skills/                  # Skills built-in y personalizadas
├── scripts/                 # Skills externas (JIT)
└── docs/                    # Documentación técnica extensa
```

## 📚 Documentación Técnica

Para entender a fondo la arquitectura, consulta:

### 🏗 **Arquitectura y Diseño**
- [Visión General](docs/overview.md)
- [Arquitectura del Sistema](docs/arquitectura_documentacion.md)
- [Módulos del Sistema](docs/modules.md)
- [Diagrama de Flujo](docs/flow_diagram.md)

### 🧩 **Componentes Específicos**
- [Gestor de Historial](docs/history_manager_documentation.md)
- [Herramienta de Creación de Planes](docs/plan_creation_tool.md)
- [Archivos CLI de Gemini](docs/gemini_cli_files.md)

### 🧠 **Sistema RAG**
- [Propuesta de RAG](docs/rag_codebase_proposal.md)
- [Plan de Implementación](docs/rag_implementation_plan.md)
- [Estado de Implementación](docs/rag_implementation_status.md)

### 🛠 **Sistema de Skills**
- [Guía de Skills](docs/SKILL.md) - Cómo crear y extender habilidades
- [Especificación de Esquemas](docs/skill_schema_specification.md)

### 📝 **Registros**
- [Registro de Cambios](docs/Cambios.md)
- [Registro de Errores y Soluciones](docs/registro_errores_soluciones.md)
- [Log de Desarrollo](docs/development_log.md)

## 🚀 Instalación

```bash
# Instalar con pipx (recomendado para aislar dependencias)
pipx install kogniterm

# O con pip
pip install kogniterm
```

## ⚙️ Configuración y Gestión (CLI)

KogniTerm incluye una CLI dedicada para gestionar tus llaves y modelos sin editar archivos de configuración manualmente.

### 🔑 Gestión de API Keys

```bash
# Configurar OpenRouter (Acceso a DeepSeek, Llama, etc.)
kogniterm keys set openrouter sk-or-v1-...

# Configurar Google Gemini
kogniterm keys set google AIzaSy...

# Configurar OpenAI
kogniterm keys set openai sk-...

# Ver estado de las llaves
kogniterm keys list
```

### 🧠 Selección de Modelos

Cambia el "cerebro" de KogniTerm al instante:

```bash
# Usar DeepSeek vía OpenRouter (Ejemplo)
kogniterm models use openrouter/deepseek/deepseek-chat

# Usar Gemini 2.0 Flash
kogniterm models use google/gemini-2.0-flash-exp

# Ver modelo activo
kogniterm models current
```

## 🎮 Comandos Mágicos y Referencias

### Comandos Mágicos (`%`)
- **`%models`**: Abre un menú interactivo para cambiar de modelo en caliente sin reiniciar la sesión.
- **`%help`**: Panel de ayuda navegable.
- **`%reset`**: Limpia el contexto y comienza de cero.
- **`%undo`**: Deshace la última acción del agente.
- **`%compress`**: Resume el historial para ahorrar tokens manteniendo lo importante.

### Referencias Inteligentes (`@`)
Inyecta contexto de archivos directamente en tu prompt:

```text
(kogniterm) › ¿Qué hace la función process en @core/logic.py?
```

El autocompletado te ayudará a encontrar tus archivos al instante.

## 🧠 Indexado de Código (RAG)

Para preguntas sobre la arquitectura global de tu proyecto:

```bash
# Indexar el directorio actual
kogniterm index .

# Indexar con exclusiones personalizadas
kogniterm index . --exclude "*.log" --exclude "node_modules"
```

Esto permite a los agentes entender relaciones entre archivos que no han leído explícitamente, gracias al sistema RAG con chunking inteligente, exclusiones .gitignore y embeddings vectoriales.

---

*Desarrollado por Gatovillano*

---

## 💙 Apoya el Proyecto

Si encuentras útil este proyecto, considera hacer una donación para apoyar su desarrollo continuo. Cada contribución ayuda a mantener el proyecto activo y a agregar nuevas características.

[![Donar con PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate?hosted_button_id=TU_ID_DE_BOTÓN)

O también puedes apoyar a través de:

* [GitHub Sponsors](https://github.com/sponsors/tu-usuario)
* [Patreon](https://www.patreon.com/tu-usuario)

¡Gracias por tu apoyo! 🙌