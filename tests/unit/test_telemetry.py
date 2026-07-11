import json
import pytest
from pathlib import Path
from kogniterm.core.delegation.telemetry import TelemetryTracker


def test_telemetry_recording(tmp_path):
    tracker = TelemetryTracker(session_id="test_session", workspace_dir=str(tmp_path))

    tracker.record_llm_call(model="gemini-1.5-pro", input_tokens=1000, output_tokens=500, cost=0.015)
    tracker.record_delegation(
        subagent_id="child_1",
        subagent_name="tester",
        task="write unit tests",
        depth=1,
        status="success",
        duration=2.5,
        summary="All tests passed",
    )

    # Verify saved JSON trace
    trace_file = tmp_path / ".kogniterm" / "telemetry" / "session_test_session.json"
    assert trace_file.exists()

    with open(trace_file, "r") as f:
        data = json.load(f)

    assert data["session_id"] == "test_session"
    assert data["total_cost"] == pytest.approx(0.015)
    assert data["total_input_tokens"] == 1000
    assert len(data["llm_calls"]) == 1
    assert len(data["delegations"]) == 1
    assert data["delegations"][0]["subagent_name"] == "tester"


def test_telemetry_accumulates_multiple_calls(tmp_path):
    tracker = TelemetryTracker(session_id="acc_session", workspace_dir=str(tmp_path))

    tracker.record_llm_call(model="gemini-1.5-flash", input_tokens=500, output_tokens=200, cost=0.005)
    tracker.record_llm_call(model="gemini-1.5-flash", input_tokens=300, output_tokens=100, cost=0.003)

    assert tracker.total_input_tokens == 800
    assert tracker.total_output_tokens == 300
    assert tracker.total_cost == pytest.approx(0.008)
    assert len(tracker.llm_calls) == 2


def test_telemetry_saves_after_each_record(tmp_path):
    """Cada record_* debe persistir el archivo inmediatamente."""
    tracker = TelemetryTracker(session_id="persist_test", workspace_dir=str(tmp_path))
    trace_file = tmp_path / ".kogniterm" / "telemetry" / "session_persist_test.json"

    assert not trace_file.exists()
    tracker.record_llm_call(model="gpt-4o-mini", input_tokens=100, output_tokens=50, cost=0.001)
    assert trace_file.exists()  # El archivo debe existir después del primer record


def test_telemetry_duration_is_positive(tmp_path):
    import time
    tracker = TelemetryTracker(session_id="dur_test", workspace_dir=str(tmp_path))
    time.sleep(0.01)
    tracker.record_llm_call(model="gpt-4o", input_tokens=10, output_tokens=5, cost=0.0001)

    trace_file = tmp_path / ".kogniterm" / "telemetry" / "session_dur_test.json"
    with open(trace_file) as f:
        data = json.load(f)

    assert data["total_duration"] > 0


def test_telemetry_delegation_fields(tmp_path):
    tracker = TelemetryTracker(session_id="deleg_test", workspace_dir=str(tmp_path))
    tracker.record_delegation(
        subagent_id="agent_abc",
        subagent_name="deep_coder",
        task="fix bug in module",
        depth=2,
        status="failed",
        duration=5.0,
        summary="Encountered import error",
    )

    trace_file = tmp_path / ".kogniterm" / "telemetry" / "session_deleg_test.json"
    with open(trace_file) as f:
        data = json.load(f)

    d = data["delegations"][0]
    assert d["subagent_id"] == "agent_abc"
    assert d["subagent_name"] == "deep_coder"
    assert d["depth"] == 2
    assert d["status"] == "failed"
    assert d["duration"] == pytest.approx(5.0)


def test_llm_service_telemetry_integration(tmp_path):
    from unittest.mock import MagicMock
    from kogniterm.core.llm_service import LLMService
    from langchain_core.messages import AIMessage, HumanMessage

    # Instanciar LLMService (usamos MagicMock para sus dependencias internas complejas)
    llm_service = LLMService.__new__(LLMService)
    llm_service.model_name = "gemini-1.5-flash"
    llm_service.history_manager = MagicMock()
    llm_service.history_manager.conversation_history = []
    
    # Configurar el tracker de telemetría
    tracker = TelemetryTracker(session_id="integration_session", workspace_dir=str(tmp_path))
    llm_service.telemetry_tracker = tracker

    # Simulamos el generador interno _invoke_inner
    def mock_invoke_inner(*args, **kwargs):
        yield AIMessage(content="Hello from mock LLM response")

    llm_service._invoke_inner = mock_invoke_inner

    # Consumir el generador invoke()
    results = list(llm_service.invoke(history=[HumanMessage(content="Hello")]))
    
    assert len(results) == 1
    assert results[0].content == "Hello from mock LLM response"
    
    # Comprobar que se grabó la llamada en telemetría
    trace_file = tmp_path / ".kogniterm" / "telemetry" / "session_integration_session.json"
    assert trace_file.exists()
    
    with open(trace_file) as f:
        data = json.load(f)
        
    assert len(data["llm_calls"]) == 1
    assert data["llm_calls"][0]["model"] == "gemini-1.5-flash"
    assert data["llm_calls"][0]["input_tokens"] > 0
    assert data["llm_calls"][0]["output_tokens"] > 0
    assert data["total_cost"] > 0

