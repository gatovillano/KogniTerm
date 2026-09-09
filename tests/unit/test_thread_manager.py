import asyncio
import os
import pytest
import shutil
from langchain_core.messages import HumanMessage, AIMessage
from kogniterm.core.thread_manager import ThreadManager

@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    yield str(workspace)
    if workspace.exists():
        shutil.rmtree(workspace)

def test_thread_manager_basic_crud(temp_workspace):
    tm = ThreadManager(workspace_dir=temp_workspace)
    
    # 1. Create a thread
    thread = tm.create_thread(title="Test Thread")
    assert thread.id is not None
    assert thread.title == "Test Thread"
    
    # 2. Get thread metadata
    meta = tm.get_thread_metadata(thread.id)
    assert meta is not None
    assert meta["title"] == "Test Thread"
    
    # 3. Load thread messages (empty initially)
    messages = tm.load_thread_messages(thread.id)
    assert len(messages) == 0
    
    # 4. Save thread messages
    history = [
        HumanMessage(content="Hello assistant"),
        AIMessage(content="Hello human")
    ]
    saved = tm.save_thread_messages(thread.id, history)
    assert saved is True
    
    # 5. Reload thread messages
    loaded = tm.load_thread_messages(thread.id)
    assert len(loaded) == 2
    assert loaded[0].content == "Hello assistant"
    assert loaded[1].content == "Hello human"

def test_thread_manager_find_threads(temp_workspace):
    tm = ThreadManager(workspace_dir=temp_workspace)
    
    t1 = tm.create_thread(title="Authenticating with GitHub")
    t2 = tm.create_thread(title="Debugging memory leak in TUI")
    t3 = tm.create_thread(title="Simple conversation")
    
    # Save a dummy message so metadata is fully written
    tm.save_thread_messages(t1.id, [HumanMessage(content="msg1")])
    tm.save_thread_messages(t2.id, [HumanMessage(content="msg2")])
    tm.save_thread_messages(t3.id, [HumanMessage(content="msg3")])
    
    # Search by partial title
    matches = tm.find_threads("git")
    assert len(matches) == 1
    assert matches[0]["title"] == "Authenticating with GitHub"
    
    # Search case-insensitive
    matches = tm.find_threads("tui")
    assert len(matches) == 1
    assert matches[0]["title"] == "Debugging memory leak in TUI"
    
    # Search with multiple matches
    matches = tm.find_threads("ing")
    assert len(matches) == 2  # GitHub (Authenticating) and Debugging
    
    # Search by ID
    matches = tm.find_threads(t3.id[:8])
    assert len(matches) >= 1

def test_thread_manager_current_thread_tracking(temp_workspace):
    tm = ThreadManager(workspace_dir=temp_workspace)
    assert tm.get_current_thread_id() is None
    
    t1 = tm.create_thread(title="First")
    assert tm.get_current_thread_id() == t1.id
    
    tm.set_current_thread_id("another_id")
    assert tm.get_current_thread_id() == "another_id"

def test_thread_manager_known_workspaces_persistence(tmp_path, monkeypatch):
    global_kogni = tmp_path / "global_kogniterm"
    global_kogni.mkdir()
    
    # Monkeypatch home directory for safe_abs_path("~")
    monkeypatch.setenv("HOME", str(global_kogni))

    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    ws2 = tmp_path / "ws2"
    ws2.mkdir()

    tm1 = ThreadManager(workspace_dir=str(ws1))
    t1 = tm1.create_thread(title="Hilo en WS1", workspace_dir=str(ws1))

    tm1.register_workspace(str(ws2))
    tm2_instance = ThreadManager(workspace_dir=str(ws2))
    t2 = tm2_instance.create_thread(title="Hilo en WS2", workspace_dir=str(ws2))

    # Re-instanciar ThreadManager desde un directorio diferente (simulando TUI en ws1 o ws2)
    tm3 = ThreadManager(workspace_dir=str(ws1))
    all_threads = tm3.list_threads()
    
    thread_ids = [t["id"] for t in all_threads]
    assert t1.id in thread_ids
    assert t2.id in thread_ids


def test_chat_thread_default_title_source():
    from kogniterm.core.chat_thread import ChatThread
    thread = ChatThread()
    assert thread.title_source == "default"


def test_thread_manager_fallback_title_cleaning():
    from kogniterm.core.thread_manager import ThreadManager

    # Saludos iniciales removidos y formateo limpio
    assert ThreadManager._fallback_title("Hola, necesito crear un script de bash") == "Crear un script de bash"
    assert ThreadManager._fallback_title("Buenas! Podrías ayudarme a refactorizar el código?") == "Refactorizar el código"
    assert ThreadManager._fallback_title("Hello, please fix the database query") == "Fix the database query"

    # Markdown y código
    assert ThreadManager._fallback_title("```python\ndef test(): pass\n```") == "Código python"
    assert ThreadManager._fallback_title("Revisa https://github.com/repo y dime qué opinas") == "Revisa y dime qué opinas"

    # Mensajes cortos o vacíos
    assert ThreadManager._fallback_title("") == "Nueva conversación"
    assert ThreadManager._fallback_title("   ") == "Nueva conversación"
    assert ThreadManager._fallback_title("hola") == "Nueva conversación"


@pytest.mark.asyncio
async def test_generate_title_if_needed_with_fallback_source(temp_workspace):
    from unittest.mock import MagicMock, AsyncMock
    tm = ThreadManager(workspace_dir=temp_workspace)
    thread = tm.create_thread(title="Script de bash")
    thread.title_source = "fallback"
    tm.save_thread(thread)

    mock_llm = MagicMock()
    tm._call_llm_for_title = AsyncMock(return_value="Automatización de scripts")

    # Requiere únicamente HumanMessage
    messages = [HumanMessage(content="Crea un script para backup")]
    new_title = await tm.generate_title_if_needed(thread.id, messages, mock_llm)

    assert new_title == "Automatización de scripts"
    updated = tm.get_thread(thread.id)
    assert updated.title == "Automatización de scripts"
    assert updated.title_source == "llm"


@pytest.mark.asyncio
async def test_generate_title_if_needed_ignores_manual_source(temp_workspace):
    from unittest.mock import MagicMock, AsyncMock
    tm = ThreadManager(workspace_dir=temp_workspace)
    thread = tm.create_thread(title="Mi Título Manual")
    thread.title_source = "manual"
    tm.save_thread(thread)

    mock_llm = MagicMock()
    tm._call_llm_for_title = AsyncMock(return_value="Otro título")

    messages = [HumanMessage(content="Crea un script")]
    new_title = await tm.generate_title_if_needed(thread.id, messages, mock_llm)

    assert new_title is None
    updated = tm.get_thread(thread.id)
    assert updated.title == "Mi Título Manual"
    assert updated.title_source == "manual"


@pytest.mark.asyncio
async def test_session_pool_auto_naming_trigger(temp_workspace):
    from unittest.mock import MagicMock, AsyncMock
    from kogniterm.server.session_pool import AgentSession

    tm = ThreadManager(workspace_dir=temp_workspace)
    thread = tm.create_thread(thread_id="test-session-1")
    
    mock_llm = MagicMock()
    mock_llm.model_name = "test-model"
    mock_llm.max_history_messages = 20
    mock_llm.max_history_chars = 10000
    mock_llm.auto_save_interval = 60
    mock_llm.skill_manager = None
    tm._call_llm_for_title = AsyncMock(return_value="Título Generado por IA")

    loop = asyncio.get_running_loop()
    session = AgentSession(
        session_id="test-session-1",
        llm_service=mock_llm,
        loop=loop,
        thread_manager=tm,
        workspace_dir=temp_workspace,
    )

    # Sin mensajes aún, no genera
    await session._try_generate_title()
    updated = tm.get_thread("test-session-1")
    assert updated.title == "Nueva conversación"

    # Con mensaje de usuario
    session.agent_state.add_message(HumanMessage(content="¿Cómo configurar Nginx?"))
    await session._try_generate_title()

    updated = tm.get_thread("test-session-1")
    assert updated.title == "Título Generado por IA"
    assert updated.title_source == "llm"


def test_llm_service_set_thread_manager_wires_llm_service():
    from unittest.mock import MagicMock
    from kogniterm.core.llm_service import LLMService

    llm = LLMService(use_multi_provider=False)
    mock_tm = MagicMock()
    llm.set_thread_manager(mock_tm)

    assert llm.history_manager._thread_manager == mock_tm
    assert llm.history_manager._llm_service == llm


