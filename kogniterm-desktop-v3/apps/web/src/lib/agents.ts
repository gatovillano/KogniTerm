import { createResource, createSignal } from "solid-js";
import { createStore } from "solid-js/store";
import { api } from "./api";

export interface NativeAgent {
  id: string;
  name: string;
  description: string;
  engine: string;
}

interface AgentCatalog {
  agents: NativeAgent[];
  default: string;
}

const STORAGE_KEY = "kogniterm-v3-agents";

function readSelected(): Record<string, string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as unknown;
    if (parsed && typeof parsed === "object") {
      return Object.fromEntries(
        Object.entries(parsed as Record<string, unknown>).filter(
          (entry): entry is [string, string] => typeof entry[1] === "string",
        ),
      );
    }
  } catch {
    /* Si el almacenamiento local está corrupto, se reconstruye vacío. */
  }
  return {};
}

const [catalog, setCatalog] = createSignal<AgentCatalog | null>(null);
const [catalogError, setCatalogError] = createSignal("");
const [loading, setLoading] = createSignal(false);
const [selectedByTab, setSelectedByTab] = createStore<Record<string, string>>(readSelected());
let inflight: Promise<void> | null = null;

function persistSelection() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedByTab));
  } catch {
    /* La selección puede seguir usándose en memoria. */
  }
}

async function loadCatalog(): Promise<void> {
  setLoading(true);
  try {
    const response = await api.listAgents();
    const agents = Array.isArray(response.agents) ? response.agents : [];
    setCatalog({ agents, default: response.default });
    setCatalogError("");
  } catch (error) {
    setCatalog(null);
    setCatalogError(error instanceof Error ? error.message : String(error));
  } finally {
    setLoading(false);
  }
}

/**
 * Catálogo nativo de agentes. Solo cuando está disponible se puede enviar;
 * así el selector visible y el motor usado nunca se desincronizan.
 */
export const agents = {
  catalog,
  loading,
  error: catalogError,
  ensureAgents(force = false): Promise<void> {
    if (catalog() && !force) return Promise.resolve();
    if (!inflight) {
      inflight = loadCatalog().finally(() => {
        inflight = null;
      });
    }
    return inflight;
  },
  selected(tabId: string): NativeAgent | undefined {
    const current = catalog();
    if (!current) return undefined;
    const selectedId = selectedByTab[tabId] ?? current.default;
    return current.agents.find((agent: NativeAgent) => agent.id === selectedId);
  },
  byId(id: string | undefined): NativeAgent | undefined {
    if (!id) return undefined;
    return catalog()?.agents.find((agent: NativeAgent) => agent.id === id);
  },
  select(tabId: string, id: string) {
    const agent = catalog()?.agents.find((candidate: NativeAgent) => candidate.id === id);
    if (!agent) return;
    setSelectedByTab(tabId, agent.id);
    persistSelection();
  },
  applyServerAgent(tabId: string, id: unknown) {
    if (typeof id !== "string") return;
    const agent = catalog()?.agents.find((candidate: NativeAgent) => candidate.id === id);
    if (!agent) return;
    setSelectedByTab(tabId, agent.id);
    persistSelection();
  },
};

export function useAgents(tabId: string) {
  createResource(() => agents.ensureAgents());
  return {
    catalog: agents.catalog,
    loading: agents.loading,
    error: agents.error,
    selected: () => agents.selected(tabId),
    select: (id: string) => agents.select(tabId, id),
  };
}
