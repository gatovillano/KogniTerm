graph TD
    A[Mensaje de Usuario] --> B{Clase Interpreter};
    B --> C[Enviar a Gemini (chat())];
    C --> D{Respuesta de Gemini};
    D -- Bloque de Código Bash --> E[Extraer Comando];
    E --> F{Clase CommandExecutor};
    F --> G[Ejecutar Comando (execute())];
    G --> H[Salida del Comando];
    H --> I[Añadir Salida a Historial de Interpreter];
    I --> J[Presentar a Gemini como Contexto];
    D -- Sin Bloque de Código --> K[Mostrar Respuesta Directa al Usuario];