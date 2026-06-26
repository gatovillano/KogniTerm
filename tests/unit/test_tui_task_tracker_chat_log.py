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
    Verifica que update_task_tracker rutea correctamente los planes de cada agente
    al ChatLogWidget que corresponde según su ID, y el resto al chat_log principal.
    Usa pestañas dinámicas (nueva arquitectura).
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        # Crear pestañas dinámicas para los agentes (nueva arquitectura)
        coder_log = app.add_agent_tab("agent_panel_coder_0", "Coder")
        researcher_log = app.add_agent_tab("agent_panel_researcher_1", "Researcher")
        await pilot.pause()

        main_log = app.chat_log

        coder_log.write_task_tracker = MagicMock()
        researcher_log.write_task_tracker = MagicMock()
        main_log.write_task_tracker = MagicMock()

        # Planes para: Coder → agent_panel_coder_0, Researcher → agent_panel_researcher_1,
        # MainAgent → sin coincidencia → chat_log
        agent_plans = {
            "Coder": [{"task": "escribir tests", "status": "in-progress"}],
            "Researcher": [{"task": "buscar papers", "status": "pending"}],
            "MainAgent": [{"task": "planificación general", "status": "pending"}],
        }

        app.update_task_tracker(agent_plans)
        await pilot.pause()

        assert coder_log.write_task_tracker.called, \
            "El plan de 'Coder' debe rutearse al panel del Coder"
        assert researcher_log.write_task_tracker.called, \
            "El plan de 'Researcher' debe rutearse al panel del Researcher"
        assert main_log.write_task_tracker.called, \
            "El plan de 'MainAgent' (sin coincidencia) debe ir al chat_log principal"


@pytest.mark.anyio
async def test_update_task_tracker_all_plans_to_main_log_when_no_match():
    """
    Cuando el nombre del agente no coincide con ningún widget específico,
    todo debe ir al chat_log principal.
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

        assert main_log.write_task_tracker.called, \
            "Sin coincidencia de ID, el plan debe ir al chat_log principal"
