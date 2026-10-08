"""Runner backend Desktop — reutiliza kogniterm/server/app.py sin duplicar lógica."""
import argparse
import os
import sys

# permitir `python3 apps/backend/run.py` desde la carpeta v3
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ROOT = kogniterm-desktop/ -> parent = repo root (Gemini-Interpreter)
REPO = os.path.dirname(ROOT)
if REPO not in sys.path:
    sys.path.insert(0, REPO)
if os.path.join(REPO) not in sys.path:
    sys.path.insert(0, os.path.join(REPO))

import uvicorn


def main():
    p = argparse.ArgumentParser(description="KogniTerm Desktop backend (nativo)")
    p.add_argument("--host", default=os.environ.get("KOGNITERM_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("KOGNITERM_PORT", "8755")))
    p.add_argument("--reload", action="store_true", default=False)
    args = p.parse_args()

    from kogniterm.server.app import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
