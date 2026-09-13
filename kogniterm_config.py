#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import set_key, find_dotenv

def config_kogniterm():
    install_dir = Path.home() / ".kogniterm"
    env_file = install_dir / ".env"
    
    if not env_file.exists():
        if (install_dir / ".env.example").exists():
            import shutil
            shutil.copy(install_dir / ".env.example", env_file)
        else:
            env_file.touch()

    print("--- Configuración de KogniTerm ---")
    
    providers = {
        "1": ("openai", "OpenAI"),
        "2": ("openrouter", "Groq / OpenRouter"),
        "3": ("google", "Google Gemini"),
        "4": ("anthropic", "Anthropic (Claude)"),
        "5": ("ollama", "Ollama Local"),
        "6": ("ollama_cloud", "Ollama Cloud"),
        "7": ("kilocode", "KiloCode Gateway")
    }
    
    print("Proveedores disponibles:")
    for k, v in providers.items():
        print(f"  {k}) {v[1]}")
        
    choice = input("Selecciona un proveedor [3]: ") or "3"
    provider_key, provider_name = providers.get(choice, ("google", "Google Gemini"))
    
    model = input(f"Modelo para {provider_name}: ")
    api_key = input("API Key (se ocultará): ")
    
    if not model:
        print("Error: El modelo es obligatorio.")
        sys.exit(1)

    set_key(env_file, "LLM_PROVIDER", provider_key)
    set_key(env_file, "LLM_MODEL", model)
    
    # Mapeo de llaves
    key_mapping = {
        "google": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "ollama_cloud": "OLLAMA_CLOUD_API_KEY",
        "kilocode": "KILOCODE_API_KEY"
    }
    
    key_name = key_mapping.get(provider_key, "LLM_API_KEY")
    set_key(env_file, key_name, api_key)
    
    print(f"\nConfiguración guardada en {env_file}")
    print("Para aplicar los cambios, reinicia KogniTerm.")

def config_kogniterm_cli():
    if len(sys.argv) > 2 and sys.argv[1] == "llm":
        config_kogniterm()
    else:
        print("Uso: kogniterm-config llm")

if __name__ == "__main__":
    config_kogniterm_cli()
