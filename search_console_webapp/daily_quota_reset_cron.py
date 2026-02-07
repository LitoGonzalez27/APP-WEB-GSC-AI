#!/usr/bin/env python3
"""
Cron diario para reset automático de cuotas (SERP + LLM).

- Usa quota_reset_date como fuente principal
- Resetea quota_used a 0
- Reanuda módulos/proyectos pausados por cuota
"""

import logging
from datetime import datetime

from database import get_db_connection, resume_quota_pauses_for_user
from quota_manager import compute_next_quota_reset_date


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('quota_reset_cron')


def main():
    now = datetime.utcnow()
    logger.info("🕒 === QUOTA RESET CRON STARTED ===")
    logger.info(f"⏰ Timestamp: {now.isoformat()}")

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, plan, billing_status, quota_used, quota_reset_date,
                   current_period_start, current_period_end
            FROM users
            WHERE plan != 'free'
              AND billing_status IN ('active', 'trialing', 'beta')
              AND (quota_reset_date IS NULL OR quota_reset_date <= NOW())
        """)

        users = cur.fetchall() or []
        logger.info(f"🔍 Usuarios pendientes de reset: {len(users)}")

        for user in users:
            user_id = user['id']
            next_reset = compute_next_quota_reset_date(
                period_start=user.get('current_period_start'),
                period_end=user.get('current_period_end'),
                last_reset=user.get('quota_reset_date'),
                now=now
            )

            cur.execute("""
                UPDATE users
                SET quota_used = 0,
                    quota_reset_date = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (next_reset, user_id))

            resume_quota_pauses_for_user(user_id)

            logger.info(
                f"✅ Reset de cuota user {user_id} | next_reset={next_reset.isoformat()}"
            )

        conn.commit()
        logger.info("✅ QUOTA RESET CRON FINISHED")

    except Exception as e:
        logger.error(f"❌ Error en cron de quota: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
