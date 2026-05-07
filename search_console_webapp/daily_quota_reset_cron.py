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
        # Stripe-aware filter (added 2026-05-07):
        # We only reset users for whom a reset is SAFE, i.e. one of:
        #   (a) No Stripe subscription (admin enterprise, beta, etc.) — the
        #       cron is the canonical mechanism.
        #   (b) Stripe period is genuinely over (current_period_end <= NOW)
        #       — safe to reset because Stripe has either charged for the
        #       new period (webhook should have fired) or marked past_due.
        #   (c) current_period_end IS NULL (legacy data, period info never
        #       captured). For these users we'll do a live Stripe API
        #       lookup per-user later so we don't reset prematurely.
        # Users with subscription_id AND current_period_end > NOW are
        # explicitly EXCLUDED here — Stripe is in the middle of their
        # billing period and the webhook payment_succeeded is the right
        # mechanism to reset them, not us.
        # ──────────────────────────────────────────────────────────────────
        cur.execute("""
            SELECT id, plan, billing_status, quota_used, quota_reset_date,
                   current_period_start, current_period_end, subscription_id
            FROM users
            WHERE plan != 'free'
              AND billing_status IN ('active', 'trialing', 'beta')
              AND (quota_reset_date IS NULL OR quota_reset_date <= NOW())
              AND (
                  subscription_id IS NULL
                  OR current_period_end IS NULL
                  OR current_period_end <= NOW()
              )
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
        # Live Stripe safety check (added 2026-05-07):
        # If the user has a Stripe subscription_id but current_period_end
        # is NULL (legacy / data never backfilled), do a live API lookup
        # before resetting. If Stripe says the period is still active, we
        # SKIP the reset and let the payment_succeeded webhook do its job.
        # This protects against the "user consumed all quota in 5 days,
        # we reset them on day 30 before Stripe charges day 31" gap.
        # ─────────────────────────────────────────────────────────────────
        sub_id = user.get('subscription_id')
        period_end_db = user.get('current_period_end')
        if sub_id and period_end_db is None:
            try:
                live_period_end = _fetch_live_stripe_period_end(sub_id)
                if live_period_end is not None and live_period_end > now:
                    logger.info(
                        f"⏭️ User {user_id}: Stripe period still active live "
                        f"(period_end={live_period_end.isoformat()}); skipping reset"
                    )
                    skipped_stripe_active += 1
                    continue
                if live_period_end is not None:
                    # Use live value as period_end for compute_next_quota_reset_date
                    user = dict(user) if not isinstance(user, dict) else dict(user)
                    user['current_period_end'] = live_period_end
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
