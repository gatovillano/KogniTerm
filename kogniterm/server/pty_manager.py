"""
PTY Manager para KogniTerm Server.
Provee soporte para terminales interactivos pseudo-terminal (PTY) reales
compatibles con xterm.js / Ghostty y con el frontend Desktop (OpenCode / KogniTerm Desktop).
"""

from __future__ import annotations

import asyncio
import errno
import fcntl
import logging
import os
import pty
import shutil
import struct
import subprocess
import termios
import uuid
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("kogniterm.server.pty")


class PTYProcess:
    def __init__(
        self,
        pty_id: str,
        master_fd: int,
        pid: int,
        cwd: str,
        shell: str,
        title: str = "Terminal",
        cols: int = 80,
        rows: int = 24,
    ):
        self.pty_id = pty_id
        self.master_fd = master_fd
        self.pid = pid
        self.cwd = cwd
        self.shell = shell
        self.title = title
        self.cols = cols
        self.rows = rows
        self.websockets: Set[WebSocket] = set()
        self.exited = False
        self.exit_code: Optional[int] = None
        self._reader_registered = False

    def resize(self, cols: int, rows: int) -> None:
        """Cambia el tamaño de ventana del PTY."""
        self.cols = cols
        self.rows = rows
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            logger.debug(f"[PTY:{self.pty_id}] Resize to {cols}x{rows}")
        except Exception as e:
            logger.warning(f"[PTY:{self.pty_id}] Error en resize: {e}")

    def write(self, data: bytes) -> None:
        """Escribe datos recibidos de la WebSocket en el master_fd."""
        if self.exited:
            return
        try:
            os.write(self.master_fd, data)
        except OSError as e:
            if e.errno != errno.EIO:
                logger.warning(f"[PTY:{self.pty_id}] Error escribiendo en PTY: {e}")

    def kill(self) -> None:
        """Termina el proceso del shell y cierra los descriptores."""
        self.exited = True
        try:
            import signal
            os.killpg(os.getpgid(self.pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(self.pid, 15)
            except Exception:
                pass
        try:
            os.close(self.master_fd)
        except Exception:
            pass


class PTYManager:
    _instance: Optional[PTYManager] = None

    def __init__(self):
        self._ptys: Dict[str, PTYProcess] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> PTYManager:
        if cls._instance is None:
            cls._instance = PTYManager()
        return cls._instance

    def _resolve_shell(self, requested_shell: Optional[str] = None) -> str:
        if requested_shell and os.path.exists(requested_shell):
            return requested_shell
        env_shell = os.environ.get("SHELL")
        if env_shell and os.path.exists(env_shell):
            return env_shell
        for s in ["/bin/bash", "/usr/bin/bash", "/bin/zsh", "/usr/bin/zsh", "/bin/sh"]:
            if os.path.exists(s):
                return s
        return "/bin/sh"

    async def create_pty(
        self,
        pty_id: Optional[str] = None,
        cwd: Optional[str] = None,
        shell: Optional[str] = None,
        title: Optional[str] = None,
        cols: int = 80,
        rows: int = 24,
    ) -> PTYProcess:
        pty_id = pty_id or str(uuid.uuid4())
        shell_path = self._resolve_shell(shell)
        cwd_path = os.path.abspath(os.path.expanduser(cwd or os.getcwd()))
        if not os.path.isdir(cwd_path):
            cwd_path = os.getcwd()

        master_fd, slave_fd = pty.openpty()

        # Establecer tamaño inicial
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

        # Preparar entorno para terminal interactivo
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["LANG"] = "en_US.UTF-8" if "LANG" not in env else env["LANG"]

        proc = subprocess.Popen(
            [shell_path],
            preexec_fn=os.setsid,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=cwd_path,
            env=env,
            close_fds=True,
        )
        os.close(slave_fd)

        pty_proc = PTYProcess(
            pty_id=pty_id,
            master_fd=master_fd,
            pid=proc.pid,
            cwd=cwd_path,
            shell=shell_path,
            title=title or os.path.basename(shell_path),
            cols=cols,
            rows=rows,
        )

        loop = asyncio.get_event_loop()

        def _on_readable():
            try:
                data = os.read(master_fd, 4096)
                if not data:
                    self._on_pty_exit(pty_id, 0)
                    return
                # Decodificar texto para clientes WebSocket (ghostty/xterm esperan string)
                text = data.decode("utf-8", errors="replace")
                # Broadcast a todos los WebSockets conectados
                to_remove = set()
                for ws in list(pty_proc.websockets):
                    try:
                        asyncio.create_task(ws.send_text(text))
                    except Exception:
                        to_remove.add(ws)
                for ws in to_remove:
                    pty_proc.websockets.discard(ws)
            except OSError as err:
                if err.errno == errno.EIO:
                    self._on_pty_exit(pty_id, 0)
                else:
                    logger.debug(f"[PTY:{pty_id}] OSError reading master_fd: {err}")
                    self._on_pty_exit(pty_id, 1)

        loop.add_reader(master_fd, _on_readable)
        pty_proc._reader_registered = True

        async with self._lock:
            self._ptys[pty_id] = pty_proc

        logger.info(f"[PTY:{pty_id}] Proceso PTY iniciado (PID {proc.pid}) en '{cwd_path}' con shell '{shell_path}'")
        return pty_proc

    def _on_pty_exit(self, pty_id: str, exit_code: int):
        proc = self._ptys.get(pty_id)
        if not proc:
            return
        proc.exited = True
        proc.exit_code = exit_code
        loop = asyncio.get_event_loop()
        if proc._reader_registered:
            try:
                loop.remove_reader(proc.master_fd)
            except Exception:
                pass
            proc._reader_registered = False

        # Cerrar sockets con código limpio
        for ws in list(proc.websockets):
            try:
                asyncio.create_task(ws.close(code=1000))
            except Exception:
                pass
        proc.websockets.clear()
        logger.info(f"[PTY:{pty_id}] Proceso PTY finalizado con código {exit_code}")

    async def get_pty(self, pty_id: str) -> Optional[PTYProcess]:
        async with self._lock:
            return self._ptys.get(pty_id)

    async def list_ptys(self) -> list[dict]:
        async with self._lock:
            return [
                {
                    "id": p.pty_id,
                    "title": p.title,
                    "shell": p.shell,
                    "cwd": p.cwd,
                    "cols": p.cols,
                    "rows": p.rows,
                    "status": "exited" if p.exited else "running",
                }
                for p in self._ptys.values()
            ]

    async def resize_pty(self, pty_id: str, cols: int, rows: int) -> bool:
        proc = await self.get_pty(pty_id)
        if not proc or proc.exited:
            return False
        proc.resize(cols, rows)
        return True

    async def kill_pty(self, pty_id: str) -> bool:
        async with self._lock:
            proc = self._ptys.pop(pty_id, None)
        if not proc:
            return False
        loop = asyncio.get_event_loop()
        if proc._reader_registered:
            try:
                loop.remove_reader(proc.master_fd)
            except Exception:
                pass
            proc._reader_registered = False
        proc.kill()
        return True

    async def handle_websocket(self, websocket: WebSocket, pty_id: str, directory: Optional[str] = None):
        """Maneja la conexión WebSocket bidireccional para xterm.js / Ghostty."""
        await websocket.accept()
        proc = await self.get_pty(pty_id)
        if not proc or proc.exited:
            # Crear automáticamente si no existe para ese id
            proc = await self.create_pty(pty_id=pty_id, cwd=directory)

        proc.websockets.add(websocket)
        logger.info(f"[PTY:{pty_id}] Cliente WebSocket conectado. Total activos: {len(proc.websockets)}")

        try:
            while True:
                msg = await websocket.receive()
                if "text" in msg and msg["text"]:
                    data = msg["text"].encode("utf-8")
                    proc.write(data)
                elif "bytes" in msg and msg["bytes"]:
                    proc.write(msg["bytes"])
                elif msg.get("type") == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f"[PTY:{pty_id}] WebSocket exception: {e}")
        finally:
            proc.websockets.discard(websocket)
            logger.info(f"[PTY:{pty_id}] Cliente WebSocket desconectado.")


pty_manager = PTYManager.get_instance()
