import subprocess
import json
from datetime import datetime
from typing import List, Dict, Any

def docker_error_logs(**kwargs):
    """
    Muestra los errores de los contenedores Docker de las últimas 24 horas.
    
    Parámetros:
    - all_containers (bool): Incluir contenedores detenidos. Default: False.
    - hours (int): Número de horas hacia atrás. Default: 24.
    - keywords (list): Palabras clave para filtrar. Default: ["error", "ERROR", "failed", "Failed", "exception", "Exception", "fatal", "Fatal"].
    - show_tail (int): Máximo de líneas por contenedor. Default: 50.
    
    Retorna:
    - str: Informe formateado con los errores encontrados.
    """
    # Obtener parámetros con defaults
    all_containers = kwargs.get('all_containers', False)
    hours = kwargs.get('hours', 24)
    keywords = kwargs.get('keywords', ["error", "ERROR", "failed", "Failed", "exception", "Exception", "fatal", "Fatal"])
    show_tail = kwargs.get('show_tail', 50)
    
    # Paso 1: Obtener lista de contenedores
    cmd_ps = ["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"] if all_containers else ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"]
    
    try:
        result_ps = subprocess.run(cmd_ps, capture_output=True, text=True, timeout=30)
        if result_ps.returncode != 0:
            return f"❌ Error al obtener contenedores: {result_ps.stderr.strip()}"
        
        containers = []
        for line in result_ps.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    containers.append({
                        'id': parts[0],
                        'name': parts[1],
                        'status': parts[2],
                        'image': parts[3] if len(parts) > 3 else ''
                    })
        
        if not containers:
            return "⚠️ No se encontraron contenedores Docker."
        
        # Paso 2: Recolectar errores por contenedor
        total_errors = 0
        report_lines = []
        report_lines.append(f"🔍 Informe de errores Docker (últimas {hours} horas)")
        report_lines.append(f"📊 Contenedores revisados: {len(containers)}")
        report_lines.append(f"🔑 Palabras clave: {', '.join(keywords)}")
        report_lines.append("")
        
        # Construir patrón grep
        pattern = '|'.join(keywords)
        
        for container in containers:
            cid = container['id']
            name = container['name']
            status = container['status']
            
            # Obtener logs del contenedor
            cmd_logs = ["docker", "logs", f"--since={hours}h", cid]
            try:
                result_logs = subprocess.run(cmd_logs, capture_output=True, text=True, timeout=60)
                # docker logs puede fallar si el contenedor no tiene logs o no existe
                logs = result_logs.stdout if result_logs.returncode == 0 else ""
                # También considerar stderr si hay
                if result_logs.stderr and "does not exist" not in result_logs.stderr.lower():
                    logs += result_logs.stderr
            except subprocess.TimeoutExpired:
                logs = ""
            
            # Filtrar líneas que contengan alguna palabra clave
            error_lines = []
            for line in logs.split('\n'):
                line_stripped = line.strip()
                if line_stripped:
                    # Verificar si contiene alguna palabra clave (case insensitive)
                    if any(kw.lower() in line_stripped.lower() for kw in keywords):
                        error_lines.append(line_stripped)
            
            # Limitar a show_tail líneas (las más recientes están al final en docker logs)
            if len(error_lines) > show_tail:
                error_lines = error_lines[-show_tail:]
            
            if error_lines:
                total_errors += len(error_lines)
                report_lines.append(f"📦 Contenedor: {name} (ID: {cid[:12]}) - Estado: {status}")
                report_lines.append(f"   ❌ Errores encontrados: {len(error_lines)}")
                for err in error_lines:
                    # Truncar líneas muy largas
                    if len(err) > 200:
                        err = err[:197] + "..."
                    report_lines.append(f"     • {err}")
                report_lines.append("")
        
        # Paso 3: Resumen final
        report_lines.insert(2, f"   Total de errores encontrados: {total_errors}")
        report_lines.append("=" * 60)
        if total_errors == 0:
            report_lines.append("✅ No se encontraron errores en los logs de los contenedores.")
        else:
            report_lines.append(f"⚠️ Se encontraron {total_errors} líneas de error en total.")
        
        return "\n".join(report_lines)
        
    except subprocess.TimeoutExpired as e:
        return f"⏱️ Timeout: La operación tardó demasiado tiempo. {str(e)}"
    except Exception as e:
        return f"❌ Error inesperado: {str(e)}"

# Esquema de parámetros para la documentación
parameters_schema = {
    "type": "object",
    "properties": {
        "all_containers": {
            "type": "boolean",
            "default": False,
            "description": "Incluir contenedores detenidos"
        },
        "hours": {
            "type": "integer",
            "default": 24,
            "minimum": 1,
            "maximum": 168,
            "description": "Número de horas hacia atrás"
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["error", "ERROR", "failed", "Failed", "exception", "Exception", "fatal", "Fatal"],
            "description": "Lista de palabras clave para filtrar"
        },
        "show_tail": {
            "type": "integer",
            "default": 50,
            "minimum": 1,
            "maximum": 500,
            "description": "Máximo de líneas de error por contenedor"
        }
    }
}