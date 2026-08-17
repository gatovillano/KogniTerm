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


def test_parse_model_name():
    from kogniterm.core.multi_provider_manager import MultiProviderManager

    owner, pure = MultiProviderManager._parse_model_name("openrouter/anthropic/claude-3.5-sonnet")
    assert owner == "anthropic"
    assert pure == "claude-3.5-sonnet"

    owner, pure = MultiProviderManager._parse_model_name("anthropic/claude-3-5-sonnet-20241022")
    assert owner == "anthropic"
    assert pure == "claude-3-5-sonnet-20241022"

    owner, pure = MultiProviderManager._parse_model_name("gpt-4o")
    assert owner == "openai"
    assert pure == "gpt-4o"

    owner, pure = MultiProviderManager._parse_model_name("gemini-2.5-flash")
    assert owner == "google"
    assert pure == "gemini-2.5-flash"


def test_resolve_model_for_provider_native_and_openrouter():
    from kogniterm.core.multi_provider_manager import MultiProviderManager, ProviderConfig

    manager = MultiProviderManager()
    p_google = ProviderConfig(name="google", model_prefix="gemini", api_key_env="GOOGLE_API_KEY")
    p_openrouter = ProviderConfig(name="openrouter", model_prefix="openrouter", api_key_env="OPENROUTER_API_KEY")
    p_anthropic = ProviderConfig(name="anthropic", model_prefix="anthropic", api_key_env="ANTHROPIC_API_KEY")

    # Native Google
    assert manager._resolve_model_for_provider(p_google, "gemini-2.5-flash") == "gemini/gemini-2.5-flash"
    assert manager._resolve_model_for_provider(p_google, "google/gemini-2.5-pro") == "gemini/gemini-2.5-pro"

    # OpenRouter
    assert manager._resolve_model_for_provider(p_openrouter, "anthropic/claude-3.5-sonnet") == "openrouter/anthropic/claude-3.5-sonnet"
    assert manager._resolve_model_for_provider(p_openrouter, "gpt-4o") == "openrouter/openai/gpt-4o"

    # Native Anthropic when given OpenRouter formatted model
    assert manager._resolve_model_for_provider(p_anthropic, "openrouter/anthropic/claude-3.5-sonnet") == "anthropic/claude-3.5-sonnet"


def test_resolve_model_for_provider_cross_fallback():
    from kogniterm.core.multi_provider_manager import MultiProviderManager, ProviderConfig

    manager = MultiProviderManager()
    p_google = ProviderConfig(name="google", model_prefix="gemini", api_key_env="GOOGLE_API_KEY")
    p_openai = ProviderConfig(name="openai", model_prefix="openai", api_key_env="OPENAI_API_KEY")
    p_anthropic = ProviderConfig(name="anthropic", model_prefix="anthropic", api_key_env="ANTHROPIC_API_KEY")

    # Cross-provider fallback: Anthropic Flagship -> Google (Must resolve to gemini/gemini-2.5-pro instead of gemini/claude...)
    resolved_google = manager._resolve_model_for_provider(p_google, "anthropic/claude-3-5-sonnet")
    assert resolved_google == "gemini/gemini-2.5-pro"

    # Cross-provider fallback: OpenAI Flagship -> Anthropic
    resolved_anthropic = manager._resolve_model_for_provider(p_anthropic, "gpt-4o")
    assert resolved_anthropic == "anthropic/claude-3-5-sonnet-20241022"

    # Cross-provider fallback: Fast Model -> Google
    resolved_fast_google = manager._resolve_model_for_provider(p_google, "gpt-4o-mini")
    assert resolved_fast_google == "gemini/gemini-2.5-flash"


