#!/usr/bin/env python3
"""
Entry point para lanzar el KogniTerm Server desde la línea de comandos.

Uso:
    python -m kogniterm.server
    python -m kogniterm.server --host 0.0.0.0 --port 8765
    python -m kogniterm.server --reload   # modo desarrollo
    kogniterm-server                       # si se instala con pip install -e .
"""

import argparse
from kogniterm.server.app import run_server


def main():
    parser = argparse.ArgumentParser(
        prog="kogniterm-server",
        description="KogniTerm Backend API — Servidor persistente multi-canal",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host de escucha (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Puerto (default: 8765)")
    parser.add_argument("--reload", action="store_true", help="Hot-reload (solo desarrollo)")
    parser.add_argument("--workspace", "--cwd", default=None, help="Directorio de trabajo / workspace inicial")
    args = parser.parse_args()

    print(f"🚀 Iniciando KogniTerm Server en http://{args.host}:{args.port}")
    print(f"   Docs: http://localhost:{args.port}/docs")
    print(f"   WS:   ws://localhost:{args.port}/ws/<session_id>")
    print(f"   SSE:  http://localhost:{args.port}/sse/<session_id>?message=...")
    run_server(host=args.host, port=args.port, reload=args.reload, workspace=args.workspace)



if __name__ == "__main__":
    main()
