import re

with open("kogniterm/core/multi_provider_manager.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the execute method to replace its internal logic
execute_def = """    def execute(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tools: Optional[List[Dict]] = None,
        force_provider: Optional[ProviderConfig] = None,
        **kwargs
    ):
"""

new_determine_ideal = """    def _determine_ideal_provider(self, model_name: str, force_provider: Optional[ProviderConfig] = None) -> Optional[ProviderConfig]:
        if force_provider:
            return force_provider
            
        if not model_name:
            return self.get_primary_provider()
            
        available = self.get_available_providers()
        
        # 1. Priorizar el proveedor preferido si está disponible
        if self.preferred_provider:
            pref_p = next((p for p in available if p.name == self.preferred_provider), None)
            if pref_p:
                model_prefix = model_name.split("/")[0] if "/" in model_name else None
                if model_prefix:
                    # Si el prefijo coincide con el preferido, o ambos son ollama
                    if model_prefix == pref_p.name or model_prefix == pref_p.model_prefix or model_prefix.replace("-", "_") == pref_p.name:
                        return pref_p
                    elif pref_p.name.startswith("ollama") and model_prefix == "ollama":
                        return pref_p
                    # Si el prefijo NO coincide, permitimos que siga la lógica normal
                else:
                    # Modelo sin prefijo (ej. gpt-4o), forzamos al proveedor preferido
                    return pref_p

        # 2. Si no se resolvió por preferido, intentar por prefijo de Ollama
        if model_name.startswith("ollama/"):
            provider = next((p for p in available if p.name == "ollama"), None)
            if provider: return provider
        
        # 3. Lógica basada en prefijo genérico
        if "/" in model_name:
            parts = model_name.split("/", 1)
            prefix = parts[0]
            provider = next((p for p in available if p.name == prefix or p.name == prefix.replace("-", "_") or p.model_prefix == prefix), None)
            if provider: return provider
        
        # 4. Inferencia por nombre del modelo
        lower_model = model_name.lower()
        if lower_model.startswith("gemini"):
            provider = next((p for p in available if p.name == "google"), None)
            if provider: return provider
        elif "gpt" in lower_model:
            provider = next((p for p in available if p.name == "openai"), None)
            if provider: return provider
        elif "claude" in lower_model:
            provider = next((p for p in available if p.name == "anthropic"), None)
            if provider: return provider

        # 5. Fallback final al proveedor primario
        return self.get_primary_provider()

    def execute(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tools: Optional[List[Dict]] = None,
        force_provider: Optional[ProviderConfig] = None,
        **kwargs
    ):
        \"\"\"
        Ejecuta una solicitud con el proveedor adecuado.
        \"\"\"
        provider = self._determine_ideal_provider(model_name, force_provider)
        
        if not provider:
            raise ValueError("No hay proveedores configurados disponibles. Revisa tus API Keys.")
"""

# Replace in execute method
content = re.sub(
    r'    def execute\(.*?\n        provider = force_provider.*?\n        if not provider:\n            raise ValueError\("No hay proveedores configurados disponibles\. Revisa tus API Keys\."\)',
    new_determine_ideal,
    content,
    flags=re.DOTALL
)

# Replace execute_with_fallback
old_fallback = """    def execute_with_fallback(self, *args, **kwargs):
        \"\"\"Ejecuta una solicitud intentando proveedores en cascada si hay error.\"\"\"
        chain = self.get_fallback_chain()
        if not chain:
            raise ValueError("No hay proveedores disponibles para fallback.")
            
        last_exception = None
        
        # Determine if we should forcefully restrict to preferred provider
        force_provider_arg = kwargs.get("force_provider")
        target_provider = force_provider_arg or (chain[0] if chain else None)
        
        for provider in chain:"""

new_fallback = """    def execute_with_fallback(self, *args, **kwargs):
        \"\"\"Ejecuta una solicitud intentando proveedores en cascada si hay error.\"\"\"
        model_name = kwargs.get("model_name")
        if not model_name and len(args) > 0:
            model_name = args[0]
            
        force_provider_arg = kwargs.get("force_provider")
        
        ideal_provider = self._determine_ideal_provider(model_name, force_provider_arg)
        base_chain = self.get_fallback_chain()
        
        # Construir nueva cadena poniendo el ideal primero
        chain = []
        if ideal_provider:
            chain.append(ideal_provider)
            
        for p in base_chain:
            if p != ideal_provider:
                chain.append(p)
                
        if not chain:
            raise ValueError("No hay proveedores disponibles para fallback.")
            
        last_exception = None
        for provider in chain:"""

content = content.replace(old_fallback, new_fallback)

with open("kogniterm/core/multi_provider_manager.py", "w", encoding="utf-8") as f:
    f.write(content)
