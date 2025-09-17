### 📂 `kogniterm/core/tools/`

Este directorio contiene las implementaciones de las herramientas que KogniTerm puede utilizar para interactuar con el sistema, la web y la memoria contextual. Cada archivo representa una herramienta específica, diseñada para realizar una tarea particular.

#### 🛠️ `web_fetch_tool.py`
- **Propósito**: Define la herramienta `WebFetchTool` para obtener el contenido HTML de una URL.
- **Clase**: `WebFetchTool`
- **Descripción**: Permite realizar solicitudes HTTP GET para obtener el contenido de una página web.
- **Funcionalidad clave**: Utiliza `RequestsWrapper` de `langchain_community.utilities` para realizar la petición.
- **Entrada**: Requiere una `url` (cadena de texto) como parámetro.
- **Salida**: Devuelve el contenido HTML de la URL o un mensaje de error si la operación falla.
- **Consideraciones**: No soporta operaciones asíncronas (`_arun` no implementado).
