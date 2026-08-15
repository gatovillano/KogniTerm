import os

from kogniterm.core.multi_provider_manager import ProviderConfig


def test_ollama_local_is_configured_when_target_is_local(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
    monkeypatch.setenv("OLLAMA_PROVIDER_TARGET", "local")

    provider = ProviderConfig(
        name="ollama",
        model_prefix="ollama",
        api_key_env="OLLAMA_API_KEY",
        api_base="http://localhost:11434",
        api_base_env="OLLAMA_API_BASE",
    )

    assert provider.is_configured() is True


def test_ollama_cloud_is_not_configured_when_target_is_local(monkeypatch):
    monkeypatch.setenv("OLLAMA_PROVIDER_TARGET", "local")
    monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "dummy-cloud-key")

    provider = ProviderConfig(
        name="ollama_cloud",
        model_prefix="ollama",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        api_base="https://ollama.com/v1",
    )

    assert provider.is_configured() is False


def test_ollama_local_is_not_configured_when_target_is_cloud(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
    monkeypatch.setenv("OLLAMA_PROVIDER_TARGET", "cloud")

    provider = ProviderConfig(
        name="ollama",
        model_prefix="ollama",
        api_key_env="OLLAMA_API_KEY",
        api_base="http://localhost:11434",
        api_base_env="OLLAMA_API_BASE",
    )

    assert provider.is_configured() is False


def test_execute_with_fallback_handles_429_generator_error(monkeypatch):
    import requests
    from kogniterm.core.multi_provider_manager import MultiProviderManager, ProviderConfig

    monkeypatch.setenv("TEST_KEY_1", "dummy1")
    monkeypatch.setenv("TEST_KEY_2", "dummy2")

    manager = MultiProviderManager()
    p1 = ProviderConfig(name="primary", model_prefix="test", api_key_env="TEST_KEY_1")
    p2 = ProviderConfig(name="secondary", model_prefix="test", api_key_env="TEST_KEY_2")
    manager.providers = {"primary": p1, "secondary": p2}
    manager.fallback_chain = ["primary", "secondary"]

    call_history = []

    def mock_execute(*args, **kwargs):
        provider = kwargs.get("force_provider")
        call_history.append(provider.name)
        if provider.name == "primary":
            # Simular un error 429 (Resource Exhausted) durante la iteración del generador
            raise requests.HTTPError("API Error (429): Resource has been exhausted")
            yield  # convertir a generador
        else:
            yield "success_from_secondary"

    manager.execute = mock_execute

    gen = manager.execute_with_fallback(model_name="test-model")
    res = list(gen)

    assert res == ["success_from_secondary"]
    assert call_history == ["primary", "secondary"]

