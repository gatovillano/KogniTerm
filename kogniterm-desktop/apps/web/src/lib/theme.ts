import { createSignal } from "solid-js";
import type { ITheme } from "@xterm/xterm";

export type Theme = "dark" | "light";

export const XTERM_THEME_DARK: ITheme = {
  background: "#08080a",
  foreground: "#f4f4f5",
  cursor: "#e4e4e7",
  selectionBackground: "rgba(255, 255, 255, 0.28)",
};

export const XTERM_THEME_LIGHT: ITheme = {
  background: "#fafafa",
  foreground: "#18181b",
  cursor: "#18181b",
  cursorAccent: "#fafafa",
  selectionBackground: "rgba(24, 24, 27, 0.18)",
  black: "#18181b",
  red: "#dc2626",
  green: "#15803d",
  yellow: "#b45309",
  blue: "#1d4ed8",
  magenta: "#9333ea",
  cyan: "#0369a1",
  white: "#52525b",
  brightBlack: "#71717a",
  brightRed: "#b91c1c",
  brightGreen: "#166534",
  brightYellow: "#92400e",
  brightBlue: "#1e40af",
  brightMagenta: "#7e22ce",
  brightCyan: "#075985",
  brightWhite: "#27272a",
};

export function getXtermTheme(t: Theme = theme()): ITheme {
  return t === "light" ? XTERM_THEME_LIGHT : XTERM_THEME_DARK;
}

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
