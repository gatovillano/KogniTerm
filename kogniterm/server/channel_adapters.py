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
        session = self._get_session()
        # Procesar eventos en background mientras el agente trabaja
        process_task = asyncio.create_task(self._process_events(session))
        await session.send(message, pool._executor)
        # Esperar un poco para que los últimos eventos se procesen
        await asyncio.sleep(0.2)
        process_task.cancel()
        try:
            await process_task
        except asyncio.CancelledError:
            pass

    async def _process_events(self, session: AgentSession) -> None:
        """Lee la cola de eventos y los despacha al canal."""
        async for event in session.ui.events():
            try:
                await self.send_to_channel(event)
            except Exception as exc:
                logger.warning(f"[{self.__class__.__name__}] Error enviando evento: {exc}")
            if event["type"] in ("done", "error"):
                break

    async def send_to_channel(self, event: dict) -> None:
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

    async def send_to_channel(self, event: dict) -> None:
        t = event["type"]
        d = event["data"]

        if t == "stream":
            print(d, end="", flush=True)
        elif t == "message":
            print(f"\n[Agente] {d.get('text', '')}")
        elif t == "tool_start":
            print(f"\n⚙️  [{d.get('tool')}] {d.get('description', '')}")
        elif t == "tool_output":
            print(f"\n📤 {d.get('output', '')}")
        elif t == "done":
            print("\n✅ Completado.")
        elif t == "error":
            print(f"\n❌ Error: {d.get('message', d)}")

    async def interactive_loop(self) -> None:
        """Loop interactivo de CLI que mantiene el agente despierto."""
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

    async def send_to_channel(self, event: dict) -> None:
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

    async def send_to_channel(self, event: dict) -> None:
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
        elif t == "tool_start":
            if self.slack_app:
                await self.slack_app.client.chat_postMessage(
                    channel=self.channel,
                    text=f"⚙️ Ejecutando herramienta: `{d.get('tool')}`"
                )


# ── Adaptador Telegram ────────────────────────────────────────────────────────


class TelegramAdapter(ChannelAdapter):
    """
    Adaptador para Telegram usando la librería python-telegram-bot.
    Mantiene la sesión del agente mapeada al chat_id de Telegram.
    """

    def __init__(self, token: str, session_id: Optional[str] = None):
        super().__init__(session_id)
        self.token = token
        self.app = None
        self._current_chat_id: Optional[int] = None
        self._draft_id: Optional[int] = None
        self._stream_text: str = ""

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
        # Enviar al agente
        await self.send_message(user_text)

    async def send_to_channel(self, event: dict) -> None:
        if not self._current_chat_id or not self.app:
            return

        t = event["type"]
        d = event["data"]

        # Solo soportado en chats privados (por ahora)
        if t == "stream":
            # Inicializar draft_id si es la primera vez
            if self._draft_id is None:
                import random
                self._draft_id = random.randint(1_000_000, 9_999_999)
                self._stream_text = ""
            self._stream_text += d
            # Llamar a sendMessageDraft (requiere método manual)
            await self._send_message_draft(self._current_chat_id, self._draft_id, self._stream_text)
        elif t == "done":
            # Al finalizar, enviar el mensaje completo y limpiar draft
            if self._stream_text:
                await self.app.bot.send_message(chat_id=self._current_chat_id, text=self._stream_text)
            self._draft_id = None
            self._stream_text = ""
        elif t == "error":
            self._draft_id = None
            self._stream_text = ""
            await self.app.bot.send_message(chat_id=self._current_chat_id, text=f"❌ Error: {d}")
        elif t == "tool_start":
            await self.app.bot.send_message(
                chat_id=self._current_chat_id, 
                text=f"⚙️ `{d.get('tool')}`..."
            )
        elif t == "message":
            # Enviar mensaje de texto normal
            await self.app.bot.send_message(chat_id=self._current_chat_id, text=d)

    async def _send_message_draft(self, chat_id: int, draft_id: int, text: str) -> None:
        """
        Llama al método nativo sendMessageDraft de la API de Telegram usando el bot HTTP API directamente,
        ya que python-telegram-bot puede no exponerlo aún.
        """
        import aiohttp
        # Obtener el token del bot
        token = self.token
        url = f"https://api.telegram.org/bot{token}/sendMessageDraft"
        payload = {
            "chat_id": chat_id,
            "draft_id": draft_id,
            "text": text,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                # No importa el resultado, es efímero
                await resp.text()

    # _flush_buffer ya no es necesario con streaming nativo
