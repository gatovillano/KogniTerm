"""
Módulo de analítica de uso para KogniTerm.
Proporciona funcionalidades para generar reportes de uso basados en el historial de sesiones.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter


class KogniInsightsEngine:
    """
    Motor de analítica que procesa el historial de sesiones de KogniTerm
    para generar reportes de uso, costos, tokens y patrones de interacción.
    """

    def __init__(self):
        """Inicializa el motor de analítica."""
        self.history_dir = self._get_history_directory()
        self.sessions_data = []

    def _get_history_directory(self) -> Path:
        """
        Obtiene el directorio donde se almacenan los archivos de historial de sesiones.
        
        Returns:
            Path: Ruta al directorio de historial
        """
        # Usar el directorio estándar de KogniTerm para historial
        home_dir = Path.home()
        history_dir = home_dir / ".kogniterm" / "data" / "history"
        
        # Crear el directorio si no existe
        history_dir.mkdir(parents=True, exist_ok=True)
        
        return history_dir

    def _load_session_files(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Carga los archivos de sesión desde el directorio de historial.
        
        Args:
            days: Número de días hacia atrás para filtrar sesiones
            
        Returns:
            Lista de diccionarios con los datos de las sesiones
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        sessions = []
        
        if not self.history_dir.exists():
            return sessions
            
        # Buscar archivos de sesión con patrón session_*_YYYYMMDD_HHMMSS.json
        for session_file in self.history_dir.glob("session_*.json"):
            try:
                # Extraer fecha del nombre del archivo: session_<name>_<YYYYMMDD>_<HHMMSS>.json
                parts = session_file.stem.split('_')
                if len(parts) >= 4:
                    date_str = parts[-2]  # YYYYMMDD
                    time_str = parts[-1]  # HHMMSS
                    datetime_str = f"{date_str}_{time_str}"
                    file_date = datetime.strptime(datetime_str, "%Y%m%d_%H%M%S")
                    
                    # Filtrar por fecha
                    if file_date >= cutoff_date:
                        # Cargar el contenido del archivo
                        with open(session_file, 'r', encoding='utf-8') as f:
                            session_data = json.load(f)
                            
                        # Añadir metadatos del archivo
                        session_data['_file_date'] = file_date
                        session_data['_file_path'] = str(session_file)
                        sessions.append(session_data)
                        
            except (ValueError, IndexError, json.JSONDecodeError) as e:
                # Si hay error al procesar el archivo, continuar con el siguiente
                continue
                
        # Ordenar por fecha (más reciente primero)
        sessions.sort(key=lambda x: x.get('_file_date', datetime.min), reverse=True)
        return sessions

    def _extract_metrics_from_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae métricas relevantes de una sesión de datos.
        
        Args:
            session_data: Diccionario con los datos de la sesión
            
        Returns:
            Diccionario con métricas extraídas
        """
        metrics = {
            'model_used': 'unknown',
            'total_tokens': 0,
            'total_cost': 0.0,
            'tools_used': [],
            'message_count': 0,
            'session_duration': 0.0
        }
        
        # Extraer modelo utilizado
        if 'model' in session_data:
            metrics['model_used'] = session_data['model']
        elif 'llm_config' in session_data and 'model' in session_data['llm_config']:
            metrics['model_used'] = session_data['llm_config']['model']
            
        # Contar mensajes
        if 'messages' in session_data and isinstance(session_data['messages'], list):
            metrics['message_count'] = len(session_data['messages'])
            
            # Extraer tokens y costo de los mensajes (si están disponibles)
            for msg in session_data['messages']:
                if isinstance(msg, dict):
                    # Tokens
                    if 'tokens' in msg:
                        try:
                            metrics['total_tokens'] += int(msg['tokens'])
                        except (ValueError, TypeError):
                            pass
                    elif 'token_count' in msg:
                        try:
                            metrics['total_tokens'] += int(msg['token_count'])
                        except (ValueError, TypeError):
                            pass
                            
                    # Costo
                    if 'cost' in msg:
                        try:
                            metrics['total_cost'] += float(msg['cost'])
                        except (ValueError, TypeError):
                            pass
                    elif 'cost_usd' in msg:
                        try:
                            metrics['total_cost'] += float(msg['cost_usd'])
                        except (ValueError, TypeError):
                            pass
                            
                    # Herramientas utilizadas
                    if 'tools_used' in msg and isinstance(msg['tools_used'], list):
                        metrics['tools_used'].extend(msg['tools_used'])
                    elif 'tool_calls' in msg and isinstance(msg['tool_calls'], list):
                        for tool_call in msg['tool_calls']:
                            if isinstance(tool_call, dict) and 'name' in tool_call:
                                metrics['tools_used'].append(tool_call['name'])
                                
        # Calcular duración de la sesión si hay timestamps
        if 'start_time' in session_data and 'end_time' in session_data:
            try:
                start = datetime.fromisoformat(session_data['start_time'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(session_data['end_time'].replace('Z', '+00:00'))
                metrics['session_duration'] = (end - start).total_seconds()
            except (ValueError, TypeError):
                pass
                
        return metrics

    def generate_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Genera un reporte de analítica de uso para los últimos N días.
        
        Args:
            days: Número de días hacia atrás para incluir en el reporte (default: 30)
            
        Returns:
            Diccionario con el reporte completo de analítica
        """
        # Cargar sesiones del período especificado
        raw_sessions = self._load_session_files(days)
        
        # Inicializar contadores y acumuladores
        report = {
            'period_days': days,
            'sessions_analyzed': len(raw_sessions),
            'summary': {
                'total_sessions': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
                'avg_tokens_per_session': 0.0,
                'avg_cost_per_session': 0.0,
                'top_model': 'N/A',
                'top_tool': 'N/A'
            },
            'model_ranking': [],
            'tool_ranking': [],
            'daily_usage': [],
            'sessions_detail': []
        }
        
        if not raw_sessions:
            return report
            
        # Procesar cada sesión
        model_counter = Counter()
        tool_counter = Counter()
        daily_tokens = defaultdict(int)
        daily_cost = defaultdict(float)
        
        total_tokens = 0
        total_cost = 0.0
        
        for session in raw_sessions:
            metrics = self._extract_metrics_from_session(session)
            
            # Actualizar totales
            total_tokens += metrics['total_tokens']
            total_cost += metrics['total_cost']
            
            # Contar modelo utilizado
            model_used = metrics['model_used']
            if model_used != 'unknown':
                model_counter[model_used] += 1
                
            # Contar herramientas utilizadas
            for tool in metrics['tools_used']:
                tool_counter[tool] += 1
                
            # Agrupar por fecha
            file_date = session.get('_file_date')
            if file_date:
                date_key = file_date.strftime('%Y-%m-%d')
                daily_tokens[date_key] += metrics['total_tokens']
                daily_cost[date_key] += metrics['total_cost']
                
            # Guardar detalle de la sesión (opcional, para debug)
            report['sessions_detail'].append({
                'date': file_date.strftime('%Y-%m-%d %H:%M:%S') if file_date else 'unknown',
                'model': metrics['model_used'],
                'tokens': metrics['total_tokens'],
                'cost': metrics['total_cost'],
                'messages': metrics['message_count'],
                'tools': list(set(metrics['tools_used']))  # Herramientas únicas
            })
        
        # Calcular promedios
        session_count = len(raw_sessions)
        if session_count > 0:
            report['summary']['total_sessions'] = session_count
            report['summary']['total_tokens'] = total_tokens
            report['summary']['total_cost'] = total_cost
            report['summary']['avg_tokens_per_session'] = total_tokens / session_count
            report['summary']['avg_cost_per_session'] = total_cost / session_count
            
            # Modelo más usado
            if model_counter:
                report['summary']['top_model'] = model_counter.most_common(1)[0][0]
                # Ranking de modelos
                for model, count in model_counter.most_common():
                    # Calcular promedio de tokens y costo para este modelo
                    model_sessions = [s for s in report['sessions_detail'] if s['model'] == model]
                    avg_tokens = sum(s['tokens'] for s in model_sessions) / len(model_sessions) if model_sessions else 0
                    avg_cost = sum(s['cost'] for s in model_sessions) / len(model_sessions) if model_sessions else 0
                    
                    report['model_ranking'].append({
                        'model': model,
                        'sessions': count,
                        'tokens': sum(s['tokens'] for s in model_sessions),
                        'avg_tokens_per_session': avg_tokens,
                        'cost': sum(s['cost'] for s in model_sessions),
                        'avg_cost_per_session': avg_cost
                    })
            
            # Herramienta más usada
            if tool_counter:
                report['summary']['top_tool'] = tool_counter.most_common(1)[0][0]
                # Ranking de herramientas
                for tool, count in tool_counter.most_common():
                    report['tool_ranking'].append({
                        'tool': tool,
                        'count': count
                    })
        
        # Preparar uso diario (últimos 7 días para no sobrecargar el reporte)
        sorted_dates = sorted(daily_tokens.keys(), reverse=True)[:7]
        for date in sorted_dates:
            report['daily_usage'].append({
                'date': date,
                'tokens': daily_tokens[date],
                'cost': daily_cost[date]
            })
        
        return report


# Función de conveniencia para uso externo
def generate_insights_report(days: int = 30) -> Dict[str, Any]:
    """
    Función de conveniencia para generar un reporte de analítica.
    
    Args:
        days: Número de días hacia atrás para incluir en el reporte
        
    Returns:
        Diccionario con el reporte de analítica
    """
    engine = KogniInsightsEngine()
    return engine.generate_report(days)


if __name__ == "__main__":
    # Ejemplo de uso cuando se ejecuta directamente
    import pprint
    engine = KogniInsightsEngine()
    report = engine.generate_report(30)
    pprint.pprint(report)