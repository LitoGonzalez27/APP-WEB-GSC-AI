#!/usr/bin/env python3
"""
Migración: búsqueda web en LLM Monitoring, fase P3 (2026-09-13)

Solo añade (no borra ni reescribe datos de usuarios):
1. llm_model_registry.cost_per_1k_search_calls NUMERIC: precio de la herramienta de
   búsqueda por 1.000 llamadas, aparte de los tokens. NULL = sin precio (el provider
   avisa en el log y no suma coste de búsqueda).
2. llm_monitoring_results.units_consumed SMALLINT NOT NULL DEFAULT 1: unidades de cuota
   de cada respuesta. Todas las filas existentes quedan en 1, que es exactamente lo que
   contaba el COUNT(*) anterior: el consumo histórico no cambia. Solo los proyectos con
   search_mode='auto' escriben pesos mayores (llm_monitoring_limits.units_per_task).
3. Precios oficiales de búsqueda de los modelos current (páginas consultadas el
   2026-09-13), con una fila en llm_model_changelog por cambio real:
   - OpenAI gpt-5.5: 10 USD / 1.000 llamadas (modelos de razonamiento; los tokens del
     contenido de búsqueda se cobran a precio del modelo). developers.openai.com/api/docs/pricing
   - OpenAI gpt-4o (fallback, no razonamiento): 25 USD / 1.000 llamadas.
   - Anthropic claude-sonnet-5: 10 USD / 1.000 búsquedas.
     platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
   - Google gemini-3.6-flash: 14 USD / 1.000 consultas de búsqueda (Gemini 3.x cobra cada
     consulta). Hay 5.000 gratis al mes compartidas, pero por decisión de Carlos se
     registra el precio de lista. ai.google.dev/gemini-api/docs/pricing
   Perplexity no lo necesita: el Agent API devuelve el coste real.

En PostgreSQL ≥ 11 añadir una columna con DEFAULT constante no reescribe la tabla.
Idempotente. Ejecutar ANTES de desplegar el código de P3 (el código además comprueba
que units_consumed exista y, si no, cuenta filas como antes).

Uso:
    python3 migrate_llm_search_p3.py            # simulación: muestra qué cambiaría
    python3 migrate_llm_search_p3.py --apply    # aplica en la BD de DATABASE_URL
"""

import argparse
import json
import logging
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CHANGED_BY = 'migration:2026-09-p3'

SCHEMA_STATEMENTS = [
    # Si una transacción larga (p.ej. el cron) retiene la tabla, fallar a los 5 s y
    # reintentar en vez de dejar la app esperando detrás del ALTER.
    ("lock_timeout 5s", "SET LOCAL lock_timeout = '5s'"),
    ("cost_per_1k_search_calls en el registry", """
        ALTER TABLE llm_model_registry
        ADD COLUMN IF NOT EXISTS cost_per_1k_search_calls NUMERIC(10, 4)
    """),
    ("units_consumed en resultados", """
        ALTER TABLE llm_monitoring_results
        ADD COLUMN IF NOT EXISTS units_consumed SMALLINT NOT NULL DEFAULT 1
    """),
    ("CHECK de units_consumed", """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'llm_monitoring_results_units_consumed_check'
            ) THEN
                -- NOT VALID: no recorre la tabla bajo bloqueo (las filas existentes
                -- valen 1 por el DEFAULT); se aplica a todo lo que se escriba después
                ALTER TABLE llm_monitoring_results
                ADD CONSTRAINT llm_monitoring_results_units_consumed_check
                CHECK (units_consumed >= 1) NOT VALID;
            END IF;
        END $$
    """),
]

# (provider, model_id, USD por 1.000 llamadas de búsqueda, obligatorio)
SEARCH_PRICES = [
    ('openai', 'gpt-5.5', Decimal('10'), True),
    ('openai', 'gpt-4o', Decimal('25'), False),
    ('anthropic', 'claude-sonnet-5', Decimal('10'), True),
    ('google', 'gemini-3.6-flash', Decimal('14'), True),
]


def apply_schema(cur):
    for label, sql in SCHEMA_STATEMENTS:
        cur.execute(sql)
        logger.info(f"   ✅ {label}")


def plan_price_changes(cur):
    changes = []
    for provider, model_id, price, required in SEARCH_PRICES:
        cur.execute("""
            SELECT cost_per_1k_search_calls FROM llm_model_registry
            WHERE llm_provider = %s AND model_id = %s
        """, (provider, model_id))
        row = cur.fetchone()
        if not row:
            if required:
                raise RuntimeError(f"No existe {provider}/{model_id} en llm_model_registry")
            logger.info(f"   ⏭️ {provider}/{model_id} no está en el registry: se omite")
            continue
        old = row['cost_per_1k_search_calls']
        if old is None or Decimal(str(old)) != price:
            changes.append((provider, model_id, old, price))
    return changes


def apply_price_changes(cur, changes):
    for provider, model_id, old, price in changes:
        cur.execute("""
            UPDATE llm_model_registry SET cost_per_1k_search_calls = %s, updated_at = NOW()
            WHERE llm_provider = %s AND model_id = %s
        """, (price, provider, model_id))
        cur.execute("""
            INSERT INTO llm_model_changelog
                (llm_provider, old_model_id, new_model_id, change_type, changed_by, reason, metadata)
            VALUES (%s, %s, %s, 'price_fix', %s, %s, %s)
        """, (provider, model_id, model_id, CHANGED_BY,
              'Precio oficial de la herramienta de búsqueda web (USD por 1.000 llamadas)',
              json.dumps({'cost_per_1k_search_calls': [None if old is None else str(old), str(price)]})))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='escribir en BD (sin esto solo simula)')
    args = parser.parse_args()

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        sys.exit(1)
    try:
        cur = conn.cursor()
        # La simulación también ejecuta los ALTER (para poder leer la columna nueva) y
        # después hace rollback: no queda nada escrito.
        apply_schema(cur)
        changes = plan_price_changes(cur)
        for provider, model_id, old, price in changes:
            logger.info(f"   {provider}/{model_id}: cost_per_1k_search_calls {old} → {price}")
        if not args.apply:
            logger.info(f"🔎 Simulación: esquema + {len(changes)} precios pendientes. "
                        f"Ejecuta con --apply para aplicarlos.")
            conn.rollback()
            return
        apply_price_changes(cur, changes)
        conn.commit()
        logger.info(f"✅ Esquema listo y {len(changes)} precios aplicados")
    except Exception:
        conn.rollback()
        logger.exception("❌ Migración revertida")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
