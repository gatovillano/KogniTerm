import os
import json
import uuid
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from kogniterm.core.antigravity_client import AntigravityClient, run_login_flow
from kogniterm.core.multi_provider_manager import MultiProviderManager, ProviderConfig
from kogniterm.core.llm_service import LLMService

@patch("kogniterm.core.antigravity_client.requests.post")
def test_antigravity_is_logged_in_check(mock_post, tmp_path, monkeypatch):
    # Mock user path to point to a temp dir
    fake_home = str(tmp_path)
    monkeypatch.setenv("HOME", fake_home)
    token_dir = tmp_path / ".gemini" / "antigravity-cli"
    token_file = token_dir / "antigravity-oauth-token"
    
    # Reset class cache variables
    AntigravityClient._access_token = None
    AntigravityClient._token_expiry = 0
    AntigravityClient._project_id = None
    
    # 1. Not logged in initially
    assert AntigravityClient.is_logged_in() is False
    
    # 2. Logged in after creating token file
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps({
        "token": {
            "access_token": "old-token",
            "refresh_token": "fake-refresh-token"
        }
    }))
    
    assert AntigravityClient.is_logged_in() is True
    
    # Mock OAuth response for token refresh
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "fake-access-token",
        "expires_in": 3600
    }
    mock_post.return_value = mock_response
    
    assert AntigravityClient.get_token() == "fake-access-token"

@patch("kogniterm.core.antigravity_client.requests.post")
def test_antigravity_get_project_id(mock_post, tmp_path, monkeypatch):
    fake_home = str(tmp_path)
    monkeypatch.setenv("HOME", fake_home)
    token_dir = tmp_path / ".gemini" / "antigravity-cli"
    token_file = token_dir / "antigravity-oauth-token"
    
    AntigravityClient._access_token = "fake-access-token"
    AntigravityClient._token_expiry = 9999999999
    AntigravityClient._project_id = None
    
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps({
        "token": {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token"
        }
    }))
    
    # Mock loadCodeAssist response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "cloudaicompanionProject": "fake-token-project"
    }
    mock_post.return_value = mock_response
    
    assert AntigravityClient.get_project_id() == "fake-token-project"

@patch("kogniterm.core.antigravity_client.requests.post")
def test_antigravity_completion_stream(mock_post):
    # Mock a stream of Server-Sent Events (SSE)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        b'data: {"response": {"candidates": [{"content": {"parts": [{"text": "Hello "}]}}]}}',
        b'',
        b'data: {"response": {"candidates": [{"content": {"parts": [{"text": "world!"}]}}]}}'
    ]
    mock_post.return_value = mock_response

    # Mock token and project checks
    with patch.object(AntigravityClient, "get_token", return_value="fake-token"), \
         patch.object(AntigravityClient, "get_project_id", return_value="fake-project"):
         
        chunks = list(AntigravityClient.completion(
            model="antigravity/gemini-3-flash",
            messages=[{"role": "user", "content": "Hi"}],
            stream=True
        ))
        
        assert len(chunks) == 2
        assert chunks[0].choices[0].delta.content == "Hello "
        assert chunks[1].choices[0].delta.content == "world!"

@patch("kogniterm.core.antigravity_client.requests.post")
def test_antigravity_completion_non_stream(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello world non-stream!"}]
                }
            }]
        }
    }
    mock_post.return_value = mock_response

    with patch.object(AntigravityClient, "get_token", return_value="fake-token"), \
         patch.object(AntigravityClient, "get_project_id", return_value="fake-project"):
         
        response = AntigravityClient.completion(
            model="antigravity/gemini-3-flash",
            messages=[{"role": "user", "content": "Hi"}],
            stream=False
        )
        
        assert response.choices[0]["message"]["content"] == "Hello world non-stream!"

@patch("kogniterm.core.antigravity_client.AntigravityClient.completion")
def test_multi_provider_manager_routing(mock_completion):
    mock_completion.return_value = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Chunk"))])
    ]
    
    manager = MultiProviderManager()
    
    # Mock is_logged_in to bypass checks
    with patch.object(AntigravityClient, "is_logged_in", return_value=True):
        res = manager.execute(
            model_name="antigravity/gemini-3-flash",
            messages=[{"role": "user", "content": "Test"}],
            stream=True,
            provider="antigravity"
        )
        
        chunks = list(res)
        assert len(chunks) == 1
        assert chunks[0].choices[0].delta.content == "Chunk"
        mock_completion.assert_called_once()


@patch("kogniterm.core.antigravity_client.requests.post")
def test_antigravity_fetch_available_models_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": {
            "gemini-3-pro": {"displayName": "Gemini 3 Pro"},
            "gemini-3-flash": {"displayName": "Gemini 3 Flash"}
        }
    }
    mock_post.return_value = mock_response

    with patch.object(AntigravityClient, "get_token", return_value="fake-token"), \
         patch.object(AntigravityClient, "get_project_id", return_value="fake-project"):
         
        models = AntigravityClient.fetch_available_models()
        
        # Sorted by display name
        assert len(models) == 2
        assert models[0][0] == "antigravity/gemini-3-flash"
        assert models[0][1] == "🛸 Gemini 3 Flash (gemini-3-flash)"
        assert models[1][0] == "antigravity/gemini-3-pro"
        assert models[1][1] == "🛸 Gemini 3 Pro (gemini-3-pro)"


@patch("kogniterm.core.antigravity_client.requests.post")
def test_antigravity_fetch_available_models_fallback(mock_post):
    # Simulate API failure
    mock_post.side_effect = Exception("API error")

    with patch.object(AntigravityClient, "get_token", return_value="fake-token"), \
         patch.object(AntigravityClient, "get_project_id", return_value="fake-project"):
         
        models = AntigravityClient.fetch_available_models()
        
        # Verify fallback list is returned
        assert len(models) > 0
        assert any(m[0] == "antigravity/gemini-3-flash" for m in models)
        assert any(m[0] == "antigravity/gemini-2.5-pro" for m in models)


def test_thought_signature_propagation():
    from langchain_core.messages import AIMessage
    from kogniterm.core.llm_service import LLMService

    # Create AIMessage with thought_signatures in additional_kwargs
    ai_msg = AIMessage(
        content="Testing",
        tool_calls=[{"id": "call_123", "name": "test_tool", "args": {"foo": "bar"}}],
        additional_kwargs={"thought_signatures": {"call_123": "sig_abc"}}
    )

    # Convert to LiteLLM format
    service = LLMService()
    service.set_model("antigravity/gemini-2.5-flash")
    litellm_msg = service._to_litellm_message(ai_msg)

    # Verify that thought_signature is in the serialized tool call
    assert litellm_msg["role"] == "assistant"
    assert len(litellm_msg["tool_calls"]) == 1
    tc = litellm_msg["tool_calls"][0]
    assert tc["id"] == "call_123"
    assert tc["thought_signature"] == "sig_abc"

    # Map this LiteLLM format message to Antigravity's API payload format
    payload_msgs, system_instruction = AntigravityClient.map_messages([litellm_msg])
    
    assert len(payload_msgs) == 1
    assert payload_msgs[0]["role"] == "model"
    part = payload_msgs[0]["parts"][0]
    assert "functionCall" in part
    assert part["thoughtSignature"] == "sig_abc"
    assert part["functionCall"]["name"] == "test_tool"
    assert part["functionCall"]["args"] == {"foo": "bar"}


def test_thinking_config_injection():
    # Test that gemini-2.5-pro does NOT add thinkingConfig to request_payload because we disabled it to force manual CoT
    with patch.object(AntigravityClient, "get_token", return_value="fake-token"), \
         patch.object(AntigravityClient, "get_project_id", return_value="fake-project"), \
         patch("kogniterm.core.antigravity_client.requests.post") as mock_post:
         
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Hello world"}]
                    }
                }]
            }
        }
        mock_post.return_value = mock_response

        # Execute completion (non-stream) for gemini-2.5-pro
        AntigravityClient.completion(
            model="antigravity/gemini-2.5-pro",
            messages=[{"role": "user", "content": "Hi"}],
            stream=False
        )
        
        # Verify mock_post was called and request body does NOT contain thinkingConfig
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        request_body = call_kwargs["json"]
        request_payload = request_body["request"]
        
        # thinkingConfig should be absent because supports_thinking was set to False
        if "generationConfig" in request_payload:
            assert "thinkingConfig" not in request_payload["generationConfig"]


def test_agent_dynamic_prompts():
    from kogniterm.core.llm_service import LLMService
    from kogniterm.core.agents.code_agent import get_system_message as get_code_system
    from kogniterm.core.agents.researcher_agent import get_system_message as get_researcher_system
    
    service = LLMService()
    
    # Antigravity models should have "<thought>" manually prompted since we force manual CoT on them
    service.set_model("antigravity/gemini-3-flash")
    code_msg = get_code_system(service)
    researcher_msg = get_researcher_system(service)
    
    assert "<thought>" in code_msg.content
    assert "<thought>" in researcher_msg.content
    
    # Even gemini-2.5-pro (an Antigravity model) should have "<thought>" manually prompted now
    service.set_model("antigravity/gemini-2.5-pro")
    code_msg_thinking = get_code_system(service)
    researcher_msg_thinking = get_researcher_system(service)
    
    assert "<thought>" in code_msg_thinking.content
    assert "<thought>" in researcher_msg_thinking.content




