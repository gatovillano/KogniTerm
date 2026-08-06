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
