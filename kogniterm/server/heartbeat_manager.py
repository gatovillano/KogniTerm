"""
HeartbeatManager — Gestor de tareas periódicas para KogniTerm Server.

Permite ejecutar de forma independiente y configurable múltiples "heartbeats" (latidos periódicos).
Cada heartbeat tiene un prompt, un intervalo de tiempo (periodicidad) y una sesión destino.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from kogniterm.server.config import server_config, HeartbeatConfig
from kogniterm.server.session_pool import pool

logger = logging.getLogger("kogniterm.server.heartbeat_manager")


class HeartbeatScheduler:
    """
    Gestor de tareas en segundo plano que programa y ejecuta los heartbeats configurados.
    Permite sincronización dinámica cuando se agregan, modifican o deshabilitan heartbeats.
    """

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running: bool = False

    def start(self) -> None:
        """Inicia el planificador de heartbeats."""
        if self._running:
            return
        self._running = True
        logger.info("⏱️  Iniciando HeartbeatScheduler...")
        self.sync_tasks()

    def stop(self) -> None:
        """Detiene de forma limpia todas las tareas de heartbeat en segundo plano."""
        if not self._running:
            return
        self._running = False
        logger.info("🛑 Deteniendo HeartbeatScheduler...")
        for hb_id, task in list(self._tasks.items()):
            task.cancel()
        self._tasks.clear()

    def sync_tasks(self) -> None:
        """
        Sincroniza las tareas asyncio activas con la configuración actual en server_config.
        Cancela tareas eliminadas/deshabilitadas y lanza nuevas tareas para heartbeats activos.
        """
        if not self._running:
            return

        current_heartbeats = {hb.id: hb for hb in server_config.settings.heartbeats}

        # Cancelar tareas de heartbeats eliminados o deshabilitados
        for hb_id in list(self._tasks.keys()):
            hb = current_heartbeats.get(hb_id)
            if not hb or not hb.enabled:
                logger.info(f"⏱️ Cancelando tarea de heartbeat: {hb_id}")
                task = self._tasks.pop(hb_id)
                task.cancel()

        # Iniciar tareas para heartbeats habilitados que aún no tienen tarea en ejecución
        for hb_id, hb in current_heartbeats.items():
            if hb.enabled and hb_id not in self._tasks:
                logger.info(
                    f"⏱️ Programando heartbeat '{hb.name}' ({hb_id}) cada {hb.interval_seconds}s"
                )
                task = asyncio.create_task(self._heartbeat_loop(hb_id))
                self._tasks[hb_id] = task

    async def _heartbeat_loop(self, heartbeat_id: str) -> None:
        """Bucle periódico para un heartbeat específico."""
        while self._running:
            # Obtener configuración fresca
            hb = next((h for h in server_config.settings.heartbeats if h.id == heartbeat_id), None)
            if not hb or not hb.enabled:
                break

            try:
                await asyncio.sleep(hb.interval_seconds)
            except asyncio.CancelledError:
                break

            # Volver a verificar estado tras el sleep
            hb = next((h for h in server_config.settings.heartbeats if h.id == heartbeat_id), None)
            if not hb or not hb.enabled:
                break

            await self.trigger_heartbeat(heartbeat_id)

    async def trigger_heartbeat(self, heartbeat_id: str) -> bool:
        """
        Ejecuta manualmente o por ciclo un heartbeat específico de forma asíncrona.
        Guarda la sesión con su título en el historial y envía el resultado a Telegram si está configurado.
        Retorna True si la ejecución se completó correctamente, False en caso contrario.
        """
        hb = next((h for h in server_config.settings.heartbeats if h.id == heartbeat_id), None)
        if not hb:
            logger.warning(f"⚠️ Heartbeat {heartbeat_id} no encontrado en la configuración.")
            return False

        logger.info(f"💓 Ejecutando heartbeat '{hb.name}' (ID: {hb.id})...")
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            # Esperar a que el SessionPool esté listo
            await pool.wait_until_ready()

            target_session_id = hb.session_id or f"heartbeat_{hb.id}"
            session = pool.get_or_create(target_session_id)

            # Establecer un título descriptivo en el hilo para visualizar en la lista de sesiones
            if session.thread_manager:
                try:
                    thread = session.thread_manager.get_thread(target_session_id)
                    title_name = f"💓 Heartbeat: {hb.name}"
                    if not thread:
                        session.thread_manager.create_thread(thread_id=target_session_id, title=title_name)
                    elif not thread.title or thread.title == "Nueva conversación":
                        thread.title = title_name
                        session.thread_manager.save_thread(thread)
                except Exception as ex:
                    logger.warning(f"No se pudo actualizar título del hilo para {target_session_id}: {ex}")

            # Enviar prompt al agente en la sesión elegida
            await session.send(hb.prompt, pool._executor)

            # Extraer el último texto de respuesta generado por el agente
            last_response = ""
            for msg in reversed(session.agent_state.messages):
                msg_type = getattr(msg, "type", "")
                if msg_type in ("ai", "assistant") or msg.__class__.__name__ in ("AIMessage", "AssistantMessage"):
                    content = getattr(msg, "content", "")
                    if isinstance(content, str):
                        last_response = content
                    elif isinstance(content, list):
                        last_response = "\n".join(
                            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
                        )
                    if last_response:
                        break

            # Actualizar estado exitoso en la configuración
            server_config.update_heartbeat_status(
                heartbeat_id=hb.id,
                status="success",
                error=None,
                run_time=now_iso,
            )
            logger.info(f"✅ Heartbeat '{hb.name}' ejecutado exitosamente en sesión '{target_session_id}'.")

            # Despachar resultado a Telegram si el canal está configurado y habilitado
            await self._notify_telegram_if_configured(hb.name, last_response)

            return True

        except Exception as e:
            logger.error(f"❌ Error durante ejecución del heartbeat '{hb.name}': {e}")
            server_config.update_heartbeat_status(
                heartbeat_id=hb.id,
                status="error",
                error=str(e),
                run_time=now_iso,
            )
            return False

    async def _notify_telegram_if_configured(self, heartbeat_name: str, result_text: str) -> None:
        """Envia el resultado del heartbeat al Bot de Telegram si está activo."""
        tg_channel = next(
            (c for c in server_config.settings.channels if c.type in ("telegram", "telegram_bot") and c.enabled),
            None,
        )
        if not tg_channel:
            return

        token = tg_channel.params.get("token")
        chat_id = tg_channel.params.get("chat_id")
        if not token or not chat_id:
            logger.warning("⚠️ Canal Telegram activo pero falta 'token' o 'chat_id' en params para notificar heartbeat.")
            return

        import httpx
        from kogniterm.server.channel_adapters import TelegramAdapter

        cleaned_text = TelegramAdapter._clean_text_for_telegram(result_text or "Heartbeat ejecutado sin salida de texto.")
        if len(cleaned_text) > 3800:
            cleaned_text = cleaned_text[:3800] + "\n\n... (Resumen truncado)"

        message_body = f"💓 *Heartbeat: {heartbeat_name}*\n\n{cleaned_text}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                res = await client.post(url, json={"chat_id": chat_id, "text": message_body, "parse_mode": "Markdown"})
                if res.status_code != 200:
                    # Fallback sin parse_mode en caso de caracteres especiales Markdown no válidos
                    plain_body = f"💓 Heartbeat: {heartbeat_name}\n\n{cleaned_text}"
                    await client.post(url, json={"chat_id": chat_id, "text": plain_body})
            logger.info(f"📲 Resultado de heartbeat '{heartbeat_name}' enviado a Telegram (chat_id: {chat_id}).")
        except Exception as exc:
            logger.error(f"❌ Error al enviar resultado de heartbeat a Telegram: {exc}")


# Instancia global del scheduler de heartbeats
heartbeat_scheduler = HeartbeatScheduler()
