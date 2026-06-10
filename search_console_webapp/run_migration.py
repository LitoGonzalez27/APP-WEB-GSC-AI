#!/usr/bin/env python3
"""
Migración: Switch Google model → Gemini 3 Flash + tablas de resiliencia
Ejecutar: python3 run_migration.py "postgresql://..."
O con Railway: railway run python3 run_migration.py
"""
import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_database_url():
    """Obtiene DATABASE_URL de args o env"""
    if len(sys.argv) > 1 and sys.argv[1].startswith('postgres'):
        return sys.argv[1]
    url = os.getenv('DATABASE_URL')
    if url:
        return url
    print("❌ No se encontró DATABASE_URL")
    print("   Uso: python3 run_migration.py \"postgresql://...\"")
    print("   O:   railway run python3 run_migration.py")
    sys.exit(1)


def run_migration():
    db_url = get_database_url()
    print(f"🔗 Conectando a BD... ({db_url[:30]}...)")

    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    try:
        # ── Estado ANTES ──
        print("\n📊 Estado ANTES de la migración:")
        print("=" * 70)
        cur.execute("""
            SELECT model_id, model_display_name, is_current,
                   cost_per_1m_input_tokens, cost_per_1m_output_tokens
            FROM llm_model_registry
            WHERE llm_provider = 'google'
            ORDER BY is_current DESC
        """)
        for r in cur.fetchall():
            status = "✅ CURRENT" if r['is_current'] else "          "
            print(f"  {status} | {r['model_id']:30} | ${r['cost_per_1m_input_tokens']}/{r['cost_per_1m_output_tokens']} per 1M")

        # ── 1. Insertar/actualizar gemini-3-flash-preview ──
        print("\n🔄 [1/4] Insertando gemini-3-flash-preview...")
        cur.execute("""
            INSERT INTO llm_model_registry (
                llm_provider, model_id, model_display_name,
                cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                is_current, is_available
            ) VALUES (
                'google', 'gemini-3-flash-preview', 'Gemini 3 Flash',
                0.50, 3.00, FALSE, TRUE
            )
            ON CONFLICT (llm_provider, model_id) DO UPDATE SET
                model_display_name = 'Gemini 3 Flash',
                cost_per_1m_input_tokens = 0.50,
                cost_per_1m_output_tokens = 3.00,
                is_available = TRUE,
                updated_at = NOW()
        """)
        print("   ✅ gemini-3-flash-preview insertado/actualizado")

        # ── 2. Quitar is_current de TODOS los modelos Google ──
        print("🔄 [2/4] Quitando is_current de todos los modelos Google...")
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = FALSE, updated_at = NOW()
            WHERE llm_provider = 'google'
        """)
        print(f"   ✅ {cur.rowcount} modelos Google → is_current = FALSE")

        # ── 3. Marcar Flash como current ──
        print("🔄 [3/4] Marcando gemini-3-flash-preview como CURRENT...")
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = TRUE, updated_at = NOW()
            WHERE llm_provider = 'google' AND model_id = 'gemini-3-flash-preview'
        """)
        print(f"   ✅ {cur.rowcount} fila actualizada")

        # ── 4. Crear tablas de resiliencia ──
        print("🔄 [4/4] Creando tablas de resiliencia...")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_monitoring_analysis_lock (
                id INTEGER PRIMARY KEY DEFAULT 1,
                is_running BOOLEAN DEFAULT FALSE,
                started_at TIMESTAMP,
                started_by TEXT,
                CONSTRAINT single_row CHECK (id = 1)
            )
        """)
        cur.execute("""
            INSERT INTO llm_monitoring_analysis_lock (id, is_running)
            VALUES (1, FALSE)
            ON CONFLICT (id) DO NOTHING
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_monitoring_analysis_runs (
                id SERIAL PRIMARY KEY,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                status TEXT DEFAULT 'running',
                total_projects INTEGER DEFAULT 0,
                successful_projects INTEGER DEFAULT 0,
                failed_projects INTEGER DEFAULT 0,
                total_queries INTEGER DEFAULT 0,
                error_message TEXT,
                triggered_by TEXT DEFAULT 'cron'
            )
        """)
        print("   ✅ Tablas llm_monitoring_analysis_lock + _runs creadas")

        # ── COMMIT ──
        conn.commit()

        # ── Estado DESPUÉS ──
        print("\n📊 Estado DESPUÉS de la migración:")
        print("=" * 70)
        cur.execute("""
            SELECT model_id, model_display_name, is_current,
                   cost_per_1m_input_tokens, cost_per_1m_output_tokens
            FROM llm_model_registry
            WHERE llm_provider = 'google'
            ORDER BY is_current DESC
        """)
        for r in cur.fetchall():
            status = "✅ CURRENT" if r['is_current'] else "          "
            print(f"  {status} | {r['model_id']:30} | ${r['cost_per_1m_input_tokens']}/{r['cost_per_1m_output_tokens']} per 1M")

        print("\n" + "=" * 70)
        print("🎉 MIGRACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 70)

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run_migration()
