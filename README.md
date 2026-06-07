# 🤖 KogniTerm

![KogniTerm Banner](image.png)
<video controls src="kogniterm/kogniterm.mp4" title="KogniTerm Demo"></video>

**KogniTerm** es un agente evolutivo de terminal de última generación. Transforma tu línea de comandos en un entorno de desarrollo colaborativo donde **Agentes de IA Especializados** trabajan contigo para razonar, investigar, codificar y ejecutar tareas complejas.

A diferencia de otros asistentes, KogniTerm no depende de las capacidades nativas de "Tool Calling" de los modelos. Gracias a su **Motor de Parseo Universal**, es capaz de otorgar capacidades agénticas a prácticamente cualquier LLM (DeepSeek, Llama 3, Mistral, etc.), interpretando sus intenciones directamente desde el lenguaje natural.

## 🚀 Instalación Rápida

El método oficial y recomendado para instalar **KogniTerm** de forma global y mantenerlo actualizado con facilidad es usar su script de instalación interactivo:

```bash
curl -fsSL https://raw.githubusercontent.com/gatovillano/KogniTerm/main/install.sh | bash
```

Este script automatizado:
1. Descargará los últimos cambios oficiales de GitHub.
2. Configurarará un entorno virtual de Python aislado en `~/.kogniterm/venv`.
3. Creará un script de lanzamiento global en `~/.local/bin/kogniterm`.
4. Te guiará de manera interactiva para configurar tu proveedor de LLM y el bot de Telegram.

> [!NOTE]
> Asegúrate de tener `~/.local/bin` en tu variable de entorno `$PATH`. De lo contrario, puedes ejecutarlo activando el entorno con: `source ~/.kogniterm/venv/bin/activate && kogniterm`.

### Alternativa: Instalación tradicional desde PyPI

Si prefieres no usar el instalador de GitHub, puedes descargarlo de PyPI:

```bash
# Opción aislada (recomendada)
pipx install kogniterm

# Opción estándar
pip install kogniterm
```

Una vez instalado, inicia la terminal ejecutando:
```bash
kogniterm
```


---

## 🏗 Arquitectura y Evolución

KogniTerm ha evolucionado de un monolito local a un ecosistema modular.

### 🔄 Migración a Cliente-Servidor (En Progreso)
Estamos migrando la arquitectura hacia un modelo desacoplado para habilitar la **Ubicuidad Agéntica**. 

**¿Qué significa esto?**
Tradicionalmente, la TUI alojaba toda la lógica. Ahora, estamos moviendo el cerebro (LangGraph, LLMService y el Ejecutor) a un **Servidor Centralizado (FastAPI)**.

**Beneficios de este cambio:**
- **Multi-Canal**: El mismo agente puede ser controlado desde la **TUI (Textual)** en tu PC y desde un **Bot de Telegram** en tu móvil simultáneamente.
- **Persistencia Total**: Si cierras la terminal, la sesión sigue viva en el servidor. Puedes reconectarte y retomar la tarea exactamente donde quedó.
- **Resiliencia**: Separación total entre la interfaz visual y la ejecución de procesos críticos en el host.

### 🧠 Núcleo Multi-Agente
El sistema orquesta un equipo de especialistas:
- **🤖 BashAgent**: Orquestador principal y punto de interacción.
- **🕵️ ResearcherAgent**: Especialista en análisis, lectura y reportes (SÓLO LECTURA).
- **👨‍💻 CodeAgent**: Ingeniero de software enfocado en ediciones precisas y seguras.

### ⚙️ Motor de Parseo Universal
El corazón de KogniTerm es su capacidad de convertir texto plano en acciones. Ya sea que el modelo use Tool Calling nativo o genere JSON/XML dentro de un párrafo, el motor lo normaliza para ejecutar la herramienta correcta.

---

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
- **Límites de ejecución**: Timeout y restricciones de recursos en comandos

## ⚙️ Configuración y Gestión (CLI)

KogniTerm incluye una CLI dedicada para gestionar tus llaves y modelos.

### 🔑 Gestión de API Keys
```bash
kogniterm keys set openrouter sk-or-v1-...
kogniterm keys set google AIzaSy...
kogniterm keys list
```

### 🤖 Configuración de bot de Telegram
```bash
kogniterm config telegram       # Asistente interactivo
kogniterm config telegram status # Ver estado
kogniterm config telegram enable # Activar bot
```

### 🧠 Selección de Modelos
```bash
kogniterm models use google/gemini-2.0-flash-exp
kogniterm models current
```

## 🎮 Experiencia Interactiva

### Comandos Mágicos (`%`)
- **`%models`**: Cambia el modelo en caliente.
- **`%reset`**: Limpia el contexto y comienza de cero.
- **`%undo`**: Deshace la última acción del agente.
- **`%compress`**: Resume el historial para ahorrar tokens.

### Referencias Inteligentes (`@`)
Inyecta contexto de archivos directamente: `¿Qué hace la función process en @core/logic.py?`

## 🧠 Indexado de Código (RAG)
Para preguntas sobre la arquitectura global de tu proyecto:
```bash
kogniterm index .
```
Utiliza embeddings vectoriales y chunking inteligente para que los agentes "conozcan" todo tu repositorio sin leer cada archivo manualmente.

---

## 🗂 Estructura del Proyecto

```
kogniterm/
├── terminal/           # Interfaz TUI y CLI
├── core/               # Cerebro: Agentes, Estado y Motor LLM
├── server/             # Backend FastAPI (Nueva Arquitectura)
├── skills/             # Framework de habilidades modulares
├── rag/                # Indexador semántico
└── docs/               # Documentación técnica extensa
```

## 📚 Documentación Técnica
Consulta la carpeta `docs/` para detalles sobre:
- `overview.md`: Visión general y filosofía.
- `plan_migracion_cliente_servidor.md`: Detalles técnicos de la nueva arquitectura.
- `SKILL.md`: Cómo crear y extender habilidades.

---
*Desarrollado por Gatovillano*
---

## 💙 Apoya el Proyecto
Si encuentras útil este proyecto, considera hacer una donación para apoyar su desarrollo continuo. 

[![Donar con PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate?hosted_button_id=TU_ID_DE_BOTÓN)
