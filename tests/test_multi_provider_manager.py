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
