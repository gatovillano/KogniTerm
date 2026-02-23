# Migración a Sistema de Skills Dinámico

## 📋 Resumen Ejecutivo

Este documento describe la migración completa del sistema de herramientas de KogniTerm desde una arquitectura monolítica con herramientas hardcoded hacia un sistema modular de skills con discovery automático, JIT loading y tres niveles de gestión (workspace/managed/bundled), inspirado en OpenClaw.

**Estado actual**: Herramientas integradas en `core/tools/` con lista estática `ALL_TOOLS_CLASSES`

**Arquitectura objetivo**: Sistema de skills con:

- Discovery automático de skills en múltiples ubicaciones
- JIT (Just-In-Time) loading de skills
- Tres niveles: `workspace/` (proyecto), `managed/` (usuario), `bundled/` (core)
- 100% compatibilidad hacia atrás
- Metadatos enriquecidos en `SKILL.md`

---

## 🎯 Objetivos

1. **Modularidad**: Añadir skills nuevas sin modificar el core
2. **Flexibilidad**: Skills pueden instalarse/desinstalarse dinámicamente
3. **Seguridad**: Metadatos de seguridad por skill (security_level, allowlist, sandbox)
4. **Compatibilidad**: Herramientas legacy siguen funcionando durante transición
5. **Discoverability**: Auto-detección de skills en múltiples directorios
6. **Context-aware**: Skills pueden filtrarse por permisos de agente

---

## 📁 Estructura de Carpetas Objetivo

```
kogniterm/
├── core/
│   ├── tools/                    # [DEPRECATED] Mantener para compatibilidad
│   │   ├── __init__.py           # ALL_TOOLS_CLASSES (migrado gradual)
│   │   └── tool_manager.py       # ToolManager actualizado
│   └── skills/                   # NUEVO: Gestión de skills
│       ├── __init__.py
│       ├── skill_manager.py      # Clase principal (discovery, loading, registry)
│       ├── skill_loader.py       # Carga dinámica de módulos Python
│       ├── skill_validator.py    # Valida estructura y SKILL.md
│       └── skill_migrator.py     # Convierte tools → skills
├── skills/                       # NUEVO: Carpeta global de skills
│   ├── workspace/               # Skills del proyecto actual (gitignored)
│   │   └── .gitkeep
│   ├── managed/                 # Skills instalados por usuario (pip install)
│   │   └── .gitkeep
│   └── bundled/                 # Skills del core (migrados desde tools/)
│       ├── execute_command/
│       │   ├── SKILL.md
│       │   ├── scripts/
│       │   │   └── tool.py
│       │   └── references/
│       ├── file_operations/
│       │   ├── SKILL.md
│       │   ├── scripts/
│       │   │   └── tool.py
│       │   └── references/
│       └── ...
└── .kogniterm/
    └── skills_config.yaml       # Config: qué skill levels activar
```

---

## 📄 Formato SKILL.md (Especificación)

Cada skill debe tener un `SKILL.md` con frontmatter YAML:

```yaml
---
name: execute_command
version: 1.0.0
author: "KogniTerm Core"
description: "Ejecuta comandos en la terminal del sistema"
category: "system"
tags: ["bash", "shell", "terminal", "execution"]
dependencies:
  - "subprocess>=0.0.1"  # Siempre True, es stdlib
  - "asyncio>=0.0.1"
required_permissions: ["execute", "filesystem"]
security_level: "elevated"  # low | medium | high | elevated
allowlist: true              # Si requiere allowlisting explícito
auto_approve: false          # Si se aprueba automáticamente (ej. solo lectura)
sandbox_required: true       # Si debe ejecutarse en Docker
---
```

**Instrucciones para el LLM** (después del `---`):

- Descripción detallada de lo que hace la skill
- Lista de herramientas disponibles con parámetros
- Ejemplos de uso
- Consideraciones de seguridad

---

## 🔧 Componentes Técnicos

### 1. Skill (clase de datos)

```python
@dataclass
class Skill:
    path: Path                    # Ruta raíz de la skill
    name: str                     # Nombre único
    version: str                  # Versión (semver)
    description: str              # Descripción corta
    category: str                 # Categoría (system, file, web, etc.)
    tags: List[str]               # Tags para búsqueda
    dependencies: List[str]       # Dependencias pip
    required_permissions: List[str]  # Permisos necesarios
    security_level: str          # low|medium|high|elevated
    allowlist: bool              # Requiere allowlisting
    auto_approve: bool           # Auto-aprobación
    sandbox_required: bool       # Necesita sandbox Docker
    instructions: str            # Instrucciones para LLM (extraídas de SKILL.md)
    scripts_path: Path           # Ruta a scripts/
    references_path: Path        # Ruta a references/
    loaded: bool                 # Si está cargada en memoria
    tools: List[Any]             # Herramientas cargadas
```

### 2. SkillManager

Responsabilidades:

- **Discovery**: Buscar skills en `bundled/`, `managed/`, `workspace/`
- **Validación**: Verificar que cada skill tenga estructura válida
- **Loading**: Cargar módulos Python desde `scripts/` (JIT)
- **Registro**: Mantener `tool_registry` global (nombre → tool + metadata)
- **Filtrado**: Filtrar skills por permisos/contexto de agente
- **Unloading**: Descargar skills (para recargar o desinstalar)

Métodos principales:

```python
class SkillManager:
    def __init__(self, base_path=None, user_skills_path=None)
    def discover_all_skills(self) -> List[Skill]
    def load_skill(self, skill_name: str, agent_context: dict = None) -> bool
    def unload_skill(self, skill_name: str)
    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]
    def get_available_tools(self, agent_context: dict = None) -> List[Dict[str, Any]]
    def validate_skill(self, skill_path: Path) -> Tuple[bool, List[str]]
```

### 3. SkillLoader

Carga dinámica de módulos Python:

```python
def _import_tools(self, skill: Skill) -> List[Any]:
    """Importa todas las funciones/clases de scripts/*.py"""
    tools = []
    for script_file in skill.scripts_path.glob('*.py'):
        spec = importlib.util.spec_from_file_location(...)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Buscar callables con atributos 'name' o 'run'
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                if hasattr(attr, 'name') or hasattr(attr, 'run'):
                    tools.append(attr)
    return tools
```

### 4. SkillValidator

Validaciones:

- Estructura de carpetas: `SKILL.md`, `scripts/`, `references/` existen
- SKILL.md: YAML válido con campos requeridos (`name`, `version`, `description`)
- scripts/: al menos un archivo `.py`
- Dependencias: formato válido (pip spec)
- Permisos: valores válidos en `required_permissions`
- Security level: uno de [low, medium, high, elevated]

### 5. SkillMigrator

Convierte herramientas existentes en skills automáticamente:

**Proceso**:

1. Parsear archivo `tool.py` con AST
2. Extraer clase principal (buscar `class X(BaseTool)`)
3. Extraer metadatos: `name`, `description`, docstring
4. Inferir dependencias desde imports (AST)
5. Inferir permisos basados en nombre de herramienta
6. Inferir security_level basado en riesgo
7. Generar `SKILL.md` con frontmatter YAML
8. Copiar código a `scripts/tool.py`
9. Crear `references/.gitkeep`

**Limitaciones**:

- No puede inferir 100% de la semántica (requiere revisión manual)
- Dependencias pueden necesitar ajuste manual
- Permisos/seguridad pueden necesitar tuning

---

## 🔄 Integración con ToolManager

### Cambios en ToolManager

```python
class ToolManager:
    def __init__(self, ...):
        self.skill_manager = None          # Se inyecta después
        self.legacy_tools = []             # Herramientas legacy
        self.legacy_tool_map = {}          # Map legacy

    def set_skill_manager(self, skill_manager):
        """Inyecta el SkillManager"""
        self.skill_manager = skill_manager

    def load_tools(self, load_legacy: bool = True, load_skills: bool = True):
        """Carga herramientas, priorizando skills sobre legacy"""

        # 1. Cargar skills si está disponible
        if load_skills and self.skill_manager:
            skills = self.skill_manager.discover_all_skills()
            for skill in skills:
                self.skill_manager.load_skill(skill.name)

            # Registrar en tool_map (sobrescribe legacy)
            for tool_name, tool_info in self.skill_manager.tool_registry.items():
                self.tools.append(tool_info['tool'])
                self.tool_map[tool_name] = tool_info['tool']

        # 2. Cargar herramientas legacy (solo si no hay skill con mismo nombre)
        if load_legacy:
            for ToolClass in ALL_TOOLS_CLASSES:
                tool_instance = ToolClass(**tool_kwargs)
                base_name = getattr(tool_instance, 'name', ToolClass.__name__)

                if base_name in self.tool_map:  # Ya existe skill
                    continue

                self.legacy_tools.append(tool_instance)
                self.legacy_tool_map[base_name] = tool_instance
                self.tools.append(tool_instance)
                self.tool_map[base_name] = tool_instance

    def get_tool(self, tool_name: str):
        """Obtiene herramienta, primero de skills, luego legacy"""
        if self.skill_manager:
            tool_info = self.skill_manager.get_tool(tool_name)
            if tool_info:
                return tool_info['tool']
        return self.tool_map.get(tool_name) or self.legacy_tool_map.get(tool_name)

    def get_tools_for_llm(self, agent_context: dict = None):
        """Devuelve metadata para LLM con información de skill"""
        tools_metadata = []

        # Skills
        if self.skill_manager:
            for tool_name, tool_info in self.skill_manager.tool_registry.items():
                metadata = {
                    'name': tool_name,
                    'description': getattr(tool_info['tool'], 'description', ''),
                    'skill': tool_info['skill'],
                    'security_level': tool_info['security_level']
                }
                # Extraer schema de parámetros
                if hasattr(tool_info['tool'], 'parameters_schema'):
                    metadata['parameters'] = tool_info['tool'].parameters_schema
                elif hasattr(tool_info['tool'], 'run') and tool_info['tool'].run.__annotations__:
                    metadata['parameters'] = self._infer_schema_from_hints(tool_info['tool'].run)
                tools_metadata.append(metadata)

        # Legacy
        for tool in self.legacy_tools:
            if tool not in self.tools:
                metadata = {
                    'name': getattr(tool, 'name', tool.__class__.__name__),
                    'description': getattr(tool, 'description', ''),
                    'skill': 'core_legacy',
                    'security_level': 'unknown'
                }
                tools_metadata.append(metadata)

        return tools_metadata
```

---

## 🚀 Proceso de Migración Paso a Paso

### Fase 0: Preparación (1-2 días)

1. Crear estructura de carpetas:
   - `kogniterm/core/skills/` con módulos básicos
   - `kogniterm/skills/bundled/`, `managed/`, `workspace/`
2. Crear `SkillManager` vacío (sin lógica)
3. Actualizar `ToolManager.__init__` para aceptar `skill_manager`
4. Crear `SkillValidator` básico

**Entregable**: Estructura creada, ToolManager actualizado para inyectar skill_manager

### Fase 1: Migración Manual de 2-3 Tools (2-3 días)

1. Migrar `ExecuteCommandTool` a skill manualmente:
   - Crear `skills/bundled/execute_command/SKILL.md`
   - Copiar código a `scripts/tool.py` (ajustar imports)
   - Asegurar que la función/class mantiene la interfaz
2. Migrar `FileOperationsTool` a skill
3. Migrar `MemoryAppendTool` a skill
4. Verificar que KogniTerm aún funcione con legacy tools

**Entregable**: 3 skills migradas manualmente, KogniTerm funcionando

### Fase 2: SkillManager Básico (3-4 días)

1. Implementar `discover_all_skills()`:
   - Buscar en `bundled/`, `managed/`, `workspace/`
   - Parsear `SKILL.md` con frontmatter YAML
   - Crear objetos `Skill`
2. Implementar `load_skill()` básico:
   - Validar dependencias (solo warnings)
   - Cargar scripts con `importlib.util`
   - Registrar herramientas en `tool_registry`
3. Integrar en `ToolManager.load_tools()`
4. Probar que las skills migradas se cargan correctamente

**Entregable**: SkillManager funcional, skills se cargan automáticamente

### Fase 3: Migrador Automático (3-4 días)

1. Implementar `SkillMigrator`:
   - Parsear AST de herramientas existentes
   - Extraer metadatos (name, description, docstring)
   - Detectar imports → dependencias
   - Inferir permisos/seguridad por nombre
   - Generar `SKILL.md` completo
   - Copiar código a `scripts/tool.py`
2. Migrar todas las herramientas restantes automáticamente
3. Revisar y ajustar `SKILL.md` generados (algunos necesitarán tuning manual)
4. Actualizar `ALL_TOOLS_CLASSES` para reflejar migración

**Entregable**: Todas las herramientas migradas a skills, migrador funcional

### Fase 4: Compatibilidad y Testing (3-4 días)

1. Asegurar que `ToolManager.get_tool()` encuentra tanto skills como legacy
2. Escribir tests unitarios:
   - Test discovery: encuentra todas las skills
   - Test loading: carga correcta de scripts
   - Test tool_registry: herramientas registradas
   - Test migración: tool → skill produce resultado válido
3. Probar KogniTerm completo con solo skills (desactivando legacy)
4. Probar KogniTerm con modo híbrido (skills + legacy)
5. Test de regresión: cada skill debe comportarse idéntico a la herramienta original

**Entregable**: Suite de tests, KogniTerm funcionando 100% con skills

### Fase 5: Features Avanzadas (Opcional, 5-7 días)

1. **JIT Loading mejorado**: Cargar skills solo cuando sean relevantes para el contexto
2. **Dependencias aisladas**: Venv por skill para aislamiento total
3. **Hot-reload**: `watchdog` para recargar skills modificadas sin restart
4. **Skill marketplace**: `kogniterm skills install <url>` para instalar skills externas
5. **Skill dependencies**: Skills pueden depender de otras skills
6. **Skill versioning**: Manejo de múltiples versiones de una skill

**Entregable**: Features avanzadas implementadas (si hay tiempo)

---

## 🧪 Testing Strategy

### Tests Unitarios

```python
# tests/core/skills/test_skill_manager.py
def test_discover_all_skills():
    """Debe encontrar todas las skills en bundled/managed/workspace"""
    manager = SkillManager(base_path=test_path)
    skills = manager.discover_all_skills()
    assert len(skills) > 0
    assert all(isinstance(s, Skill) for s in skills)

def test_load_skill():
    """Debe cargar una skill y registrar sus herramientas"""
    manager = SkillManager(base_path=test_path)
    success = manager.load_skill('execute_command')
    assert success
    assert 'execute_command' in manager.tool_registry
    assert len(manager.tool_registry['execute_command']['tool']) > 0

def test_get_tool():
    """Debe retornar herramienta por nombre"""
    manager = SkillManager(base_path=test_path)
    manager.load_skill('execute_command')
    tool_info = manager.get_tool('execute_command')
    assert tool_info is not None
    assert tool_info['skill'] == 'execute_command'

def test_validate_skill():
    """Debe validar SKILL.md correctamente"""
    validator = SkillValidator()
    is_valid, errors = validator.validate_skill(Path('skills/bundled/execute_command'))
    assert is_valid
    assert len(errors) == 0

def test_validate_invalid_skill():
    """Debe rechazar skill inválida"""
    validator = SkillValidator()
    is_valid, errors = validator.validate_skill(Path('skills/bundled/invalid_skill'))
    assert not is_valid
    assert len(errors) > 0
```

### Tests de Integración

```python
# tests/integration/test_tool_manager_integration.py
def test_tool_manager_with_skills():
    """ToolManager debe cargar skills y legacy tools"""
    tm = ToolManager()
    sm = SkillManager(base_path=test_path)
    tm.set_skill_manager(sm)
    tm.load_tools(load_legacy=True, load_skills=True)

    # Verificar que herramientas de skills están disponibles
    assert tm.get_tool('execute_command') is not None

    # Verificar que herramientas legacy sin skill también están
    assert tm.get_tool('think_tool') is not None

def test_tool_priority_skills_over_legacy():
    """Si existe skill y legacy, skill tiene prioridad"""
    tm = ToolManager()
    sm = SkillManager(base_path=test_path)
    tm.set_skill_manager(sm)
    tm.load_tools(load_legacy=True, load_skills=True)

    tool = tm.get_tool('execute_command')
    # Verificar que es la versión de skill, no legacy
    assert hasattr(tool, '__module__')
    assert 'skills' in tool.__module__ or 'skill' in tool.__module__

def test_get_tools_for_llm():
    """Debe retornar metadata completa para LLM"""
    tm = ToolManager()
    sm = SkillManager(base_path=test_path)
    tm.set_skill_manager(sm)
    tm.load_tools()

    metadata = tm.get_tools_for_llm()
    for tool in metadata:
        assert 'name' in tool
        assert 'description' in tool
        assert 'skill' in tool  # Información de skill
        assert 'security_level' in tool
```

### Tests de Migración

```python
# tests/core/skills/test_skill_migrator.py
def test_migrate_tool_to_skill():
    """Debe convertir execute_command_tool.py en skill válida"""
    migrator = SkillMigrator(
        tools_path=Path('kogniterm/core/tools'),
        skills_output_path=Path('test_output/skills/bundled')
    )
    migrator.migrate_tool_to_skill(Path('kogniterm/core/tools/execute_command_tool.py'))

    skill_path = Path('test_output/skills/bundled/execute_command')
    assert skill_path.exists()
    assert (skill_path / 'SKILL.md').exists()
    assert (skill_path / 'scripts' / 'tool.py').exists()

    # Validar SKILL.md
    validator = SkillValidator()
    is_valid, errors = validator.validate_skill(skill_path)
    assert is_valid, f"Skill inválida: {errors}"
```

---

## ⚠️ Consideraciones Críticas

### Compatibilidad Hacia Atrás

- **NO eliminar** `core/tools/` inmediatamente
- Mantener `ALL_TOOLS_CLASSES` funcionando durante transición
- `ToolManager` debe poder mezclar legacy + skills
- Usuarios existentes no deben notar cambios

### Seguridad

- Las skills migradas deben heredar el nivel de seguridad de la tool original
- `allowlist` y `sandbox_required` se definen en `SKILL.md`
- El Gateway (futuro) debe respetar `security_level`
- Skills con `security_level=elevated` requieren aprobación manual

### Dependencias

- Si una skill requiere `pandas`, debe declararse en `dependencies`
- El sistema NO debe instalar automáticamente sin confirmación
- Usar venv aislado por skill en implementación avanzada
- Dependencias stdlib (subprocess, os, json) no necesitan especificarse

### Performance

- JIT loading: skills se cargan solo cuando se usan (lazy)
- Cache de `tool_registry` para búsqueda O(1)
- Discovery solo al inicio (o cuando se añade/elimina skill)

---

## 📚 Ejemplo: Migración de ExecuteCommandTool

### Antes (core/tools/execute_command_tool.py)

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class ExecuteCommandTool(BaseTool):
    name: str = "execute_command"
    description: str = "Ejecuta un comando bash y devuelve su salida."

    class ExecuteCommandInput(BaseModel):
        command: str = Field(description="El comando bash a ejecutar.")

    args_schema: Type[BaseModel] = ExecuteCommandInput

    def _run(self, command: str) -> Any:
        # Implementación...
        pass
```

### Después (skills/bundled/execute_command/)

```
execute_command/
├── SKILL.md
├── scripts/
│   └── tool.py
└── references/
```

**SKILL.md**:

```yaml
---
name: execute_command
version: 1.0.0
author: "KogniTerm Core"
description: "Ejecuta comandos en la terminal del sistema"
category: "system"
tags: ["bash", "shell", "terminal", "execution"]
dependencies: []
required_permissions: ["execute", "filesystem"]
security_level: "elevated"
allowlist: true
auto_approve: false
sandbox_required: true
---
```

**scripts/tool.py**:

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

def execute_command(command: str) -> str:
    """Ejecuta un comando en la terminal."""
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else result.stderr

# Metadata (opcional, puede estar solo en SKILL.md)
TOOL_METADATA = {
    'name': 'execute_command',
    'description': 'Ejecuta un comando en la terminal',
    'parameters': {
        'type': 'object',
        'properties': {
            'command': {'type': 'string', 'description': 'Comando a ejecutar'}
        },
        'required': ['command']
    }
}
```

---

## 🎯 Criterios de Éxito

✅ **Funcional**: KogniTerm funciona igual (o mejor) con skills
✅ **Compatible**: Herramientas legacy aún funcionan si no hay skill
✅ **Modular**: Se puede añadir una skill nueva sin tocar el core
✅ **Seguro**: Niveles de seguridad respetados
✅ **Documentado**: Cada skill tiene SKILL.md completo
✅ **Testeado**: Tests unitarios para SkillManager y migración
✅ **Performant**: JIT loading no degrada performance
✅ **Discoverable**: Auto-detección funciona en los 3 niveles

---

## 📖 Guía para Desarrolladores

### Añadir una Nueva Skill

1. Crear directorio en `skills/bundled/` o `skills/managed/`:

   ```bash
   mkdir -p skills/bundled/mi_nueva_skill/{scripts,references}
   ```

2. Crear `SKILL.md` con metadatos YAML

3. Implementar herramienta en `scripts/tool.py`:

   ```python
   def mi_herramienta(param1: str, param2: int = 5) -> str:
       """Descripción de lo que hace."""
       # Implementación
       return resultado
   ```

4. (Opcional) Añadir `TOOL_METADATA` para schema explícito

5. Reiniciar KogniTerm o recargar skills:

   ```python
   skill_manager = SkillManager()
   skill_manager.discover_all_skills()
   skill_manager.load_skill('mi_nueva_skill')
   ```

### Migrar una Herramienta Existente

```bash
python -m kogniterm.core.skills.skill_migrator
# Esto migra todas las herramientas en core/tools/ a skills/bundled/
```

### Validar una Skill

```python
from kogniterm.core.skills.skill_validator import SkillValidator

validator = SkillValidator()
is_valid, errors = validator.validate_skill(Path('skills/bundled/mi_skill'))
if not is_valid:
    print(f"Errores: {errors}")
```

---

## 🔄 Rollback Plan

Si la migración falla:

1. Desactivar skills en `ToolManager`:

   ```python
   tm.load_tools(load_legacy=True, load_skills=False)
   ```

2. Eliminar `kogniterm/skills/` (o mover a backup)

3. KogniTerm funcionará 100% con herramientas legacy

4. Corregir issues y reintentar migración

---

## 📊 Timeline Estimado

| Fase | Duración | Entregables |
|------|----------|-------------|
| Fase 0 | 1-2 días | Estructura, SkillManager vacío |
| Fase 1 | 2-3 días | 3 skills migradas manualmente |
| Fase 2 | 3-4 días | SkillManager funcional |
| Fase 3 | 3-4 días | Migrador automático, todas las skills migradas |
| Fase 4 | 3-4 días | Tests, integración completa |
| Fase 5 | 5-7 días | Features avanzadas (opcional) |
| **Total** | **17-24 días** | Sistema completo de skills |

---

## 📝 Notas Adicionales

- **JIT Loading**: Las skills se cargan solo cuando se solicitan por primera vez (lazy loading)
- **Context Filtering**: Futuramente, `get_available_tools(agent_context)` filtrará skills por permisos
- **Skill Dependencies**: Skills pueden depender de otras skills (ej: `web_scraper` depende de `http_request`)
- **Marketplace**: Skills externas pueden instalarse vía `pip` o desde repositorios Git
- **Hot Reload**: En desarrollo, cambios en `scripts/` se recargan automáticamente (watchdog)

---

**Documento creado**: 2025-02-13
**Autor**: Arquitecto de Software Senior
**Estado**: En implementación
