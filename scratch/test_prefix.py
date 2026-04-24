import os
from litellm import completion

# Mocking environment for test
os.environ["OLLAMA_CLOUD_API_KEY"] = "test_key"
model = "ollama_chat/cogito-2.1:671b"
# We won't actually call the API, just see how LiteLLM handles the model name if we can.
# But since we can't easily intercept the outgoing request without complex mocks, 
# let's just check the code again.

print(f"Testing prefix for model: {model}")
