import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.tui_app import KogniTermTUI


@pytest.mark.anyio
async def test_input_container_remains_centered_during_spinner():
    """Verify that #input_container does not shift horizontally when the spinner/live_display is active."""
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test(size=(120, 30)) as pilot:
        bc = app.query_one("#bottom_container")
        bc.display = True
        await pilot.pause()

        ic = app.query_one("#input_container")
        ld = app.query_one("#live_display")

        # Before spinner
        x_before = ic.region.x
        assert x_before > 0, "Input container should be centered with margin > 0"
        assert ld.display is False

        # Start spinner
        app.is_processing = True
        app._start_spinner()
        await pilot.pause()

        assert ld.display is True
        x_during = ic.region.x
        ld_x = ld.region.x

        # Verify #input_container position does not shift
        assert x_during == x_before, f"Input container shifted horizontally: was {x_before}, became {x_during}"
        # Verify #live_display has the exact same centered x coordinate
        assert ld_x == x_before, f"Live display x ({ld_x}) does not match input container x ({x_before})"

        # Stop spinner
        app.is_processing = False
        app._stop_spinner()
        await pilot.pause()

        x_after = ic.region.x
        assert ld.display is False
        assert x_after == x_before, f"Input container shifted after spinner: was {x_before}, became {x_after}"
