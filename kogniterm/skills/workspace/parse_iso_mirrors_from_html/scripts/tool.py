import subprocess
import re
import os

def parse_iso_mirrors_from_html(**kwargs):
    """
    Parsea una página HTML de directorio de mirrors y extrae URLs de archivos ISO.
    
    Args:
        html_url (str): URL de la página HTML a parsear.
        iso_pattern (str, optional): Patrón regex para filtrar archivos ISO. Default: r'\.iso$'.
        base_url (str, optional): URL base para enlaces relativos.
    
    Returns:
        str: Lista de URLs de ISO encontradas, separadas por newlines.
    """
    html_url = kwargs.get('html_url')
    if not html_url:
        return "ERROR: html_url es requerido"
    
    iso_pattern = kwargs.get('iso_pattern', r'\.iso$')
    base_url = kwargs.get('base_url', '')
    
    try:
        # Obtener HTML
        result = subprocess.run(
            ['curl', '-s', html_url],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return f"ERROR: No se pudo obtener {html_url}: {result.stderr}"
        
        html = result.stdout
        
        # Extraer todos los href
        hrefs = re.findall(r'href="([^"]+)"', html)
        
        # Filtrar por patrón ISO
        iso_urls = []
        pattern_re = re.compile(iso_pattern)
        for href in hrefs:
            if pattern_re.search(href):
                # Construir URL completa si es relativa y hay base_url
                if not href.startswith(('http://', 'https://')):
                    if base_url:
                        # Asegurar que base_url termine con /
                        if not base_url.endswith('/'):
                            base_url += '/'
                        href = base_url + href
                    else:
                        # Si no hay base_url, saltar enlaces relativos
                        continue
                iso_urls.append(href)
        
        # Eliminar duplicados manteniendo orden
        seen = set()
        unique_urls = []
        for url in iso_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return '\n'.join(unique_urls)
        
    except subprocess.TimeoutExpired:
        return f"ERROR: Timeout al obtener {html_url}"
    except Exception as e:
        return f"ERROR: {str(e)}"

parameters_schema = {
    "type": "object",
    "properties": {
        "html_url": {
            "type": "string",
            "description": "URL de la página HTML a parsear"
        },
        "iso_pattern": {
            "type": "string",
            "description": "Patrón regex para filtrar archivos ISO (default: \\.iso$)"
        },
        "base_url": {
            "type": "string",
            "description": "URL base para enlaces relativos"
        }
    },
    "required": ["html_url"]
}