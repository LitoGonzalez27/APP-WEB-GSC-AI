import os
import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def connect_db(database_url):
    """Establece conexión a la base de datos."""
    if not database_url:
        raise ValueError("DATABASE_URL no está configurado.")
    return psycopg2.connect(database_url)


def _column_exists(cur, table_name, column_name):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def _table_exists(cur, table_name):
    cur.execute("SELECT to_regclass(%s) AS reg", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and (row[0] if isinstance(row, tuple) else row.get('reg')))


def migrate_admin_perf_indexes():
    """Crea índices para mejorar performance del panel admin."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurado en el entorno.")
        return False

    conn = None
    try:
        conn = connect_db(database_url)
        conn.autocommit = True
        cur = conn.cursor()

        # quota_usage_events
        if _table_exists(cur, "quota_usage_events"):
            if _column_exists(cur, "quota_usage_events", "timestamp"):
                logger.info("🔧 Creando índice quota_usage_events(timestamp)...")
                cur.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quota_events_timestamp_billing ON quota_usage_events(timestamp)")
                logger.info("✅ índice creado")
            if _column_exists(cur, "quota_usage_events", "source") and _column_exists(cur, "quota_usage_events", "timestamp"):
                logger.info("🔧 Creando índice quota_usage_events(source, timestamp)...")
                cur.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quota_events_source_timestamp ON quota_usage_events(source, timestamp)")
                logger.info("✅ índice creado")
            if _column_exists(cur, "quota_usage_events", "operation_type") and _column_exists(cur, "quota_usage_events", "timestamp"):
                logger.info("🔧 Creando índice quota_usage_events(operation_type, timestamp)...")
                cur.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quota_events_optype_timestamp ON quota_usage_events(operation_type, timestamp)")
                logger.info("✅ índice creado")

        # llm_monitoring_results
        if _table_exists(cur, "llm_monitoring_results"):
            if _column_exists(cur, "llm_monitoring_results", "analysis_date"):
                logger.info("🔧 Creando índice llm_monitoring_results(analysis_date, project_id)...")
                cur.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_results_date_project ON llm_monitoring_results(analysis_date, project_id)")
                logger.info("✅ índice creado")

        # ai_mode_projects
        if _table_exists(cur, "ai_mode_projects"):
            if _column_exists(cur, "ai_mode_projects", "is_paused_by_quota"):
                logger.info("🔧 Creando índice ai_mode_projects(user_id, is_paused_by_quota)...")
                cur.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_mode_user_paused ON ai_mode_projects(user_id, is_paused_by_quota)")
                logger.info("✅ índice creado")

        # llm_monitoring_projects
        if _table_exists(cur, "llm_monitoring_projects"):
            if _column_exists(cur, "llm_monitoring_projects", "is_paused_by_quota"):
                logger.info("🔧 Creando índice llm_monitoring_projects(user_id, is_paused_by_quota)...")
                cur.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_proj_user_paused ON llm_monitoring_projects(user_id, is_paused_by_quota)")
                logger.info("✅ índice creado")

        logger.info("🎉 Índices de performance creados/verificados.")
        return True
    except Exception as exc:
        logger.error(f"❌ Error creando índices: {exc}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    if migrate_admin_perf_indexes():
        logger.info("Script de índices ejecutado con éxito.")
    else:
        logger.error("Script de índices falló.")

