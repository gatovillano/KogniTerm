import os
import sys
from kogniterm.core.multi_provider_manager import get_provider_manager

# Simular el entorno del usuario
os.environ["OLLAMA_CLOUD_API_KEY"] = "b2147ce5a75842b48ca6cee762c9965d.c8WoUA34TkbAxMc0F-OUs3rK"
os.environ["OPENROUTER_API_KEY"] = "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"

manager = get_provider_manager()
model_name = "ollama/cogito-2.1:671b"

available = manager.get_available_providers()
print(f"Available providers: {[p.name for p in available]}")

prefix = model_name.split("/")[0]
provider = next((p for p in available if p.model_prefix == prefix), None)

if provider:
    print(f"Found provider by prefix: {provider.name}")
else:
    print("Provider not found by prefix")
    primary = manager.get_primary_provider()
    print(f"Primary provider: {primary.name if primary else 'None'}")
