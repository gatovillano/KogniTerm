"""
Adaptadores de canal para KogniTerm Server.

Cada adaptador consume los eventos del SessionPool y los traduce
al protocolo del canal correspondiente (Slack, Discord, Telegram, CLI, etc.).

Uso rápido:
    from kogniterm.server.channel_adapters import SlackAdapter, CLIAdapter
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Optional, Dict, Any

from kogniterm.server.session_pool import AgentSession, pool

logger = logging.getLogger("kogniterm.server.channel_adapters")


# ── Clase base ─────────────────────────────────────────────────────────────────


class ChannelAdapter:
    """
    Adaptador base para integrar KogniTerm con un canal externo.

    Subclases deben implementar `send_to_channel()` para entregar
    los eventos al destino correcto.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or pool.new_session_id()
        self._session: Optional[AgentSession] = None

    def _get_session(self) -> AgentSession:
        if self._session is None:
            self._session = pool.get_or_create(self.session_id)
        return self._session

    async def send_message(self, message: str) -> None:
        """Envía un mensaje al agente y procesa los eventos de respuesta."""
        await pool.wait_until_ready()
        session = self._get_session()
        # Procesar eventos en background mientras el agente trabaja
        process_task = asyncio.create_task(self._process_events(session))
        await session.send(message, pool._executor)
        # Esperar a que se terminen de procesar todos los eventos de la cola de respuesta
        try:
            await asyncio.wait_for(process_task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning(f"[{self.__class__.__name__}] Timeout esperando eventos finales de la sesión {self.session_id}")
            process_task.cancel()
            try:
                await process_task
            except asyncio.CancelledError:
                pass

    async def _process_events(self, session: AgentSession) -> None:
        """Lee la cola de eventos y los despacha al canal."""
        async for event in session.ui.events():
            try:
                await self.send_to_channel(event, session.session_id)
            except Exception as exc:
                logger.exception(f"[{self.__class__.__name__}] Error crítico enviando evento al canal: {exc}")
            if event["type"] in ("done", "error"):
                break

    async def send_to_channel(self, event: dict, session_id: Optional[str] = None) -> None:
        """
        Implementar en subclases: enviar el evento al canal externo.
        `event` tiene la forma: {"type": str, "data": Any, "ts": str}
        """
        raise NotImplementedError


# ── Adaptador CLI ─────────────────────────────────────────────────────────────


class CLIAdapter(ChannelAdapter):
    """
    Adaptador de línea de comandos (para pruebas locales o scripts).
    Imprime los eventos en stdout.
    """

    PRINTABLE_TYPES = {"stream", "message", "tool_start", "tool_output", "done", "error"}

    async def send_to_channel(self, event: dict, session_id: Optional[str] = None) -> None:
        t = event["type"]
        d = event["data"]

        if t == "stream":
            print(d, end="", flush=True)
        elif t == "message":
            print(f"\n[Agente] {d.get('text', '')}")
        elif t in ("tool_start", "tool_call"):
            tool_name = d.get('tool') or d.get('name') or 'herramienta'
            print(f"\n⚙️  [{tool_name}] {d.get('description', '')}")
        elif t in ("tool_output", "tool_result"):
            output_content = d.get('output') or d.get('content') or ''
            print(f"\n📤 {output_content}")
        elif t == "done":
            print("\n✅ Completado.")
        elif t == "error":
            print(f"\n❌ Error: {d.get('message', d)}")

    async def interactive_loop(self) -> None:
        """Loop interactivo de CLI que mantiene el agente despierto."""
        await pool.wait_until_ready()
        print(f"KogniTerm CLI — Sesión: {self.session_id}")
        print("Escribe 'exit' para salir, 'interrupt' para interrumpir.\n")
        loop = asyncio.get_event_loop()
        while True:
            try:
                user_input = await loop.run_in_executor(None, input, ">>> ")
            except EOFError:
                break

            if user_input.strip().lower() in ("exit", "quit", "salir"):
                break
            elif user_input.strip().lower() == "interrupt":
                self._get_session().interrupt()
                print("⚡ Interrupción enviada.")
                continue
            elif not user_input.strip():
                continue

            await self.send_message(user_input)
        print("Sesión cerrada.")


# ── Adaptador Webhook genérico ─────────────────────────────────────────────────


class WebhookAdapter(ChannelAdapter):
    """
    Adaptador que convierte los eventos del agente en llamadas HTTP POST
    a un webhook externo (Slack incoming webhooks, n8n, Zapier, etc.).
    """

    def __init__(self, webhook_url: str, session_id: Optional[str] = None, filter_types: Optional[list] = None):
        super().__init__(session_id)
        self.webhook_url = webhook_url
        self.filter_types = filter_types or ["stream", "done", "error", "tool_start"]

    async def send_to_channel(self, event: dict, session_id: Optional[str] = None) -> None:
        if event["type"] not in self.filter_types:
            return

        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(self.webhook_url, json={
                    "session_id": self.session_id,
                    **event,
                })
        except Exception as exc:
            logger.warning(f"[WebhookAdapter] Error POST a {self.webhook_url}: {exc}")


# ── Adaptador Slack (ejemplo de referencia) ───────────────────────────────────


class SlackAdapter(ChannelAdapter):
    """
    Adaptador básico para Slack usando la Bolt SDK o webhooks de Slack.

    Para usar con Slack Bolt:
        from slack_bolt.async_app import AsyncApp
        slack = SlackAdapter(slack_app=app, channel="#general")
    """

    def __init__(
        self,
        slack_app=None,
        channel: str = "#general",
        session_id: Optional[str] = None,
    ):
        super().__init__(session_id)
        self.slack_app = slack_app
        self.channel = channel
        self._buffer: list[str] = []  # Acumular chunks de texto

    async def send_to_channel(self, event: dict, session_id: Optional[str] = None) -> None:
        t = event["type"]
        d = event["data"]

        if t == "stream":
            self._buffer.append(d)
        elif t == "done":
            # Enviar todo el texto acumulado como un solo mensaje
            full_text = "".join(self._buffer).strip()
            self._buffer.clear()
            if full_text and self.slack_app:
                await self.slack_app.client.chat_postMessage(
                    channel=self.channel, text=full_text
                )
        elif t == "error":
            if self.slack_app:
                await self.slack_app.client.chat_postMessage(
                    channel=self.channel, text=f"❌ Error: {d.get('message', d)}"
                )
        elif t in ("tool_start", "tool_call"):
            tool_name = d.get('tool') or d.get('name') or 'herramienta'
            if self.slack_app:
                await self.slack_app.client.chat_postMessage(
                    channel=self.channel,
                    text=f"⚙️ Ejecutando herramienta: `{tool_name}`"
                )


# ── Adaptador Telegram ────────────────────────────────────────────────────────



class TelegramAdapter(ChannelAdapter):
    import re

    @staticmethod
    def _clean_text_for_telegram(text: str) -> str:
        """
        Limpia secuencias ANSI, bordes Rich/Textual y espacios innecesarios para Telegram.
        """
        if not isinstance(text, str):
            return str(text)
        # Quitar secuencias ANSI
        text = TelegramAdapter.re.sub(r"\x1b\[[0-9;]*m", "", text)
        # Quitar bordes tipo caja (╭─, │, ╰─, etc.) y líneas vacías largas
        text = TelegramAdapter.re.sub(r"[\u2500-\u257F]+", "", text)  # Unicode box drawing
        text = TelegramAdapter.re.sub(r"^\s*[│┃╭╰─]+\s*$", "", text, flags=TelegramAdapter.re.MULTILINE)
        # Quitar líneas vacías excesivas
        text = TelegramAdapter.re.sub(r"\n{3,}", "\n\n", text)
        # Strip general
        return text.strip()

    """
    Adaptador para Telegram usando la librería python-telegram-bot.
    Mantiene la sesión del agente mapeada al chat_id de Telegram.
    """

    def __init__(self, token: str, session_id: Optional[str] = None):
        # session_id aquí solo se usa como fallback, pero cada chat_id tendrá su propio hilo
        super().__init__(session_id)
        self.token = token
        self.app = None
        self._current_chat_id: Optional[int] = None
        self._chat_sessions: Dict[int, str] = {}  # chat_id -> session_id
        self._stream_texts: Dict[int, str] = {}   # chat_id -> texto acumulado del stream
        self._draft_ids: Dict[int, int] = {}      # chat_id -> draft_id

    async def start(self):
        """Inicia el bot de Telegram en modo non-blocking."""
        from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
        
        self.app = ApplicationBuilder().token(self.token).build()

        # Handlers
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("stop", self._handle_stop))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info(f"Telegram bot iniciado para sesión {self.session_id}")

    async def stop(self):
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    async def _handle_start(self, update, context):
        await update.message.reply_text(f"🚀 KogniTerm conectado. Sesión: `{self.session_id}`")

    async def _handle_stop(self, update, context):
        pool.delete(self.session_id)
        await update.message.reply_text("🛑 Sesión cerrada y memoria liberada.")

    async def _handle_message(self, update, context):
        self._current_chat_id = update.effective_chat.id
        user_text = update.message.text
        import logging
        logging.getLogger("kogniterm.server.channel_adapters").info(
            f"Mensaje recibido de Telegram: {user_text} (chat_id={self._current_chat_id})"
        )
        # Asignar un session_id único por chat_id
        chat_id = self._current_chat_id
        if chat_id not in self._chat_sessions:
            # Usa el chat_id como session_id (str)
            self._chat_sessions[chat_id] = f"telegram_{chat_id}"
        self.session_id = self._chat_sessions[chat_id]
        # Forzar que el _session se reinicialice para este chat
        self._session = None
        # Enviar al agente
        await self.send_message(user_text)

    async def send_to_channel(self, event: dict, session_id: Optional[str] = None) -> None:
        import logging
        logger = logging.getLogger("kogniterm.server.channel_adapters")
        logger.info(
            f"[TelegramAdapter] Evento recibido en send_to_channel: {event} (session_id={session_id})"
        )
        
        # Determinar el chat_id a partir del session_id si es posible
        chat_id = None
        if session_id and session_id.startswith("telegram_"):
            try:
                chat_id = int(session_id.split("_")[1])
            except (IndexError, ValueError):
                pass
        
        if not chat_id:
            chat_id = self._current_chat_id

        if not chat_id:
            logger.warning("[TelegramAdapter] No se pudo enviar el evento porque no se determinó el chat_id.")
            return
        if not self.app:
            logger.warning("[TelegramAdapter] No se pudo enviar el evento porque self.app es None.")
            return

        t = event["type"]
        d = event["data"]

        # Inicializar estructuras para este chat_id si no existen
        if chat_id not in self._stream_texts:
            self._stream_texts[chat_id] = ""
        if chat_id not in self._draft_ids:
            self._draft_ids[chat_id] = None

        # Separar stream y live_update
        if t == "stream":
            if self._draft_ids[chat_id] is None:
                import random
                self._draft_ids[chat_id] = random.randint(1_000_000, 9_999_999)
                self._stream_texts[chat_id] = ""
            
            # Acumular chunks sin limpiar para no perder espacios
            self._stream_texts[chat_id] += d
            
            # Enviar el borrador en streaming a Telegram
            await self._send_message_draft(chat_id, self._draft_ids[chat_id], self._stream_texts[chat_id])
            
        elif t == "live_update":
            # Ignorar live_update para Telegram (evita duplicar "Pensando...")
            pass
        elif t == "done":
            logger.info(f"[TelegramAdapter] Evento 'done' recibido para chat_id {chat_id}. Longitud de stream acumulado: {len(self._stream_texts[chat_id])}")
            if self._stream_texts[chat_id]:
                final_text = self._clean_text_for_telegram(self._stream_texts[chat_id])
                if final_text:
                    logger.info(f"[TelegramAdapter] Enviando texto final a Telegram (chat_id={chat_id}): {final_text[:50]}...")
                    await self.app.bot.send_message(chat_id=chat_id, text=final_text)
                else:
                    logger.info(f"[TelegramAdapter] final_text quedó vacío después de limpiar para chat_id {chat_id}.")
            else:
                logger.info(f"[TelegramAdapter] No hay texto de stream acumulado para enviar al chat_id {chat_id}.")
            self._draft_ids[chat_id] = None
            self._stream_texts[chat_id] = ""
        elif t == "error":
            self._draft_ids[chat_id] = None
            self._stream_texts[chat_id] = ""
            err_msg = d.get('message', d) if isinstance(d, dict) else d
            cleaned_err = self._clean_text_for_telegram(err_msg)
            if cleaned_err:
                logger.info(f"[TelegramAdapter] Enviando mensaje de error a Telegram (chat_id={chat_id}): {cleaned_err[:50]}...")
                await self.app.bot.send_message(chat_id=chat_id, text=f"❌ Error: {cleaned_err}")
        elif t in ("tool_start", "tool_call"):
            tool_name = d.get('tool') or d.get('name') or 'herramienta'
            logger.info(f"[TelegramAdapter] Enviando inicio de herramienta a Telegram (chat_id={chat_id}): {tool_name}")
            await self.app.bot.send_message(
                chat_id=chat_id, 
                text=f"⚙️ `{tool_name}`..."
            )
        elif t == "message":
            # Limpiar el mensaje antes de enviarlo
            msg_text = d.get('text', d) if isinstance(d, dict) else d
            cleaned = self._clean_text_for_telegram(msg_text)
            if cleaned:
                logger.info(f"[TelegramAdapter] Enviando mensaje de texto a Telegram (chat_id={chat_id}): {cleaned[:50]}...")
                await self.app.bot.send_message(chat_id=chat_id, text=cleaned)

    async def _send_message_draft(self, chat_id: int, draft_id: int, text: str) -> None:
        """
        Llama al método nativo sendMessageDraft de la API de Telegram usando el bot HTTP API directamente.
        Se ejecuta de manera segura para evitar que fallas en este endpoint efímero afecten el flujo principal.
        """
        import aiohttp
        try:
            token = self.token
            url = f"https://api.telegram.org/bot{token}/sendMessageDraft"
            payload = {
                "chat_id": chat_id,
                "draft_id": draft_id,
                "text": text,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=2.0) as resp:
                    # Solo leemos el texto, no arrojamos excepciones por código de estado HTTP
                    await resp.text()
        except Exception as exc:
            logger.debug(f"[TelegramAdapter] Error al enviar borrador sendMessageDraft: {exc}")

    # _flush_buffer ya no es necesario con streaming nativo
