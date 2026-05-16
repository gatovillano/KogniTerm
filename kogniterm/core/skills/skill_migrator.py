"""
SkillMigrator: Convierte herramientas existentes (core/tools/) en skills.

Este módulo analiza las clases de herramientas legacy y las transforma
en skills con estructura completa (SKILL.md, scripts/, references/).
"""

import ast
import inspect
from pathlib import Path
from typing import List, Dict, Any, Tuple
import yaml
import re
from datetime import datetime

from .skill_manager import SkillValidator, Skill


class SkillMigrator:
    """
    Migrador de herramientas legacy a skills.

    Proceso:
    1. Parsear archivo .py con AST
    2. Extraer clase principal de herramienta
    3. Extraer metadatos (name, description, docstring)
    4. Detectar imports → dependencias
    5. Inferir permisos y nivel de seguridad
    6. Generar SKILL.md con frontmatter YAML
    7. Copiar/adaptar código a scripts/tool.py
    8. Crear estructura de references/
    """

    # Mapeo de nombres de herramientas a permisos inferidos
    PERMISSION_MAP = {
        'file': 'filesystem',
        'directory': 'filesystem',
        'write': 'filesystem',
        'delete': 'filesystem',
        'remove': 'filesystem',
        'command': 'execute',
        'exec': 'execute',
        'shell': 'execute',
        'bash': 'execute',
        'browser': 'network',
        'web': 'network',
        'http': 'network',
        'fetch': 'network',
        'memory': 'memory',
        'storage': 'memory',
        'github': 'network',
        'search': 'network'
    }

    # Mapeo de nombres a niveles de seguridad
    SECURITY_MAP = {
        'execute_command': 'elevated',
        'pc_interaction': 'elevated',
        'file_delete': 'elevated',
        'file_write': 'elevated',
        'file_operations': 'high',
        'browser': 'high',
        'http_request': 'high',
        'github': 'medium',
        'web_fetch': 'medium',
        'web_scraping': 'medium',
        'memory': 'low',
        'think': 'low',
        'search': 'medium'
    }

    def __init__(
        self,
        tools_path: Path,
        skills_output_path: Path,
        validator: Optional[SkillValidator] = None
    ):
        """
        Inicializa el migrador.

        Args:
            tools_path: Ruta a core/tools/ (herramientas legacy)
            skills_output_path: Ruta a skills/bundled/ (destino)
            validator: Instancia de SkillValidator (opcional)
        """
        self.tools_path = Path(tools_path)
        self.skills_output_path = Path(skills_output_path)
        self.validator = validator or SkillValidator()

    def migrate_all_tools(self, dry_run: bool = False) -> Dict[str, Tuple[bool, str]]:
        """
        Migra todas las herramientas en core/tools/ a skills/bundled/.

        Args:
            dry_run: Si True, solo simula sin crear archivos

        Returns:
            Diccionario {tool_name: (success, message)}
        """
        results = {}

        # Iterar sobre todos los archivos .py en tools/
        for tool_file in self.tools_path.glob('*.py'):
            # Saltar archivos especiales
            if tool_file.name.startswith('_'):
                continue

            try:
                success, message = self.migrate_tool_to_skill(tool_file, dry_run)
                results[tool_file.stem] = (success, message)
            except Exception as e:
                results[tool_file.stem] = (False, f"Error inesperado: {e}")
                logger.error(f"Error migrando {tool_file.name}: {e}", exc_info=True)

        return results

    def migrate_tool_to_skill(
        self,
        tool_file: Path,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """
        Convierte una herramienta individual en una skill.

        Args:
            tool_file: Ruta al archivo .py de la herramienta
            dry_run: Si True, solo simula sin crear archivos

        Returns:
            (success, message)
        """
        logger.info(f"Migrando {tool_file.name}...")

        # 1. Parsear AST
        try:
            with open(tool_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
                tree = ast.parse(source_code)
        except SyntaxError as e:
            return False, f"Error de sintaxis en {tool_file.name}: {e}"

        # 2. Extraer clase principal de herramienta
        tool_class = self._find_tool_class(tree, tool_file)
        if not tool_class:
            return False, "No se encontró clase de herramienta válida"

        # 3. Extraer metadatos
        tool_name = self._extract_tool_name(tool_class, tool_file)
        description = self._extract_description(tool_class, source_code)
        docstring = ast.get_docstring(tool_class) or ""

        # 4. Detectar dependencias
        dependencies = self._detect_dependencies(tree, tool_file)

        # 5. Inferir permisos y seguridad
        permissions = self._infer_permissions(tool_name)
        security_level = self._infer_security_level(tool_name)
        needs_allowlist = self._needs_allowlist(tool_name)
        needs_sandbox = self._needs_sandbox(tool_name)

        # 6. Crear estructura de skill
        skill_dir = self.skills_output_path / tool_name
        if not dry_run:
            skill_dir.mkdir(parents=True, exist_ok=True)

        # 7. Generar SKILL.md
        skill_config = {
            'name': tool_name,
            'version': '1.0.0',
            'author': 'KogniTerm Core (auto-migrated)',
            'description': description,
            'category': self._infer_category(tool_name),
            'tags': [tool_name] + self._infer_tags(tool_name),
            'dependencies': dependencies,
            'required_permissions': permissions,
            'allowed-tools': [],
            'denied-tools': [],
            'security_level': security_level,
            'allowlist': needs_allowlist,
            'auto_approve': False,
            'sandbox_required': needs_sandbox,
            'resources': [],
            'assets': [],
            'metadata': {
                'migrated_from': str(tool_file),
                'format': 'agent-skills-compatible'
            }
        }

        skill_md_content = self._generate_skill_md(skill_config, docstring)

        if not dry_run:
            skill_md_path = skill_dir / 'SKILL.md'
            skill_md_path.write_text(skill_md_content, encoding='utf-8')

        # 8. Crear scripts/tool.py
        scripts_dir = skill_dir / 'scripts'
        if not dry_run:
            scripts_dir.mkdir(exist_ok=True)

            # Adaptar código fuente: extraer solo la clase/herramienta relevante
            adapted_code = self._adapt_source_code(source_code, tool_class, tool_name)
            tool_script_path = scripts_dir / 'tool.py'
            tool_script_path.write_text(adapted_code, encoding='utf-8')

        # 9. Crear references/
        references_dir = skill_dir / 'references'
        if not dry_run:
            references_dir.mkdir(exist_ok=True)
            (references_dir / '.gitkeep').touch()

        logger.info(f"✅ {tool_file.name} → {skill_dir}")
        return True, f"Skill creada en {skill_dir}"

    def _find_tool_class(self, tree: ast.AST, tool_file: Path) -> Optional[ast.ClassDef]:
        """
        Encuentra la clase principal de herramienta en el AST.

        Criterios:
        - Es una clase (ast.ClassDef)
        - Hereda de BaseTool o tiene atributos 'name' y método 'run'
        """
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Verificar que herede de BaseTool (o similar)
            is_tool_class = False
            for base in node.bases:
                if isinstance(base, ast.Name) and 'Tool' in base.id:
                    is_tool_class = True
                    break
                elif isinstance(base, ast.Attribute):
                    if 'Tool' in base.attr:
                        is_tool_class = True
                        break

            # Si no hereda de Tool, verificar que tenga 'name' y 'run'
            if not is_tool_class:
                has_name = any(
                    isinstance(n, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == 'name' for t in n.targets)
                    for n in node.body
                )
                has_run = any(
                    isinstance(n, ast.FunctionDef) and n.name == 'run'
                    for n in node.body
                )
                is_tool_class = has_name and has_run

            if is_tool_class:
                return node

        return None

    def _extract_tool_name(self, tool_class: ast.ClassDef, tool_file: Path) -> str:
        """Extrae el nombre de la herramienta desde la clase."""
        # Buscar asignación a 'name'
        for node in tool_class.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'name':
                        if isinstance(node.value, ast.Constant):
                            return node.value.value.lower().replace(' ', '_')
                        elif isinstance(node.value, ast.Str):  # Python < 3.8
                            return node.value.s.lower().replace(' ', '_')

        # Fallback: nombre del archivo sin sufijo _tool
        name = tool_file.stem
        if name.endswith('_tool'):
            name = name[:-5]
        return name.lower()

    def _extract_description(self, tool_class: ast.ClassDef, source_code: str) -> str:
        """Extrae descripción desde docstring o asignación."""
        # Intentar docstring de clase
        docstring = ast.get_docstring(tool_class)
        if docstring:
            # Tomar primera línea
            return docstring.strip().split('\n')[0]

        # Buscar asignación a 'description'
        for node in tool_class.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'description':
                        if isinstance(node.value, ast.Constant):
                            return node.value.value
                        elif isinstance(node.value, ast.Str):
                            return node.value.s

        return "Herramienta migrada automáticamente"

    def _detect_dependencies(self, tree: ast.AST, tool_file: Path) -> List[str]:
        """
        Detecta dependencias analizando imports en el AST.

        Filtra stdlib comunes y devuelve solo dependencias externas.
        """
        dependencies = set()
        stdlib_modules = {
            'os', 'sys', 'json', 'pathlib', 'typing', 'asyncio', 'logging',
            'subprocess', 'shlex', 're', 'datetime', 'time', 'math', 'random',
            'collections', 'itertools', 'functools', 'abc', 'dataclasses',
            'enum', 'hashlib', 'base64', 'urllib', 'http', 'socket',
            'tempfile', 'shutil', 'glob', 'fnmatch', 'stat', 'platform'
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module not in stdlib_modules:
                        dependencies.add(f"{module}>=1.0.0")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split('.')[0]
                    if module not in stdlib_modules:
                        dependencies.add(f"{module}>=1.0.0")

        return sorted(list(dependencies))

    def _infer_permissions(self, tool_name: str) -> List[str]:
        """Infiere permisos basados en el nombre de la herramienta."""
        permissions = []
        tool_lower = tool_name.lower()

        for keyword, permission in self.PERMISSION_MAP.items():
            if keyword in tool_lower:
                if permission not in permissions:
                    permissions.append(permission)

        return permissions

    def _infer_security_level(self, tool_name: str) -> str:
        """Infiere nivel de seguridad basado en el nombre."""
        tool_lower = tool_name.lower()

        # Búsqueda exacta primero
        if tool_lower in self.SECURITY_MAP:
            return self.SECURITY_MAP[tool_lower]

        # Búsqueda por substrings
        for key, level in self.SECURITY_MAP.items():
            if key in tool_lower:
                return level

        return 'medium'  # Default

    def _needs_allowlist(self, tool_name: str) -> bool:
        """Determina si la skill requiere allowlisting explícito."""
        high_risk_keywords = ['execute', 'command', 'shell', 'bash', 'pc_interaction']
        tool_lower = tool_name.lower()

        return any(kw in tool_lower for kw in high_risk_keywords)

    def _needs_sandbox(self, tool_name: str) -> bool:
        """Determina si la skill necesita ejecución en sandbox Docker."""
        sandbox_keywords = ['execute_command', 'browser', 'web_fetch', 'web_scraping', 'pc_interaction']
        tool_lower = tool_name.lower()

        return any(kw in tool_lower for kw in sandbox_keywords)

    def _infer_category(self, tool_name: str) -> str:
        """Infiere categoría basada en el nombre."""
        categories = {
            'command': 'system',
            'file': 'filesystem',
            'memory': 'memory',
            'web': 'network',
            'browser': 'network',
            'search': 'network',
            'github': 'development',
            'code': 'development',
            'plan': 'planning',
            'think': 'reasoning',
            'python': 'execution'
        }

        tool_lower = tool_name.lower()
        for keyword, category in categories.items():
            if keyword in tool_lower:
                return category

        return 'general'

    def _infer_tags(self, tool_name: str) -> List[str]:
        """Infiere tags basados en el nombre."""
        tags = []
        tool_lower = tool_name.lower()

        # Tags comunes
        tag_keywords = {
            'bash': ['bash', 'shell'],
            'terminal': ['terminal', 'command'],
            'file': ['file', 'filesystem'],
            'network': ['http', 'web', 'network', 'fetch'],
            'browser': ['browser', 'web', 'automation'],
            'memory': ['memory', 'storage'],
            'development': ['code', 'git', 'github', 'development']
        }

        for tag, keywords in tag_keywords.items():
            if any(kw in tool_lower for kw in keywords):
                if tag not in tags:
                    tags.append(tag)

        return tags

    def _generate_skill_md(self, config: dict, docstring: str = "") -> str:
        """Genera contenido completo del archivo SKILL.md."""
        # Frontmatter YAML
        yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)

        # Instrucciones para LLM
        instructions = self._generate_instructions(config, docstring)

        return f"---\n{yaml_content}---\n\n{instructions}"

    def _generate_instructions(self, config: dict, docstring: str) -> str:
        """Genera sección de instrucciones para el LLM."""
        description = config['description']
        name = config['name']
        security_level = config['security_level']
        permissions = config['required_permissions']
        sandbox = config['sandbox_required']

        instructions = f"""# Instrucciones para el LLM

{description}

## Herramientas disponibles:

### {name}

{description if docstring else '(Descripción detallada pendiente de migración)'}

**Parámetros:**
(La implementación específica se documentará después de migrar)

## Consideraciones de seguridad:

- Nivel de seguridad: **{security_level}**
- Permisos requeridos: {', '.join(permissions) if permissions else 'Ninguno'}
- Requiere allowlisting: {config['allowlist']}
- Ejecución en sandbox: {sandbox}

## Cómo usar:

1. Llama a la herramienta con los parámetros adecuados
2. Verifica los resultados antes de proceder
3. Si falla, revisa los permisos y dependencias

---

*Esta skill fue migrada automáticamente. Revisar y ajustar metadatos según sea necesario.*
"""

        return instructions

    def _adapt_source_code(self, source_code: str, tool_class: ast.ClassDef, tool_name: str) -> str:
        """
        Adapta el código fuente para la skill.

        Por ahora, devuelve el código original. En versiones futuras,
        puede transformar la clase en función simple o ajustar imports.
        """
        # TODO: En el futuro, transformar class -> function si es necesario
        # Por ahora, devolver código original
        return source_code


def migrate_tools_cli():
    """CLI para migrar herramientas desde línea de comandos."""
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description='Migra herramientas legacy a skills')
    parser.add_argument(
        '--tools-path',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'tools',
        help='Ruta a core/tools/'
    )
    parser.add_argument(
        '--output-path',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'skills' / 'bundled',
        help='Ruta a skills/bundled/'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular sin crear archivos'
    )

    args = parser.parse_args()

    migrator = SkillMigrator(args.tools_path, args.output_path)
    results = migrator.migrate_all_tools(dry_run=args.dry_run)

    print("\n" + "="*60)
    print("RESULTADOS DE MIGRACIÓN")
    print("="*60)

    success_count = 0
    for tool_name, (success, message) in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {tool_name}: {message}")
        if success:
            success_count += 1

    print(f"\nTotal: {len(results)} herramientas, {success_count} exitosas")


if __name__ == '__main__':
    migrate_tools_cli()
