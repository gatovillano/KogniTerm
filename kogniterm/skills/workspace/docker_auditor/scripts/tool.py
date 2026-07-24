import json
import re
import subprocess
from typing import Dict, Any

def docker_auditor(since: str = "24h", output_format: str = "markdown", include_logs: bool = True) -> str:
    """
    Audita el estado de los contenedores Docker, uso de recursos, estado de salud y errores recientes en logs.
    """
    try:
        # 1. Obtener contenedores
        cmd_ps = ["docker", "ps", "-a", "--format", "{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}|{{.Ports}}"]
        ps_output = subprocess.check_output(cmd_ps, stderr=subprocess.STDOUT).decode("utf-8", errors="replace").strip()
        
        containers = []
        if ps_output:
            for line in ps_output.splitlines():
                if line:
                    parts = line.split("|")
                    if len(parts) >= 5:
                        containers.append({
                            "id": parts[0],
                            "name": parts[1],
                            "status": parts[2],
                            "image": parts[3],
                            "ports": parts[4]
                        })

        # 2. Obtener uso de disco con docker system df
        try:
            df_output = subprocess.check_output(["docker", "system", "df"], stderr=subprocess.STDOUT).decode("utf-8", errors="replace").strip()
        except Exception as e:
            df_output = f"No disponible: {e}"

        # 3. Analizar logs y errores
        error_keywords = re.compile(r'(error|exception|fatal|failed|crit|unhealthy|severe)', re.IGNORECASE)
        audit_results = []

        total_running = 0
        total_stopped = 0
        unhealthy_count = 0

        for c in containers:
            is_running = c["status"].startswith("Up")
            if is_running:
                total_running += 1
            else:
                total_stopped += 1

            is_unhealthy = "unhealthy" in c["status"].lower()
            if is_unhealthy:
                unhealthy_count += 1

            c_info = {
                "name": c["name"],
                "status": c["status"],
                "image": c["image"],
                "ports": c["ports"],
                "unhealthy": is_unhealthy,
                "error_count": 0,
                "sample_errors": []
            }

            if include_logs and is_running:
                try:
                    logs = subprocess.check_output(
                        ["docker", "logs", "--since", since, c["name"]],
                        stderr=subprocess.STDOUT,
                        timeout=10
                    ).decode("utf-8", errors="replace")
                    
                    log_lines = logs.splitlines()
                    err_lines = [l for l in log_lines if error_keywords.search(l)]
                    c_info["error_count"] = len(err_lines)
                    c_info["sample_errors"] = err_lines[-5:] if err_lines else []
                except Exception as ex:
                    c_info["log_error"] = str(ex)

            audit_results.append(c_info)

        summary = {
            "total_containers": len(containers),
            "running": total_running,
            "stopped": total_stopped,
            "unhealthy": unhealthy_count,
            "time_window": since
        }

        if output_format.lower() == "json":
            return json.dumps({"summary": summary, "system_df": df_output, "containers": audit_results}, indent=2)

        # Markdown output
        md = []
        md.append(f"# 🐳 Informe de Auditoría Docker ({since})\n")
        md.append(f"**Total contenedores:** {summary['total_containers']} | 🟢 **Activos:** {summary['running']} | 🔴 **Detenidos:** {summary['stopped']} | ⚠️ **Unhealthy:** {summary['unhealthy']}\n")
        
        md.append("## 💾 Uso de Espacio en Sistema (docker system df)")
        md.append("```")
        md.append(df_output)
        md.append("```\n")

        md.append("## 📋 Detalle de Contenedores")
        for c in audit_results:
            health_badge = "⚠️ UNHEALTHY" if c["unhealthy"] else ("🟢 UP" if c["status"].startswith("Up") else "🔴 STOPPED")
            md.append(f"### `{c['name']}` ({health_badge})")
            md.append(f"- **Imagen:** `{c['image']}`")
            md.append(f"- **Estado:** {c['status']}")
            md.append(f"- **Puertos:** `{c['ports'] or 'Ninguno'}`")
            md.append(f"- **Errores detectados ({since}):** {c['error_count']}")
            if c["sample_errors"]:
                md.append("  - **Muestra de errores:**")
                for err in c["sample_errors"]:
                    md.append(f"    - `{err[:150]}`")
            md.append("")

        return "\n".join(md)

    except Exception as e:
        return f"Error al ejecutar auditoría Docker: {str(e)}"

parameters_schema = {
    "type": "object",
    "properties": {
        "since": {
            "type": "string",
            "description": "Ventana de tiempo para evaluar logs (ej: '1h', '24h', '7d'). Default: '24h'."
        },
        "output_format": {
            "type": "string",
            "description": "Formato de salida: 'markdown' o 'json'. Default: 'markdown'."
        },
        "include_logs": {
            "type": "boolean",
            "description": "Si es True, escanea los logs en busca de errores. Default: True."
        }
    },
    "required": []
}
