import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.tui_app import KogniTermTUI
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget
from kogniterm.terminal.tui.session import SessionContext


def _make_app():
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    llm_service.conversation_history = []
    app = KogniTermTUI(llm_service=llm_service)
    return app


async def _dismiss_splash(app, pilot):
    """Oculta el splash para interactuar con la barra de pestañas."""
    app._splash_visible = False
    app.query_one("#splash_overlay").display = False
    app.query_one("#bottom_container").display = True
    await pilot.pause()


@pytest.mark.anyio
async def test_sessions_bar_with_plus_button():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Barra superior de pestañas + botón "+"
        bar = app.query_one("#sessions_bar")
        assert bar is not None
        plus = app.query_one("#new_session_btn")
        assert plus is not None
        assert "+" in str(plus.label)
        # Una sesión inicial con su widget visible
        sessions = app.list_sessions()
        assert len(sessions) == 1
        widget = app.query_one(f"#{sessions[0].chat_widget_id}", ChatLogWidget)
        assert widget is not None
        assert widget.display is True
        # chat_log legacy apunta a la sesión activa
        assert app.chat_log is widget


@pytest.mark.anyio
async def test_create_switch_close_sessions_same_workspace():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.get_active_session()
        ws = app.workspace_directory

        second = app.create_session(title="Segunda")
        await pilot.pause()
        assert len(app.list_sessions()) == 2
        assert app.get_active_session().session_id == second.session_id
        # Mismo workspace en ambas (pestañas del mismo proyecto)
        assert app.workspace_directory == ws
        # El thread de cada sesión vive en el mismo workspace
        assert second.thread_id != first.thread_id

        # Solo el widget activo es visible
        assert app._session_widget(second).display is True
        assert app._session_widget(first).display is False

        # Switch de vuelta
        assert app.switch_session(first.session_id) is True
        await pilot.pause()
        assert app.get_active_session().session_id == first.session_id
        assert app._session_widget(first).display is True
        assert app._session_widget(second).display is False

        # Renombrar
        assert app.rename_session("Principal", first.session_id) is True
        assert first.title == "Principal"

        # Cerrar la segunda
        assert app.close_session(second.session_id) is True
        await pilot.pause()
        assert len(app.list_sessions()) == 1

        # No se puede cerrar la última
        assert app.close_session(first.session_id) is False
        assert len(app.list_sessions()) == 1


@pytest.mark.anyio
async def test_sessions_isolate_history_and_processing():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.get_active_session()
        second = app.create_session(title="Aislada")
        await pilot.pause()

        # Historiales independientes
        assert first.agent_state is not second.agent_state
        assert first.agent_state.messages is not second.agent_state.messages
        # Colas de interrupción independientes
        assert first.interrupt_queue is not second.interrupt_queue

        # Flag de procesado por sesión: si la segunda procesa, la primera sigue libre
        second.is_processing = True
        app.switch_session(first.session_id)
        assert app.is_processing is False
        app.switch_session(second.session_id)
        assert app.is_processing is True
        second.is_processing = False

        # SessionContext por defecto vacío
        assert SessionContext.get() is None


@pytest.mark.anyio
async def test_plus_button_creates_session():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _dismiss_splash(app, pilot)
        before = len(app.list_sessions())
        await pilot.click("#new_session_btn")
        await pilot.pause()
        assert len(app.list_sessions()) == before + 1


@pytest.mark.anyio
async def test_session_commands_dispatch():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()

        # /new crea pestaña
        assert await app._handle_session_command("/new Mi tab", session) is True
        assert len(app.list_sessions()) == 2

        # /tabs lista
        assert await app._handle_session_command("/tabs", session) is True

        # /switch 1 vuelve a la primera
        assert await app._handle_session_command("/switch 1", session) is True
        assert app.get_active_session().title.startswith("Sesión")

        # /rename
        assert await app._handle_session_command("/rename Principal", session) is True

        # /reset limpia sin tocar otras pestañas
        assert await app._handle_session_command("/reset", session) is True

        # comando normal no se consume
        assert await app._handle_session_command("hola mundo", session) is False
        assert await app._handle_session_command("/models", session) is False


@pytest.mark.anyio
async def test_session_has_own_executor_and_handler():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.get_active_session()
        second = app.create_session(title="Cmd")
        await pilot.pause()

        # Los managers son perezosos: se construyen bajo demanda
        app._ensure_session_managers(first)
        app._ensure_session_managers(second)

        assert first.command_executor is not None
        assert second.command_executor is not None
        assert first.command_executor is not second.command_executor
        # Cada handler usa el executor y la UI de su pestaña
        assert first.approval_handler is not None
        assert second.approval_handler is not None
        assert first.approval_handler is not second.approval_handler
        assert first.approval_handler.command_executor is first.command_executor
        assert second.approval_handler.command_executor is second.command_executor
        assert first.approval_handler.terminal_ui is first.ui_proxy
        assert second.approval_handler.terminal_ui is second.ui_proxy
        # Cola de interrupción propia en el handler
        assert first.approval_handler.interrupt_queue is first.interrupt_queue


@pytest.mark.anyio
async def test_cursor_state_is_per_session():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.get_active_session()
        second = app.create_session(title="Term")
        await pilot.pause()

        # Activar cursor en la segunda pestaña (fondo)
        app.switch_session(first.session_id)
        app.set_terminal_cursor(True, second.command_executor, session_id=second.session_id)
        assert second.cursor_active is True
        assert second.interactive_executor is second.command_executor
        # La UI global sigue reflejando la pestaña activa (primera, inactiva)
        assert app._cursor_active is False

        # Al cambiar a la segunda, la UI global la refleja
        app.switch_session(second.session_id)
        assert app._cursor_active is True
        assert app.interactive_executor is second.command_executor

        app.set_terminal_cursor(False, session_id=second.session_id)
        assert second.cursor_active is False
        assert app._cursor_active is False


@pytest.mark.anyio
async def test_approval_mounts_inside_background_tab():
    import asyncio

    from kogniterm.terminal.tui.components.inline_approval import InlineApprovalWidget

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.get_active_session()
        second = app.create_session(title="Aprob")
        await pilot.pause()
        app.switch_session(first.session_id)
        await pilot.pause()
        # El config del proyecto puede tener auto_approve; lo desactivamos
        # solo en memoria para poder probar el widget de aprobación.
        app._auto_approve_all = False

        # 1) Resolución del host: la aprobación va al chat log de su pestaña
        host, session = app._approval_host(second.session_id)
        assert host is app._session_widget(second)
        assert session is second

        # 2) Montaje inline real (variante async, sin hilos bloqueados)
        task = asyncio.ensure_future(
            app.ask_for_approval_async(
                "¿Ejecutar comando?", "Confirmación", "ls -la", "bash",
                second.session_id,
            )
        )
        widgets = []
        for _ in range(100):
            await asyncio.sleep(0.05)
            widgets = list(app._session_widget(second).query(InlineApprovalWidget))
            if widgets:
                break
        assert len(widgets) == 1, "el widget de aprobación debe ir en la pestaña 2"
        # Contador pendiente + marca en la pestaña
        assert second.pending_approvals == 1
        tab_btn = app.query_one(f"#session-tab-{second.session_id}")
        assert tab_btn.label.plain.startswith("? ")
        # La primera pestaña no tiene aprobaciones
        assert list(app._session_widget(first).query(InlineApprovalWidget)) == []

        # 3) Decisión del usuario (como si pulsara Aceptar)
        app.switch_session(second.session_id)
        await pilot.pause()
        widgets[0]._resolve("accept")
        result = await asyncio.wait_for(task, timeout=20)
        # Textual elimina el widget de forma asíncrona: dar un reflow
        await pilot.pause()
        await asyncio.sleep(0.1)
        await pilot.pause()

        assert result is True
        assert second.pending_approvals == 0
        assert list(app._session_widget(second).query(InlineApprovalWidget)) == []


@pytest.mark.anyio
async def test_server_client_per_tab_routing():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.get_active_session()
        second = app.create_session(title="Remota")
        await pilot.pause()

        c1 = app._ensure_session_client(first)
        c2 = app._ensure_session_client(second)
        try:
            assert c1 is not None and c2 is not None
            assert c1._tab_id == first.session_id
            assert c2._tab_id == second.session_id
            # Sesiones remotas distintas por pestaña
            assert c1._session_id != c2._session_id

            # Enrutado al widget de cada pestaña
            assert c1._get_chat_log(None) is app._session_widget(first)
            assert c2._get_chat_log(None) is app._session_widget(second)

            # Evento del agente principal del cliente 2 llega a la pestaña 2
            # aunque la activa sea la 1
            app.switch_session(first.session_id)
            await pilot.pause()
            before = len(list(app._session_widget(second).children))
            c2._route_event({"type": "message", "data": {"text": "hola tab2"}})
            await pilot.pause()
            await pilot.pause()
            after = len(list(app._session_widget(second).children))
            assert after > before

            # done del tab 2 limpia su flag sin tocar la pestaña 1
            second.is_processing = True
            c2._on_agent_done()
            assert second.is_processing is False
        finally:
            for c in (c1, c2):
                try:
                    c.stop()
                except Exception:
                    pass
            for s in (first, second):
                try:
                    if s.ws_task is not None:
                        s.ws_task.cancel()
                except Exception:
                    pass
                s.ws_client = None
                s.ws_task = None


@pytest.mark.anyio
async def test_server_stream_does_not_duplicate_response():
    """Regression: cada fragmento de texto NO debe crear un widget nuevo.

    Antes, `_stop_main_spinner_sync()` llamaba a `chat_log.stop_stream()` en
    cada chunk, lo que cerraba el widget en curso y hacía que la respuesta
    apareciera repetida tantas veces como fragmentos llegaran.
    """
    from kogniterm.terminal.tui.components.chat_log import MessageWidget

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        client = app._ensure_session_client(session)
        try:
            client._connected = True
            # El servidor va emitiendo la respuesta por fragmentos
            for chunk in ["Hola", ", ", "esto", " es", " una", " respuesta", " larga."]:
                client._route_event({"type": "stream", "data": chunk})
                await pilot.pause()
            client._route_event({"type": "live_stop"})
            await pilot.pause()
            await pilot.pause()

            widget = app._session_widget(session)
            msgs = [w for w in widget.children if isinstance(w, MessageWidget)]
            assert len(msgs) == 1, (
                f"la respuesta debe vivir en 1 widget, hay {len(msgs)} "
                f"(se está duplicando)"
            )
        finally:
            try:
                client._connected = False
                client.stop()
            except Exception:
                pass
            if session.ws_task is not None:
                try:
                    session.ws_task.cancel()
                except Exception:
                    pass
            session.ws_client = None
            session.ws_task = None


@pytest.mark.anyio
async def test_session_tab_has_close_button_and_closes():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _dismiss_splash(app, pilot)
        first = app.get_active_session()
        second = app.create_session(title="Para cerrar")
        await pilot.pause()
        await pilot.pause()

        # Cada pestaña tiene su botón de cierre
        assert app.query_one(f"#session-wrap-{first.session_id}") is not None
        close_btn = app.query_one(f"#session-close-{second.session_id}")
        assert str(close_btn.label.plain) == "×"

        # Cerrar con el evento del botón
        await pilot.click(f"#session-close-{second.session_id}")
        await pilot.pause()
        await pilot.pause()
        assert len(app.list_sessions()) == 1
        assert app.get_session(second.session_id) is None
        # No queda el botón de la pestaña cerrada
        with pytest.raises(Exception):
            app.query_one(f"#session-close-{second.session_id}")
        # La última pestaña no se puede cerrar
        assert app.close_session(first.session_id) is False


@pytest.mark.anyio
async def test_tab_colors_follow_active_theme():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        app._refresh_session_tabs()
        await pilot.pause()
        btn = app.query_one(f"#session-tab-{session.session_id}")
        active_bg = btn.styles.background
        assert active_bg is not None

        # Al cambiar de tema, la pestaña activa se repinta con la nueva paleta
        from kogniterm.terminal.themes import ColorPalette, set_kogniterm_theme

        set_kogniterm_theme("matrix")
        try:
            app.apply_theme("matrix", persist=False)
            await pilot.pause()
            new_bg = app.query_one(f"#session-tab-{session.session_id}").styles.background
            assert new_bg is not None
        finally:
            set_kogniterm_theme("default")
            app.apply_theme("default", persist=False)


@pytest.mark.anyio
async def test_inactive_busy_tab_keeps_visible_label():
    """Regression: un borde en la pestaña (1 fila) ocultaba el nombre.

    Al cambiar de pestaña, la que queda inactiva se pintaba con un borde que
    consumía toda su altura y su nombre desaparecía.
    """
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = app.get_active_session()
        second = app.create_session(title="Segunda")
        await pilot.pause(); await pilot.pause()

        # La primera queda ocupada mientras la segunda es la activa
        first.is_processing = True
        app.switch_session(second.session_id)
        await pilot.pause(); await pilot.pause()

        btn = app.query_one(f"#session-tab-{first.session_id}")
        # El nombre sigue presente
        assert "Sesión 1" in btn.label.plain
        # La pestaña mantiene su única fila: ningún borde visible que se la coma
        assert btn.styles.height.value == 1
        for edge in (btn.styles.border_top, btn.styles.border_bottom):
            assert not (edge and edge[0]), f"borde no vacío: {edge}"


@pytest.mark.anyio
async def test_processing_tab_shows_animated_spinner():
    import asyncio as _asyncio

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        btn = app.query_one(f"#session-tab-{session.session_id}")
        frames = set(app.SESSION_SPINNER_FRAMES)

        # Sin trabajo: sin spinner
        assert btn.label.plain.strip() == session.title

        # El agente empieza a trabajar -> spinner
        session.is_processing = True
        app._refresh_session_tabs()
        await pilot.pause()
        assert btn.label.plain.split()[0] in frames, btn.label.plain

        # El spinner anima (el frame avanza)
        seen = {btn.label.plain.split()[0]}
        for _ in range(12):
            await _asyncio.sleep(0.13)
            await pilot.pause()
            seen.add(btn.label.plain.split()[0])
        assert len(seen) > 1, "el spinner debería animar"

        # Al terminar, el spinner desaparece y el timer se para
        session.is_processing = False
        app._refresh_session_tabs()
        await pilot.pause()
        assert btn.label.plain.strip() == session.title
        assert app._session_spinner_timer is None


@pytest.mark.anyio
async def test_session_title_from_request_and_llm():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        btn = app.query_one(f"#session-tab-{session.session_id}")

        # Título provisional inmediato según la petición (máx 40 en el modelo)
        app._provisional_title_from_request(
            session, "arregla el error de autenticación"
        )
        await pilot.pause()
        assert session.title == "arregla el error de autenticación"
        assert "arregla" in btn.label.plain

        # Un título del LLM lo sustituye
        app._apply_session_title(session.session_id, "Fix de autenticación")
        await pilot.pause()
        assert session.title == "Fix de autenticación"
        assert btn.label.plain.strip() == "Fix de autenticación"

        # Ya no se pisa con otro provisional
        app._provisional_title_from_request(session, "otra cosa distinta")
        assert session.title == "Fix de autenticación"


@pytest.mark.anyio
async def test_long_title_is_truncated_with_dots():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        btn = app.query_one(f"#session-tab-{session.session_id}")

        largo = "Implementar un sistema distribuido con colas y reintentos"
        app._apply_session_title(session.session_id, largo)
        await pilot.pause()
        shown = btn.label.plain.strip()
        assert len(shown) <= 26, shown
        assert shown.endswith("..."), shown
        assert not shown.endswith("…"), "debe usar '...'"

        # El título completo se conserva en el modelo
        assert session.title == largo


@pytest.mark.anyio
async def test_server_title_event_updates_tab():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        client = app._ensure_session_client(session)
        try:
            client._route_event(
                {"type": "thread_title_updated", "data": {"title": "Título del servidor"}}
            )
            await pilot.pause()
            assert session.title == "Título del servidor"
            btn = app.query_one(f"#session-tab-{session.session_id}")
            assert btn.label.plain.strip() == "Título del servidor"
        finally:
            try:
                client.stop()
            except Exception:
                pass
            if session.ws_task is not None:
                try:
                    session.ws_task.cancel()
                except Exception:
                    pass
            session.ws_client = None
            session.ws_task = None


@pytest.mark.anyio
async def test_send_long_message_shows_dots_in_tab():
    """E2E: al enviar una petición larga, la pestaña muestra '...'."""
    from unittest.mock import MagicMock, AsyncMock

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        # El agente responde al instante (sin LLM real)
        fake_mgr = MagicMock()
        fake_mgr.invoke_agent.return_value = {"messages": []}
        session.interaction_manager = fake_mgr
        session._managers_ready = True

        largo = "necesito que implementes por favor el sistema completo de pagos"
        assert len(largo) > 20
        await app._handle_input_async(largo, session.session_id)
        await pilot.pause()
        await pilot.pause()

        btn = app.query_one(f"#session-tab-{session.session_id}")
        shown = btn.label.plain.strip()
        # Sin el spinner (no hay proceso), debe verse el título cortado con ...
        core = shown[2:].strip() if shown[:1] in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏" else shown
        assert core.endswith("..."), f"sin puntos: {shown!r}"
        assert len(core) <= 26, f"demasiado largo: {shown!r}"


@pytest.mark.anyio
async def test_tab_marquee_scrolls_long_title_on_hover():
    import asyncio as _asyncio

    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await _dismiss_splash(app, pilot)
        session = app.get_active_session()
        largo = "Implementar el sistema completo de pagos distribuidos"
        assert len(largo) > 20
        app._apply_session_title(session.session_id, largo)
        await pilot.pause()
        btn = app.query_one(f"#session-tab-{session.session_id}")
        static = btn.label.plain
        assert static.strip().endswith("..."), static

        # Al posicionar el ratón, la marquesina empieza a desplazar el título
        await pilot.hover(f"#session-tab-{session.session_id}")
        seen = set()
        for _ in range(14):
            await _asyncio.sleep(0.26)
            seen.add(app.query_one(f"#session-tab-{session.session_id}").label.plain)
        # Debe haber mostrado varias ventanas desplazándose a la izquierda
        assert len(seen) > 2, f"la marquesina no se movió: {seen}"
        assert any(
            not v.startswith("Implementar") for v in seen
        ), f"nunca avanzó más allá de la cabecera: {seen}"
        assert any("complet" in v for v in seen), f"nunca mostró el medio: {seen}"

        # Al salir el ratón, vuelve la etiqueta estática con "..."
        await pilot.hover("#new_session_btn")
        await pilot.pause()
        restored = app.query_one(f"#session-tab-{session.session_id}").label.plain
        assert restored.strip().endswith("..."), restored
        assert app._marquee_timer is None


@pytest.mark.anyio
async def test_tab_marquee_ignores_short_titles():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        session = app.get_active_session()
        app._tab_hover_enter(session.session_id)
        # "Sesión 1" cabe entero: no arranca ningún timer
        assert app._hover_tab_id is None
        assert app._marquee_timer is None
