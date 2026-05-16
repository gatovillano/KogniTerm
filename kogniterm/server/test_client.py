#!/usr/bin/env python3
"""
Cliente de prueba para KogniTerm Server API.

Uso:
    python -m kogniterm.server.test_client [--ws | --sse | --rest] --message "Hola"

Requiere que el servidor esté corriendo:
    python -m kogniterm.server --host 0.0.0.0 --port 8765
"""

import argparse
import asyncio
import json
import httpx
import websockets


API_BASE = "http://localhost:8765"
WS_BASE  = "ws://localhost:8765"


async def test_health():
    """Verifica el estado del servidor."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/health")
        print("── Health ──────────────────────────────")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))


async def test_websocket(session_id: str, message: str):
    """Prueba el canal WebSocket con streaming en tiempo real."""
    uri = f"{WS_BASE}/ws/{session_id}"
    print(f"── WebSocket → {uri}")
    print(f"Mensaje: {message}\n")

    async with websockets.connect(uri) as ws:
        # Esperar confirmación de conexión
        welcome = json.loads(await ws.recv())
        print(f"[Conectado] {welcome}")

        # Enviar mensaje
        await ws.send(json.dumps({"type": "message", "text": message}))

        # Recibir eventos en tiempo real
        print("\n── Respuesta ──────────────────────────")
        async for raw in ws:
            event = json.loads(raw)
            t = event["type"]
            d = event["data"]

            if t == "stream":
                print(d, end="", flush=True)
            elif t == "tool_start":
                print(f"\n⚙️  [{d.get('tool')}] {d.get('description','')}")
            elif t == "tool_output":
                print(f"\n📤 {d.get('output','')[:200]}")
            elif t == "message":
                print(f"\n💬 {d.get('text','')}")
            elif t == "done":
                print("\n✅ Completado.")
                break
            elif t == "error":
                print(f"\n❌ Error: {d}")
                break


async def test_sse(session_id: str, message: str):
    """Prueba el canal SSE."""
    url = f"{API_BASE}/sse/{session_id}"
    print(f"── SSE → {url}")
    print(f"Mensaje: {message}\n── Respuesta ──────────────────────────")

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("GET", url, params={"message": message}) as r:
            async for line in r.aiter_lines():
                if line.startswith("data:"):
                    event = json.loads(line[5:].strip())
                    t = event["type"]
                    d = event["data"]
                    if t == "stream":
                        print(d, end="", flush=True)
                    elif t == "done":
                        print("\n✅ Completado.")
                        break
                    elif t == "error":
                        print(f"\n❌ {d}")
                        break


async def test_rest(session_id: str, message: str):
    """Prueba el canal REST síncrono."""
    url = f"{API_BASE}/chat/{session_id}"
    print(f"── REST POST → {url}")
    print(f"Mensaje: {message}\n")

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json={"message": message})
        data = r.json()
        print("── Respuesta ──────────────────────────")
        print(data.get("response", "(sin respuesta)"))


async def main():
    parser = argparse.ArgumentParser(description="KogniTerm Server Test Client")
    parser.add_argument("--mode", choices=["ws", "sse", "rest", "health"], default="ws",
                        help="Canal a probar (default: ws)")
    parser.add_argument("--session", default="test-session", help="ID de sesión")
    parser.add_argument("--message", default="¿Cuál es el directorio actual?", help="Mensaje al agente")
    args = parser.parse_args()

    if args.mode == "health":
        await test_health()
    elif args.mode == "ws":
        await test_websocket(args.session, args.message)
    elif args.mode == "sse":
        await test_sse(args.session, args.message)
    elif args.mode == "rest":
        await test_rest(args.session, args.message)


if __name__ == "__main__":
    asyncio.run(main())
