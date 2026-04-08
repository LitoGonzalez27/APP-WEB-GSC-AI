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
    """
    Reset diario de cuotas para usuarios con plan de pago.

    Patrón: commit-por-usuario (no una sola transacción gigante).
    Cada usuario se resetea en su propia conexión corta. Esto evita el
    self-deadlock que existía en versiones anteriores, donde una única
    conexión tomaba row-lock en users.id=X y luego llamaba a
    resume_quota_pauses_for_user(X) — que abría una NUEVA conexión y
    bloqueaba para siempre esperando el lock de la primera.

    Ventajas:
    - Atomicidad por usuario: un fallo en uno no afecta a los demás.
    - Si el proceso muere a mitad, los ya procesados quedan OK y los
      restantes se recogen en la siguiente ejecución.
    - Sin transacciones largas que puedan acumular zombies.
    """
    now = datetime.utcnow()
    logger.info("🕒 === QUOTA RESET CRON STARTED ===")
    logger.info(f"⏰ Timestamp: {now.isoformat()}")

    # 1) Listar usuarios pendientes en una conexión corta y cerrarla antes del loop
    list_conn = get_db_connection()
    if not list_conn:
        logger.error("❌ No se pudo conectar a la BD")
        return

    try:
        cur = list_conn.cursor()
        cur.execute("""
            SELECT id, plan, billing_status, quota_used, quota_reset_date,
                   current_period_start, current_period_end
            FROM users
            WHERE plan != 'free'
              AND billing_status IN ('active', 'trialing', 'beta')
              AND (quota_reset_date IS NULL OR quota_reset_date <= NOW())
        """)
        users = cur.fetchall() or []
        cur.close()
    except Exception as e:
        logger.error(f"❌ Error listando usuarios pendientes de reset: {e}", exc_info=True)
        try:
            list_conn.close()
        except Exception:
            pass
        return
    finally:
        try:
            list_conn.close()
        except Exception:
            pass

    logger.info(f"🔍 Usuarios pendientes de reset: {len(users)}")

    reset_ok = 0
    reset_fail = 0
    resume_fail = 0

    for user in users:
        user_id = user['id']
        try:
            next_reset = compute_next_quota_reset_date(
                period_start=user.get('current_period_start'),
                period_end=user.get('current_period_end'),
                last_reset=user.get('quota_reset_date'),
                now=now
            )
        except Exception as e:
            logger.error(f"❌ Error calculando next_reset para user {user_id}: {e}", exc_info=True)
            reset_fail += 1
            continue

        # 2) Reset de cuota en transacción propia del usuario.
        #    COMMIT antes de llamar a resume_quota_pauses_for_user para liberar
        #    el row-lock y evitar el self-deadlock.
        user_conn = get_db_connection()
        if not user_conn:
            logger.error(f"❌ No DB conn for user {user_id}, skipping")
            reset_fail += 1
            continue

        ucur = None
        try:
            ucur = user_conn.cursor()
            ucur.execute("""
                UPDATE users
                SET quota_used = 0,
                    quota_reset_date = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (next_reset, user_id))
            user_conn.commit()
            reset_ok += 1
        except Exception as e:
            logger.error(f"❌ Error reset user {user_id}: {e}", exc_info=True)
            try:
                user_conn.rollback()
            except Exception:
                pass
            reset_fail += 1
            continue
        finally:
            try:
                if ucur is not None:
                    ucur.close()
            except Exception:
                pass
            try:
                user_conn.close()
            except Exception:
                pass

        # 3) Con el lock liberado, rehabilitar módulos pausados (abre su propia conn).
        #    Si esto falla, el reset de cuota YA está commiteado — solo se loggea warning.
        try:
            resume_quota_pauses_for_user(user_id)
        except Exception as resume_error:
            logger.warning(f"Could not resume pauses for user {user_id}: {resume_error}")
            resume_fail += 1

        logger.info(
            f"✅ Reset user {user_id} | next_reset={next_reset.isoformat()}"
        )

    logger.info(
        f"✅ QUOTA RESET CRON FINISHED | ok={reset_ok} reset_fail={reset_fail} resume_fail={resume_fail}"
    )


if __name__ == "__main__":
    main()
