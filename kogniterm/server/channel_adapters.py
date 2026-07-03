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
import time
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
        # Esperar a que se terminen de procesar todos los eventos de la cola de respuesta.
        # El timeout es generoso (10 min) para no cortar generaciones largas del LLM
        # que emiten tool_calls, índices o respuestas extensas.
        try:
            await asyncio.wait_for(process_task, timeout=600.0)
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

    PRINTABLE_TYPES = {"stream", "message", "tool_start", "tool_output", "tool_result", "terminal_output", "done", "error"}

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
        elif t in ("tool_output", "tool_result", "terminal_output"):
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



# ── Helper functions for Markdown to Telegram HTML conversion ─────────────────

def _parse_inline_helper(escaped_text: str) -> str:
    i = 0
    n = len(escaped_text)
    res = []
    stack = []
    
    while i < n:
        if stack and stack[-1] == 'code':
            if escaped_text[i] == '`':
                res.append('</code>')
                stack.pop()
                i += 1
            else:
                res.append(escaped_text[i])
                i += 1
            continue
            
        if escaped_text[i] == '`':
            res.append('<code>')
            stack.append('code')
            i += 1
            continue
            
        if escaped_text[i:i+2] == '**' or escaped_text[i:i+2] == '__':
            if 'b' in stack:
                temp_closed = []
                while stack and stack[-1] != 'b':
                    t = stack.pop()
                    res.append(f'</{t}>')
                    temp_closed.append(t)
                stack.pop()
                res.append('</b>')
                for t in reversed(temp_closed):
                    res.append(f'<{t}>')
                    stack.append(t)
            else:
                res.append('<b>')
                stack.append('b')
            i += 2
            continue
            
        if escaped_text[i:i+2] == '~~':
            if 's' in stack:
                temp_closed = []
                while stack and stack[-1] != 's':
                    t = stack.pop()
                    res.append(f'</{t}>')
                    temp_closed.append(t)
                stack.pop()
                res.append('</s>')
                for t in reversed(temp_closed):
                    res.append(f'<{t}>')
                    stack.append(t)
            else:
                res.append('<s>')
                stack.append('s')
            i += 2
            continue
            
        if escaped_text[i] == '*' or escaped_text[i] == '_':
            if 'i' in stack:
                temp_closed = []
                while stack and stack[-1] != 'i':
                    t = stack.pop()
                    res.append(f'</{t}>')
                    temp_closed.append(t)
                stack.pop()
                res.append('</i>')
                for t in reversed(temp_closed):
                    res.append(f'<{t}>')
                    stack.append(t)
            else:
                res.append('<i>')
                stack.append('i')
            i += 1
            continue
            
        if escaped_text[i] == '[':
            close_bracket = escaped_text.find(']', i)
            if close_bracket != -1 and close_bracket + 1 < n and escaped_text[close_bracket + 1] == '(':
                close_paren = escaped_text.find(')', close_bracket + 2)
                if close_paren != -1:
                    link_text = escaped_text[i+1:close_bracket]
                    url = escaped_text[close_bracket+2:close_paren]
                    parsed_link_text = _parse_inline_helper(link_text)
                    res.append(f'<a href="{url}">{parsed_link_text}</a>')
                    i = close_paren + 1
                    continue
                    
        res.append(escaped_text[i])
        i += 1
        
    while stack:
        t = stack.pop()
        res.append(f'</{t}>')
        
    return ''.join(res)


def parse_inline_styles(text: str) -> str:
    import html
    return _parse_inline_helper(html.escape(text))


def markdown_to_telegram_html(md: str) -> str:
    if not md:
        return ""
        
    lines = md.split('\n')
    output_lines = []
    
    in_code_block = False
    code_block_lang = ""
    code_block_lines = []
    
    in_blockquote = False
    blockquote_lines = []
    
    def flush_blockquote():
        nonlocal in_blockquote, blockquote_lines
        if in_blockquote:
            content = '\n'.join(blockquote_lines)
            parsed_content = parse_inline_styles(content)
            output_lines.append(f'<blockquote>{parsed_content}</blockquote>')
            blockquote_lines = []
            in_blockquote = False

    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('```'):
            if in_code_block:
                import html
                code_content = '\n'.join(code_block_lines)
                escaped_code = html.escape(code_content)
                if code_block_lang:
                    output_lines.append(f'<pre><code class="language-{code_block_lang}">{escaped_code}</code></pre>')
                else:
                    output_lines.append(f'<pre><code>{escaped_code}</code></pre>')
                in_code_block = False
                code_block_lines = []
                code_block_lang = ""
            else:
                flush_blockquote()
                in_code_block = True
                code_block_lang = stripped[3:].strip()
            continue
            
        if in_code_block:
            code_block_lines.append(line)
            continue
            
        if stripped.startswith('>'):
            content = line.lstrip()[1:]
            if content.startswith(' '):
                content = content[1:]
            blockquote_lines.append(content)
            in_blockquote = True
            continue
        else:
            flush_blockquote()
            
        if stripped.startswith('#'):
            hashes = 0
            for char in stripped:
                if char == '#':
                    hashes += 1
                else:
                    break
            if hashes > 0 and len(stripped) > hashes and stripped[hashes] == ' ':
                header_text = stripped[hashes:].strip()
                parsed_header = parse_inline_styles(header_text)
                output_lines.append(f'<b>{parsed_header}</b>')
                continue
                
        output_lines.append(parse_inline_styles(line))
        
    if in_code_block:
        import html
        code_content = '\n'.join(code_block_lines)
        escaped_code = html.escape(code_content)
        if code_block_lang:
            output_lines.append(f'<pre><code class="language-{code_block_lang}">{escaped_code}</code></pre>')
        else:
            output_lines.append(f'<pre><code>{escaped_code}</code></pre>')
            
    flush_blockquote()
    
    return '\n'.join(output_lines)


def split_markdown(text: str, max_chars: int = 3500) -> tuple[str, str]:
    if len(text) <= max_chars:
        return text, ""
    split_idx = text.rfind('\n', 0, max_chars)
    if split_idx == -1 or split_idx < max_chars // 2:
        split_idx = max_chars
    return text[:split_idx], text[split_idx:]


def clean_thinking_text(text: str) -> str:
    import re
    # Remove ANSI codes
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip top, bottom, or middle box boundaries
        if '─' in stripped or '╭' in stripped or '╰' in stripped:
            continue
            
        line_content = line.strip()
        # Remove vertical borders at the start or end of the line
        line_content = re.sub(r'^[│┃]', '', line_content)
        line_content = re.sub(r'[│┃]$', '', line_content)
        
        line_content = line_content.strip()
        if line_content:
            cleaned_lines.append(line_content)
            
    return '\n'.join(cleaned_lines)


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

    DRAFT_THROTTLE_S: float = 0.300
    DRAFT_MAX_CHARS: int = 4096

    @staticmethod
    def _make_draft_id(chat_id: int) -> int:
        """
        Genera un draft_id determinístico y estable por chat_id.
        Debe ser entero positivo no-cero (requisito de sendMessageDraft).
        """
        return (abs(hash(f"telegram_{chat_id}")) % (2**31 - 1)) + 1

    def __init__(self, token: str, session_id: Optional[str] = None):
        # session_id aquí solo se usa como fallback, pero cada chat_id tendrá su propio hilo
        super().__init__(session_id)
        self.token = token
        self.app = None
        self._current_chat_id: Optional[int] = None
        self._chat_sessions: Dict[int, str] = {}  # chat_id -> session_id
        self._stream_texts: Dict[int, str] = {}   # chat_id -> texto acumulado del stream
        self._draft_ids: Dict[int, int] = {}      # chat_id -> draft_id (estable)
        self._draft_last_sent_text: Dict[int, str] = {}   # último texto HTML enviado
        self._draft_last_sent_at: Dict[int, float] = {}   # monotonic() del último envío
        self._draft_overflow: Dict[int, bool] = {}        # True cuando len > 4096
        self._thinking_active: Dict[int, bool] = {}       # chat_id -> pensando actualmente
        self._stream_active: Dict[int, bool] = {}         # chat_id -> streaming de respuesta activo

    async def start(self):
        """Inicia el bot de Telegram en modo non-blocking."""
        from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
        
        self.app = ApplicationBuilder().token(self.token).build()

        # Handlers
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("stop", self._handle_stop))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback_query))

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
        import html
        escaped_session_id = html.escape(self.session_id)
        await update.message.reply_text(f"🚀 KogniTerm conectado. Sesión: <code>{escaped_session_id}</code>", parse_mode='HTML')

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

    async def _handle_callback_query(self, update, context):
        query = update.callback_query
        
        data = query.data
        if not data or ":" not in data:
            await query.answer()
            return
            
        action, request_id = data.split(":", 1)
        approved = action == "approve"
        
        chat_id = update.effective_chat.id
        session_id = self._chat_sessions.get(chat_id)
        if not session_id:
            session_id = f"telegram_{chat_id}"
            
        session = pool.get(session_id)
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        if session:
            session.ui.handle_approval_response(request_id, approved)
            await query.answer(text="✅ Aprobado" if approved else "❌ Denegado")
            
            # Actualizar el mensaje de Telegram para remover los botones e indicar la decisión en los botones
            status_text = "🟢 Aprobado" if approved else "🔴 Denegado"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(status_text, callback_data="none")]])
            try:
                await query.edit_message_reply_markup(reply_markup=reply_markup)
            except Exception as e:
                logger.warning(f"No se pudo actualizar el markup de aprobación en Telegram: {e}")
        else:
            await query.answer(text="⚠️ Sesión expirada o inactiva")
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Sesión expirada", callback_data="none")]])
            try:
                await query.edit_message_reply_markup(reply_markup=reply_markup)
            except Exception as e:
                logger.warning(f"No se pudo actualizar el markup de expiración en Telegram: {e}")

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
        if chat_id not in self._thinking_active:
            self._thinking_active[chat_id] = False
        if chat_id not in self._stream_active:
            self._stream_active[chat_id] = False

        if t == "stream":
            if not self._stream_active.get(chat_id, False):
                self._stream_active[chat_id] = True
                if self._draft_ids[chat_id] is None:
                    self._draft_ids[chat_id] = self._make_draft_id(chat_id)
                self._stream_texts[chat_id] = ""
                self._draft_overflow[chat_id] = False
                self._draft_last_sent_text[chat_id] = ""
                self._draft_last_sent_at[chat_id] = 0.0

            # Acumular chunks sin limpiar para no perder espacios internos
            self._stream_texts[chat_id] += d
            await self._enqueue_draft(chat_id, self._stream_texts[chat_id])
            
        elif t == "live_update":
            # Procesar el pensamiento acumulado del agente en el borrador
            if not self._thinking_active.get(chat_id, False):
                self._thinking_active[chat_id] = True
                if self._draft_ids[chat_id] is None:
                    self._draft_ids[chat_id] = self._make_draft_id(chat_id)
                self._draft_overflow[chat_id] = False
                self._draft_last_sent_text[chat_id] = ""
                self._draft_last_sent_at[chat_id] = 0.0

            if isinstance(d, dict):
                raw_thinking = d.get("thinking", "")
            else:
                raw_thinking = d

            cleaned_thinking = clean_thinking_text(raw_thinking)
            if cleaned_thinking:
                import html
                # Envuelve el pensamiento en un bloque de cita (blockquote) de Telegram HTML
                html_thinking = f"<blockquote><b>🤔 Pensando...</b>\n{html.escape(cleaned_thinking)}</blockquote>"
                await self._enqueue_draft(chat_id, html_thinking, is_html=True)

        elif t == "done":
            logger.info(f"[TelegramAdapter] Evento 'done' recibido para chat_id {chat_id}. Longitud de stream acumulado: {len(self._stream_texts[chat_id])}")
            if self._stream_texts[chat_id]:
                final_text = self._clean_text_for_telegram(self._stream_texts[chat_id])
                if final_text:
                    logger.info(f"[TelegramAdapter] Enviando texto final a Telegram (chat_id={chat_id}, len={len(final_text)}): {final_text[:50]}...")
                    html_msg = markdown_to_telegram_html(final_text)
                    await self.app.bot.send_message(chat_id=chat_id, text=html_msg, parse_mode='HTML')
                else:
                    logger.info(f"[TelegramAdapter] final_text quedó vacío después de limpiar para chat_id {chat_id}.")
                    # Borrar borrador explicitamente
                    if self._draft_ids[chat_id] is not None:
                        await self._send_message_draft(chat_id, self._draft_ids[chat_id], "")
            else:
                # Borrar borrador llamando a sendMessageDraft con texto vacío
                if self._draft_ids[chat_id] is not None:
                    await self._send_message_draft(chat_id, self._draft_ids[chat_id], "")
            
            # Resetear estado del stream y del draft
            self._draft_ids[chat_id] = None
            self._stream_texts[chat_id] = ""
            self._draft_overflow[chat_id] = False
            self._draft_last_sent_text[chat_id] = ""
            self._draft_last_sent_at[chat_id] = 0.0
            self._thinking_active[chat_id] = False
            self._stream_active[chat_id] = False

        elif t == "error":
            # Borrar borrador
            if self._draft_ids[chat_id] is not None:
                await self._send_message_draft(chat_id, self._draft_ids[chat_id], "")

            # Resetear estado de stream y del draft
            self._draft_ids[chat_id] = None
            self._stream_texts[chat_id] = ""
            self._draft_overflow[chat_id] = False
            self._draft_last_sent_text[chat_id] = ""
            self._draft_last_sent_at[chat_id] = 0.0
            self._thinking_active[chat_id] = False
            self._stream_active[chat_id] = False
            
            err_msg = d.get('message', d) if isinstance(d, dict) else d
            cleaned_err = self._clean_text_for_telegram(err_msg)
            if cleaned_err:
                logger.info(f"[TelegramAdapter] Enviando mensaje de error a Telegram (chat_id={chat_id}): {cleaned_err[:50]}...")
                import html
                escaped_err = f"❌ <b>Error:</b> {html.escape(cleaned_err)}"
                await self.app.bot.send_message(chat_id=chat_id, text=escaped_err, parse_mode='HTML')

        elif t in ("tool_start", "tool_call"):
            tool_name = d.get('tool') or d.get('name') or 'herramienta'
            logger.info(f"[TelegramAdapter] Enviando inicio de herramienta a Telegram (chat_id={chat_id}): {tool_name}")
            import html
            escaped_tool = f"⚙️ <code>{html.escape(tool_name)}</code>..."
            await self.app.bot.send_message(chat_id=chat_id, text=escaped_tool, parse_mode='HTML')

            # Resetear banderas de stream/pensamiento al ejecutar herramienta
            self._thinking_active[chat_id] = False
            self._stream_active[chat_id] = False

        elif t == "approval_required":
            request_id = d.get("id")
            message = d.get("message", "")
            title = d.get("title", "Aprobación Requerida")
            diff_content = d.get("diff_content", "")
            file_path = d.get("file_path", "")
            
            import html
            msg_html = f"⚠️ <b>{html.escape(title)}</b>\n\n{html.escape(message)}"
            if file_path:
                msg_html += f"\n📁 <b>Archivo:</b> <code>{html.escape(file_path)}</code>"
            
            if diff_content:
                if len(diff_content) > 2000:
                    diff_content = diff_content[:2000] + "\n... (diff truncado)"
                msg_html += f"\n\n<pre><code class=\"language-diff\">{html.escape(diff_content)}</code></pre>"
                
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [
                    InlineKeyboardButton("✅ Aprobar", callback_data=f"approve:{request_id}"),
                    InlineKeyboardButton("❌ Denegar", callback_data=f"deny:{request_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            logger.info(f"[TelegramAdapter] Enviando solicitud de aprobación {request_id} a chat_id {chat_id}")
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=msg_html,
                parse_mode='HTML',
                reply_markup=reply_markup
            )

        elif t == "message":
            # Limpiar el mensaje antes de enviarlo
            msg_text = d.get('text', d) if isinstance(d, dict) else d
            cleaned = self._clean_text_for_telegram(msg_text)
            if cleaned:
                logger.info(f"[TelegramAdapter] Enviando mensaje de texto a Telegram (chat_id={chat_id}): {cleaned[:50]}...")
                html_msg = markdown_to_telegram_html(cleaned)
                await self.app.bot.send_message(chat_id=chat_id, text=html_msg, parse_mode='HTML')

    async def _enqueue_draft(self, chat_id: int, text: str, is_html: bool = False) -> None:
        if self._draft_overflow.get(chat_id, False):
            return

        if is_html:
            html_content = text
        else:
            cleaned = self._clean_text_for_telegram(text)
            if not cleaned:
                return
            # Convertir a HTML para un renderizado seguro y correcto de Markdown
            html_content = markdown_to_telegram_html(cleaned)

        if html_content == self._draft_last_sent_text.get(chat_id, ""):
            return

        if len(html_content) > self.DRAFT_MAX_CHARS:
            self._draft_overflow[chat_id] = True
            logger.info(
                f"[TelegramAdapter] Draft omitido por overflow (chat_id={chat_id}, "
                f"len={len(html_content)} > {self.DRAFT_MAX_CHARS}); se enviará completo vía send_message."
            )
            return

        now = time.monotonic()
        last = self._draft_last_sent_at.get(chat_id, 0.0)
        if (now - last) < self.DRAFT_THROTTLE_S:
            return

        self._draft_last_sent_text[chat_id] = html_content
        self._draft_last_sent_at[chat_id] = now
        await self._send_message_draft(chat_id, self._draft_ids[chat_id], html_content)

    async def _send_message_draft(self, chat_id: int, draft_id: int, text: str) -> None:
        import aiohttp
        try:
            token = self.token
            url = f"https://api.telegram.org/bot{token}/sendMessageDraft"
            payload = {
                "chat_id": chat_id,
                "draft_id": draft_id,
                "text": text,
                "parse_mode": "HTML",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=2.0) as resp:
                    if resp.status != 200:
                        logger.error(f"[TelegramAdapter] Error al enviar borrador: HTTP {resp.status} - {await resp.text()}")
                    else:
                        await resp.text()
        except Exception as exc:
            logger.debug(f"[TelegramAdapter] Error al enviar borrador sendMessageDraft: {exc}")

