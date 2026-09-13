#!/usr/bin/env python3
"""
Migración: registry de modelos LLM al día (2026-09-13)

Qué cambia en llm_model_registry (fuentes oficiales consultadas el 2026-09-13):
- Google: current gemini-3.5-flash → gemini-3.6-flash (modelo por defecto de la
  app Gemini para todos los usuarios). Precio 0.75 / 3.75 USD por 1M
  (ai.google.dev/gemini-api/docs/pricing; sube a 1.50 / 7.50 el 2027-01-01).
- Anthropic: claude-sonnet-5 a 2 / 10 USD por 1M (platform.claude.com/docs/en/
  about-claude/pricing: el precio introductorio pasa a estándar).
- OpenAI: gpt-5.5 a 5 / 30 USD por 1M (developers.openai.com/api/docs/models/gpt-5.5).
  gpt-5.3-chat-latest deja de estar disponible (404 desde 2026-08-31).
- Perplexity: sonar pasa a servirse por el Agent API (preset fast).

Cada cambio real deja una fila en llm_model_changelog. Idempotente: si el
registry ya está así, no escribe nada.

Uso:
    python3 migrate_models_2026_09.py            # simulación: muestra qué cambiaría
    python3 migrate_models_2026_09.py --apply    # aplica en la BD de DATABASE_URL
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

CHANGED_BY = 'migration:2026-09'

# (provider, model_id) → campos objetivo
TARGETS = [
    ('google', 'gemini-3.6-flash', {
        'model_display_name': 'Gemini 3.6 Flash',
        'cost_per_1m_input_tokens': Decimal('0.75'),
        'cost_per_1m_output_tokens': Decimal('3.75'),
        'is_available': True,
        'pending_approval': False,
    }, 'Precio oficial y alta como modelo por defecto de la app Gemini'),
    ('anthropic', 'claude-sonnet-5', {
        'cost_per_1m_input_tokens': Decimal('2'),
        'cost_per_1m_output_tokens': Decimal('10'),
    }, 'El precio introductorio 2/10 pasa a estándar'),
    ('openai', 'gpt-5.5', {
        'model_display_name': 'GPT-5.5',
        'cost_per_1m_input_tokens': Decimal('5'),
        'cost_per_1m_output_tokens': Decimal('30'),
    }, 'Precio oficial de la página del modelo'),
    ('openai', 'gpt-5.3-chat-latest', {
        'model_display_name': 'GPT-5.3 Instant (retirado)',
        'is_available': False,
    }, 'Serie -chat-latest retirada por OpenAI (404)'),
    ('perplexity', 'sonar', {
        'model_display_name': 'Perplexity (Agent API)',
    }, 'Sonar por Chat Completions se retira el 2026-09-27; se usa el Agent API'),
]

# provider → modelo que debe quedar como único current
CURRENT = {'google': 'gemini-3.6-flash'}


def _normalize(value):
    return Decimal(str(value)) if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) else value


def plan_changes(cur):
    """Lista de cambios pendientes (vacía si el registry ya está al día)."""
    changes = []
    for provider, model_id, fields, reason in TARGETS:
        cur.execute(
            f"SELECT {', '.join(fields)} FROM llm_model_registry WHERE llm_provider = %s AND model_id = %s",
            (provider, model_id),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"No existe {provider}/{model_id} en llm_model_registry")
        diff = {k: (row[k], v) for k, v in fields.items() if _normalize(row[k]) != v}
        if diff:
            changes.append({'kind': 'update', 'provider': provider, 'model_id': model_id,
                            'diff': diff, 'reason': reason})

    for provider, model_id in CURRENT.items():
        cur.execute(
            "SELECT model_id, model_display_name FROM llm_model_registry WHERE llm_provider = %s AND is_current = TRUE",
            (provider,),
        )
        currents = cur.fetchall()
        if [r['model_id'] for r in currents] != [model_id]:
            changes.append({'kind': 'switch_current', 'provider': provider, 'model_id': model_id,
                            'old': currents[0] if currents else None})
    return changes


def apply_changes(cur, changes):
    for change in changes:
        provider, model_id = change['provider'], change['model_id']
        if change['kind'] == 'update':
            assignments = ', '.join(f"{k} = %s" for k in change['diff'])
            cur.execute(
                f"UPDATE llm_model_registry SET {assignments}, updated_at = NOW() "
                f"WHERE llm_provider = %s AND model_id = %s",
                [new for _, new in change['diff'].values()] + [provider, model_id],
            )
            diff = change['diff']
            if diff.get('is_available', (None, True))[1] is False:
                change_type = 'deprecated'
            elif any(k.startswith('cost_per_') for k in diff):
                change_type = 'price_fix'
            else:
                change_type = 'metadata_update'
            cur.execute("""
                INSERT INTO llm_model_changelog
                    (llm_provider, old_model_id, new_model_id, change_type, changed_by, reason, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (provider, model_id, model_id, change_type, CHANGED_BY, change['reason'],
                  json.dumps({k: [str(o), str(n)] for k, (o, n) in change['diff'].items()})))
        else:
            old = change['old']
            cur.execute("UPDATE llm_model_registry SET is_current = FALSE, updated_at = NOW() "
                        "WHERE llm_provider = %s AND is_current = TRUE AND model_id <> %s", (provider, model_id))
            cur.execute("UPDATE llm_model_registry SET is_current = TRUE, updated_at = NOW() "
                        "WHERE llm_provider = %s AND model_id = %s", (provider, model_id))
            cur.execute("""
                INSERT INTO llm_model_changelog
                    (llm_provider, old_model_id, new_model_id, old_display_name, new_display_name,
                     change_type, changed_by, reason, metadata)
                SELECT %s, %s, model_id, %s, model_display_name, 'manual_switch', %s, %s, '{}'::jsonb
                FROM llm_model_registry WHERE llm_provider = %s AND model_id = %s
            """, (provider, old['model_id'] if old else None, old['model_display_name'] if old else None,
                  CHANGED_BY, 'Modelo por defecto que ven los usuarios gratuitos de la app', provider, model_id))


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
        changes = plan_changes(cur)
        if not changes:
            logger.info("✅ El registry ya está al día: nada que cambiar")
            return
        for c in changes:
            detail = c.get('diff') or f"current: {c['old']['model_id'] if c['old'] else None} → {c['model_id']}"
            logger.info(f"   {c['provider']}/{c['model_id']}: {detail}")
        if not args.apply:
            logger.info(f"🔎 Simulación: {len(changes)} cambios pendientes. Ejecuta con --apply para aplicarlos.")
            conn.rollback()
            return
        apply_changes(cur, changes)
        conn.commit()
        logger.info(f"✅ {len(changes)} cambios aplicados")
    except Exception:
        conn.rollback()
        logger.exception("❌ Migración revertida")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
