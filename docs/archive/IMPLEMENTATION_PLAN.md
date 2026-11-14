# Plan de Implementación: Workspaces y Memoria en KogniTerm Desktop

## Visión General

Implementar un sistema de workspaces y memoria contextual para KogniTerm Desktop, permitiendo:
- Crear y gestionar workspaces con carpetas separadas
- Mantener memoria contextual por workspace
- Sincronizar historial de chat por workspace
- Permitir switching entre workspaces dentro de la misma ventana

---

## 1. Mapeo de Componentes Existentes

### 1.1 `LLMService` (`kogniterm/core/llm_service.py`)
**Responsabilidad actual**: Gestiona el modelo LLM, proveedores, y contexto.
**Métodos existentes**: `update_workspace()` (líneas 353-391), `get_context()`, `get_memory()`
**Modificación necesaria**:
- `update_workspace()` → aceptar nombre de workspace y actualizar `history_file_path`
- Método auxiliar: `_get_workspace_context()` → cargar contexto específico del workspace
- Método auxiliar: `_get_workspace_config()` → cargar configuración del workspace

### 1.2 `HistoryManager` (`kogniterm/core/history_manager.py`)
**Responsabilidad actual**: Gestiona historial de conversación con optimizaciones de rendimiento.
**Métodos existentes**: `_save_history()`, `_load_history()`, `_truncate_history()`, `_summarize_and_compress()`
**Modificación necesaria**:
- Aceptar `workspace_id` como parámetro en `_save_history()` y `_load_history()`
- Método auxiliar: `_get_workspace_history_path(workspace_id)` → generar ruta por workspace
- Método auxiliar: `_get_workspace_config_path(workspace_id)` → generar ruta de config por workspace

### 1.3 `WorkspaceContext` (`kogniterm/core/context/workspace_context.py`)
**Responsabilidad actual**: Gestiona el contexto del proyecto actual.
**Métodos existentes**: `initialize_context()`, `build_context_message()`, `_get_folder_structure()`, `_get_file_contents()`
**Modificación necesaria**:
- Aceptar `workspace_id` como parámetro
- Método auxiliar: `_get_workspace_memory_path(workspace_id)` → generar ruta de memoria por workspace
- Método auxiliar: `_get_workspace_config_path(workspace_id)` → generar ruta de config por workspace

### 1.4 `AgentState` (`kogniterm/core/agent_state.py`)
**Responsabilidad actual**: Define la estructura del estado que fluye a través del grafo.
**Métodos existentes**: `attach_history_manager()`, `add_pending_confirmation()`
**Modificación necesaria**:
- Añadir campo `workspace_id: Optional[str] = None`
- Método auxiliar: `update_workspace(workspace_id: str)` → actualizar workspace_id y reconfigurar

---

## 2. Módulos Nuevos a Crear

### 2.1 `kogniterm/core/workspace_manager.py`
**Propósito**: Gestor central de workspaces para el sistema.

**Contenido**:
```python
# workspace_manager.py
class WorkspaceManager:
    """Gestor de workspaces para KogniTerm Desktop."""
    
    def __init__(self, config_manager, workspace_dir: str = ".kogniterm/workspaces"):
        self.config_manager = config_manager
        self.workspace_dir = workspace_dir
        self.workspaces: Dict[str, dict] = {}
        self.current_workspace: Optional[str] = None
    
    def create_workspace(self, name: str, description: str = "") -> dict:
        """Crea un nuevo workspace con su carpeta y configuración."""
        pass
    
    def list_workspaces(self) -> list:
        """Lista todos los workspaces disponibles."""
        pass
    
    def switch_workspace(self, workspace_id: str) -> dict:
        """Cambia el workspace actual y actualiza el contexto."""
        pass
    
    def get_workspace_info(self, workspace_id: str) -> dict:
        """Obtiene información detallada de un workspace."""
        pass
    
    def delete_workspace(self, workspace_id: str) -> bool:
        """Elimina un workspace y su carpeta."""
        pass
    
    def get_workspace_memory_path(self, workspace_id: str) -> str:
        """Obtiene la ruta del archivo de memoria para un workspace."""
        pass
    
    def get_workspace_history_path(self, workspace_id: str) -> str:
        """Obtiene la ruta del historial para un workspace."""
        pass
    
    def get_workspace_config_path(self, workspace_id: str) -> str:
        """Obtiene la ruta de configuración para un workspace."""
        pass
    
    def _validate_workspace_name(self, name: str) -> bool:
        """Valida el nombre del workspace."""
        pass
```

### 2.2 `kogniterm/core/memory_manager.py`
**Propósito**: Gestor de memoria contextual por workspace.

**Contenido**:
```python
# memory_manager.py
class MemoryManager:
    """Gestor de memoria contextual por workspace."""
    
    def __init__(self, workspace_manager: WorkspaceManager, config_manager):
        self.workspace_manager = workspace_manager
        self.config_manager = config_manager
    
    def store_memory(self, workspace_id: str, memory_data: dict) -> bool:
        """Almacena memoria contextual para un workspace."""
        pass
    
    def get_memory(self, workspace_id: str) -> Optional[dict]:
        """Obtiene memoria contextual para un workspace."""
        pass
    
    def load_memory(self, workspace_id: str) -> Optional[dict]:
        """Carga memoria desde archivo JSON."""
        pass
    
    def save_memory(self, workspace_id: str, memory_data: dict) -> bool:
        """Guarda memoria en archivo JSON."""
        pass
    
    def delete_memory(self, workspace_id: str) -> bool:
        """Elimina memoria de un workspace."""
        pass
    
    def list_all_memories(self) -> list:
        """Lista todas las memorias disponibles."""
        pass
```

### 2.3 `kogniterm/terminal/workspace_manager.py`
**Propósito**: Gestor de workspaces para el terminal (módulo existente, necesita actualización).

**Contenido**:
```python
# workspace_manager.py (terminal)
class TerminalWorkspaceManager:
    """Gestor de workspaces para el terminal."""
    
    def __init__(self, workspace_manager: WorkspaceManager, history_manager: HistoryManager):
        self.workspace_manager = workspace_manager
        self.history_manager = history_manager
    
    def list_workspaces(self) -> list:
        """Lista workspaces disponibles."""
        pass
    
    def switch_workspace(self, workspace_id: str) -> dict:
        """Cambia el workspace actual."""
        pass
    
    def get_workspace_memory(self, workspace_id: str) -> dict:
        """Obtiene memoria del workspace."""
        pass
    
    def save_workspace_memory(self, workspace_id: str, memory_data: dict) -> bool:
        """Guarda memoria del workspace."""
        pass
```

### 2.4 `kogniterm/core/workspace_service.py`
**Propósito**: Servicio de workspace para la aplicación web (React/TypeScript).

**Contenido**:
```python
# workspace_service.py
class WorkspaceService:
    """Servicio de workspace para la aplicación web."""
    
    def __init__(self, backend_url: str, workspace_manager: WorkspaceManager):
        self.backend_url = backend_url
        self.workspace_manager = workspace_manager
    
    async def create_workspace(self, name: str, description: str) -> dict:
        """Crea un nuevo workspace en el backend."""
        pass
    
    async def list_workspaces(self) -> list:
        """Lista workspaces disponibles."""
        pass
    
    async def switch_workspace(self, workspace_id: str) -> dict:
        """Cambia el workspace actual."""
        pass
    
    async def get_workspace_info(self, workspace_id: str) -> dict:
        """Obtiene información detallada de un workspace."""
        pass
    
    async def delete_workspace(self, workspace_id: str) -> bool:
        """Elimina un workspace."""
        pass
    
    async def save_workspace_memory(self, workspace_id: str, memory_data: dict) -> bool:
        """Guarda memoria del workspace."""
        pass
    
    async def get_workspace_memory(self, workspace_id: str) -> dict:
        """Obtiene memoria del workspace."""
        pass
```

---

## 3. Integraciones Existentes

### 3.1 `LLMService.update_workspace()`
**Actual**: Método que actualiza el workspace dinámicamente.
**Modificación**: Aceptar `workspace_id` como parámetro adicional.

```python
# En kogniterm/core/llm_service.py
def update_workspace(self, workspace_id: str = None) -> None:
    """Actualiza el directorio del workspace dinámicamente."""
    if workspace_id:
        self.current_workspace = workspace_id
        self._update_workspace_context(workspace_id)
```

### 3.2 `HistoryManager`
**Actual**: Métodos que usan `history_file_path` fijo.
**Modificación**: Aceptar `workspace_id` como parámetro para generar ruta específica.

```python
# En kogniterm/core/history_manager.py
def _get_workspace_history_path(self, workspace_id: str) -> str:
    """Obtiene la ruta del historial para un workspace."""
    return os.path.join(self.history_file_path, workspace_id, "history.json")
```

### 3.3 `WorkspaceContext`
**Actual**: Métodos que usan contexto del proyecto actual.
**Modificación**: Aceptar `workspace_id` como parámetro.

```python
# En kogniterm/core/context/workspace_context.py
def initialize_context(self, workspace_id: str = None) -> None:
    """Inicializa el contexto para un workspace."""
    if workspace_id:
        self.current_workspace = workspace_id
```

### 3.4 `AgentState`
**Actual**: Métodos que usan `history_file_path` fijo.
**Modificación**: Añadir campo `workspace_id` y métodos auxiliares.

```python
# En kogniterm/core/agent_state.py
class AgentState:
    workspace_id: Optional[str] = None  # Nuevo campo
    
    def update_workspace(self, workspace_id: str) -> None:
        """Actualiza el workspace actual."""
        self.workspace_id = workspace_id
        self.history_file_path = os.path.join(os.getcwd(), ".kogniterm", "workspaces", workspace_id, "history.json")
```

---

## 4. Métodos de Integración

### 4.1 `LLMService` → `WorkspaceManager`
**Propósito**: Conectar LLMService con WorkspaceManager.

```python
# En kogniterm/core/llm_service.py
def update_workspace(self, workspace_id: str) -> None:
    """Actualiza el directorio del workspace dinámicamente."""
    self.current_workspace = workspace_id
    
    # Actualizar ruta del historial
    workspace_dir = os.path.join(self.workspace_dir, workspace_id)
    self.history_file_path = os.path.join(workspace_dir, "history.json")
    
    # Actualizar ruta del contexto
    self.context_file_path = os.path.join(workspace_dir, "context.json")
    
    # Recrear objetos necesarios
    self.history_manager = HistoryManager(
        history_file_path=self.history_file_path,
        max_history_messages=100,
        max_history_chars=150000
    )
    
    self.workspace_context = WorkspaceContext(
        workspace_dir=workspace_dir,
        history_manager=self.history_manager
    )
```

### 4.2 `HistoryManager` → `MemoryManager`
**Propósito**: Conectar HistoryManager con MemoryManager.

```python
# En kogniterm/core/history_manager.py
def _get_workspace_memory_path(self, workspace_id: str) -> str:
    """Obtiene la ruta del archivo de memoria para un workspace."""
    return os.path.join(self.history_file_path, workspace_id, "memory.json")

def save_memory(self, workspace_id: str, memory_data: dict) -> bool:
    """Guarda memoria del workspace."""
    memory_path = self._get_workspace_memory_path(workspace_id)
    # Guardar memoria en archivo JSON
    pass

def load_memory(self, workspace_id: str) -> Optional[dict]:
    """Carga memoria desde archivo JSON."""
    memory_path = self._get_workspace_memory_path(workspace_id)
    # Cargar memoria desde archivo JSON
    pass
```

### 4.3 `WorkspaceManager` → `LLMService`
**Propósito**: Conectar WorkspaceManager con LLMService.

```python
# En kogniterm/core/workspace_manager.py
def get_llm_service(self) -> LLMService:
    """Obtiene el LLMService para el workspace actual."""
    return self.llm_service
```

### 4.4 `TerminalWorkspaceManager` → `WorkspaceManager`
**Propósito**: Conectar TerminalWorkspaceManager con WorkspaceManager.

```python
# En kogniterm/terminal/workspace_manager.py
def get_workspace_manager(self) -> WorkspaceManager:
    """Obtiene el WorkspaceManager para el terminal."""
    return self.workspace_manager
```

---

## 5. Pruebas Unitarias

### 5.1 Tests para `WorkspaceManager`
```python
# tests/test_workspace_manager.py
class TestWorkspaceManager:
    """Tests para WorkspaceManager."""
    
    def test_create_workspace(self):
        """Testa la creación de un workspace."""
        workspace_manager = WorkspaceManager(config_manager)
        result = workspace_manager.create_workspace("test_workspace")
        assert result is not None
        assert result["name"] == "test_workspace"
    
    def test_list_workspaces(self):
        """Testa la lista de workspaces."""
        workspace_manager = WorkspaceManager(config_manager)
        workspaces = workspace_manager.list_workspaces()
        assert isinstance(workspaces, list)
    
    def test_switch_workspace(self):
        """Testa el cambio de workspace."""
        workspace_manager = WorkspaceManager(config_manager)
        workspace_manager.create_workspace("test_workspace")
        result = workspace_manager.switch_workspace("test_workspace")
        assert result["workspace_id"] == "test_workspace"
    
    def test_delete_workspace(self):
        """Testa la eliminación de un workspace."""
        workspace_manager = WorkspaceManager(config_manager)
        workspace_manager.create_workspace("test_workspace")
        result = workspace_manager.delete_workspace("test_workspace")
        assert result is True
```

### 5.2 Tests para `MemoryManager`
```python
# tests/test_memory_manager.py
class TestMemoryManager:
    """Tests para MemoryManager."""
    
    def test_store_memory(self):
        """Testa el almacenamiento de memoria."""
        memory_manager = MemoryManager(workspace_manager, config_manager)
        result = memory_manager.store_memory("test_workspace", {"key": "value"})
        assert result is True
    
    def test_get_memory(self):
        """Testa la obtención de memoria."""
        memory_manager = MemoryManager(workspace_manager, config_manager)
        memory = memory_manager.get_memory("test_workspace")
        assert memory is not None
    
    def test_save_memory(self):
        """Testa el guardado de memoria."""
        memory_manager = MemoryManager(workspace_manager, config_manager)
        result = memory_manager.save_memory("test_workspace", {"key": "value"})
        assert result is True
    
    def test_delete_memory(self):
        """Testa la eliminación de memoria."""
        memory_manager = MemoryManager(workspace_manager, config_manager)
        result = memory_manager.delete_memory("test_workspace")
        assert result is True
```

### 5.3 Tests para `TerminalWorkspaceManager`
```python
# tests/test_terminal_workspace_manager.py
class TestTerminalWorkspaceManager:
    """Tests para TerminalWorkspaceManager."""
    
    def test_list_workspaces(self):
        """Testa la lista de workspaces en el terminal."""
        terminal_workspace_manager = TerminalWorkspaceManager(workspace_manager, history_manager)
        workspaces = terminal_workspace_manager.list_workspaces()
        assert isinstance(workspaces, list)
    
    def test_switch_workspace(self):
        """Testa el cambio de workspace en el terminal."""
        terminal_workspace_manager = TerminalWorkspaceManager(workspace_manager, history_manager)
        result = terminal_workspace_manager.switch_workspace("test_workspace")
        assert result["workspace_id"] == "test_workspace"
    
    def test_get_workspace_memory(self):
        """Testa la obtención de memoria del workspace."""
        terminal_workspace_manager = TerminalWorkspaceManager(workspace_manager, history_manager)
        memory = terminal_workspace_manager.get_workspace_memory("test_workspace")
        assert memory is not None
```

### 5.4 Tests para `WorkspaceService`
```python
# tests/test_workspace_service.py
class TestWorkspaceService:
    """Tests para WorkspaceService."""
    
    async def test_create_workspace(self):
        """Testa la creación de workspace en el backend."""
        workspace_service = WorkspaceService(backend_url, workspace_manager)
        result = await workspace_service.create_workspace("test_workspace", "Test workspace")
        assert result is not None
    
    async def test_list_workspaces(self):
        """Testa la lista de workspaces en el backend."""
        workspace_service = WorkspaceService(backend_url, workspace_manager)
        workspaces = await workspace_service.list_workspaces()
        assert isinstance(workspaces, list)
    
    async def test_switch_workspace(self):
        """Testa el cambio de workspace en el backend."""
        workspace_service = WorkspaceService(backend_url, workspace_manager)
        result = await workspace_service.switch_workspace("test_workspace")
        assert result["workspace_id"] == "test_workspace"
    
    async def test_delete_workspace(self):
        """Testa la eliminación de workspace en el backend."""
        workspace_service = WorkspaceService(backend_url, workspace_manager)
        result = await workspace_service.delete_workspace("test_workspace")
        assert result is True
```

---

## 6. Documentación

### 6.1 API Documentation
Documentar la API de workspace:
```markdown
# API de Workspaces

## Crear Workspace
```
POST /api/workspaces
{
    "name": "string",
    "description": "string (opcional)"
}
```

## Listar Workspaces
```
GET /api/workspaces
```

## Cambiar Workspace
```
POST /api/workspaces/{workspace_id}/switch
```

## Obtener Workspace Info
```
GET /api/workspaces/{workspace_id}
```

## Eliminar Workspace
```
DELETE /api/workspaces/{workspace_id}
```

## Guardar Memoria del Workspace
```
POST /api/workspaces/{workspace_id}/memory
{
    "key": "string",
    "value": "any"
}
```

## Obtener Memoria del Workspace
```
GET /api/workspaces/{workspace_id}/memory
```
```

### 6.2 Guía de Usuario
Crear documentación para el usuario:
- Cómo crear un workspace
- Cómo cambiar entre workspaces
- Cómo guardar memoria del workspace
- Cómo eliminar un workspace

---

## 7. Prioridades

| Prioridad | Tarea | Descripción |
|-----------|-------|-------------|
| **P0** | Crear `WorkspaceManager` | Módulo principal para gestión de workspaces |
| **P0** | Crear `MemoryManager` | Módulo para gestión de memoria contextual |
| **P1** | Actualizar `LLMService.update_workspace()` | Integrar workspace_id con LLMService |
| **P1** | Actualizar `HistoryManager` | Integrar workspace_id con HistoryManager |
| **P1** | Actualizar `WorkspaceContext` | Integrar workspace_id con WorkspaceContext |
| **P1** | Actualizar `AgentState` | Añadir workspace_id al estado |
| **P2** | Crear `TerminalWorkspaceManager` | Módulo para terminal |
| **P2** | Crear `WorkspaceService` | Servicio web para workspace |
| **P3** | Tests unitarios | Tests para cada módulo nuevo |
| **P3** | Documentación | API docs y guía de usuario |
| **P4** | Integración de UI | Actualizar interfaz para workspaces |

---

## 8. Riesgos Identificados

### Riesgo 1: Conflictos de archivos
**Descripción**: Los workspaces comparten el mismo directorio `.kogniterm/` pero con diferentes nombres.
**Mitigación**: Usar nombres únicos para cada workspace (ej: `workspace_1`, `workspace_2`).
**Impacto**: Bajo

### Riesgo 2: Configuración de API keys
**Descripción**: Las API keys del workspace no están configuradas correctamente.
**Mitigación**: Validar API keys en el momento de crear el workspace.
**Impacto**: Medio

### Riesgo 3: Persistencia de memoria
**Descripción**: La memoria puede no persistir correctamente entre sesiones.
**Mitigación**: Usar archivos JSON con persistencia atómica.
**Impacto**: Medio

### Riesgo 4: Error de import
**Descripción**: `kogniterm/core/llm/__init__.py` no exporta `LLMService`.
**Mitigación**: Añadir `LLMService` a `__all__` en `__init__.py`.
**Impacto**: Medio

### Riesgo 5: Falta de archivo `src/`
**Descripción**: El archivo `src/` no existe en el proyecto.
**Mitigación**: Usar la estructura de directorios existente.
**Impacto**: Bajo

---

## 9. Cronograma

| Semana | Tarea | Entregables |
|--------|-------|-------------|
| 1 | Crear `WorkspaceManager` | Módulo principal con CRUD |
| 2 | Crear `MemoryManager` | Módulo de memoria contextual |
| 3 | Actualizar `LLMService` | Integración con workspace_id |
| 4 | Actualizar `HistoryManager` | Integración con workspace_id |
| 5 | Actualizar `WorkspaceContext` | Integración con workspace_id |
| 6 | Actualizar `AgentState` | Añadir workspace_id |
| 7 | Crear `TerminalWorkspaceManager` | Módulo de terminal |
| 8 | Crear `WorkspaceService` | Servicio web |
| 9 | Tests unitarios | Tests completos |
| 10 | Documentación | API docs y guía |
| 11 | Integración UI | Interfaz de workspaces |
| 12 | Testing final | Testing completo |

---

## 10. Checklist de Implementación

- [ ] Crear `WorkspaceManager` (módulo principal)
- [ ] Crear `MemoryManager` (módulo de memoria)
- [ ] Crear `TerminalWorkspaceManager` (módulo de terminal)
- [ ] Crear `WorkspaceService` (servicio web)
- [ ] Actualizar `LLMService.update_workspace()`
- [ ] Actualizar `HistoryManager`
- [ ] Actualizar `WorkspaceContext`
- [ ] Actualizar `AgentState`
- [ ] Crear tests unitarios (paso a paso)
- [ ] Crear documentación API
- [ ] Crear guía de usuario
- [ ] Integración UI (React/TypeScript)
- [ ] Testing final
- [ ] Preparación para producción
