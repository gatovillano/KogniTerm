import datetime

with open('/home/gato/Proyectos/Gemini-Interpreter/docs/Cambios.md', 'a') as f:
    f.write('\n\n## ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n\n')
    f.write('### Solución a falla de inicio de TUI\n')
    f.write('- Se corrigió un error que impedía iniciar la TUI debido a argumentos faltantes en la instanciación de `KogniTermTUI` tras la refactorización cliente-servidor.\n')
    f.write('- Se cambiaron los argumentos `llm_service`, `command_executor` y `agent_state` en `tui_app.py` para que sean opcionales (por defecto `None`) y se añadieron comprobaciones de nulidad antes de usarlos.\n')
    f.write('- Se reemplazó el uso de la función obsoleta `asyncio.get_event_loop()` por `asyncio.get_running_loop()` en `push_screen_wait` de `tui_app.py` para evitar que los modales se congelen o fallen.\n')
