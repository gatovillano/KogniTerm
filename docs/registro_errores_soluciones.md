# Registro de Errores y Soluciones - KogniTerm

## Error 400 OpenRouter - "Field required" (code:20015)

### Descripción del Problema

Al usar modelos de OpenRouter a través de SiliconFlow, se presentaba el siguiente error:

```
litellm.BadRequestError: OpenrouterException - {
  "error": {
    "message": "Provider returned error",
    "code": 400,
    "metadata": {
      "raw": "{\"code\":20015,\"message\":\"Field required\",\"data\":null}",
      "provider_name": "SiliconFlow"
    },
    "user_id": "user_2vrvx1X6OHpgry4nNt2dJcSxlrz"
  }
}
```

### Causa Raíz

El error `code:20015` con `"Field required"` indica que el proveedor SiliconFlow (backend de OpenRouter) requiere campos adicionales en la solicitud que no se estaban enviando correctamente. Aunque el `user_id` aparecía en el error, faltaban otros campos obligatorios en el payload principal.

### Solución Implementada - Sistema Robusto con Fallback

#### 1. Configuración Completa con Campos Adicionales

Se implementa una configuración robusta que incluye todos los campos comúnmente requeridos:

```python
# Configuración específica para OpenRouter/SiliconFlow con campos adicionales
if "openrouter" in self.model_name.lower():
    # Asegurar formato correcto del modelo
    if not completion_kwargs["model"].startswith("openrouter/"):
        completion_kwargs["model"] = f"openrouter/{self.model_name}"
    
    # Agregar campos requeridos por SiliconFlow/OpenRouter
    completion_kwargs["user"] = f"user_{self._generate_short_id(12)}"
    
    # Agregar metadata y parámetros adicionales que pueden ser requeridos
    completion_kwargs["metadata"] = {
        "user_id": completion_kwargs["user"],
        "application_name": "KogniTerm"
    }
    
    # Para algunos modelos puede ser necesario especificar modalidades
    if "vision" in self.model_name.lower() or "multimodal" in self.model_name.lower():
        completion_kwargs["modalities"] = ["text"]
    
    # Configurar parámetros de proveedor si es necesario
    completion_kwargs["provider"] = {
        "order": ["OpenRouter"],
        "allow_fallbacks": True
    }
```

#### 2. Sistema de Fallback de Tres Niveles

Para errores 20015 de SiliconFlow, se implementa un sistema de fallback progresivo:

##### Nivel 1: Configuración Específica por Modelo

```python
# Configuración específica para OpenRouter/SiliconFlow con campos adicionales
if "openrouter" in self.model_name.lower():
    # Para modelos específicos como Nex-AGI, usar configuración más simple
    if "nex-agi" in self.model_name.lower() or "deepseek" in self.model_name.lower():
        # Configuración minimalista para Nex-AGI/DeepSeek
        completion_kwargs["user"] = f"user_{self._generate_short_id(12)}"
        # NO enviar campos adicionales que puedan causar problemas
        logger.debug(f"Configuración minimalista para Nex-AGI/DeepSeek: {completion_kwargs['model']}")
    else:
        # Configuración estándar para otros modelos
        completion_kwargs["user"] = f"user_{self._generate_short_id(12)}"
        completion_kwargs["metadata"] = {
            "user_id": completion_kwargs["user"],
            "application_name": "KogniTerm"
        }
```

##### Nivel 2: Configuración Alternativa Simplificada

```python
# Si es un error 20015 de SiliconFlow, intentar con configuración alternativa
if "20015" in error_msg and "Field required" in error_msg:
    logger.info("Intentando configuración alternativa para SiliconFlow...")
    try:
        # Crear configuración alternativa más específica
        alt_kwargs = {
            "model": completion_kwargs["model"],
            "messages": completion_kwargs["messages"],
            "stream": True,
            "api_key": completion_kwargs["api_key"],
            "temperature": completion_kwargs.get("temperature", 0.7),
            "max_tokens": completion_kwargs.get("max_tokens", 4096),
            "user": f"user_{self._generate_short_id(12)}",
            "num_retries": 1,  # Reducir reintentos en fallback
            "timeout": 60     # Timeout más corto en fallback
        }
        
        # Solo agregar parámetros adicionales si el modelo no es Nex-AGI/DeepSeek
        if not ("nex-agi" in self.model_name.lower() or "deepseek" in self.model_name.lower()):
            alt_kwargs["top_k"] = self.generation_params.get("top_k", 40)
            alt_kwargs["top_p"] = self.generation_params.get("top_p", 0.95)
        
        # Intentar llamada alternativa
        response_generator = completion(**alt_kwargs)
        # ... procesamiento normal
```

##### Nivel 3: Configuración Ultra-Minimalista

```python
# Intentar configuración ultra-minimalista para modelos muy específicos
if "nex-agi" in self.model_name.lower() or "deepseek" in self.model_name.lower():
    logger.info("Intentando configuración ultra-minimalista para Nex-AGI/DeepSeek...")
    try:
        ultra_kwargs = {
            "model": completion_kwargs["model"],
            "messages": completion_kwargs["messages"],
            "stream": True,
            "api_key": completion_kwargs["api_key"],
            "user": f"user_{self._generate_short_id(8)}"  # ID más corto
        }
        
        # Intentar llamada ultra-minimalista
        response_generator = completion(**ultra_kwargs)
        # ... procesamiento normal
```

#### 3. Logging Mejorado para Debug

Se implementó logging detallado para facilitar el diagnóstico:

```python
# Logging adicional para errores de OpenRouter
if "OpenrouterException" in error_msg or "20015" in error_msg:
    logger.error(f"Configuración del modelo: {self.model_name}")
    logger.error(f"API Key presente: {'Sí' if self.api_key else 'No'}")
    logger.error(f"Headers configurados: {litellm.headers}")
```

#### 4. Manejo de Errores Específicos

Se implementó detección y manejo específico para diferentes tipos de errores:

```python
elif "OpenrouterException" in error_msg or "Upstream error" in error_msg:
    if "No endpoints found" in error_msg:
        friendly_message = "⚠️ El modelo solicitado no está disponible con los parámetros actuales. Verifica que el nombre del modelo sea correcto y que esté disponible en OpenRouter."
    elif "20015" in error_msg:
        friendly_message = "🔧 Se detectó un error de campos requeridos. El sistema intentará automáticamente con una configuración alternativa."
    else:
        friendly_message = f"¡Ups! 🌐 El proveedor del modelo (OpenRouter) está experimentando problemas técnicos temporales: '{error_msg}'. Por favor, intenta de nuevo en unos momentos."
```

### Archivos Modificados

- `kogniterm/core/llm_service.py`:
  - Líneas 145-160: Configuración robusta de cabeceras
  - Líneas 593-635: Parámetros completos con detección específica por modelo
  - Líneas 680-760: Sistema de fallback de tres niveles para errores 20015
  - Líneas 800-820: Logging mejorado para debugging
  - Líneas 820-830: Manejo específico de errores de OpenRouter

### Verificación de la Solución

Para verificar que la solución funciona:

1. **Configurar variables de entorno**:

   ```bash
   export OPENROUTER_API_KEY="tu_api_key"
   export LITELLM_MODEL="nombre_del_modelo"
   ```

2. **Ejecutar KogniTerm** y probar con un modelo de OpenRouter

3. **Monitorear logs** para asegurar que no aparezcan errores 400

### Prevención Futura

Para prevenir errores similares:

1. **Siempre verificar** los requisitos específicos del proveedor en la documentación
2. **Mantener actualizadas** las cabeceras HTTP estándar
3. **Incluir campos obligatorios** como `user`, `Content-Type`, etc.
4. **Implementar manejo de errores** específico para cada proveedor
5. **Utilizar sistemas de fallback** para manejar cambios de API inesperados
6. **Monitorear logs detalladamente** para detectar patrones de errores

### Estrategia Implementada

La solución implementa una **estrategia de cuatro capas**:

1. **Configuración Inicial Específica por Modelo**:
   - Detecta modelos problemáticos (Nex-AGI/DeepSeek) y aplica configuración minimalista
   - Para otros modelos, usa configuración estándar con metadata

2. **Detección de Errores**:
   - Identifica errores específicos de SiliconFlow (código 20015)
   - Activa sistema de fallback progresivo

3. **Fallback de Dos Niveles**:
   - **Nivel 1**: Configuración alternativa simplificada sin campos problemáticos
   - **Nivel 2**: Configuración ultra-minimalista solo con campos esenciales

4. **Manejo de Fallos**:
   - Logging detallado de cada intento
   - Mensajes informativos al usuario
   - Compatibilidad con múltiples proveedores

Esta aproximación **proactiva y adaptativa** garantiza que:

- Los errores 400 se resuelvan automáticamente en la mayoría de casos
- El usuario reciba mensajes de error informativos y útiles
- El sistema mantenga compatibilidad con múltiples proveedores
- La configuración se pueda ajustar dinámicamente según el modelo específico
- Se proporcionen múltiples oportunidades de éxito antes del fallo final

### Notas Adicionales

- Este error es específico de proveedores que requieren validación estricta de campos
- SiliconFlow/OpenRouter pueden cambiar sus requisitos, por lo que se debe monitorear actualizaciones
- La solución mantiene compatibilidad con otros proveedores (Google AI Studio)
- El sistema de fallback es transparente para el usuario final

---
**Fecha**: 22-12-2025  
**Estado**: Resuelto  
**Versión**: KogniTerm 0.1.0

---

## Error de Repetición Infinita en CodebaseSearchTool

### Descripción del Problema

Al realizar búsquedas de código con `CodebaseSearchTool`, los resultados mostraban fragmentos de código con miles de líneas repetidas (ej: `from core.dependencies import get_current_user` repetido cientos de veces), lo que saturaba la terminal y el contexto del agente.

### Causa Raíz

El algoritmo de fragmentación (`chunk_file`) en `CodebaseIndexer` tenía un fallo en la lógica de solapamiento (`overlap`). Cuando una línea superaba el tamaño del solapamiento o el tamaño del fragmento, el buffer no se gestionaba correctamente, provocando que las mismas líneas se incluyeran en múltiples fragmentos de forma redundante o que el algoritmo se "atascara" en un bucle lógico de inserción.

### Solución Implementada

1. **Rediseño del Algoritmo**: Se implementó una nueva lógica en `kogniterm/core/context/codebase_indexer.py` que utiliza un contador de caracteres real y un puntero de línea que siempre avanza.
2. **Gestión de Solapamiento Robusta**: El nuevo sistema de solapamiento garantiza que solo se incluyan las últimas N líneas que quepan en el espacio de `chunk_overlap`, evitando duplicaciones innecesarias.
3. **Limpieza de Datos**: Se ejecutó una limpieza completa de la colección en ChromaDB para eliminar los fragmentos corruptos preexistentes.

### Archivos Modificados

- `kogniterm/core/context/codebase_indexer.py`: Reescritura del método `chunk_file`.
- `kogniterm/core/tools/codebase_search_tool.py`: Mejoras menores en el manejo de resultados.

**Fecha**: 30-12-2025  
**Estado**: Resuelto  
**Versión**: KogniTerm 0.1.0
