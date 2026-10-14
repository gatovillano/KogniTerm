import { createSignal } from "solid-js";

export type Theme = "dark" | "light";

const KEY = "kogniterm-theme";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* localStorage no disponible */
  }
  return "dark";
}

function applyTheme(t: Theme) {
  const root = document.documentElement;
  root.dataset.theme = t;
  root.style.colorScheme = t;
  try {
    localStorage.setItem(KEY, t);
  } catch {
    /* ignorar */
  }
}

const [theme, setThemeSignal] = createSignal<Theme>(
  typeof document !== "undefined" ? (document.documentElement.dataset.theme as Theme) || initialTheme() : "dark",
);

export function initTheme() {
  const t = initialTheme();
  setThemeSignal(t);
  applyTheme(t);
}

export function setTheme(t: Theme) {
  setThemeSignal(t);
  applyTheme(t);
}

export function toggleTheme() {
  setTheme(theme() === "dark" ? "light" : "dark");
}

export { theme };
