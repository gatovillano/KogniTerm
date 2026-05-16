
import os
import sys
from unittest.mock import MagicMock

# Mock chromadb and other potential heavy dependencies
sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.config"] = MagicMock()
sys.modules["tiktoken"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["langchain_community"] = MagicMock()
sys.modules["langchain_community.vectorstores"] = MagicMock()
sys.modules["langchain_community.embeddings"] = MagicMock()
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.tools"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()

# Mocking environment for the test
os.environ["OLLAMA_CLOUD_API_KEY"] = "fake-cloud-key"
os.environ["OLLAMA_PROVIDER_TARGET"] = "cloud"
# Even if this is set, it should prefer cloud if TARGET=cloud or cloud_key is present and base is local
os.environ["OLLAMA_API_BASE"] = "http://localhost:11434"

def verify_init():
    print("Verifying LLMService initialization...")
    # Import inside verify to use modified environment
    import kogniterm.core.llm_service as llm_service
    import litellm
    
    print(f"litellm.api_base: {litellm.api_base}")
    print(f"litellm.headers: {litellm.headers}")
    
    assert litellm.api_base == "https://ollama.com/v1"
    assert "Authorization" in litellm.headers
    assert litellm.headers["Authorization"] == "Bearer fake-cloud-key"
    print("✅ Initial setup correctly identified Ollama Cloud!")

def verify_set_model():
    print("\nVerifying set_model...")
    from kogniterm.core.llm_service import LLMService
    import litellm
    
    service = LLMService(use_multi_provider=False)
    service.set_model("ollama/some-model")
    
    print(f"After set_model - litellm.api_base: {litellm.api_base}")
    print(f"After set_model - litellm.headers: {litellm.headers}")
    
    assert litellm.api_base == "https://ollama.com/v1"
    assert litellm.headers["Authorization"] == "Bearer fake-cloud-key"
    print("✅ set_model correctly switched to Ollama Cloud!")

if __name__ == "__main__":
    try:
        verify_init()
        verify_set_model()
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        sys.exit(1)
