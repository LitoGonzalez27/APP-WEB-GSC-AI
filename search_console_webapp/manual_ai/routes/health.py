"""
Rutas de health check
"""

import logging
import json
from flask import jsonify
from datetime import date
from database import get_db_connection
from manual_ai import manual_ai_bp
from manual_ai.utils.helpers import now_utc_iso

logger = logging.getLogger(__name__)


@manual_ai_bp.route('/api/health', methods=['GET'])
def manual_ai_health():
    """
    Health-check: confirma app viva, DB accesible, última ejecución y resultados del día
    
    Returns:
        JSON con estado del sistema
    """
    try:
        # DB check
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "db": "down"}), 500
        
        cur = conn.cursor()
        today = date.today()
        
        # Últimos eventos de cron
        try:
            cur.execute("""
                SELECT event_date, event_type, event_title
                FROM manual_ai_events
                WHERE event_type IN ('daily_analysis')
                ORDER BY event_date DESC
                LIMIT 1
            """)
            last = cur.fetchone()
        except Exception:
            last = None
        
        # Conteos de hoy
        cur.execute("SELECT COUNT(*) AS c FROM manual_ai_results WHERE analysis_date = %s", (today,))
        results_today = cur.fetchone()['c']
        
        try:
            cur.execute("SELECT COUNT(*) AS c FROM manual_ai_global_domains WHERE analysis_date = %s", (today,))
            global_today = cur.fetchone()['c']
        except Exception:
            global_today = 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "ok",
            "ts": now_utc_iso(),
            "db": "ok",
            "last_cron": (last['event_date'] if last and isinstance(last, dict) else (last[0] if last else None)),
            "results_today": int(results_today),
            "global_domains_today": int(global_today)
        }), 200
        
    except Exception as e:
        logger.error(json.dumps({"event": "health_error", "error": str(e)}))
        return jsonify({"status": "error", "message": str(e)}), 500

