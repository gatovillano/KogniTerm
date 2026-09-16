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


def test_workspaces_endpoints(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ws1 = tmp_path / "project1"
    ws1.mkdir()

    app = create_app()
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {API_TOKEN}"}

        # 1. List workspaces
        resp = client.get("/api/workspaces", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "workspaces" in data

        # 2. Add workspace
        add_resp = client.post(
            "/api/workspaces",
            headers=headers,
            json={"path": str(ws1), "name": "Project 1"}
        )
        assert add_resp.status_code == 201
        add_data = add_resp.json()
        assert add_data["status"] == "ok"
        assert add_data["workspace"]["path"] == str(ws1)

        # 3. Verify in list
        list_resp = client.get("/api/workspaces", headers=headers)
        paths = [w["path"] for w in list_resp.json()["workspaces"]]
        assert str(ws1) in paths

        # 4. Remove workspace
        del_resp = client.delete(
            f"/api/workspaces?path={str(ws1)}",
            headers=headers
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "ok"

        # 5. Verify removed
        final_resp = client.get("/api/workspaces", headers=headers)
        final_paths = [w["path"] for w in final_resp.json()["workspaces"]]
        assert str(ws1) not in final_paths


