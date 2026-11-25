import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.tui_app import KogniTermTUI
from kogniterm.terminal.tui.components.status_footer import StatusFooter
from kogniterm.terminal.tui.components.task_tracker_panel import TaskTrackerPanelWidget


@pytest.mark.anyio
async def test_opencode_splash_and_theme_surfaces():
    """Verifica el card del splash, tokens de superficie y cambio de tema."""
    llm_service = MagicMock()
    llm_service.model_name = "anthropic/claude-sonnet-4"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()

        assert app.query_one("#splash_card") is not None
        assert app.query_one("#splash_workspace_bar") is not None
        assert app.query_one("#splash_subtitle") is not None
        assert app.query_one("#splash_prompt_glyph") is not None
        assert app.query_one("#input_prompt") is not None

        # Aplicar tema oscuro y tema claro sin persistir
        app.apply_theme("dracula", persist=False)
        await pilot.pause()
        assert app.dark is True
        assert app.theme == "textual-dark"

        app.apply_theme("light", persist=False)
        await pilot.pause()
        assert app.dark is False
        assert app.theme == "textual-light"


@pytest.mark.anyio
async def test_tool_output_terminal_light_and_dark_theme():
    """Verifica que ToolOutputWidget adopte modo claro y remappee ANSI blanco."""
    from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
    from kogniterm.terminal.themes import ColorPalette

    llm_service = MagicMock()
    llm_service.model_name = "anthropic/claude-sonnet-4"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()
        app.apply_theme("light", persist=False)
        await pilot.pause()

        widget = ToolOutputWidget("", "execute_command", command="echo hola")
        await app.chat_log.mount(widget)
        widget.update_content("\x1b[37mhola mundo\x1b[0m", command="echo hola")
        await pilot.pause()

        assert str(widget.styles.background.hex).lower() == ColorPalette.GRAY_100.lower()
        assert str(widget.styles.color.hex).lower() == ColorPalette.TEXT_PRIMARY.lower()

        # Verificar que un carácter ANSI blanco se remapea a texto oscuro en modo claro
        rendered = widget._render_tool_output()
        assert "hola mundo" in rendered.plain
        assert any(
            span.style and getattr(span.style, "color", None)
            and span.style.color.name.lower() == ColorPalette.TEXT_PRIMARY.lower()
            for span in rendered.spans
        )

        # Cambiar a modo oscuro y verificar que la terminal vuelve a fondo oscuro
        app.apply_theme("dracula", persist=False)
        await pilot.pause()
        assert str(widget.styles.background.hex).lower() == "#0d1117"
        assert str(widget.styles.color.hex).lower() == "#f9fafb"


@pytest.mark.anyio
async def test_session_chat_light_mode_uses_dark_text():
    """Verifica que .session-chat y sus mensajes usen texto oscuro en modo claro."""
    from kogniterm.terminal.themes import ColorPalette

    llm_service = MagicMock()
    llm_service.model_name = "anthropic/claude-sonnet-4"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()
        app.apply_theme("light", persist=False)
        await pilot.pause()

        def _assert_dark_text(widget):
            triplet = widget.rich_style.color.triplet
            assert triplet is not None
            assert max(triplet.red, triplet.green, triplet.blue) < 80, f"Texto demasiado claro en modo claro: {triplet}"

        # Sesión inicial
        initial_log = app.chat_log
        initial_log.write_agent_message("Texto visible en modo claro")
        await pilot.pause()
        assert str(initial_log.styles.color.hex).lower() == ColorPalette.TEXT_PRIMARY.lower()
        _assert_dark_text(initial_log.children[-1])

        # Nueva pestaña creada después de aplicar modo claro
        new_session = app.create_session("Pestaña clara")
        await pilot.pause()
        new_log = app._session_widget(new_session)
        assert new_log is not None
        new_log.write_agent_message("Mensaje en nueva pestaña")
        await pilot.pause()
        assert str(new_log.styles.color.hex).lower() == ColorPalette.TEXT_PRIMARY.lower()
        _assert_dark_text(new_log.children[-1])


@pytest.mark.anyio
async def test_live_display_has_no_border_and_toasts_use_dark_text():
    """Verifica que el indicador Procesando... no tenga borde y que los toasts usen texto oscuro en modo claro."""
    from textual.widgets._toast import Toast

    llm_service = MagicMock()
    llm_service.model_name = "anthropic/claude-sonnet-4"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test(size=(120, 35), notifications=True) as pilot:
        await pilot.pause()
        app.apply_theme("light", persist=False)
        await pilot.pause()

        # live_display ("Procesando...") sin borde ni marco
        b = app.live_display.styles.border
        assert b.top[0] in ("", "none")
        assert b.bottom[0] in ("", "none")
        assert b.left[0] in ("", "none")
        assert b.right[0] in ("", "none")

        # Toast notification en modo claro con texto oscuro
        app.notify("Auto-aprobación activada ⚡", severity="information")
        await pilot.pause(0.2)
        toasts = list(app.screen.query(Toast))
        assert toasts, "Se esperaba al menos un Toast montado"
        triplet = toasts[-1].rich_style.color.triplet
        assert triplet is not None
        assert max(triplet.red, triplet.green, triplet.blue) < 80


@pytest.mark.anyio
async def test_opencode_auto_approve_footer_and_border():
    """Verifica el indicador de auto-aprobación en StatusFooter y borde del input."""
    llm_service = MagicMock()
    llm_service.model_name = "openai/gpt-4o"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()
        footer = app.query_one(StatusFooter)

        app.set_auto_approve_all(True)
        await pilot.pause()
        assert "Auto ON" in footer._build_right_text()

        app.set_auto_approve_all(False)
        await pilot.pause()
        assert "Shift+Tab" in footer._build_right_text()


def test_task_tracker_progress_bar():
    """Verifica que el resumen de tareas incluye la barra de progreso."""
    widget = TaskTrackerPanelWidget()
    widget.update_tasks({
        "agent": [
            {"task": "Analizar código", "status": "done"},
            {"task": "Aplicar mejoras", "status": "in-progress"},
        ]
    })
    summary_text = widget._summary_line().plain
    assert "1/2" in summary_text
    assert "█" in summary_text
    assert "░" in summary_text
