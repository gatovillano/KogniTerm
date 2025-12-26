# 🤖 KogniTerm

![KogniTerm Banner](image.png)

**KogniTerm** es un asistente de terminal agéntico avanzado que revoluciona la forma en que interactúas con tu sistema. No es solo un intérprete de comandos; es un ecosistema de **Agentes de IA Especializados** capaces de razonar, investigar, codificar y ejecutar tareas complejas directamente en tu entorno local.

Diseñado para ser **universalmente compatible**, KogniTerm funciona con una amplia gama de modelos de lenguaje (OpenAI, Anthropic, Google Gemini, DeepSeek, OpenRouter, etc.), gracias a su robusto sistema de parseo de herramientas.

## ✨ Características Principales

### 🧠 Arquitectura Multi-Agente

KogniTerm no es un solo bot, es un equipo de especialistas:

* **BashAgent (El Operador)**: Tu interfaz principal. Maneja la terminal, ejecuta comandos y orquesta la delegación de tareas.
* **ResearcherAgent (El Detective)**: Especialista en lectura y comprensión. Analiza tu base de código, busca en la web y genera explicaciones detalladas sin modificar tus archivos.
* **CodeAgent (El Desarrollador)**: Ingeniero de software experto. Se encarga de escribir, refactorizar y aplicar parches a tu código siguiendo principios de calidad y seguridad.

### 🌐 Compatibilidad Universal de LLMs

Olvídate de las restricciones de proveedores. KogniTerm implementa un **Sistema de Parseo Universal** que permite usar modelos que no tienen soporte nativo para "Tool Calling".

* Soporta **OpenAI, Anthropic, Google Gemini**.
* Compatible con **DeepSeek, Llama 3, Mistral** y modelos vía **OpenRouter**.
* Detecta y ejecuta comandos incluso si el modelo los "alucina" en texto plano.

### 🛠 Herramientas Potentes

* **Gestión de Archivos y Directorios**: Lectura recursiva, búsqueda inteligente y edición segura.
* **Indexado de Código (RAG)**: Indexa tu proyecto localmente para que la IA entienda todo el contexto de tu repositorio.
* **Búsqueda Web Integrada**: Para obtener información actualizada durante las sesiones.
* **Ejecución de Python**: Un entorno REPL persistente para cálculos y scripts complejos.

### 🛡 Seguridad y Control

* **Human-in-the-loop**: Por defecto, KogniTerm pide confirmación antes de ejecutar cualquier comando de shell o editar archivos.
* **Modo Auto-Aprobación (`-y`)**: Para flujos de trabajo rápidos y desatendidos.
* **Visualización de Diffs**: Revisa los cambios de código con resaltado de sintaxis antes de aplicarlos.

## 🚀 Instalación

```bash
# Instalar con pipx (recomendado para aislar dependencias)
pipx install kogniterm

# O con pip
pip install kogniterm
```

## ⚙️ Configuración y Gestión de Modelos (CLI)

KogniTerm incluye una potente CLI para gestionar tus modelos y claves de API sin tocar archivos de configuración manualmente.

### 🔑 Gestión de API Keys

Configura tus proveedores de IA favoritos de forma segura:

```bash
# Configurar OpenRouter (Recomendado para acceder a todos los modelos)
kogniterm keys set openrouter sk-or-v1-...

# Configurar Google Gemini
kogniterm keys set google AIzaSy...

# Configurar OpenAI
kogniterm keys set openai sk-...

# Configurar Anthropic
kogniterm keys set anthropic sk-ant-...

# Listar las llaves configuradas (se muestran enmascaradas)
kogniterm keys list
```

### 🧠 Gestión de Modelos

Define qué "cerebro" utilizará KogniTerm por defecto:

```bash
# Establecer un modelo por defecto (ejemplo con OpenRouter)
kogniterm models use openrouter/google/gemini-2.0-flash-exp:free

# Usar un modelo directo de Google
kogniterm models use gemini/gemini-1.5-pro

# Ver el modelo actual configurado
kogniterm models current
```

> **Nota:** La configuración se guarda globalmente en `~/.kogniterm/config.json`. KogniTerm priorizará las variables de entorno explícitas si las hubiera.

## 🎮 Uso Interactivo

Una vez configurado, inicia tu asistente:

```bash
kogniterm
```

### Comandos Mágicos y Menús Interactivos

Dentro de la aplicación, tienes control total con una experiencia de usuario mejorada:

* **`%models`**: Abre un **menú interactivo** para cambiar de modelo en caliente sin reiniciar.
* **`%help`**: Despliega un menú de ayuda navegable donde puedes ejecutar comandos directamente.
* **`%reset`**: Reinicia la conversación y limpia la memoria de corto plazo.
* **`%undo`**: Deshace la última interacción (útil si el modelo se equivocó).
* **`%compress`**: Resume el historial actual para ahorrar tokens y mantener el contexto relevante.
* **Autocompletado Inteligente**: Escribe `%` para ver y seleccionar todos los comandos disponibles.
* **Barra de Estado**: La barra inferior muestra siempre el modelo activo (ej: `🤖 OR/gemini-2.0-flash`) y el estado de indexación.

### Referencia de Archivos (@)

Puedes "inyectar" el contenido de cualquier archivo en tu prompt usando `@`:

```text
(kogniterm) › Analiza el código de @src/main.py y sugiere mejoras.
```

El sistema autocompletará las rutas de tus archivos mientras escribes después de `@`.

## 🧠 Indexado de Código (RAG)

Para que KogniTerm entienda tu proyecto completo:

```bash
# Indexar el directorio actual antes de iniciar
kogniterm index .
```

O simplemente inicia `kogniterm` y responde "Sí" cuando te pregunte si deseas indexar el directorio actual. Esto permite realizar preguntas complejas sobre la arquitectura de tu código.

---
*Desarrollado con ❤️ por el equipo de KogniTerm.*
