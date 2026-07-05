#!/usr/bin/env python3
"""
Entry point para lanzar el KogniTerm Server desde la línea de comandos.

Uso:
    python -m kogniterm.server
    python -m kogniterm.server --host 0.0.0.0 --port 8765
    python -m kogniterm.server --reload   # modo desarrollo
    kogniterm-server                       # si se instala con pip install -e .
"""

import sys
import os
import signal
import time
import subprocess
from pathlib import Path
import argparse
from kogniterm.server.app import run_server


def is_running(pid: int) -> bool:
    """Verifica si un proceso con el PID dado está en ejecución."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_kogniterm_process(pid: int) -> bool:
    """Verifica si el proceso parece ser de KogniTerm para evitar matar procesos ajenos."""
    try:
        cmdline_path = f"/proc/{pid}/cmdline"
        if os.path.exists(cmdline_path):
            with open(cmdline_path, "rb") as f:
                cmdline = f.read().decode("utf-8", errors="ignore")
                # Verificamos si contiene palabras clave del servidor
                return "kogniterm" in cmdline or "python" in cmdline
    except Exception:
        pass
    return True  # Retorna True por defecto si no se puede leer (ej. macOS/Windows o permisos)


def find_pid_by_port(port: int) -> list[int]:
    """Busca PIDs de procesos que estén escuchando en el puerto tcp especificado."""
    # Intentamos con lsof
    try:
        output = subprocess.check_output(["lsof", "-t", "-i", f"tcp:{port}"], stderr=subprocess.DEVNULL)
        pids = [int(p.strip()) for p in output.decode().splitlines() if p.strip()]
        return pids
    except Exception:
        pass
        
    # Intentamos con fuser
    try:
        output = subprocess.check_output(["fuser", f"{port}/tcp"], stderr=subprocess.DEVNULL)
        pids = [int(p.strip()) for p in output.decode().split() if p.strip()]
        return pids
    except Exception:
        pass
        
    return []


def stop_server(port: int = 8765):
    """Detiene las instancias del servidor KogniTerm que corren en el puerto especificado."""
    pid_file = Path.home() / ".kogniterm" / f"server_{port}.pid"
    pid = None
    
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except Exception:
            pass
            
    pids_to_kill = []
    if pid and is_running(pid) and is_kogniterm_process(pid):
        pids_to_kill.append(pid)
    
    # Fallback: buscar qué PIDs están escuchando en el puerto
    port_pids = find_pid_by_port(port)
    for p in port_pids:
        if p not in pids_to_kill and is_running(p) and is_kogniterm_process(p):
            pids_to_kill.append(p)
            
    if not pids_to_kill:
        print(f"ℹ️ No se detectó ninguna instancia de KogniTerm Server activa en el puerto {port}.")
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass
        return
        
    for p in pids_to_kill:
        print(f"🛑 Deteniendo KogniTerm Server (PID {p}) en el puerto {port}...")
        try:
            os.kill(p, signal.SIGTERM)
        except Exception as e:
            print(f"⚠️ Error al enviar SIGTERM al PID {p}: {e}")
            
    # Esperamos hasta 5 segundos a que terminen
    all_stopped = False
    for _ in range(50):
        if not any(is_running(p) for p in pids_to_kill):
            all_stopped = True
            break
        time.sleep(0.1)
        
    if not all_stopped:
        for p in pids_to_kill:
            if is_running(p):
                print(f"⚠️ El proceso {p} no respondió a SIGTERM, enviando SIGKILL...")
                try:
                    os.kill(p, signal.SIGKILL)
                except Exception:
                    pass
        time.sleep(0.5)
        
    # Verificación final
    still_running = [p for p in pids_to_kill if is_running(p)]
    if not still_running:
        print(f"✔ Servidor en puerto {port} detenido exitosamente.")
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass
    else:
        print(f"❌ No se pudieron detener todos los procesos en el puerto {port}: {still_running}")


def main():
    # Procesar subcomandos de forma compatible
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        parser = argparse.ArgumentParser(
            prog="kogniterm-server stop",
            description="Detiene una instancia en ejecución de KogniTerm Server",
        )
        parser.add_argument("--port", type=int, default=8765, help="Puerto del servidor a detener (default: 8765)")
        args = parser.parse_args(sys.argv[2:])
        stop_server(port=args.port)
        return

    # Si se especificó "start" explícitamente, lo removemos para mantener compatibilidad
    if len(sys.argv) > 1 and sys.argv[1] == "start":
        sys.argv.pop(1)

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
