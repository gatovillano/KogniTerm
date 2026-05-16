# Sistema de Versionado de Autoguardos

## Problema Original
El autoguardado se reemplazaba constantemente en un único archivo `history.json`, lo que impedía recuperar versiones anteriores de la sesión cuando se abría una nueva.

## Solución Implementada

### Componentes

#### 1. `AutosaveManager` (`kogniterm/core/autosave_manager.py`)
Gestor de autoguardados versionados con soporte multi-sesión.

**Características:**
- **Versionado automático**: Cada autoguardado se guarda con timestamp (precisión de milisegundos)
- **Identificador único de sesión (UUID)**: Cada sesión tiene su propio identificador
- **Thread-safe**: Gestión segura de múltiples versiones con locks
- **Rotación automática**: Limpia versiones antiguas según políticas
- **Thread de limpieza**: Ejecuta cada 5 minutos para mantener límites

**Estructura de directorios:**
```
.kogniterm/
├── autosave/
│   ├── session_<UUID>/
│   │   ├── autosave_20250515_141530_123.json
│   │   ├── autosave_20250515_141545_456.json
│   │   └── ... (máximo 10 por sesión)
│   ├── session_<UUID>/
│   │   └── ...
```

**Políticas de retención:**
- **MAX_VERSIONS_PER_SESSION = 10**: Máximo 10 versiones por sesión
- **MAX_TOTAL_AUTOSAVES = 50**: Máximo 50 autoguardos totales
- **VERSION_RETENTION_DAYS = 7**: Mantener autoguardos por 7 días

#### 2. Integración en `HistoryManager`
El `HistoryManager` ahora integra el `AutosaveManager`:

```python
# Guardar automáticamente en ambos sistemas
def _handle_history_mutation(self, history):
    self._save_history(history)  # Guarda en history.json (backwards compatibility)
    
    if self.autosave_manager:
        self.autosave_manager.save_version(
            messages=history,
            description="Mutación automática del historial"
        )
```

**Métodos de acceso:**
```python
# Obtener versiones de la sesión actual
get_autosave_versions() -> List[Dict]

# Obtener TODAS las versiones de todas las sesiones
get_all_autosave_versions() -> List[Dict]

# Cargar una versión específica
load_autosave_version(file_path: str) -> Optional[List[BaseMessage]]

# Estadísticas del sistema
get_autosave_statistics() -> Dict
```

#### 3. Interfaz CLI: Comando `/autosave`

**Uso:**
```
/autosave list                           # Listar todas las versiones
/autosave restore                        # Selector interactivo de versiones
/autosave restore autosave_20250515...  # Restaurar versión específica
```

**Ejemplo de salida:**
```
📦 Autosave Versions (Current Session)

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳─────────────────────┓
┃ File                  ┃ Msgs ┃ Modified            ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇─────────────────────┩
│ autosave_20250515_... │  24  │ 2025-05-15 14:15:30 │
│ autosave_20250515_... │  20  │ 2025-05-15 14:14:15 │
└───────────────────────┴──────┴─────────────────────┘

📊 Statistics: 5 versions in current session, 12 total versions across 3 session(s).
```

## Cómo Funciona

### Flujo de Guardado
1. **Mutación del historial**: Cuando se agrega/modifica un mensaje
2. **_handle_history_mutation()** se dispara:
   - Guarda en `history.json` (compatibilidad backwards)
   - Guarda versión en `AutosaveManager` con timestamp
3. **Thread de limpieza**: Cada 5 minutos verifica y rota versiones antiguas

### Flujo de Recuperación
1. **Usuario ejecuta**: `/autosave list`
2. **Se muestran**: Todas las versiones (sesión actual + anteriores)
3. **Usuario selecciona**: Una versión específica
4. **Se carga**: El historial completo de esa versión
5. **Se restaura**: La sesión con ese historial

### Thread-Safety
- **Lock RLock**: Protege acceso a `self._session_versions`
- **Lock RLock en HistoryManager**: Protege `_save_lock` para escrituras
- **Thread de limpieza**: Ejecuta de forma segura con locks

## Ventajas

✅ **No perder versiones anteriores**: Cada cambio se guarda automáticamente
✅ **Recuperación fácil**: Comando simple `/autosave restore`
✅ **Multi-sesión**: Puedes acceder a autoguardos de sesiones anteriores
✅ **Thread-safe**: Sin condiciones de carrera
✅ **Limpieza automática**: Mantiene límites de almacenamiento
✅ **Backwards compatible**: El sistema `history.json` sigue funcionando
✅ **Sin bloqueos**: Las operaciones de guardado son asíncronas

## Configuración

**Variables de entorno:**
```bash
# Habilitar/deshabilitar autoguardado versionado
export KOGNITERM_AUTO_SAVE_INTERVAL=30  # Guardar cada 30 segundos
```

**En code:**
```python
# Acceso a estadísticas
stats = llm_service.get_autosave_statistics()
print(f"Total versions: {stats['total_versions']}")
print(f"Sessions: {stats['sessions_count']}")
```

## Casos de Uso

### Caso 1: Recuperar conversación anterior
```bash
# El user crea nueva sesión, pero quiere volver a la anterior
/autosave list              # Ver versiones disponibles
/autosave restore           # Selector interactivo
# ¡La sesión anterior está restaurada!
```

### Caso 2: Comparar versiones
```bash
# Ver cómo evolucionó una conversación
/autosave list              # Listar todos los puntos de guardado
# Cada versión muestra el timestamp y número de mensajes
```

### Caso 3: Backup automático
```bash
# El sistema guarda automáticamente cada cambio
# No necesita hacer nada - está guardado en .kogniterm/autosave/
```

## Limitaciones y Notas

⚠️ **Espacio en disco**: Por defecto se mantienen 50 autoguardos totales (rotación automática)
⚠️ **Timestamp precisión**: Milisegundos (pueden existir dos versiones en la misma sesión)
⚠️ **Sesiones antiguas**: Se limpian después de 7 días automáticamente
⚠️ **Backwards compatibility**: Se mantiene `history.json` para compatibilidad

## Futuros Mejoras

- [ ] UI visual para comparar versiones
- [ ] Exportar versiones a CSV/JSON
- [ ] Búsqueda en versiones históricas
- [ ] Compresión de versiones antiguas
- [ ] Sincronización en la nube
- [ ] Tags/comentarios en versiones
