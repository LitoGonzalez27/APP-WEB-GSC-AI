#!/usr/bin/env python3
"""
Cron diario para reset automático de cuotas (SERP + LLM).

- Usa quota_reset_date como fuente principal
- Resetea quota_used a 0
- Reanuda módulos/proyectos pausados por cuota
"""

import os
import logging
from datetime import datetime, timezone

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
    # Use timezone-aware UTC so comparisons against TIMESTAMPTZ columns
    # (current_period_end, quota_reset_date) and Stripe responses work
    # consistently. Naive utcnow() caused "can't compare offset-naive and
    # offset-aware" errors when period_end was non-null.
    now = datetime.now(timezone.utc)
    logger.info("🕒 === QUOTA RESET CRON STARTED ===")
    logger.info(f"⏰ Timestamp: {now.isoformat()}")

    # 1) Listar usuarios pendientes en una conexión corta y cerrarla antes del loop
    list_conn = get_db_connection()
    if not list_conn:
        logger.error("❌ No se pudo conectar a la BD")
        return

    try:
        cur = list_conn.cursor()
        # ──────────────────────────────────────────────────────────────────
        # Selección (reescrita 2026-08-07):
        # quota_reset_date es la fuente de verdad: si está en el pasado (o
        # NULL) el usuario está pendiente de reset. El filtro anterior
        # exigía ADEMÁS current_period_end NULL/pasado, asumiendo que "a
        # mitad de periodo Stripe ⇒ el webhook payment_succeeded resetea".
        # Eso vale para planes MENSUALES, pero en planes ANUALES
        # current_period_end queda hasta un año en el futuro y solo hay una
        # factura AL AÑO: los resets mensuales intermedios son de este cron,
        # y el filtro los excluía — usuario congelado con cuota agotada
        # (caso real: user 665719, premium anual, bloqueado desde jul-2026
        # con quota_reset_date=jun-2027).
        # No hay riesgo de reset prematuro para mensuales: la condición
        # quota_reset_date <= NOW() ya garantiza que la ventana venció, y
        # compute_next_quota_reset_date hace cap en period_end.
        # ──────────────────────────────────────────────────────────────────
        cur.execute("""
            SELECT id, plan, billing_status, quota_used, quota_reset_date,
                   current_period_start, current_period_end, subscription_id
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

    skipped_stripe_active = 0

    for user in users:
        user_id = user['id']

        # ─────────────────────────────────────────────────────────────────
        # Live Stripe lookup (reescrito 2026-08-07):
        # Si el usuario tiene suscripción pero current_period_end es NULL
        # (legacy / el webhook nunca cacheó el periodo), lo pedimos vivo a
        # Stripe para que compute_next_quota_reset_date pueda hacer cap, y
        # lo cacheamos en BD.
        # IMPORTANTE: NUNCA usar el period_end vivo como quota_reset_date.
        # El backfill antiguo hacía exactamente eso y en suscripciones
        # ANUALES estampaba un reset a un año vista, congelando la cuota
        # (bug user 665719). Ahora solo hay dos salidas:
        #   - reset debido (quota_reset_date <= NOW): seguir al flujo normal
        #     de reset usando el period_end vivo como cap.
        #   - quota_reset_date NULL con periodo activo: inicializar la fecha
        #     al próximo ciclo (compute_..., 30d cap period_end) SIN resetear
        #     — está a mitad de periodo y no le toca todavía.
        # ─────────────────────────────────────────────────────────────────
        sub_id = user.get('subscription_id')
        period_end_db = user.get('current_period_end')
        if sub_id and period_end_db is None:
            try:
                live_period_end = _fetch_live_stripe_period_end(sub_id)
                if live_period_end is not None:
                    user = dict(user)
                    user['current_period_end'] = live_period_end
                    try:
                        bf_conn = get_db_connection()
                        if bf_conn:
                            try:
                                bf_cur = bf_conn.cursor()
                                bf_cur.execute("""
                                    UPDATE users
                                    SET current_period_end = %s,
                                        updated_at = NOW()
                                    WHERE id = %s
                                """, (live_period_end, user_id))
                                bf_conn.commit()
                                logger.info(f"📌 User {user_id}: backfilled current_period_end = {live_period_end.isoformat()}")
                            finally:
                                bf_conn.close()
                    except Exception as bf_err:
                        logger.warning(f"⚠️ User {user_id}: backfill failed (non-fatal): {bf_err}")

                    if user.get('quota_reset_date') is None and live_period_end > now:
                        init_reset = compute_next_quota_reset_date(
                            period_end=live_period_end,
                            now=now
                        )
                        logger.info(
                            f"⏭️ User {user_id}: sin quota_reset_date y periodo Stripe "
                            f"activo; inicializando quota_reset_date={init_reset.isoformat()} "
                            f"sin resetear"
                        )
                        try:
                            init_conn = get_db_connection()
                            if init_conn:
                                try:
                                    init_cur = init_conn.cursor()
                                    init_cur.execute("""
                                        UPDATE users
                                        SET quota_reset_date = %s,
                                            updated_at = NOW()
                                        WHERE id = %s
                                    """, (init_reset, user_id))
                                    init_conn.commit()
                                finally:
                                    init_conn.close()
                        except Exception as init_err:
                            logger.warning(f"⚠️ User {user_id}: init quota_reset_date failed (non-fatal): {init_err}")
                        skipped_stripe_active += 1
                        continue
            except Exception as e:
                logger.warning(
                    f"⚠️ User {user_id}: live Stripe lookup failed ({e}); "
                    f"proceeding with cron reset as fallback"
                )

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
        f"✅ QUOTA RESET CRON FINISHED | ok={reset_ok} "
        f"reset_fail={reset_fail} resume_fail={resume_fail} "
        f"skipped_stripe_active={skipped_stripe_active}"
    )


def _fetch_live_stripe_period_end(subscription_id):
    """Fetch the current period_end for a subscription directly from Stripe.

    Used as a safety net when our DB has no period info (e.g. legacy users
    whose subscription was created before current_period_end was tracked,
    or where the webhook never fired correctly). Returns a timezone-naive
    datetime (UTC) if Stripe responds, or None if the subscription cannot
    be retrieved or the field is missing.

    Failures are silenced (raised to caller as exception) so the cron can
    fall back to its default behavior.
    """
    import stripe
    api_key = os.getenv('STRIPE_SECRET_KEY')
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not configured")
    stripe.api_key = api_key

    sub = stripe.Subscription.retrieve(subscription_id)
    period_end_ts = sub.get('current_period_end')
    if not period_end_ts:
        # Some subscriptions in newer API put it inside items
        items = (sub.get('items') or {}).get('data') or []
        if items:
            period_end_ts = items[0].get('current_period_end')
    if not period_end_ts:
        return None
    from datetime import datetime as _dt, timezone as _tz
    # Return timezone-aware UTC for consistency with Postgres TIMESTAMPTZ
    return _dt.fromtimestamp(period_end_ts, tz=_tz.utc)


if __name__ == "__main__":
    main()
