import pytest
import os
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

