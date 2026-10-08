import pytest
from unittest.mock import MagicMock, patch
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget, MessageWidget
from kogniterm.terminal.tui.tui_app import KogniTermTUI
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.align import Align


@pytest.mark.anyio
async def test_chat_log_write_task_tracker_in_place_update():
    """
    Verifica que write_task_tracker crea un MessageWidget la primera vez
    y lo actualiza in-place en llamadas sucesivas, sin duplicar widgets.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log
        initial_children = len(list(chat_log.children))

        # 1. Primera llamada → debe montar un MessageWidget
        panel1 = Panel(Text("Estado inicial"))
        chat_log.write_task_tracker(panel1)
        await pilot.pause()

        children_after_first = list(chat_log.children)
        assert len(children_after_first) == initial_children + 1, \
            "Debe haberse montado exactamente 1 MessageWidget"
        tracker_widget = chat_log._last_tracker_widget
        assert tracker_widget is not None
        assert isinstance(tracker_widget, MessageWidget)

        # 2. Segunda llamada → actualiza in-place, NO monta widget nuevo
        panel2 = Panel(Text("Estado actualizado"))
        chat_log.write_task_tracker(panel2)
        await pilot.pause()

        children_after_second = list(chat_log.children)
        assert len(children_after_second) == len(children_after_first), \
            "La segunda llamada NO debe añadir un widget nuevo"
        assert chat_log._last_tracker_widget is tracker_widget, \
            "El widget de tracker debe ser el mismo objeto"

        # 3. Escribir un mensaje de usuario resetea _last_tracker_widget
        # Usamos la ruta interna directamente para evitar side-effects de UI
        chat_log._last_tracker_widget = None  # simula reset tras write_user_message

        # 4. Tercera llamada tras reset → monta un NUEVO MessageWidget
        panel3 = Panel(Text("Nuevo estado"))
        chat_log.write_task_tracker(panel3)
        await pilot.pause()

        children_after_third = list(chat_log.children)
        assert len(children_after_third) == len(children_after_second) + 1, \
            "Tras el reset debe montarse un widget nuevo"
        assert chat_log._last_tracker_widget is not tracker_widget

        # 5. clear() resetea _last_tracker_widget
        chat_log.clear()
        await pilot.pause()
        assert chat_log._last_tracker_widget is None
        assert len(list(chat_log.children)) == 0


@pytest.mark.anyio
async def test_write_user_message_resets_tracker_reference():
    """
    Verifica que write_user_message pone _last_tracker_widget a None
    para que la próxima actualización del tracker sea un widget fresco.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log

        # Establecer un tracker previo simulado
        dummy_widget = MessageWidget(Text("dummy"))
        chat_log._last_tracker_widget = dummy_widget

        # write_user_message debe resetear _last_tracker_widget
        chat_log.write_user_message("Hola")
        await pilot.pause()

        assert chat_log._last_tracker_widget is None, \
            "write_user_message debe resetear _last_tracker_widget a None"


@pytest.mark.anyio
async def test_update_task_tracker_routes_to_correct_log():
    """
    El dock replegable sobre el input recibe los planes de todos los
    agentes (ya no se inyectan paneles en el flujo del chat).
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        main_log = app.chat_log
        main_log.write_task_tracker = MagicMock()

        agent_plans = {
            "Coder": [{"task": "escribir tests", "status": "in-progress"}],
            "Researcher": [{"task": "buscar papers", "status": "pending"}],
            "MainAgent": [{"task": "planificación general", "status": "pending"}],
        }

        app.update_task_tracker(agent_plans)
        await pilot.pause()

        dock = app.query_one("#task_tracker_dock")
        assert dock.display is True, "El dock debe mostrarse con tareas pendientes"
        assert dock.expanded is False, "El dock arranca replegado"
        assert dock.get_summary()["total"] == 3
        assert main_log.write_task_tracker.called is False, \
            "Ya no debe inyectarse el tracker en el flujo del chat"


@pytest.mark.anyio
async def test_update_task_tracker_all_plans_to_main_log_when_no_match():
    """
    Sin coincidencia de agente, todo va igualmente al dock sobre el input.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        main_log = app.chat_log
        main_log.write_task_tracker = MagicMock()

        agent_plans = {
            "SomeRandomAgent": [{"task": "tarea cualquiera", "status": "pending"}],
        }

        app.update_task_tracker(agent_plans)
        await pilot.pause()

        dock = app.query_one("#task_tracker_dock")
        assert dock.display is True
        assert dock.get_summary()["total"] == 1
        assert main_log.write_task_tracker.called is False


@pytest.mark.anyio
async def test_task_tracker_dock_toggle_action():
    """Ctrl+K / click pliega y despliega el panel sobre el input."""
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        app.update_task_tracker({"A": [{"task": "t1", "status": "pending"}]})
        await pilot.pause()
        dock = app.query_one("#task_tracker_dock")
        assert dock.expanded is False

        app.action_toggle_task_tracker()
        await pilot.pause()
        assert dock.expanded is True

        app.action_toggle_task_tracker()
        await pilot.pause()
        assert dock.expanded is False
