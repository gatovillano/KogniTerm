# 🤖 KogniTerm

![alt text](image.png)
Un asistente de terminal interactivo impulsado por IA que permite a los modelos de lenguaje (LLMs) ejecutar comandos de terminal y código Python en tu sistema, proporcionando una interfaz conversacional y asistida.

## ✨ Características

* **Interacción Conversacional:** Comunícate con el intérprete en lenguaje natural. 💬
* **Ejecución de Comandos y Código Python:** El LLM puede generar y ejecutar comandos de terminal y bloques de código Python en tu sistema. 💻🐍
* **Confirmación de Comandos y Código:** Siempre se te pedirá confirmación antes de ejecutar cualquier comando de terminal o bloque de código Python (a menos que uses el modo de auto‑aprobación). ✅
* **Manejo Interactivo:** Soporte para comandos y scripts Python que requieren interacción del usuario (ej. contraseñas, confirmaciones `[Y/n]`). 🤝
* **Cancelación de Comandos:** Cancela comandos en ejecución con `Ctrl+C` sin salir de la aplicación. 🛑
* **Comandos Mágicos:** `%help`, `%reset`, `%compress` y más. ✨
* **Modo de Auto‑Aprobación:** Ejecuta comandos y código automáticamente sin confirmación usando la bandera `-y`. 🚀
* **Interfaz Mejorada con Rich:** Salida de terminal formateada con Markdown y colores. 🎨
* **Agente Inteligente:** Un agente avanzado capaz de razonar y ejecutar tareas complejas en tu sistema. 🤖
* **Herramientas Integradas:** Búsqueda web, extracción de contenido, herramienta unificada de GitHub y un ejecutor Python con kernel Jupyter persistente. 🌐🐙
* **Visualización de Diffs:** Renderizado de diferencias de código con colores y resaltado de sintaxis. 📊
* **Creación de Planes:** Herramienta para generar y presentar planes de acción detallados antes de ejecutar tareas complejas. 📋
* **Prompt de Indexado al Inicio:** Pregunta al usuario si desea indexar el código al iniciar KogniTerm. 📂
* **Interrupción con ESC:** Permite detener la generación del agente usando la tecla Escape. ⏹️


## 🚀 Instalación

1. **Clonar el repositorio:**

    ```bash
    git clone <URL_DEL_REPOSITORIO_KOGNITOINTERPRETER>
    cd KogniTerm
    ```

2. **Instalar KogniTerm:**
    Puedes instalar KogniTerm directamente usando `pip`.
    * **Instalación estándar:**

        ```bash
        pip install .
        ```

    * **Instalación en modo editable (para desarrollo):**
        Si deseas que los cambios en el código fuente se reflejen sin reinstalar, usa:

        ```bash
        pip install -e .
        ```

    Esto instalará KogniTerm y sus dependencias, y el comando `kogniterm` estará disponible en tu entorno virtual.

3. **Configurar la API Key de Google Gemini:**
    Asegúrate de tener tu clave de API de Google Gemini configurada como una variable de entorno:

    ```bash
    export GOOGLE_API_KEY="TU_CLAVE_API_AQUI"
    ```

## 💻 Uso

Para iniciar KogniTerm:

```bash
kogniterm
```

Para iniciar en modo de auto-aprobación (ejecuta comandos y código sin pedir confirmación):

```bash
kogniterm -y
```
