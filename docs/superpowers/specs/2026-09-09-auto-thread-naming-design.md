# Diseño: Auto-nombrado de hilos al iniciar el chat

## Resumen
Actualmente, los hilos en KogniTerm se inicializan con el título genérico `"Nueva conversación"`. Aunque existe código preliminar para generar títulos con LLM, un error lógico causa que un fallback preliminar marque el hilo como "no genérico", abortando la invocación del LLM. Además, la generación requería obligatoriamente tanto el mensaje del usuario como la respuesta del asistente, impidiendo que el hilo tuviera un título inteligente apenas comienza la conversación.

Este diseño define un mecanismo híbrido y robusto de dos fases:
1. **Fase Inmediata (0ms)**: Asignación y persistencia instantánea de un título preliminar heurístico limpio a partir del primer mensaje del usuario y notificación a los clientes conectados.
2. **Fase Asíncrona (Segundo Plano)**: Invocación no bloqueante al LLM en paralelo para resumir el tema en un título conciso (3-6 palabras), actualizando el hilo y notificando a la interfaz cuando esté listo (siempre que el usuario no lo haya renombrado manualmente).

---

## 1. Cambios en el Modelo de Datos y Metadatos

### `kogniterm/core/chat_thread.py`
- En la clase `ChatThread`:
  - `title_source`: cambiar el valor predeterminado a `"default"` (antes `"manual"`).
  - Valores posibles de `title_source`:
    - `"default"`: Hilo recién creado con título por defecto ("Nueva conversación").
    - `"fallback"`: Hilo titulado heurísticamente mediante el primer mensaje del usuario.
    - `"llm"`: Hilo cuyo título fue generado por un modelo de lenguaje.
    - `"manual"`: Hilo cuyo título fue editado o asignado explícitamente por el usuario (intocable por la automatización).

---

## 2. Cambios en la Lógica de Gestión de Hilos

### `kogniterm/core/thread_manager.py`
- **Mejora de `_fallback_title(text: str) -> str`**:
  - Limpiar bloques de código, markdown, saltos de línea y enlaces URL.
  - Omitir saludos comunes y muletillas iniciales en español e inglés (ej. *"hola"*, *"buenas"*, *"por favor"*, *"puedes"*, *"podrías"*, *"ayúdame a"*, *"hello"*, *"please"*, etc.).
  - Tomar las primeras 5 a 7 palabras significativas (o hasta 50 caracteres).
  - Capitalizar apropiadamente la primera letra y asegurar que no termine en caracteres especiales sueltos.
  - Si el texto resultante está vacío o es inválido, devolver `"Nueva conversación"`.
- **Refactor de `generate_title_if_needed(...)`**:
  - Condición de elegibilidad: se permite generar si `title_source in ("default", "fallback")` o si el título actual coincide con un título genérico o el `thread_id`.
  - Si `title_source in ("manual", "llm")`, no se sobrescribe.
  - Requisito de mensajes: Solo requiere **al menos un mensaje del usuario** (`HumanMessage` o con texto válido). No bloquea esperando a que el asistente responda. Si ya existe respuesta del asistente, se añade al contexto del prompt para enriquecer la síntesis.
- **Refactor de `_generate_title(...)`**:
  - Prompt conciso para el LLM:
    - *"Genera un título muy conciso (máximo 4 a 6 palabras) para una conversación que comienza con este mensaje. Responde únicamente con el título, sin comillas, sin punto final y sin introducciones."*
  - Extraer y sanitizar la respuesta del LLM.
  - Guardar el nuevo título con `title_source="llm"` mediante `rename_thread(thread_id, title, source="llm")`.

---

## 3. Integración en el Servidor (Web & Desktop)

### `kogniterm/server/session_pool.py`
- En el método `AgentSession.send()`:
  - Cuando se procesa un mensaje que no es un meta-comando:
    - Verificar si el hilo actual tiene `title_source in ("default", "fallback")` o título genérico.
    - Si califica:
      1. Asignar de inmediato `_fallback_title(message)` con `source="fallback"`.
      2. Emitir evento `thread_title_updated` a través de la UI para que la barra lateral de hilos (Desktop/Web) refleje el tema instantáneamente.
      3. Lanzar `asyncio.create_task(self._try_generate_title())` inmediatamente en segundo plano, sin esperar a que `_run_agent_loop` concluya.
  - Al completar `_try_generate_title()`:
    - Si el LLM retorna un título válido, se emite nuevamente `thread_title_updated` y el cliente actualiza el título al nombre definitivo refinado.

---

## 4. Integración en la Terminal (TUI)

### `kogniterm/terminal/tui/tui_app.py` & `kogniterm/core/history_manager.py`
- En `kogniterm/terminal/tui/tui_app.py`:
  - Asegurar que `self.history_manager.set_llm_service(self.llm_service)` sea invocado cuando se inicializa la TUI.
  - Al recibir el primer mensaje en `process_agent_request` / `_handle_input_async`, aplicar el fallback inmediato al hilo activo si está en estado `"default"`.
  - Notificar el cambio de título en la interfaz de la TUI si el footer o encabezado muestra el nombre del hilo.

---

## 5. Manejo de Errores y Concurrencia
- **Manejo de Excepciones**: Las llamadas al LLM para títulos se ejecutan en un bloque `try...except` que registra errores en nivel de debug/advertencia sin interrumpir el flujo principal del chat. Si el LLM falla, el título de fallback queda intacto.
- **Concurrencia**: Las escrituras de metadatos siguen utilizando los bloqueos existentes (`_lock: threading.RLock`) y persistencia atómica (`.tmp` -> `os.replace`).
- **Respeto a la intención del usuario**: Si el usuario renombra manualmente el hilo en cualquier momento, `title_source` cambia a `"manual"` y cualquier tarea de generación pendiente que retorne posteriormente ignorará la actualización.

---

## 6. Plan de Pruebas

1. **`tests/unit/test_thread_manager.py`**:
   - Test unitario de `_fallback_title` con variedad de entradas: saludos, comandos, código, puntuación, mensajes vacíos.
   - Test de elegibilidad para generación de título (`generate_title_if_needed`) cuando `source="fallback"` vs cuando `source="manual"`.
   - Test de generación con solo `HumanMessage` (sin requerir `AIMessage`).
   - Test de actualización exitosa del hilo y emisión de metadatos con `title_source="llm"`.
2. **Ejecución de regresión**:
   - Correr toda la suite de tests unitarios existentes para verificar que no se rompan funcionalidades existentes.
