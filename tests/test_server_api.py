import pytest
import os
from fastapi.testclient import TestClient
from kogniterm.server.app import create_app, API_TOKEN

def test_workspace_files_endpoint(tmp_path, monkeypatch):
    # Setup mock workspace files
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "app_spec.tsx").write_text("export default App")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("// ignore")

    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = client.get("/api/workspace/files?query=app_spec", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    paths = [item["path"] for item in data["results"]]
    assert "app_spec.tsx" in paths
    assert "node_modules/ignored.js" not in paths


def test_inception_in_available_models(monkeypatch):
    monkeypatch.setenv("INCEPTION_API_KEY", "test-key-xyz")
    app = create_app()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = client.get("/api/models/available", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    inception = next((p for p in data["providers"] if p["id"] == "inception"), None)
    assert inception is not None
    assert inception["name"] == "Inception Labs"
    assert "inception/mercury-2" in inception["models"]


def test_update_llm_config_inception(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = client.post(
        "/api/config/llm",
        headers=headers,
        json={"provider": "inception"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "mercury-2" in data["model"]
    assert data["provider"] == "inception"

    # Verify get_llm_config reflects inception
    config_resp = client.get("/api/config/llm", headers=headers)
    assert config_resp.status_code == 200
    cfg = config_resp.json()
    assert cfg["provider"] == "inception"
    assert "mercury-2" in cfg["model"]


def test_set_key_endpoint(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = client.post(
        "/api/config/set_key",
        headers=headers,
        json={"provider": "inception", "key_value": "test-secret-key-123", "scope": "global"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    from kogniterm.terminal.config_manager import ConfigManager
    cm = ConfigManager()
    assert cm.get_api_key("inception") == "test-secret-key-123"

