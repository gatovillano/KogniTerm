import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from kogniterm.server.config import server_config, HeartbeatConfig, ServerSettings
from kogniterm.server.heartbeat_manager import HeartbeatScheduler, heartbeat_scheduler
from kogniterm.server.app import create_app


@pytest.fixture(autouse=True)
def clean_server_config(tmp_path):
    """Asegura un entorno limpio de configuración de servidor usando un archivo temporal."""
    test_config_file = tmp_path / "server_config.json"
    original_config_file = server_config.CONFIG_FILE
    server_config.CONFIG_FILE = test_config_file
    server_config.settings = ServerSettings()
    server_config.save_config(server_config.settings)
    yield
    server_config.CONFIG_FILE = original_config_file


def test_heartbeat_config_model():
    """Prueba la validación y creación del modelo HeartbeatConfig."""
    hb = HeartbeatConfig(
        name="Git Watcher",
        prompt="Check git status",
        interval_seconds=60,
    )
    assert hb.id is not None
    assert hb.enabled is True
    assert hb.name == "Git Watcher"
    assert hb.prompt == "Check git status"
    assert hb.interval_seconds == 60
    assert hb.session_id is None
    assert hb.last_run is None


def test_server_config_manager_heartbeats():
    """Prueba la gestión de heartbeats en ServerConfigManager."""
    hb1 = HeartbeatConfig(id="hb_1", name="HB 1", prompt="Prompt 1", interval_seconds=10)
    hb2 = HeartbeatConfig(id="hb_2", name="HB 2", prompt="Prompt 2", interval_seconds=20)

    # Agregar
    server_config.add_heartbeat(hb1)
    server_config.add_heartbeat(hb2)
    assert len(server_config.settings.heartbeats) == 2

    # Toggle
    server_config.toggle_heartbeat("hb_1", False)
    assert server_config.settings.heartbeats[0].enabled is False

    # Status update
    server_config.update_heartbeat_status("hb_2", "success", run_time="2026-08-05T20:00:00")
    assert server_config.settings.heartbeats[1].last_status == "success"
    assert server_config.settings.heartbeats[1].last_run == "2026-08-05T20:00:00"

    # Remove
    server_config.remove_heartbeat("hb_1")
    assert len(server_config.settings.heartbeats) == 1
    assert server_config.settings.heartbeats[0].id == "hb_2"


def test_heartbeat_rest_api_endpoints():
    """Prueba los endpoints REST de administración de heartbeats."""
    app = create_app()
    client = TestClient(app)

    # GET inicial
    res = client.get("/config/heartbeats")
    assert res.status_code == 200
    assert res.json() == {"heartbeats": []}

    # POST (crear)
    payload = {
        "id": "test_hb_1",
        "name": "System Health",
        "prompt": "Check server RAM and disk space",
        "interval_seconds": 120,
        "enabled": True,
    }
    res = client.post("/config/heartbeats", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["heartbeat"]["id"] == "test_hb_1"

    # GET (listar)
    res = client.get("/config/heartbeats")
    assert res.status_code == 200
    heartbeats = res.json()["heartbeats"]
    assert len(heartbeats) == 1
    assert heartbeats[0]["name"] == "System Health"

    # PATCH toggle
    res = client.patch("/config/heartbeats/test_hb_1/toggle?enabled=false")
    assert res.status_code == 200
    assert res.json()["enabled"] is False

    # DELETE
    res = client.delete("/config/heartbeats/test_hb_1")
    assert res.status_code == 200
    assert res.json()["status"] == "deleted"

    res = client.get("/config/heartbeats")
    assert len(res.json()["heartbeats"]) == 0


@pytest.mark.asyncio
async def test_heartbeat_scheduler_execution():
    """Prueba la ejecución asíncrona y la sincronización de tareas de HeartbeatScheduler."""
    scheduler = HeartbeatScheduler()
    hb = HeartbeatConfig(id="hb_async", name="Async HB", prompt="Say hello", interval_seconds=10)
    server_config.add_heartbeat(hb)

    mock_session = MagicMock()
    mock_session.send = AsyncMock()

    with patch("kogniterm.server.heartbeat_manager.pool") as mock_pool:
        mock_pool.wait_until_ready = AsyncMock()
        mock_pool.get_or_create.return_value = mock_session
        mock_pool._executor = MagicMock()

        # Disparar ejecución manual
        success = await scheduler.trigger_heartbeat("hb_async")
        assert success is True

        mock_pool.wait_until_ready.assert_awaited_once()
        mock_pool.get_or_create.assert_called_once_with("heartbeat_hb_async")
        mock_session.send.assert_awaited_once_with("Say hello", mock_pool._executor)

        # Verificar actualización de status
        hb_config = server_config.settings.heartbeats[0]
        assert hb_config.last_status == "success"
        assert hb_config.last_run is not None
