# Reglas de Desarrollo para KogniTerm

## Pseudo-terminales y Entornos Sin Eco
Al modificar el motor de ejecución de comandos (`CommandExecutor`) o cualquier lógica relacionada con el procesamiento y parseo de entradas/salidas de terminal, se debe garantizar la compatibilidad con terminales donde `ECHO` está desactivado (ej. ejecución en segundo plano, daemons o modo servidor).

- **Filtrado de Eco**: No asumas que la terminal siempre repetirá (echo) el comando enviado. El filtro de eco debe diferenciar explícitamente entre la línea de eco del comando y el marcador de finalización limpio (`##KOGNITERM_DONE_MARKER##`).
- **Bloqueos**: Si se descarta erróneamente el marcador de finalización confundiéndolo con un eco de comando, la ejecución del comando se quedará bloqueada en espera de más salida. Siempre verifica de forma estricta que la línea a descartar no sea idéntica al marcador limpio.
