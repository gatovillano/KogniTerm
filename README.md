# 🤖 KogniTerm

![KogniTerm Banner](image.png)

**KogniTerm** es un asistente de terminal agéntico de última generación. Transforma tu línea de comandos en un entorno de desarrollo colaborativo donde **Agentes de IA Especializados** trabajan contigo para razonar, investigar, codificar y ejecutar tareas complejas.

A diferencia de otros asistentes, KogniTerm no depende de las capacidades nativas de "Tool Calling" de los modelos. Gracias a su **Motor de Parseo Universal**, es capaz de otorgar capacidades agénticas a prácticamente cualquier LLM (DeepSeek, Llama 3, Mistral, etc.), interpretando sus intenciones directamente desde el lenguaje natural.

## ✨ Características Principales

### 🧠 Arquitectura Multi-Agente Especializada

KogniTerm orquesta un equipo de expertos digitales, cada uno con un rol y personalidad definidos:

* **🕵️ ResearcherAgent (El Detective)**:
  * **Rol**: Experto en comprensión y análisis.
  * **Misión**: Lee tu código, investiga documentación y explica sistemas complejos sin riesgo de romper nada.
  * **Cuándo usarlo**: "Explícame cómo funciona X", "Analiza este error", "Investiga la arquitectura".

* **👨‍💻 CodeAgent (El Desarrollador Senior)**:
  * **Rol**: Ingeniero de software enfocado en calidad.
  * **Principios**: Calidad sobre velocidad, verificación constante y seguridad.
  * **Misión**: Escribe, refactoriza y parchea código. Siempre verifica el contenido antes de editar y busca minimizar errores.
  * **Cuándo usarlo**: "Refactoriza esta función", "Crea un script para...", "Arregla el bug en main.py".

* **🤖 BashAgent (El Operador)**:
  * **Rol**: Tu interfaz principal y orquestador.
  * **Misión**: Maneja la terminal, ejecuta comandos del sistema y sabe exactamente a qué especialista delegar cada tarea.

### 🌐 Compatibilidad Universal (The "Any-Model" Engine)

KogniTerm rompe las barreras de los proveedores. Su sistema de **Parseo de Herramientas Híbrido** permite:

* **Soporte Nativo**: OpenAI, Anthropic, Google Gemini.
* **Soporte Extendido**: **DeepSeek**, **SiliconFlow**, **Nex-AGI**, y modelos locales (Ollama).
* **Text-to-Tool**: Si un modelo no soporta llamadas a funciones, KogniTerm detecta patrones en su texto (JSON, XML, YAML, o lenguaje natural) y ejecuta las herramientas correspondientes. ¡Haz agéntico a cualquier modelo!

### 🛠 Herramientas de Potencia Industrial

* **Sistema de Archivos Seguro**: Lectura recursiva inteligente, búsquedas con `grep` y edición atómica.
* **RAG Local (Indexado de Código)**: Convierte tu base de código en una base de conocimiento consultable.
* **Búsqueda Web**: Acceso a internet para documentación actualizada y resolución de errores en tiempo real.
* **Intérprete Python Persistente**: Un entorno REPL para cálculos, procesamiento de datos y lógica compleja.

### 🛡 Seguridad y Control

* **Human-in-the-loop**: Confirmación explícita antes de comandos destructivos o ediciones de archivos.
* **Modo Auto-Aprobación (`-y`)**: Para automatización supervisada.
* **Visualización de Diffs**: Revisa exactamente qué cambiará en tu código antes de aplicarlo.

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

## 🎮 Experiencia Interactiva

Una vez dentro de `kogniterm`, tienes superpoderes:

### Comandos Mágicos (`%`)

* **`%models`**: Abre un **menú interactivo** para cambiar de modelo en caliente sin reiniciar la sesión.
* **`%help`**: Panel de ayuda navegable.
* **`%reset`**: Limpia el contexto y comienza de cero.
* **`%undo`**: ¿El modelo se equivocó? Deshaz la última acción.
* **`%compress`**: Resume el historial para ahorrar tokens manteniendo lo importante.

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
```

Esto permite a los agentes entender relaciones entre archivos que no han leído explícitamente.

## 📚 Documentación

Explora la documentación detallada para entender a fondo KogniTerm:

### 🤝 Colaboración

* [Guía de Contribución](CONTRIBUTING.md)
* [Código de Conducta](CODE_OF_CONDUCT.md)

### 🏗 Arquitectura y Diseño

* [Visión General](docs/overview.md)
* [Arquitectura del Sistema](docs/arquitectura_documentacion.md)
* [Módulos del Sistema](docs/modules.md)
* [Diagrama de Flujo](docs/flow_diagram.md)

### 🧩 Componentes y Herramientas

* [Gestor de Historial](docs/history_manager_documentation.md)
* [Herramienta de Creación de Planes](docs/plan_creation_tool.md)
* [Archivos CLI de Gemini](docs/gemini_cli_files.md)

### 🧠 Sistema RAG (Indexado)

* [Propuesta de RAG](docs/rag_codebase_proposal.md)
* [Plan de Implementación](docs/rag_implementation_plan.md)
* [Estado de Implementación](docs/rag_implementation_status.md)

### 📝 Registros

* [Registro de Cambios](docs/Cambios.md)
* [Registro de Errores y Soluciones](docs/registro_errores_soluciones.md)
* [Log de Desarrollo](docs/development_log.md)

---
*Desarrollado por Gatovillano*

---

## 💙 Apoya el Proyecto

Si encuentras útil este proyecto, considera hacer una donación para apoyar su desarrollo continuo. Cada contribución ayuda a mantener el proyecto activo y a agregar nuevas características.

[![Donar con PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate?hosted_button_id=TU_ID_DE_BOTÓN)

O también puedes apoyar a través de:
- [GitHub Sponsors](https://github.com/sponsors/tu-usuario)
- [Patreon](https://www.patreon.com/tu-usuario)

¡Gracias por tu apoyo! 🙌
