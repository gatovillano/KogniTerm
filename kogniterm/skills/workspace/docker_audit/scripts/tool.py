import subprocess
import json
import re
from datetime import datetime

def docker_audit(time_range: str = "24h"):
    """
    Audita contenedores Docker y busca errores en logs.
    
    Args:
        time_range: Rango de tiempo para los logs (ej: "24h", "1d", "7d", "30m")
    
    Returns:
        Dict con estado de contenedores y errores encontrados
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "time_range": time_range,
        "containers": [],
        "summary": {
            "total": 0,
            "healthy": 0,
            "unhealthy": 0,
            "restarting": 0,
            "errors_found": 0
        }
    }
    
    # Obtener estado de contenedores
    try:
        cmd = ['docker', 'ps', '-a', '--format', '{{.Names}}\t{{.Status}}\t{{.Ports}}']
        status_output = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        lines = status_output.stdout.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            parts = line.split('\t')
            if len(parts) >= 2:
                name = parts[0].strip()
                status = parts[1].strip()
                
                container_info = {
                    "name": name,
                    "status": status,
                    "errors": [],
                    "health": "unknown"
                }
                
                # Determinar estado
                if "Up" in status:
                    container_info["health"] = "healthy"
                    result["summary"]["healthy"] += 1
                elif "Restarting" in status:
                    container_info["health"] = "restarting"
                    result["summary"]["restarting"] += 1
                elif "unhealthy" in status.lower():
                    container_info["health"] = "unhealthy"
                    result["summary"]["unhealthy"] += 1
                else:
                    container_info["health"] = "unknown"
                
                # Buscar errores en logs
                try:
                    log_cmd = ['docker', 'logs', f'--since={time_range}', name]
                    log_result = subprocess.run(log_cmd, capture_output=True, text=True, timeout=10)
                    
                    if log_result.returncode == 0:
                        logs = log_result.stdout
                        
                        # Buscar errores
                        error_patterns = [
                            r'error',
                            r'exception',
                            r'failed',
                            r'critical',
                            r'fatal',
                            r'traceback',
                            r'ENOTFOUND',
                            r'connection refused',
                            r'timeout'
                        ]
                        
                        error_lines = []
                        for pattern in error_patterns:
                            matches = re.findall(f'.*{pattern}.*', logs, re.IGNORECASE)
                            error_lines.extend(matches[:5])  # Máximo 5 por patrón
                        
                        container_info["errors"] = list(set(error_lines))[:10]
                        if container_info["errors"]:
                            result["summary"]["errors_found"] += 1
                            
                except Exception as e:
                    container_info["errors"] = [f"No se pudieron obtener logs: {str(e)}"]
                
                result["containers"].append(container_info)
                result["summary"]["total"] += 1
                
    except Exception as e:
        result["error"] = str(e)
    
    return result

if __name__ == "__main__":
    import sys
    time_range = sys.argv[1] if len(sys.argv) > 1 else "24h"
    print(json.dumps(docker_audit(time_range), indent=2))