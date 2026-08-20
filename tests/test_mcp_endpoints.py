import pytest
from fastapi.testclient import TestClient
from kogniterm.server.app import app

client = TestClient(app)

def test_list_mcp_servers_endpoint():
    response = client.get("/api/mcp/servers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

def test_test_mcp_connection_endpoint():
    response = client.post("/api/mcp/test-connection", json={"transport": "stdio"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
