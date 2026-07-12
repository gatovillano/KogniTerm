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


def test_multi_provider_manager_fallback_on_unavailable_and_eof(monkeypatch):
    from unittest.mock import MagicMock
    from kogniterm.core.multi_provider_manager import MultiProviderManager, ProviderConfig

    # Crear dos proveedores de prueba
    p1 = ProviderConfig(
        name="p1_primary",
        model_prefix="p1",
        api_key_env="P1_KEY",
        priority=1,
    )
    p2 = ProviderConfig(
        name="p2_fallback",
        model_prefix="p2",
        api_key_env="P2_KEY",
        priority=2,
    )

    # Configurar el manager
    manager = MultiProviderManager()
    manager.providers = [p1, p2]

    # Mockear is_configured para que ambos estén listos
    monkeypatch.setattr(p1, "is_configured", lambda: True)
    monkeypatch.setattr(p2, "is_configured", lambda: True)

    # Mockear execute para simular fallos
    call_count = 0
    def mock_execute(model_name, force_provider=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if force_provider == p1:
            raise Exception("OpenAIException - failed to load model: rpc error: code = Unavailable desc = error reading from server: EOF")
        elif force_provider == p2:
            return "success_fallback"
        raise Exception("Proveedor inesperado")

    monkeypatch.setattr(manager, "execute", mock_execute)

    # Ejecutar con fallback
    result = manager.execute_with_fallback(model_name="p1/some-model", messages=[])
    
    assert result == "success_fallback"
    assert call_count == 2  # Debe haber intentado p1 y luego p2

