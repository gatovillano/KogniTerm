# 🏗️ Esquema de Arquitectura de Agentes - KogniTerm

> **Fecha**: 2024 | **Versión**: 1.0 | **Autor**: KogniTerm

---

## 📋 Índice
1. [Visión General](#visión-general)
2. [Arquitectura Central](#arquitectura-central)
3. [Catálogo de Agentes](#catálogo-de-agentes)
4. [Sistema de Skills](#sistema-de-skills)
5. [Memoria y Contexto](#memoria-y-contexto)
6. [Mecanismos de Comunicación](#mecanismos-de-comunicación)
7. [Flujos de Trabajo](#flujos-de-trabajo)
8. [Potencial de Crecimiento](#potencial-de-crecimiento)
9. [Diagramas](#diagramas)

---

## 🎯 Visión General

KogniTerm es un **sistema multi-agente con capacidad evolutiva** diseñado para asistencia técnica en terminal, desarrollo y depuración. La arquitectura sigue un patrón de **Orquestador Central** con **Agentes Especializados** y un sistema de **Skills Dinámicas**.

### Características Clave
- ✅ **Autonomía**: Ejecución directa de comandos sin intervención humana
- ✅ **Evolutividad**: Creación dinámica de nuevas herramientas (skills)
- ✅ **Memoria Persistente**: Contexto mantenido entre sesiones
- ✅ **Paralelismo**: Ejecución simultánea de agentes especializados
- ✅ **Proactividad**: Gestión inteligente de memoria y contexto

---

## 🏛️ Arquitectura Central

```
┌─────────────────────────────────────────────────────────────┐
│                    KOGNITERM (Orquestador)                  │
│  "Experto en terminal, depuración y Python"                │
└──────────────┬──────────────────────────────────┬───────────┘
               │                                  │
               │ Invoca                            │ Crea
               ▼                                  ▼
    ┌─────────────────────┐            ┌──────────────────────┐
    │  AGENTES            │            │    SKILLS            │
    │  ESPECIALIZADOS     │            │   DINÁMICAS          │
    └──────────┬──────────┘            └──────────┬───────────┘
               │                                  │
               │ call_agent_skill                 │ skill_factory
               ▼                                  ▼
    ┌─────────────────────┐            ┌──────────────────────┐
    │ • researcher_agent   │            │ • Herramientas       │
    │ • code_agent        │            │   personalizadas     │
    │ • DeepCoder         │            │ • Lógica Python      │
    │ • DeepResearcher    │            │ • Esquema auto-reg   │
    └─────────────────────┘            └──────────────────────┘
```

### Responsabilidades del Orquestador
1. **Interpretar intenciones** del usuario
2. **Seleccionar la mejor estrategia** (agente vs skill vs herramienta nativa)
3. **Mantener contexto** mediante memoria
4. **Ejecutar comandos** de forma autónoma
5. **Coordinar agentes** para tareas complejas
6. **Crear nuevas capacidades** mediante skill_factory

---

## 🤖 Catálogo de Agentes

### 1. **KogniTerm** (Orquestador Principal)
- **Rol**: Agente evolutivo de terminal, depuración y Python
- **Capacidades**:
  - Ejecución autónoma de comandos bash
  - Edición de archivos con advanced_file_editor
  - Búsqueda en base de código vectorial
  - Análisis estático de código (radon)
  - Ejecución de código Python (Jupyter kernel)
  - Gestión de memoria contextual
  - Creación de nuevas skills

### 2. **researcher_agent** (Investigador)
- **Invocación**: `call_agent_skill(agent_name="researcher_agent", task=...)`
- **Especialidad**: Investigación profunda y creación de informes
- **Casos de uso**:
  - Análisis detallado de arquitectura
  - Investigación de tecnologías
  - Generación de documentación técnica
  - Análisis de código existente

### 3. **code_agent** (Desarrollador)
- **Invocación**: `call_agent_skill(agent_name="code_agent", task=...)`
- **Especialidad**: Desarrollo, edición y refactorización
- **Casos de uso**:
  - Implementación de características complejas
  - Refactorización de código
  - Creación de nuevos módulos
  - Optimización de rendimiento

### 4. **DeepCoder** (Especialista en Código - Paralelo)
- **Invocación**: `call_agents_parallel(task_coder=..., task_researcher=...)`
- **Especialidad**: Desarrollo intensivo y técnico
- **Ejecución**: Paralela junto con DeepResearcher

### 5. **DeepResearcher** (Especialista en Investigación - Paralelo)
- **Invocación**: `call_agents_parallel(task_coder=..., task_researcher=...)`
- **Especialidad**: Investigación y análisis profundo
- **Ejecución**: Paralela junto con DeepCoder

---

## 🛠️ Sistema de Skills

### Skills Nativas (Integradas)
| Skill | Descripción | Tipo |
|-------|-------------|------|
| `execute_command` | Ejecución de comandos bash | Shell |
| `codebase_search` | Búsqueda semántica en código | Vectorial |
| `python_executor` | Ejecución de código Python | Runtime |
| `code_analysis` | Análisis estático (radon) | Análisis |
| `github` | Interacción con GitHub | API |
| `tavily_search` | Búsqueda web optimizada | Web |
| `web_fetch` | Obtención de HTML | Web |
| `web_scraping` | Extracción estructurada | Web |
| `memory_*` | Gestión de memoria contextual | Memoria |
| `advanced_file_editor` | Edición premium de archivos | Archivos |
| `project_analyzer` | Análisis de proyectos | Análisis |
| `docker_error_logs` | Logs de errores Docker | DevOps |

### Skills Dinámicas (Creadas con skill_factory)
- **Creación**: `skill_factory(skill_name=..., tool_code=..., instructions=...)`
- **Registro**: Automático en el esquema de herramientas
- **Invocación**: Directa por nombre (como cualquier otra herramienta)
- **Persistencia**: Sobrevive entre sesiones

---

## 🧠 Memoria y Contexto

### Arquitectura de Memoria
```
┌─────────────────────────────────────────┐
│         llm_context.md                  │
│    (Archivo de Memoria Persistente)     │
├─────────────────────────────────────────┤
│ • Decisiones clave                      │
│ • Preferencias del usuario              │
│ • Hitos del proyecto                    │
│ • Información valiosa                   │
└─────────────────────────────────────────┘
         ▲              ▲             ▲
         │              │             │
    memory_init   memory_append  memory_summarize
```

### Herramientas de Memoria
| Herramienta | Función |
|-------------|---------|
| `memory_init` | Inicializa llm_context.md |
| `memory_append` | Añade contenido a la memoria |
| `memory_read` | Lee el contenido de la memoria |
| `memory_summarize` | Resume la memoria |
| `search_memory` | Evita búsquedas redundantes |

---

## 🔄 Mecanismos de Comunicación

### 1. Invocación Directa (Secuencial)
```python
resultado = call_agent_skill(
    agent_name="researcher_agent",
    task="Analizar arquitectura X"
)
```

### 2. Ejecución Paralela
```python
resultados = call_agents_parallel(
    task_coder="Implementar función Y",
    task_researcher="Investigar mejores prácticas Z"
)
```

### 3. Compartir Resultados
- **Retorno de strings**: Los agentes devuelven resultados como texto
- **Memoria compartida**: Escritura en llm_context.md
- **Contexto del proyecto**: Directorio de trabajo actual

---

## 🔀 Flujos de Trabajo

### Flujo 1: Investigación Simple
1. Usuario pide investigar X
2. KogniTerm invoca researcher_agent
3. Agente investiga y genera informe
4. Resultado presentado al usuario
5. KogniTerm guarda hito en memoria

### Flujo 2: Desarrollo Complejo
1. Usuario pide implementar característica Y
2. KogniTerm invoca code_agent
3. Agente desarrolla/refactoriza código
4. KogniTerm ejecuta pruebas
5. Resultado validado y presentado

### Flujo 3: Paralelo (Investigación + Código)
1. Usuario pide tarea compleja Z
2. KogniTerm usa call_agents_parallel
3. DeepResearcher investiga en paralelo
4. DeepCoder desarrolla en paralelo
5. KogniTerm consolida resultados

### Flujo 4: Evolución (Creación de Skill)
1. KogniTerm identifica necesidad de nueva capacidad
2. Usa skill_factory con código Python
3. Sistema registra automáticamente la skill
4. Nueva skill disponible inmediatamente
5. Memoria registra la evolución

---

## 🚀 Potencial de Crecimiento

### Nivel 1: Expansión de Skills (Actual)
- ✅ Creación ilimitada de skills dinámicas
- ✅ Integración con APIs externas
- ✅ Lógica personalizada en Python
- ✅ Registro automático en esquema

### Nivel 2: Nuevos Agentes Especializados
- 🔲 Agentes para dominios específicos
- 🔲 Agentes con personalidades distintas
- 🔲 Agentes con memoria propia
- 🔲 Jerarquías de agentes

### Nivel 3: Comunicación Avanzada
- 🔲 Colas de mensajes asíncronos
- 🔲 Event-driven architecture
- 🔲 Compartir estado en tiempo real
- 🔲 Callbacks y notificaciones

### Nivel 4: Aprendizaje y Adaptación
- 🔲 Fine-tuning basado en feedback
- 🔲 Auto-optimización de flujos
- 🔲 Detección de patrones de uso
- 🔲 Sugerencias proactivas

### Nivel 5: Orquestación Compleja
- 🔲 Grafos de dependencias
- 🔲 Balanceo de carga dinámico
- 🔲 Tolerancia a fallos
- 🔲 Métricas y monitoreo

### Nivel 6: Ecosistema Completo
- 🔲 Marketplace de skills comunitarias
- 🔲 Agentes autónomos
- 🔲 Colaboración multi-usuario
- 🔲 Integración con IDEs

---

## 📊 Diagramas

### Diagrama de Componentes
```
┌────────────────────────────────────────────────┐
│           KOGNITERM ORCHESTRATOR               │
│  ┌──────────────┐  ┌──────────────┐          │
│  │ MEMORIA      │  │ CONTEXTO     │          │
│  │ llm_context  │  │ Directorio   │          │
│  └──────────────┘  └──────────────┘          │
└──────┬───────────────┬──────────────┬─────────┘
       │               │              │
       ▼               ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│  AGENTES │   │  SKILLS  │   │ HERRAM.  │
│ researcher│   │ Dinámicas│   │ Nativas  │
│ code_agent│   │ (factory)│   │ (bash)   │
└──────────┘   └──────────┘   └──────────┘
```

---

**Documento generado por KogniTerm**  
*Última actualización: 2024*
