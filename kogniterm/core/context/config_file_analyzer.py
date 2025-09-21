import json
import re
from pathlib import Path
from typing import Dict, List, Any, TypedDict

# Definiciones de tipos para los archivos de configuración
class PackageJson(TypedDict, total=False):
    name: str
    version: str
    description: str
    main: str
    scripts: Dict[str, str]
    dependencies: Dict[str, str]
    devDependencies: Dict[str, str]
    peerDependencies: Dict[str, str]
    optionalDependencies: Dict[str, str]
    engines: Dict[str, str]
    private: bool
    license: str
    author: str
    repository: str
    keywords: List[str]

class CompilerOptions(TypedDict, total=False):
    target: str
    module: str
    lib: List[str]
    allowJs: bool
    checkJs: bool
    jsx: str
    declaration: bool
    declarationMap: bool
    sourceMap: bool
    outFile: str
    outDir: str
    rootDir: str
    composite: bool
    removeComments: bool
    noEmit: bool
    importHelpers: bool
    downlevelIteration: bool
    isolatedModules: bool
    strict: bool
    noImplicitAny: bool
    strictNullChecks: bool
    strictFunctionTypes: bool
    strictPropertyInitialization: bool
    noImplicitThis: bool
    alwaysStrict: bool
    noUnusedLocals: bool
    noUnusedParameters: bool
    noImplicitReturns: bool
    noFallthroughCasesInSwitch: bool
    esModuleInterop: bool
    allowSyntheticDefaultImports: bool
    forceConsistentCasingInFileNames: bool
    skipLibCheck: bool
    resolveJsonModule: bool

class TsconfigJson(TypedDict, total=False):
    compilerOptions: CompilerOptions
    files: List[str]
    include: List[str]
    exclude: List[str]
    extends: str
    references: List[Dict[str, str]]

class EslintrcJson(TypedDict, total=False):
    root: bool
    env: Dict[str, bool]
    extends: List[str]
    parser: str
    parserOptions: Dict[str, Any]
    plugins: List[str]
    rules: Dict[str, Any]
    settings: Dict[str, Any]

class ConfigFileAnalyzer:
    def __init__(self):
        self.config_files = {
            "package.json": None,
            "tsconfig.json": None,
            ".eslintrc.js": None,
            ".eslintrc.json": None,
        }
        self.parsers = {
            "package.json": parsePackageJson,
            "tsconfig.json": parseTsconfigJson,
            ".eslintrc.js": parseEslintrcJson,
            ".eslintrc.json": parseEslintrcJson,
        }

    def is_config_file(self, file_name: str) -> bool:
        return file_name in self.config_files

    def handle_config_change(self, file_path: str):
        file_name = Path(file_path).name
        if self.is_config_file(file_name):
            parser = self.parsers.get(file_name)
            if parser:
                try:
                    self.config_files[file_name] = parser(file_path)
                    print(f"Configuración recargada para {file_name}")
                except Exception as e:
                    print(f"Error al recargar {file_name}: {e}")

def _read_json_file(file_path: str) -> Dict[str, Any]:
    """Lee y parsea un archivo JSON."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"El archivo no fue encontrado: {file_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def parsePackageJson(file_path: str) -> PackageJson:
    """
    Analiza un archivo package.json y devuelve un objeto PackageJson.
    """
    data = _read_json_file(file_path)
    return PackageJson(data)

def parseTsconfigJson(file_path: str) -> TsconfigJson:
    """
    Analiza un archivo tsconfig.json y devuelve un objeto TsconfigJson.
    """
    data = _read_json_file(file_path)
    return TsconfigJson(data)

def parseEslintrcJson(file_path: str) -> EslintrcJson:
    """
    Analiza un archivo .eslintrc.js y devuelve un objeto EslintrcJson.
    Dado que es un archivo JS, se realiza una lectura básica y se intenta
    extraer un objeto JSON si el archivo lo permite (ej. module.exports = { ... }).
    Esto es una implementación simplificada. Una solución robusta requeriría
    un parser de JavaScript en Python o la ejecución del archivo JS.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"El archivo no fue encontrado: {file_path}")

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Intento simplificado de extraer una configuración de ESLint de un archivo JS.
    # Busca un patrón como 'module.exports = { ... }' y extrae el JSON.
    match = re.search(r'module\.exports\s*=\s*(\{[\s\S]*?\});', content)
    if match:
        try:
            # Intentar parsear el string extraído como JSON
            # Esto puede fallar si el JS no es un JSON válido o tiene comentarios, etc.
            config_str = match.group(1)
            # Eliminar posibles comentarios de JS para que sea un JSON válido
            config_str = re.sub(r'//.*?\n|/\*.*?\*/', '', config_str, flags=re.S)
            data = json.loads(config_str)
            return EslintrcJson(data)
        except json.JSONDecodeError:
            # Si falla el parseo, se devuelve un objeto vacío o se levanta una excepción.
            # Para este caso, devolvemos un objeto vacío para una implementación simplificada.
            print(f"Advertencia: No se pudo parsear el contenido de .eslintrc.js como JSON: {file_path}")
            return EslintrcJson()
    else:
        print(f"Advertencia: No se encontró 'module.exports = {{...}}' en {file_path}. Devolviendo objeto vacío.")
        return EslintrcJson()
