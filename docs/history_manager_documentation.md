# 📝 Documentación del Módulo `HistoryManager` en KogniTerm

Este documento detalla el funcionamiento interno y la arquitectura de la clase `HistoryManager`, ubicada en `kogniterm/core/history_manager.py`, responsable de la gestión del historial de conversación en KogniTerm.

## 🎯 1. Propósito General

La clase `HistoryManager` está diseñada para gestionar de manera eficiente y robusta el historial de conversación entre el usuario y el asistente de IA. Su objetivo principal es:
*   Almacenar, cargar y guardar mensajes de conversación.
*   Mantener el historial dentro de límites configurables (número de mensajes y longitud en caracteres).
*   Optimizar el rendimiento mediante el uso de caché.
*   Garantizar la integridad de los mensajes y manejar posibles errores durante la serialización/deserialización.

## 🛠️ 2. Atributos Principales

| Atributo                      | Tipo                  | Descripción                                                                                                                                                                                                           |
| :---------------------------- | :-------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `history_file_path`           | `str`                 | Ruta absoluta o relativa al archivo JSON donde se persiste el historial de conversación.                                                                                                                              |
| `max_history_messages`        | `int`                 | Número máximo de mensajes que se deben mantener en el historial activo. Los mensajes más antiguos se truncan si se excede este límite.                                                                                 |
| `max_history_chars`           | `int`                 | Longitud máxima en caracteres (aproximadamente) del historial de conversación. Se utiliza junto con `max_history_messages` para truncar el historial.                                                                     |
| `conversation_history`        | `List[BaseMessage]`   | Lista de objetos `BaseMessage` (de Langchain) que representan el historial de conversación actual en memoria.                                                                                                         |
| `tokenizer`                   | `tiktoken.Encoding`   | Instancia del tokenizador `tiktoken` (modelo `gpt-4`) utilizado para calcular la longitud de los mensajes en tokens.                                                                                                   |
| `_message_length_cache`       | `Dict[int, int]`      | Caché para almacenar la longitud calculada de los mensajes (en caracteres JSON) utilizando un hash del mensaje como clave. Esto evita recálculos redundantes.                                                            |

### Constantes de Configuración

*   `MIN_MESSAGES_TO_KEEP`: Mínimo de mensajes a mantener incluso después de truncamiento (por defecto 5).
*   `MAX_SUMMARY_LENGTH_RATIO`: Proporción del `max_history_chars` dedicada al resumen (25%).
*   `DEFAULT_MAX_SUMMARY_LENGTH`: Longitud máxima por defecto para un resumen (2000 caracteres).
*   `SUMMARY_TRUNCATION_SUFFIX`: Sufijo añadido a los resúmenes truncados.
*   `MAX_TOOL_MESSAGE_CONTENT_LENGTH_ASSUMED`: Longitud máxima asumida para el contenido de un `ToolMessage`.

## ⚙️ 3. Métodos Clave

### 3.1. Métodos Privados (Auxiliares)

*   `_get_token_count(self, text: str) -> int`:
    *   Calcula el número de tokens para una cadena de texto dada usando el tokenizador `tiktoken`.
*   `_get_message_hash(self, message: BaseMessage) -> int`:
    *   Genera un hash único para un mensaje `BaseMessage` basándose en su contenido y `tool_calls` (si existen). Utilizado para la caché.
*   `_get_message_length(self, message: BaseMessage) -> int`:
    *   Calcula la longitud de un mensaje (en caracteres de su representación JSON) utilizando la caché. Si el mensaje no está en caché, lo serializa y almacena su longitud.
*   `_to_litellm_message_for_len_calc(self, message: BaseMessage) -> Dict[str, Any]`:
    *   Convierte un mensaje de Langchain (`BaseMessage`) a un formato compatible con LiteLLM para calcular su longitud. Esto es necesario porque `json.dumps` se aplica a este formato para obtener la longitud de serialización.
*   `_load_history(self) -> List[BaseMessage]`:
    *   **Propósito**: Carga el historial de conversación desde el archivo JSON especificado en `history_file_path`.
    *   **Funcionamiento**:
        *   Verifica si la ruta del archivo existe y si el archivo no está vacío.
        *   Lee y decodifica el JSON del archivo.
        *   Itera sobre los elementos serializados y los convierte de nuevo a objetos `BaseMessage` (HumanMessage, AIMessage, ToolMessage, SystemMessage) de Langchain.
        *   Maneja la deserialización de `tool_calls` dentro de `AIMessage`, incluyendo la lógica para parsear argumentos que podrían estar como cadenas JSON.
        *   Incluye manejo de errores para `json.JSONDecodeError` y otras excepciones.
    *   **Retorna**: Una lista de objetos `BaseMessage` o una lista vacía si hay errores o el archivo está vacío/no existe.
*   `_save_history(self, history: List[BaseMessage])`:
    *   **Propósito**: Persiste el historial de conversación actual en el archivo JSON.
    *   **Funcionamiento**:
        *   Crea el directorio si no existe.
        *   Convierte la lista de objetos `BaseMessage` a una lista de diccionarios serializables, manejando la estructura específica de `AIMessage` con `tool_calls`.
        *   Escribe la representación JSON formateada (con indentación) en el archivo.
        *   Actualiza `self.conversation_history` in-place si la lista proporcionada es diferente para mantener las referencias.
*   `_filter_empty_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]`:
    *   Filtra mensajes de asistente que están vacíos y no tienen `tool_calls`. Utilizado durante el truncamiento o resumen.
*   `_truncate_history_by_length(self, history: List[BaseMessage], max_length: int) -> List[BaseMessage]`:
    *   Trunca el historial desde el principio (mensajes más antiguos) para asegurar que la longitud total (en caracteres JSON) no exceda `max_length`. Siempre intenta mantener `MIN_MESSAGES_TO_KEEP`.
*   `_summarize_and_truncate_history(self, history: List[BaseMessage]) -> List[BaseMessage]`:
    *   **Propósito**: Genera un resumen del historial más antiguo y lo concatena con los mensajes más recientes para mantener el historial dentro de los límites.
    *   **Funcionamiento**:
        *   Identifica los mensajes que deben ser resumidos y los mensajes más recientes que deben conservarse.
        *   Utiliza un LLM (a través de `llm_service.get_llm_model().invoke`) para generar un resumen de los mensajes antiguos.
        *   Si el resumen excede la longitud máxima permitida, lo trunca y añade un sufijo.
        *   Reemplaza los mensajes antiguos con el `SystemMessage` de resumen.
        *   Este método es clave para mantener un contexto relevante sin exceder los límites del modelo.
*   `_to_litellm_message(self, message: BaseMessage) -> Dict[str, Any]`:
    *   Convierte un mensaje de Langchain a un formato compatible con LiteLLM, que es utilizado internamente para la comunicación con el modelo de lenguaje.
*   `_get_current_history_length(self) -> int`:
    *   Calcula la longitud total del historial actual en caracteres JSON, utilizando la caché de longitud de mensajes.
*   `_validate_and_get_history(self, current_history: List[BaseMessage], messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]`:
    *   Valida el historial para asegurar la integridad de los pares `AIMessage` y `ToolMessage`.
    *   Si un `ToolMessage` no tiene un `tool_call_id` que corresponda a un `AIMessage` previo con `tool_calls`, lo marca como inválido y lo ignora.
*   `_remove_invalid_tool_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]`:
    *   Elimina `ToolMessage` inválidos (aquellos sin un `tool_call_id` correspondiente a un `AIMessage` previo).
*   `_handle_history_truncation(self, current_history: List[BaseMessage]) -> List[BaseMessage]`:
    *   Aplica la lógica de truncamiento y resumen al historial, combinando `_truncate_history_by_length` y `_summarize_and_truncate_history` para mantener el historial dentro de `max_history_messages` y `max_history_chars`.

### 3.2. Métodos Públicos

*   `add_message(self, message: BaseMessage)`:
    *   **Propósito**: Agrega un nuevo mensaje (`BaseMessage`) al historial de conversación en memoria y luego persiste el historial actualizado en el archivo JSON.
*   `get_history(self) -> List[BaseMessage]`:
    *   **Propósito**: Retorna la lista actual de mensajes del historial de conversación en memoria.
*   `clear_history(self)`:
    *   **Propósito**: Limpia completamente el historial de conversación en memoria y también borra el historial persistido en el archivo JSON. También vacía la caché de longitud de mensajes.
*   `get_formatted_history(self, prompt_messages: Optional[List[BaseMessage]] = None) -> List[Dict[str, Any]]`:
    *   **Propósito**: Prepara y formatea el historial de conversación para ser enviado a un modelo de lenguaje.
    *   **Funcionamiento**:
        *   Combina el historial interno con `prompt_messages` opcionales.
        *   Aplica truncamiento y resumen para asegurar que el historial se ajuste a los límites configurados (`max_history_messages`, `max_history_chars`).
        *   Valida la integridad de los `ToolMessage` y los elimina si son inválidos.
        *   Convierte los mensajes de Langchain a un formato compatible con LiteLLM/OpenAI (`Dict[str, Any]`).
        *   Asegura que el historial final no exceda los límites de tokens del modelo.

## 🔄 4. Flujo de Trabajo del Historial

1.  **Inicialización**: Al crear una instancia de `HistoryManager`, se intenta cargar el historial desde `history_file_path`. Si el archivo no existe o está vacío/corrupto, se inicializa un historial vacío.
2.  **Añadir Mensajes**: Cuando se llama a `add_message()`, el nuevo `BaseMessage` se añade a `conversation_history` y el historial completo se guarda inmediatamente en el archivo.
3.  **Obtener Historial Formateado**: Antes de interactuar con un LLM, `get_formatted_history()` se encarga de:
    *   Unir el historial en memoria con cualquier mensaje de `prompt_messages` que el usuario desee añadir para la invocación actual.
    *   Aplicar la lógica de truncamiento y resumen para asegurar que el historial final no exceda los límites de tamaño y cantidad de mensajes.
    *   Validar y limpiar los `ToolMessage` para evitar inconsistencias.
    *   Convertir los mensajes al formato `LiteLLM` (`Dict[str, Any]`) esperado por el modelo de lenguaje.
4.  **Persistencia**: El historial se guarda en formato JSON en el disco (`.json`) para mantener la continuidad de la conversación entre sesiones.

## ⚡ 5. Optimización y Robustez

*   **Caché de Longitud**: El uso de `_message_length_cache` evita recálculos costosos de la longitud de los mensajes, mejorando el rendimiento al truncar y resumir.
*   **Manejo de Errores**: Se implementan bloques `try-except` para gestionar errores durante la carga y guardado del historial (ej. `json.JSONDecodeError`), lo que hace que el sistema sea más resistente a archivos de historial corruptos.
*   **Validación de `ToolMessage`**: La lógica para validar `ToolMessage` asegura que solo los mensajes de herramientas válidamente vinculados a un `AIMessage` previo con `tool_calls` sean incluidos en el historial final, previniendo errores en el LLM.
*   **Truncamiento Inteligente**: La combinación de truncamiento por número de mensajes y por longitud en caracteres, junto con la capacidad de resumir mensajes antiguos, permite mantener un historial relevante y conciso sin sobrecargar el modelo de lenguaje.
*   **Persistencia en JSON**: El formato JSON es legible y fácil de depurar, además de ser un estándar para la serialización de datos.
*   **Uso de `tiktoken`**: Para un cálculo preciso de tokens, lo cual es crucial para interactuar con modelos de lenguaje que tienen límites de contexto basados en tokens.
