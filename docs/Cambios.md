
---
## 17-09-2025 Mejora de la Inmediatez de Interrupciones
**Descripción general:** Se mejoró la capacidad de respuesta a las interrupciones con la tecla `Esc` al optimizar el monitoreo del `interrupt_queue` en el `LLMService`.

-   **Punto 1**: Se redujo el `time.sleep` en `LLMService._invoke_tool_with_interrupt` de `0.1` a `0.01` segundos para una detección más rápida de las señales de interrupción.
-   **Punto 2**: Se refactorizó el bucle de monitoreo en `LLMService._invoke_tool_with_interrupt` para utilizar `future.result(timeout=0.01)` y manejar `TimeoutError`, lo que permite una verificación más activa y una respuesta más inmediata a las interrupciones.
