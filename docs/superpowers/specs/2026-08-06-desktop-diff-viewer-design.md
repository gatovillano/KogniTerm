# Especificación de Diseño: Visor Gráfico de Diffs Aplicados en KogniTerm Desktop

## Visión General
Implementar un sistema visual completo para mostrar los Diffs una vez aplicadas las ediciones en el cliente Desktop de KogniTerm (`kogniterm-desktop`). Este sistema incluye una tarjeta visual interactiva (`AppliedDiffCard`) integrada en el flujo de chat y una pestaña dedicada en el panel lateral derecho (`RightSidebar`) para explorar el historial de ediciones aplicadas durante la sesión.

---

## Componentes y Arquitectura Frontend

### 1. Tipos de Datos (`types/chat.ts`)
Se define la interfaz `AppliedDiff`:
```typescript
export interface AppliedDiff {
    id: string;
    filePath: string;
    toolName?: string;
    diffContent: string;
    additions: number;
    deletions: number;
    timestamp: number;
}
```

### 2. Componente Visual de Diff Aplicado (`AppliedDiffCard.tsx`)
Ubicación: `kogniterm-desktop/apps/desktop/src/components/chat/AppliedDiffCard.tsx`

**Características UI:**
- **Header:** Nombre del archivo con icono `FileCode`, etiqueta/badge del nombre de la herramienta (ej. `replace_file_content`, `write_to_file`), y estado `[Editado]`.
- **Barra/Gráfica de Estadísticas:**
  - Chip verde `+X` (líneas añadidas) y chip rojo `-Y` (líneas eliminadas).
  - Barra de proporción visual (porcentaje verde/rojo según adiciones vs eliminaciones).
- **Visor de Código Diff:**
  - Formato unified diff con resaltado de líneas:
    - Líneas `+` en verde (`text-emerald-400 bg-emerald-500/10`)
    - Líneas `-` en rojo (`text-rose-400 bg-rose-500/10`)
    - Cabeceras `@` / `@@` en índigo (`text-indigo-400 bg-indigo-500/10`)
  - Numeración y formateo con fuente monoespaciada limpia.
- **Acciones:**
  - Botón colapsar/expandir el bloque de código.
  - Botón para copiar el contenido del Diff al portapapeles.

### 3. Pestaña e Historial en Sidebar Derecho (`DiffSidebar.tsx` & `RightSidebar.tsx`)
Ubicaciones:
- `kogniterm-desktop/apps/desktop/src/components/chat/DiffSidebar.tsx`
- `kogniterm-desktop/apps/desktop/src/components/chat/RightSidebar.tsx`

**Características UI:**
- Nueva pestaña con icono `FileDiff` / `GitCompare` en `RightSidebar`.
- Badge indicador numérico con el número total de Diffs aplicados en la sesión.
- Lista cronológica filtrable de todos los `AppliedDiffCard` aplicados.
- Buscador rápido por nombre de archivo.

### 4. Integración en Estado y Conversación (`useChat.ts` & `ChatMessage.tsx`)
- En `useChat.ts`:
  - Se agrega el estado `appliedDiffs: AppliedDiff[]`.
  - Al recibir eventos WebSocket `tool_result` o `approval_response` (cuando un diff es aprobado y ejecutado), se analiza si el contenido contiene un diff unificado o metadatos de edición de archivos.
  - Parsea el contenido, calcula el recuento de adiciones/eliminaciones y registra el `AppliedDiff`.
- En `ChatMessage.tsx`:
  - Cuando un mensaje de rol `tool` contiene un diff aplicado, detecta el formato y renderiza el componente `AppliedDiffCard` enriquecido en lugar del bloque de texto plano `Resultado de Herramienta`.

---

## Verificación y Pruebas
1. **Pruebas de renderizado UI:** Verificar que `AppliedDiffCard` calcule correctamente las adiciones/eliminaciones y renderice las líneas coloreadas.
2. **Pruebas de integración WebSocket:** Verificar que los mensajes de resultado de herramienta con diffs actualicen tanto el chat como la pestaña de Diffs del Sidebar en tiempo real.
3. **Pruebas de interacción:** Probar el colapso/expansión, filtrado en el sidebar y copia al portapapeles.
