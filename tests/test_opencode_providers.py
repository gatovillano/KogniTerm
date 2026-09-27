try:
    import pytest
except ImportError:
    class MockPytest:
        class mark:
            @staticmethod
            def asyncio(f): return f
    pytest = MockPytest()
from httpx import AsyncClient, ASGITransport
from kogniterm.server.app import create_app

@pytest.mark.asyncio
async def test_opencode_provider_list():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test v2 (/api/provider)
        resp = await client.get("/api/provider")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        providers = data["data"]
        assert isinstance(providers, list)
        provider_ids = [p["id"] for p in providers]
        assert "google" in provider_ids
        # Check provider structure
        google_p = next(p for p in providers if p["id"] == "google")
        assert "models" in google_p
        assert isinstance(google_p["models"], dict)

        # Test v1 (/provider)
        resp_v1 = await client.get("/provider")
        assert resp_v1.status_code == 200
        v1_data = resp_v1.json()
        assert isinstance(v1_data, list)

@pytest.mark.asyncio
async def test_opencode_model_list():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/model")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        models = data["data"]
        assert isinstance(models, list)
        assert len(models) > 0
        first = models[0]
        assert "id" in first
        assert "name" in first
        assert "providerID" in first

@pytest.mark.asyncio
async def test_opencode_default_model():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/model/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        model = data["data"]
        assert "id" in model
        assert "providerID" in model

@pytest.mark.asyncio
async def test_opencode_provider_caching():
    import time
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First call warms cache
        await client.get("/api/provider")
        # Second call should be near-instantaneous (< 100ms)
        t0 = time.time()
        resp = await client.get("/api/provider")
        t1 = time.time()
        assert resp.status_code == 200
        assert (t1 - t0) < 0.1, f"Cached response took too long: {t1 - t0:.3f}s"

if __name__ == "__main__":
    import asyncio
    async def run_all():
        print("Running test_opencode_provider_list...")
        await test_opencode_provider_list()
        print("Running test_opencode_model_list...")
        await test_opencode_model_list()
        print("Running test_opencode_default_model...")
        await test_opencode_default_model()
        print("Running test_opencode_provider_caching...")
        await test_opencode_provider_caching()
        print("ALL TESTS PASSED!")

    asyncio.run(run_all())
