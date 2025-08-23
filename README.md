# 🤖 KognitoInterpreter

Un intérprete de línea de comandos interactivo que permite a los modelos de lenguaje (LLMs) ejecutar comandos en tu sistema, proporcionando una interfaz conversacional y asistida.

> **Inspiración:** Este proyecto está inspirado en [Open Interpreter](https://github.com/OpenInterpreter/open-interpreter). Nace de la necesidad de una integración más robusta y funcional con modelos de Google Gemini, ya que la compatibilidad directa de Open Interpreter con Gemini no siempre es óptima.

## ✨ Características

*   **Interacción Conversacional:** Comunícate con el intérprete en lenguaje natural.
*   **Ejecución de Comandos:** El LLM puede generar y ejecutar comandos de terminal en tu sistema.
*   **Confirmación de Comandos:** Siempre se te pedirá confirmación antes de ejecutar cualquier comando (a menos que uses el modo de auto-aprobación).
*   **Manejo Interactivo:** Soporte para comandos que requieren interacción del usuario (ej. contraseñas, confirmaciones `[Y/n]`).
*   **Cancelación de Comandos:** Cancela comandos en ejecución con `Ctrl+C` sin salir de la aplicación.
*   **Comandos Mágicos:**
    *   `%help`: Muestra los comandos disponibles.
    *   `%reset`: Reinicia la conversación.
    *   `%undo`: Deshace el último mensaje y la respuesta del LLM.
*   **Modo de Auto-Aprobación:** Inicia el intérprete con la bandera `-y` para ejecutar comandos automáticamente sin confirmación.
*   **Interfaz de Usuario Mejorada:** Salida de terminal formateada con Markdown y colores gracias a la librería `rich`.

## 🚀 Instalación

1.  **Clonar el repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO_KOGNITOINTERPRETER>
    cd KognitoInterpreter
    ```
2.  **Crear y activar el entorno virtual:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Instalar dependencias:**
    ```bash
    pip install -r kogniterm/requirements.txt
    ```

4.  **Configurar la API Key de Google Gemini:**
    Asegúrate de tener tu clave de API de Google Gemini configurada como una variable de entorno:
    ```bash
    export GOOGLE_API_KEY="TU_CLAVE_API_AQUI"
    ```

## 💻 Uso

Para iniciar el intérprete:

```bash
python3 main.py
```

Para iniciar en modo de auto-aprobación (ejecuta comandos sin pedir confirmación):

```bash
python3 main.py -y
```

## 🗺️ Próximos Pasos (Roadmap)

Estamos trabajando en una arquitectura de agente orquestador basada en LangGraph para permitir una planificación de tareas más compleja y la integración de múltiples herramientas (búsqueda web, operaciones de archivos, etc.).

---