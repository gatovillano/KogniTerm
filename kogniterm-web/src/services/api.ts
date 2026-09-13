const API_BASE = '/api';

export async function checkServerHealth(): Promise<boolean> {
  try {
    const res = await fetch('/api/threads', { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

export async function sendChatMessage(sessionId: string, message: string, agent: string, model: string) {
  try {
    const res = await fetch(`/api/chat/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, agent, model })
    });
    if (!res.ok) throw new Error('Error en respuesta del servidor');
    return await res.json();
  } catch (err) {
    console.warn('Backend REST no disponible, usando modo simulado inteligente:', err);
    return null;
  }
}

export function createSessionWebSocket(sessionId: string, onMessage: (data: any) => void): WebSocket | null {
  try {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        onMessage({ text: event.data });
      }
    };
    return ws;
  } catch (err) {
    console.warn('No se pudo establecer WebSocket con el servidor:', err);
    return null;
  }
}
