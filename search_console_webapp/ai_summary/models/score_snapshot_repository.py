"""
Repositorio del histórico diario del AI Visibility Score (ai_brand_score_snapshots).
Una fila por marca y día; se upserta al ver el resumen (30d) y desde el cron.
"""

import logging
from datetime import date
from typing import Dict, List

from database import db_conn

logger = logging.getLogger(__name__)

ALLOWED_HISTORY_MONTHS = (3, 6, 12)


class ScoreSnapshotRepository:

    @staticmethod
    def upsert_today(brand_id: int, summary: Dict) -> bool:
        """
        Registrar el score de hoy a partir de un summary ya calculado
        (periodo 30d, la definición canónica del score histórico).
        No-op silencioso si el score es None (marca sin datos).
        """
        score = (summary.get('score') or {}).get('value')
        if score is None:
            return False

        channels = summary.get('channels') or {}

        def channel_visibility(name):
            return (channels.get(name) or {}).get('visibility_pct')

        with db_conn() as conn:
            if not conn:
                return False
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO ai_brand_score_snapshots
                        (brand_id, snapshot_date, score,
                         aio_visibility, ai_mode_visibility, llm_visibility, channels_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (brand_id, snapshot_date) DO UPDATE SET
                        score = EXCLUDED.score,
                        aio_visibility = EXCLUDED.aio_visibility,
                        ai_mode_visibility = EXCLUDED.ai_mode_visibility,
                        llm_visibility = EXCLUDED.llm_visibility,
                        channels_used = EXCLUDED.channels_used
                """, (
                    brand_id, date.today(), score,
                    channel_visibility('ai_overview'),
                    channel_visibility('ai_mode'),
                    channel_visibility('llm'),
                    (summary.get('score') or {}).get('channels_used') or [],
                ))
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Error upserting score snapshot for brand {brand_id}: {e}")
                return False

    @staticmethod
    def get_history(brand_id: int, months: int = 6) -> List[Dict]:
        if months not in ALLOWED_HISTORY_MONTHS:
            months = 6
        with db_conn() as conn:
            if not conn:
                return []
            cur = conn.cursor()
            cur.execute("""
                SELECT snapshot_date, score,
                       aio_visibility, ai_mode_visibility, llm_visibility
                FROM ai_brand_score_snapshots
                WHERE brand_id = %s
                  AND snapshot_date >= CURRENT_DATE - (%s * INTERVAL '1 month')
                ORDER BY snapshot_date ASC
            """, (brand_id, months))
            return [{
                'date': r['snapshot_date'].isoformat(),
                'score': float(r['score']),
                'aio_visibility': float(r['aio_visibility']) if r['aio_visibility'] is not None else None,
                'ai_mode_visibility': float(r['ai_mode_visibility']) if r['ai_mode_visibility'] is not None else None,
                'llm_visibility': float(r['llm_visibility']) if r['llm_visibility'] is not None else None,
            } for r in cur.fetchall()]

    @staticmethod
    def get_latest_scores(brand_ids: List[int]) -> Dict[int, Dict]:
        """
        Último score por marca + delta contra el snapshot más cercano a hace
        30 días (o el más antiguo disponible si la serie es más corta).
        Devuelve {brand_id: {score, delta, date}}.
        """
        if not brand_ids:
            return {}
        with db_conn() as conn:
            if not conn:
                return {}
            cur = conn.cursor()
            cur.execute("""
                WITH latest AS (
                    SELECT DISTINCT ON (brand_id)
                        brand_id, snapshot_date, score
                    FROM ai_brand_score_snapshots
                    WHERE brand_id = ANY(%s)
                    ORDER BY brand_id, snapshot_date DESC
                ),
                reference AS (
                    SELECT DISTINCT ON (s.brand_id)
                        s.brand_id, s.score AS ref_score
                    FROM ai_brand_score_snapshots s
                    JOIN latest l ON l.brand_id = s.brand_id
                    WHERE s.snapshot_date <= l.snapshot_date - INTERVAL '28 days'
                    ORDER BY s.brand_id, s.snapshot_date DESC
                )
                SELECT l.brand_id, l.snapshot_date, l.score, r.ref_score
                FROM latest l
                LEFT JOIN reference r ON r.brand_id = l.brand_id
            """, (brand_ids,))
            return {
                r['brand_id']: {
                    'score': float(r['score']),
                    'delta': round(float(r['score']) - float(r['ref_score']), 1)
                             if r['ref_score'] is not None else None,
                    'date': r['snapshot_date'].isoformat(),
                }
                for r in cur.fetchall()
            }
