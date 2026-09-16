/**
 * Configuración centralizada de endpoints de API y WebSocket para KogniTerm Desktop y Web.
 * Detecta dinámicamente el host del navegador para funcionar indistintamente en
 * localhost, 127.0.0.1, IP de red local o el contenedor de Tauri.
 */

export const getBackendHost = (): string => {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const host = window.location.hostname;
    // En Tauri, el hostname puede ser 'tauri.localhost' o similar; en ese caso usar 127.0.0.1
    if (host !== 'tauri.localhost' && host !== '') {
      return host;
    }
  }
  return '127.0.0.1';
};

export const BACKEND_PORT = 8765;

export const getApiBaseUrl = (): string => {
  return `http://${getBackendHost()}:${BACKEND_PORT}`;
};

export const getWsBaseUrl = (): string => {
  return `ws://${getBackendHost()}:${BACKEND_PORT}`;
};

export const API_BASE_URL = getApiBaseUrl();
export const WS_BASE_URL = getWsBaseUrl();
