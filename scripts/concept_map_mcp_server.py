"""
concept-map-mcp — Servidor MCP para generar mapas conceptuales interactivos
en archivos HTML independientes (standalone) usando vis-network.

Stack:
- FastMCP (mcp[cli]) como framework de servidor MCP.
- Pydantic v2 para validación estricta de tipos.
- vis-network vía CDN (unpkg/cdnjs) para renderizado de grafos.
- webbrowser (stdlib) para apertura automática silenciosa.

Uso rápido:
    uv run --with "mcp[cli]" python server.py
"""

from __future__ import annotations

import re
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------

# Carpetas de persistencia: prioridad local, fallback a /tmp.
OUTPUT_DIR = Path("./concept_maps").resolve()
try:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    OUTPUT_DIR = Path("/tmp/concept_maps")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Modelos Pydantic (validación estricta)
# ---------------------------------------------------------------------------


class ConceptNode(BaseModel):
    """Un nodo del mapa conceptual."""

    id: str | int = Field(..., description="Identificador único del nodo")
    label: str = Field(..., min_length=1, description="Texto visible del nodo")
    group: str | None = Field(
        default=None, description="Categoría para asignar color"
    )
    description: str | None = Field(
        default=None, description="Texto explicativo para el tooltip/hover"
    )

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("label no puede estar en blanco")
        return v.strip()


class ConceptEdge(BaseModel):
    """Una arista dirigida del mapa conceptual."""

    from_node: str | int = Field(..., description="ID del nodo origen")
    to_node: str | int = Field(..., description="ID del nodo destino")
    label: str | None = Field(
        default=None, description="Verbo o frase que describe la relación"
    )

    @field_validator("label")
    @classmethod
    def _label_strip(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v


# ---------------------------------------------------------------------------
# Paletas de color por grupo
# ---------------------------------------------------------------------------

GROUP_PALETTES: dict[str, dict[str, str]] = {
    # Clases / Módulos — azul violeta
    "clase": {"bg": "#6366f1", "border": "#818cf8", "highlight": "#a5b4fc"},
    "clases": {"bg": "#6366f1", "border": "#818cf8", "highlight": "#a5b4fc"},
    "modulo": {"bg": "#6366f1", "border": "#818cf8", "highlight": "#a5b4fc"},
    "módulo": {"bg": "#6366f1", "border": "#818cf8", "highlight": "#a5b4fc"},
    "modulos": {"bg": "#6366f1", "border": "#818cf8", "highlight": "#a5b4fc"},
    "módulos": {"bg": "#6366f1", "border": "#818cf8", "highlight": "#a5b4fc"},
    "base_datos": {"bg": "#6366f1", "border": "#818cf8", "highlight": "#a5b4fc"},
    # Funciones / Acciones — verde esmeralda
    "función": {"bg": "#10b981", "border": "#34d399", "highlight": "#6ee7b7"},
    "funcion": {"bg": "#10b981", "border": "#34d399", "highlight": "#6ee7b7"},
    "funciones": {"bg": "#10b981", "border": "#34d399", "highlight": "#6ee7b7"},
    "acción": {"bg": "#10b981", "border": "#34d399", "highlight": "#6ee7b7"},
    "accion": {"bg": "#10b981", "border": "#34d399", "highlight": "#6ee7b7"},
    "acciones": {"bg": "#10b981", "border": "#34d399", "highlight": "#6ee7b7"},
    # Conceptos / Variables — ámbar
    "concepto": {"bg": "#f59e0b", "border": "#fbbf24", "highlight": "#fcd34d"},
    "conceptos": {"bg": "#f59e0b", "border": "#fbbf24", "highlight": "#fcd34d"},
    "variable": {"bg": "#f59e0b", "border": "#fbbf24", "highlight": "#fcd34d"},
    "variables": {"bg": "#f59e0b", "border": "#fbbf24", "highlight": "#fcd34d"},
    # Advertencias / Dependencias críticas — rojo coral
    "advertencia": {
        "bg": "#f43f5e",
        "border": "#fb7185",
        "highlight": "#fda4af",
    },
    "advertencias": {
        "bg": "#f43f5e",
        "border": "#fb7185",
        "highlight": "#fda4af",
    },
    "peligro": {"bg": "#f43f5e", "border": "#fb7185", "highlight": "#fda4af"},
    "critico": {"bg": "#f43f5e", "border": "#fb7185", "highlight": "#fda4af"},
    "crítico": {"bg": "#f43f5e", "border": "#fb7185", "highlight": "#fda4af"},
    "critica": {"bg": "#f43f5e", "border": "#fb7185", "highlight": "#fda4af"},
    "crítica": {"bg": "#f43f5e", "border": "#fb7185", "highlight": "#fda4af"},
}

# Paleta por defecto (galaxia / cian índigo)
FALLBACK_GROUP = {"bg": "#3b82f6", "border": "#60a5fa", "highlight": "#93c5fd"}

# ---------------------------------------------------------------------------
# Helper de sanitización
# ---------------------------------------------------------------------------


def _slugify(value: str) -> str:
    """Convierte un texto en un nombre de archivo seguro (slug)."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "mapa"


# ---------------------------------------------------------------------------
# Plantilla HTML (standalone)
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE_HTML__</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
  rel="stylesheet"
/>
<script
  type="text/javascript"
  src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"
></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg: #0f172a;
    --surface: rgba(255, 255, 255, 0.06);
    --surface-strong: rgba(30, 41, 59, 0.72);
    --border: rgba(255, 255, 255, 0.12);
    --text: #f8fafc;
    --text-dim: #94a3b8;
    --accent: #818cf8;
    --accent-2: #38bdf8;
  }

  html, body {
    height: 100%;
    overflow: hidden;
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
  }

  /* Fondo con gradiente suave + cuadrícula sutil */
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: 0;
    background:
      radial-gradient(1000px 500px at 75% -10%, rgba(99, 102, 241, 0.18), transparent 60%),
      radial-gradient(800px 400px at 10% 110%, rgba(56, 189, 248, 0.14), transparent 60%),
      linear-gradient(rgba(148, 163, 184, 0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(148, 163, 184, 0.04) 1px, transparent 1px);
    background-size: 100% 100%, 100% 100%, 44px 44px, 44px 44px;
    pointer-events: none;
  }

  #network {
    position: fixed;
    inset: 0;
    z-index: 1;
  }

  /* ── Overlay flotante (glassmorphism) ─────────────────────────── */
  .toolbar {
    position: fixed;
    top: 18px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 18px;
    border-radius: 16px;
    background: var(--surface-strong);
    border: 1px solid var(--border);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 12px 32px rgba(2, 6, 23, 0.45);
    max-width: calc(100vw - 32px);
    flex-wrap: wrap;
    justify-content: center;
  }

  .toolbar h1 {
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 260px;
  }

  .stats {
    display: flex;
    gap: 8px;
    font-size: 0.78rem;
    color: var(--text-dim);
    white-space: nowrap;
  }

  .stats .chip {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 3px 10px;
  }

  .stats b { color: var(--text); font-weight: 600; }

  .sep {
    width: 1px;
    height: 22px;
    background: var(--border);
  }

  .btn-group { display: flex; gap: 8px; }

  .btn {
    appearance: none;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    font-family: inherit;
    font-size: 0.8rem;
    font-weight: 500;
    padding: 7px 14px;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease, transform 0.05s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }

  .btn:hover { background: rgba(255, 255, 255, 0.12); border-color: rgba(255, 255, 255, 0.2); }
  .btn:active { transform: translateY(1px); }
  .btn.primary { background: var(--accent); border-color: var(--accent); color: #0b1020; }
  .btn.primary:hover { background: #a5b4fc; border-color: #a5b4fc; }

  /* Tooltip del nodo (vis-network) */
  .vis-tooltip {
    position: absolute;
    background: rgba(15, 23, 42, 0.95) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
    font-family: inherit !important;
    font-size: 0.78rem !important;
    padding: 8px 12px !important;
    box-shadow: 0 10px 24px rgba(2, 6, 23, 0.5) !important;
    max-width: 260px;
    line-height: 1.45;
  }
</style>
</head>
<body>

<div id="network"></div>

<div class="toolbar">
  <h1 title="__TITLE_HTML__">__TITLE_HTML__</h1>
  <div class="stats">
    <span class="chip">🧩 <b id="statNodes">0</b> nodos</span>
    <span class="chip">🔗 <b id="statEdges">0</b> relaciones</span>
  </div>
  <div class="sep"></div>
  <div class="btn-group">
    <button class="btn" id="btnFit" title="Centrar la vista">⛶ Centrar vista</button>
    <button class="btn" id="btnPhysics" title="Fijar / soltar la física">⏸ Fijar física</button>
    <button class="btn primary" id="btnPng" title="Exportar el mapa como PNG">⬇ Exportar PNG</button>
  </div>
</div>

<script>
  // ── Datos inyectados por el servidor ─────────────────────────────
  const RAW_NODES = __NODES_JSON__;
  const RAW_EDGES = __EDGES_JSON__;
  const GROUP_COLORS = __GROUP_COLORS_JSON__;

  // ── Traducción de grupos a colores ───────────────────────────────
  function groupColor(group) {
    return GROUP_COLORS[String(group)] || GROUP_COLORS['__default__'];
  }

  // ── Preparar nodos ───────────────────────────────────────────────
  const nodes = RAW_NODES.map(function (n) {
    const c = groupColor(n.group);
    const node = {
      id: n.id,
      label: n.label,
      shape: 'box',
      borderRadius: 8,
      shadow: { enabled: true, color: 'rgba(0,0,0,0.35)', size: 12, x: 0, y: 3 },
      margin: { top: 12, right: 18, bottom: 12, left: 18 },
      font: { color: '#f8fafc', face: 'Inter', size: 14, multi: false },
      color: {
        background: c.bg,
        border: c.border,
        highlight: { background: c.highlight, border: '#ffffff' },
        hover: { background: c.bg, border: '#ffffff' }
      },
      shapeProperties: { borderRadius: 8 }
    };
    if (n.description) node.title = n.description;
    return node;
  });

  // ── Preparar aristas ─────────────────────────────────────────────
  const edges = RAW_EDGES.map(function (e) {
    const edge = {
      from: e.from_node,
      to: e.to_node,
      arrows: { to: { enabled: true, scaleFactor: 0.9 } },
      color: { color: '#64748b', highlight: '#94a3b8', hover: '#94a3b8', opacity: 0.65 },
      smooth: { type: 'continuous', forceDirection: 'none', roundness: 0.5 },
      width: 1.6,
      selectionWidth: 1.5,
      hoverWidth: 1.5,
      font: {
        color: '#e2e8f0',
        face: 'Inter',
        size: 12,
        background: 'rgba(15, 23, 42, 0.85)',
        strokeWidth: 0,
        align: 'middle'
      }
    };
    if (e.label) edge.label = e.label;
    return edge;
  });

  // ── Configuración del grafo ──────────────────────────────────────
  const options = {
    autoResize: true,
    interaction: {
      hover: true,
      tooltipDelay: 120,
      navigationButtons: true,
      keyboard: { enabled: true, bindToWindow: false },
      zoomView: true,
      dragView: true
    },
    physics: {
      enabled: true,
      stabilization: {
        enabled: true,
        iterations: 120,
        updateInterval: 12,
        onlyDynamicEdges: false,
        fit: true
      },
      barnesHut: {
        gravitationalConstant: -4200,
        centralGravity: 0.32,
        springLength: 130,
        springConstant: 0.04,
        damping: 0.09,
        avoidOverlap: 0.45
      }
    }
  };

  // ── Instanciar la red ────────────────────────────────────────────
  const container = document.getElementById('network');
  const network = new vis.Network(container, { nodes, edges }, options);

  // Actualizar contadores
  document.getElementById('statNodes').textContent = nodes.length;
  document.getElementById('statEdges').textContent = edges.length;

  // ── Botones de acción ────────────────────────────────────────────
  let physicsFrozen = false;

  document.getElementById('btnFit').addEventListener('click', function () {
    network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
  });

  document.getElementById('btnPhysics').addEventListener('click', function () {
    physicsFrozen = !physicsFrozen;
    network.setOptions({ physics: { enabled: !physicsFrozen } });
    const b = document.getElementById('btnPhysics');
    b.textContent = physicsFrozen ? '▶ Soltar física' : '⏸ Fijar física';
  });

  document.getElementById('btnPng').addEventListener('click', function () {
    network.setOptions({ physics: { enabled: false } });
    try {
      const dataUrl = network.canvas.getCanvas().toDataURL('image/png');
      const a = document.createElement('a');
      a.href = dataUrl;
      const title = document.title.replace(/[^\w\-]+/g, '_').toLowerCase();
      a.download = (title || 'concept_map') + '.png';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      alert('No se pudo exportar el PNG: ' + err);
    }
  });

  // Al terminar la estabilización, centrar la vista
  network.once('stabilized', function () {
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
  });
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Aplicación FastMCP
# ---------------------------------------------------------------------------

mcp = FastMCP("concept-map-mcp")


@mcp.tool()
def generate_concept_map(
    title: str = Field(..., description="Título principal del mapa conceptual"),
    nodes: list[ConceptNode] = Field(
        ..., description="Lista de nodos del mapa conceptual"
    ),
    edges: list[ConceptEdge] = Field(
        default_factory=list, description="Lista de enlaces dirigidos"
    ),
    output_filename: str | None = Field(
        default=None,
        description="Nombre del archivo (ej. auth_flow.html). "
        "Si se omite, se genera automáticamente desde el título + timestamp",
    ),
    auto_open: bool = Field(
        default=True,
        description="Si es True, abre el archivo en el navegador predeterminado",
    ),
) -> str:
    """Genera un mapa conceptual interactivo (HTML standalone) a partir de una
    estructura de grafo (nodos y aristas).

    El archivo resultante es autocontenido (usa vis-network vía CDN), con tema
    oscuro moderno, paleta de colores por grupo, panel de control flotante con
    glassmorphism, y botones para centrar vista, fijar/soltar física y exportar
    PNG. Devuelve la ruta absoluta (file://), el resumen métrico y la
    confirmación de apertura en el navegador.
    """
    # Validar unicidad de IDs y referencias de aristas
    node_ids: set[str | int] = set()
    for node in nodes:
        if node.id in node_ids:
            raise ValueError(f"ID de nodo duplicado: {node.id!r}")
        node_ids.add(node.id)

    sanitized_edges: list[ConceptEdge] = []
    for edge in edges:
        if edge.from_node not in node_ids:
            raise ValueError(
                f"La arista {edge.from_node!r} -> {edge.to_node!r} "
                f"referencia un origen inexistente: {edge.from_node!r}"
            )
        if edge.to_node not in node_ids:
            raise ValueError(
                f"La arista {edge.from_node!r} -> {edge.to_node!r} "
                f"referencia un destino inexistente: {edge.to_node!r}"
            )
        sanitized_edges.append(edge)

    if not nodes:
        raise ValueError("Debe incluirse al menos un nodo")

    # Calcular los colores por grupo presentes (más el fallback)
    used_groups: set[str] = {str(n.group) for n in nodes if n.group}
    group_colors: dict[str, dict[str, str]] = {
        "__default__": FALLBACK_GROUP
    }
    for g in used_groups:
        group_colors[g] = GROUP_PALETTES.get(g, FALLBACK_GROUP)

    # Resolver nombre de archivo de salida
    if output_filename and output_filename.strip():
        filename = output_filename.strip()
        if not filename.lower().endswith(".html"):
            filename += ".html"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{_slugify(title)}_{timestamp}.html"

    output_path = OUTPUT_DIR / filename

    # Datos JSON para inyección en el HTML
    nodes_json = (
        "["
        + ",".join(
            '{"id": %s, "label": %s%s, "group": %s, "description": %s}'
            % (
                _js_json(n.id),
                _js_json(n.label),
                "",
                _js_json(n.group),
                _js_json(n.description),
            )
            for n in nodes
        )
        + "]"
    )
    edges_json = (
        "["
        + ",".join(
            '{"from_node": %s, "to_node": %s, "label": %s}'
            % (_js_json(e.from_node), _js_json(e.to_node), _js_json(e.label))
            for e in sanitized_edges
        )
        + "]"
    )
    group_colors_json = _js_json(group_colors)

    html = (
        HTML_TEMPLATE.replace("__TITLE_HTML__", _html_escape(title))
        .replace("__NODES_JSON__", nodes_json)
        .replace("__EDGES_JSON__", edges_json)
        .replace("__GROUP_COLORS_JSON__", group_colors_json)
    )

    output_path.write_text(html, encoding="utf-8")

    # Apertura automática (silenciosa ante errores)
    opened = False
    if auto_open:
        try:
            opened = webbrowser.open(output_path.as_uri())
        except Exception:
            opened = False

    # Resumen métrico
    total_nodes = len(nodes)
    total_edges = len(sanitized_edges)
    summary = (
        f"✅ Mapa conceptual generado: **{title}**\n"
        f"📄 Archivo: `file://{output_path}`\n"
        f"📊 Resumen métrico: **{total_nodes} nodos**, **{total_edges} conexiones**\n"
        f"🌐 Abierto en el navegador: **{'Sí' if opened else 'No'}**"
    )
    return summary


def _js_json(value: Any) -> str:
    """Serializa un valor a JSON válido (para inyección segura en JS)."""
    if value is None:
        return "null"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    # Para strings y demás: JSON con comillas dobles
    import json

    return json.dumps(str(value), ensure_ascii=False)


def _html_escape(value: str) -> str:
    """Escapa texto para uso seguro en HTML."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


if __name__ == "__main__":
    mcp.run()
