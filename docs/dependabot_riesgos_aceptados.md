# Riesgos de seguridad aceptados (Dependabot)

Registro de alertas de Dependabot que se atienden por mitigación
arquitectónica en lugar de parche, porque no existe versión corregida.

## ChromaDB — 4 alertas (alertas #34, #64, #65, #66)

**Versión afectada:** `>= 0.4.17, <= 1.5.9` (la versión del lock, `1.5.9`,
ya es la última publicada; `first_patched_version: n/a` en las 4 alertas).

**Vulnerabilidades reportadas:**

| Alerta | Problema |
|--------|----------|
| #34 | Inyección de código **pre-autenticación** en el servidor Chroma |
| #66 | Inyección de código vía endpoint autenticado |
| #65 | Lectura/escritura arbitraria entre tenants por usuarios autenticados |
| #64 | `SimpleRBACAuthorizationProvider` no verifica tenant/db/colección |

**Por qué es riesgo aceptado:** KogniTerm usa ChromaDB exclusivamente en
modo **embebido** (ver `kogniterm/core/context/vector_db_manager.py`:
`chromadb.PersistentClient(path=..., ...)`). Las 4 vulnerabilidades
corresponden al modo **servidor** (`chroma run` / `chromadb-server`) con
capa de autenticación/autorización multi-tenant. En modo embebido:

- No hay servidor HTTP ni endpoints de red: no existe superficie pre-auth.
- El acceso a los datos equivale al acceso al directorio local del
  workspace (`.kogniterm/`), con el mismo nivel de privilegio del proceso.
- No hay tenants ni RBAC en uso.

**Mitigaciones vigentes:**

1. Nunca exponer Chroma como servicio HTTP (no hay ninguna invocación de
   `chroma run` ni `chromadb.HttpClient` en el código).
2. La ruta de la base de datos vive dentro del workspace del proyecto
   (`.kogniterm/`), heredando el sandbox de permisos del usuario.

**Cuándo reevaluar:** si se actualiza a una versión con parche (>= 1.6.x
que corrija las alertas), o si en algún momento se añade un modo cliente/
servidor compartido entre máquinas — en ese caso el riesgo deja de ser
aceptable y hay que repasar la autenticación del servidor Chroma.
