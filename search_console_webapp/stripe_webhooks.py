#!/usr/bin/env python3
"""
STRIPE WEBHOOKS HANDLER
======================

Maneja los webhooks de Stripe para sincronizar eventos de billing
con nuestra base de datos local.
"""

import os
import json
import logging
import stripe
from datetime import datetime
from flask import request, jsonify
from stripe_config import get_stripe_config
from database import get_db_connection, resume_quota_pauses_for_user
from email_service import send_email, send_trial_started_email

logger = logging.getLogger(__name__)

class StripeWebhookHandler:
    """Manejador de webhooks de Stripe"""
    
    def __init__(self):
        """Inicializa el manejador con configuración"""
        self.config = get_stripe_config()
        stripe.api_key = self.config.secret_key
        self.webhook_secret = self.config.webhook_secret
        
        logger.info(f"🔗 Stripe webhook handler initialized - Environment: {self.config.app_env}")
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict:
        """Verifica la firma del webhook y construye el evento"""
        last_error = None
        for secret in [self.webhook_secret, getattr(self.config, 'webhook_secret_alt', None)]:
            if not secret:
                continue
            try:
                event = stripe.Webhook.construct_event(payload, signature, secret)
                logger.info(f"✅ Webhook signature verified - Event: {event['type']}")
                return event
            except Exception as e:
                last_error = e
                continue
        # Si llega aquí, todos los secretos fallaron
        if isinstance(last_error, stripe.error.SignatureVerificationError):
            logger.error(f"❌ Invalid signature with provided secrets: {last_error}")
            raise ValueError("Invalid signature")
        elif isinstance(last_error, ValueError):
            logger.error(f"❌ Invalid payload: {last_error}")
            raise ValueError("Invalid payload")
        else:
            logger.error(f"❌ Webhook verification failed: {last_error}")
            raise ValueError("Webhook verification failed")
    
    def handle_webhook(self, payload: bytes, signature: str) -> dict:
        """Maneja un webhook de Stripe — con deduplicación por event_id (idempotencia).

        Stripe documenta explícitamente que puede entregar el mismo evento
        más de una vez (timeouts, reintentos de red). Sin idempotencia, un
        evento duplicado dispararía dos veces el efecto secundario:
        emails de trial duplicados, doble llamada a track_quota_consumption,
        etc. Con la tabla `stripe_webhook_events` y un INSERT…ON CONFLICT
        DO NOTHING, garantizamos que un evento se procesa una sola vez.

        Si el evento ya estaba registrado y completado, devolvemos 200 OK
        sin reprocesar (idempotente para Stripe).
        """
        try:
            # Verificar firma — primer paso obligatorio
            event = self.verify_webhook_signature(payload, signature)

            event_id = event.get('id')
            event_type = event['type']
            event_data = event['data']['object']

            # Deduplicación: ¿ya hemos procesado este event_id?
            if event_id:
                already_processed, claim_ok = _claim_webhook_event(event_id, event_type)
                if already_processed:
                    logger.info(f"🔁 Webhook event {event_id} ya procesado — idempotent ack")
                    return {'success': True, 'message': 'Event already processed', 'idempotent': True}
                if not claim_ok:
                    # No pudimos reclamar el evento (DB caída) — devolver 5xx para que Stripe reintente
                    logger.warning(f"⚠️ Could not claim webhook event {event_id} — DB issue")
                    return {'success': False, 'error': 'cannot_claim_event'}

            logger.info(f"🔄 Processing event: {event_type} (id={event_id})")

            if event_type == 'checkout.session.completed':
                result = self._handle_checkout_completed(event_data)
            elif event_type == 'customer.subscription.created':
                result = self._handle_subscription_created(event_data)
            elif event_type == 'customer.subscription.updated':
                result = self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                result = self._handle_subscription_deleted(event_data)
            elif event_type == 'invoice.payment.succeeded':
                result = self._handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment.failed':
                result = self._handle_payment_failed(event_data)
            else:
                logger.info(f"ℹ️ Unhandled event type: {event_type}")
                result = {'success': True, 'message': f'Event {event_type} received but not processed'}

            # Marcar el evento como procesado (incluso si el handler devolvió success=False —
            # eso lo refleja el campo status, pero la idempotencia debe consumir el evento).
            if event_id:
                _mark_webhook_event_processed(event_id, success=result.get('success', False),
                                              error_message=result.get('error'))
            return result

        except Exception as e:
            logger.error(f"❌ Error processing webhook: {e}", exc_info=True)
            # No marcamos el evento como procesado para que Stripe reintente
            return {'success': False, 'error': str(e)}


# ---------------------------------------------------------------------------
# Webhook idempotency helpers (added 2026-05-07)
# ---------------------------------------------------------------------------

def _ensure_webhook_events_table(cur):
    """Idempotente: crea la tabla la primera vez que se llama."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS stripe_webhook_events (
            event_id VARCHAR(120) PRIMARY KEY,
            event_type VARCHAR(80) NOT NULL,
            received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
            error_message TEXT
        )
    ''')
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_stripe_webhook_events_received
        ON stripe_webhook_events(received_at DESC)
    ''')


def _claim_webhook_event(event_id: str, event_type: str):
    """Intenta reclamar la propiedad del evento. Devuelve (already_processed, claim_ok).

    Returns:
      (True, True)  → ya estaba procesado, no hay que hacer nada
      (False, True) → reclamado con éxito, procede a procesar
      (False, False)→ no se pudo reclamar (BD inaccesible) — devolver 5xx a Stripe
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False, False
        cur = conn.cursor()
        _ensure_webhook_events_table(cur)
        # INSERT…ON CONFLICT DO NOTHING + RETURNING para detectar si era nuevo
        cur.execute('''
            INSERT INTO stripe_webhook_events (event_id, event_type, status)
            VALUES (%s, %s, 'in_progress')
            ON CONFLICT (event_id) DO NOTHING
            RETURNING event_id
        ''', (event_id, event_type))
        row = cur.fetchone()
        conn.commit()
        if row is None:
            # Existía → ya procesado (o en proceso)
            return True, True
        return False, True
    except Exception as e:
        logger.error(f"Error claiming webhook event {event_id}: {e}")
        if conn:
            try: conn.rollback()
            except Exception: pass
        return False, False
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


def _mark_webhook_event_processed(event_id: str, success: bool, error_message: str = None):
    """Marca el evento como completado (success o failure)."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute('''
            UPDATE stripe_webhook_events
            SET processed_at = NOW(),
                status = %s,
                error_message = %s
            WHERE event_id = %s
        ''', ('processed' if success else 'failed', (error_message or '')[:500], event_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Could not mark webhook event {event_id} as processed: {e}")
        if conn:
            try: conn.rollback()
            except Exception: pass
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


def _alert_unmatched_customer(customer_id: str, subscription_id: str, action: str):
    """Send alert email when a webhook arrives for a customer not in our DB.

    Gated by CRON_ALERTS_ENABLED so it can be silenced. Also rate-limited
    to avoid spam: at most one alert per (customer_id, hour).
    """
    if os.getenv('CRON_ALERTS_ENABLED', 'true').lower() != 'true':
        return

    # Lightweight rate-limit via DB: insert a row, only send if it's the first
    # in the last hour for this customer_id.
    conn = None
    should_send = True
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS stripe_webhook_alerts_sent (
                    id SERIAL PRIMARY KEY,
                    alert_key VARCHAR(200) NOT NULL,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_stripe_webhook_alerts_key
                ON stripe_webhook_alerts_sent(alert_key, sent_at DESC)
            ''')
            cur.execute('''
                SELECT 1 FROM stripe_webhook_alerts_sent
                WHERE alert_key = %s AND sent_at > NOW() - INTERVAL '1 hour'
                LIMIT 1
            ''', (f'unmatched_customer:{customer_id}',))
            if cur.fetchone():
                should_send = False
            else:
                cur.execute('''
                    INSERT INTO stripe_webhook_alerts_sent (alert_key) VALUES (%s)
                ''', (f'unmatched_customer:{customer_id}',))
            conn.commit()
    except Exception as e:
        logger.warning(f"Rate-limit check for unmatched-customer alert failed: {e}")
        if conn:
            try: conn.rollback()
            except Exception: pass
    finally:
        if conn:
            try: conn.close()
            except Exception: pass

    if not should_send:
        return

    try:
        from email_service import send_email
    except Exception as e:
        logger.warning(f"Cannot import email_service for unmatched-customer alert: {e}")
        return

    to = os.getenv('CRON_ALERTS_EMAIL', 'info@soycarlosgonzalez.com')
    env_name = os.getenv('APP_ENV', os.getenv('RAILWAY_ENVIRONMENT_NAME', 'unknown'))

    html = f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
        <h2 style="color:#dc2626;margin-top:0">🚨 Stripe webhook — customer no encontrado</h2>
        <p><strong>Entorno:</strong> {env_name}</p>
        <p>Llegó un webhook de Stripe que NO pudimos asociar a un usuario en nuestra BD,
           ni por <code>stripe_customer_id</code>, ni por <code>subscription_id</code>,
           ni por email del cliente en Stripe.</p>
        <table style="border-collapse:collapse;font-size:14px">
            <tr><td style="padding:6px;border:1px solid #e5e7eb"><strong>customer_id</strong></td>
                <td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{customer_id}</td></tr>
            <tr><td style="padding:6px;border:1px solid #e5e7eb"><strong>subscription_id</strong></td>
                <td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{subscription_id}</td></tr>
            <tr><td style="padding:6px;border:1px solid #e5e7eb"><strong>action</strong></td>
                <td style="padding:6px;border:1px solid #e5e7eb">{action}</td></tr>
        </table>
        <p style="margin-top:18px">Stripe reintentará automáticamente durante 3 días con backoff
           exponencial. Si llega un nuevo evento del mismo customer y nuestro registro de usuario
           ya existe (race resuelta), se procesará. Si persiste el fallo: investigar manualmente
           en el dashboard de Stripe vs. la BD.</p>
        <p style="color:#6b7280;font-size:12px;margin-top:24px">
            Rate-limited: máximo 1 alerta por customer_id por hora. Para silenciar:
            <code>CRON_ALERTS_ENABLED=false</code>.
        </p>
    </body></html>
    """
    try:
        send_email(to, f"[{env_name.upper()}] Stripe webhook customer_not_found", html)
        logger.info(f"📧 Sent unmatched-customer alert to {to}")
    except Exception as e:
        logger.warning(f"Failed to send unmatched-customer alert: {e}")
    
    def _handle_checkout_completed(self, session: dict) -> dict:
        """Maneja checkout.session.completed"""
        try:
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            client_reference_id = session.get('client_reference_id')  # Nuestro user_id
            
            if not client_reference_id:
                logger.warning("⚠️ No client_reference_id in checkout session")
                return {'success': False, 'error': 'No user reference found'}
            
            logger.info(f"💳 Checkout completed - User: {client_reference_id}, Customer: {customer_id}")
            
            # Actualizar usuario con customer_id
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Database connection failed'}
            
            cur = conn.cursor()
            try:
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT FALSE")
            except Exception as _e_addcol:
                logger.warning(f"No se pudo asegurar columna trial_used: {_e_addcol}")
            cur.execute('''
                UPDATE users 
                SET 
                    stripe_customer_id = %s,
                    subscription_id = %s,
                    updated_at = NOW()
                WHERE id = %s
            ''', (customer_id, subscription_id, client_reference_id))
            
            if cur.rowcount == 0:
                logger.warning(f"⚠️ User {client_reference_id} not found for checkout completion")
                return {'success': False, 'error': 'User not found'}
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ User {client_reference_id} updated with Stripe customer {customer_id}")
            return {'success': True, 'message': 'Checkout completed successfully'}
            
        except Exception as e:
            logger.error(f"❌ Error handling checkout completion: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_subscription_created(self, subscription: dict) -> dict:
        """Maneja customer.subscription.created"""
        return self._update_subscription(subscription, 'created')
    
    def _handle_subscription_updated(self, subscription: dict) -> dict:
        """Maneja customer.subscription.updated"""
        return self._update_subscription(subscription, 'updated')
    
    def _handle_subscription_deleted(self, subscription: dict) -> dict:
        """Maneja customer.subscription.deleted"""
        return self._update_subscription(subscription, 'deleted')
    
    def _update_subscription(self, subscription: dict, action: str) -> dict:
        """Actualiza suscripción en base de datos"""
        try:
            customer_id = subscription.get('customer')
            subscription_id = subscription['id']
            status = subscription.get('status')
            current_period_start = subscription.get('current_period_start')
            current_period_end = subscription.get('current_period_end')
            trial_end_ts = subscription.get('trial_end')
            
            # Obtener producto y plan de los items de la suscripción
            items = subscription.get('items', {}).get('data', [])
            if not items:
                logger.warning(f"⚠️ No items in subscription {subscription_id}")
                return {'success': False, 'error': 'No subscription items found'}
            
            price_id = items[0]['price']['id']
            product_id = items[0]['price']['product']
            
            # Determinar plan basado en price_id
            plan = self._get_plan_from_price_id(price_id, product_id)
            
            # Convertir timestamps
            period_start = datetime.fromtimestamp(current_period_start) if current_period_start else None
            period_end = datetime.fromtimestamp(current_period_end) if current_period_end else None
            
            logger.info(f"🔄 Subscription {action} - Customer: {customer_id}, Plan: {plan}, Status: {status}")
            
            # Actualizar en base de datos
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Database connection failed'}
            
            cur = conn.cursor()
            
            if action == 'deleted':
                # Cancelación: volver a free
                cur.execute('''
                    UPDATE users 
                    SET 
                        plan = 'free',
                        current_plan = 'free',
                        billing_status = 'canceled',
                        quota_limit = 0,
                        subscription_id = NULL,
                        current_period_start = NULL,
                        current_period_end = NULL,
                        updated_at = NOW()
                    WHERE stripe_customer_id = %s
                ''', (customer_id,))

                # Opcional: desactivar proyectos del usuario para evitar cron
                try:
                    cur.execute('''
                        UPDATE manual_ai_projects
                        SET is_active = false, updated_at = NOW()
                        WHERE user_id = (SELECT id FROM users WHERE stripe_customer_id = %s)
                    ''', (customer_id,))
                except Exception as _e:
                    logger.warning(f"⚠️ Could not deactivate user's projects on cancellation: {_e}")
            else:
                # Crear/actualizar suscripción
                quota_limit = self.config.get_plan_limits().get(plan, 0)
                billing_status = 'active' if status == 'active' else status
                
                # Si es trialing, marcar explícitamente plan y estado
                is_trialing = status == 'trialing'
                from quota_manager import compute_next_quota_reset_date
                next_reset = compute_next_quota_reset_date(
                    period_start=period_start,
                    period_end=period_end,
                    last_reset=None
                )
                cur.execute('''
                    UPDATE users 
                    SET 
                        plan = %s,
                        current_plan = %s,
                        billing_status = %s,
                        quota_limit = %s,
                        subscription_id = %s,
                        current_period_start = %s,
                        current_period_end = %s,
                        quota_reset_date = COALESCE(quota_reset_date, %s),
                        trial_used = CASE WHEN %s THEN true ELSE trial_used END,
                        updated_at = NOW()
                    WHERE stripe_customer_id = %s
                ''', (plan, plan, billing_status, quota_limit, subscription_id, 
                      period_start, period_end, next_reset, is_trialing, customer_id))
            
            if cur.rowcount == 0:
                logger.warning(f"⚠️ Customer {customer_id} not found for subscription {action}. Trying fallbacks...")
                # Fallback 1: intentar por subscription_id
                try:
                    if action == 'deleted':
                        cur.execute('''
                            UPDATE users 
                            SET 
                                plan = 'free',
                                current_plan = 'free',
                                billing_status = 'canceled',
                                quota_limit = 0,
                                subscription_id = NULL,
                                current_period_start = NULL,
                                current_period_end = NULL,
                                updated_at = NOW()
                            WHERE subscription_id = %s
                        ''', (subscription_id,))
                    else:
                        cur.execute('''
                            UPDATE users 
                            SET 
                                plan = %s,
                                current_plan = %s,
                                billing_status = %s,
                                quota_limit = %s,
                                subscription_id = %s,
                                current_period_start = %s,
                                current_period_end = %s,
                                trial_used = CASE WHEN %s THEN true ELSE trial_used END,
                                updated_at = NOW()
                            WHERE subscription_id = %s
                        ''', (plan, plan, billing_status, quota_limit, subscription_id, 
                              period_start, period_end, is_trialing, subscription_id))
                except Exception as _e_fb1:
                    logger.warning(f"Fallback by subscription_id failed: {_e_fb1}")

                # Fallback 2: intentar por email del Customer en Stripe
                if cur.rowcount == 0:
                    cust_email = None
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        cust_email = getattr(cust, 'email', None) or (cust.get('email') if isinstance(cust, dict) else None)
                    except Exception as _e_fb2:
                        logger.warning(f"Could not retrieve customer {customer_id} from Stripe: {_e_fb2}")
                    if cust_email:
                        try:
                            if action == 'deleted':
                                cur.execute('''
                                    UPDATE users 
                                    SET 
                                        plan = 'free',
                                        current_plan = 'free',
                                        billing_status = 'canceled',
                                        quota_limit = 0,
                                        subscription_id = NULL,
                                        current_period_start = NULL,
                                        current_period_end = NULL,
                                        stripe_customer_id = %s,
                                        updated_at = NOW()
                                    WHERE lower(email) = lower(%s)
                                ''', (customer_id, cust_email))
                            else:
                                cur.execute('''
                                    UPDATE users 
                                    SET 
                                        plan = %s,
                                        current_plan = %s,
                                        billing_status = %s,
                                        quota_limit = %s,
                                        subscription_id = %s,
                                        current_period_start = %s,
                                        current_period_end = %s,
                                        trial_used = CASE WHEN %s THEN true ELSE trial_used END,
                                        stripe_customer_id = %s,
                                        updated_at = NOW()
                                    WHERE lower(email) = lower(%s)
                                ''', (plan, plan, billing_status, quota_limit, subscription_id, 
                                      period_start, period_end, is_trialing, customer_id, cust_email))
                        except Exception as _e_fb3:
                            logger.warning(f"Fallback by customer email failed: {_e_fb3}")

                if cur.rowcount == 0:
                    # Could not find the user via customer_id, subscription_id, or
                    # Stripe-customer-email lookup. Possible causes:
                    #   - Race during signup: webhook arrived before our user row was inserted.
                    #   - Customer was deleted from our DB but Stripe still has them.
                    # We return success=False with a recognizable error code; the route
                    # layer translates this to HTTP 503 so Stripe retries with backoff.
                    # Also email an alert so we don't lose visibility on persistent mismatches.
                    logger.error(
                        f"❌ Webhook customer_not_found: customer_id={customer_id} "
                        f"subscription_id={subscription_id} action={action}"
                    )
                    conn.commit()
                    conn.close()
                    try:
                        _alert_unmatched_customer(customer_id, subscription_id, action)
                    except Exception as _alert_err:
                        logger.warning(f"Could not send unmatched-customer alert: {_alert_err}")
                    return {
                        'success': False,
                        'error': 'customer_not_found',
                        'customer_id': customer_id,
                        'subscription_id': subscription_id,
                        'message': (
                            'No user found for this Stripe customer/subscription. '
                            'Returning 5xx so Stripe retries with backoff in case of '
                            'a signup race condition.'
                        ),
                    }
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Subscription {action} processed successfully for customer {customer_id}")
            
            # Enviar email de inicio de trial (una sola vez) - en inglés usando helpers
            try:
                if status == 'trialing' and action in ['created', 'updated']:
                    conn2 = get_db_connection()
                    if conn2:
                        cur2 = conn2.cursor()
                        # Asegurar columna para idempotencia
                        try:
                            cur2.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_started_email_sent_at TIMESTAMPTZ")
                        except Exception:
                            pass
                        cur2.execute('SELECT email, name, trial_started_email_sent_at FROM users WHERE stripe_customer_id = %s LIMIT 1', (customer_id,))
                        row = cur2.fetchone()
                        if row and (not row.get('trial_started_email_sent_at')):
                            user_email = row['email']
                            trial_end = datetime.fromtimestamp(trial_end_ts) if trial_end_ts else period_end
                            try:
                                send_trial_started_email(user_email, plan, trial_end)
                                cur2.execute('UPDATE users SET trial_started_email_sent_at = NOW() WHERE stripe_customer_id = %s', (customer_id,))
                                conn2.commit()
                                logger.info(f"✉️ Trial-start email enviado a {user_email}")
                            except Exception as _em:
                                logger.warning(f"No se pudo enviar email de trial-start: {_em}")
                        conn2.close()
            except Exception as _e:
                logger.warning(f"Post-processing (trial email) falló: {_e}")
            return {'success': True, 'message': f'Subscription {action} processed'}
            
        except Exception as e:
            logger.error(f"❌ Error handling subscription {action}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_payment_succeeded(self, invoice: dict) -> dict:
        """Maneja invoice.payment.succeeded"""
        try:
            customer_id = invoice.get('customer')
            subscription_id = invoice.get('subscription')

            # Robust period extraction (fixed 2026-05-07):
            # In modern Stripe API the invoice object often does NOT carry
            # period_start/period_end directly at the top level — the period
            # lives inside lines.data[N].period.start/end. The previous code
            # only looked at the top level, so the `if period_start and ...`
            # branch below never ran for ANY user, which is why every paying
            # account in the DB had current_period_end=NULL and quota was
            # never reset via the webhook path.
            period_start = invoice.get('period_start')
            period_end = invoice.get('period_end')
            if not (period_start and period_end):
                try:
                    lines = (invoice.get('lines') or {}).get('data') or []
                    if lines:
                        line_period = (lines[0] or {}).get('period') or {}
                        period_start = period_start or line_period.get('start')
                        period_end = period_end or line_period.get('end')
                except Exception as _e:
                    logger.warning(f"⚠️ Could not extract period from invoice.lines: {_e}")
            # Last-resort fallback: fetch from the subscription via Stripe API.
            # This guarantees we always populate the period if a sub exists.
            if not (period_start and period_end) and subscription_id:
                try:
                    import stripe as _stripe
                    if os.getenv('STRIPE_SECRET_KEY'):
                        _stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
                    sub = _stripe.Subscription.retrieve(subscription_id)
                    period_start = period_start or sub.get('current_period_start')
                    period_end = period_end or sub.get('current_period_end')
                    if not (period_start and period_end):
                        items = (sub.get('items') or {}).get('data') or []
                        if items:
                            period_start = period_start or items[0].get('current_period_start')
                            period_end = period_end or items[0].get('current_period_end')
                    logger.info(f"📡 Fetched period from Stripe API for sub {subscription_id}")
                except Exception as _e:
                    logger.warning(f"⚠️ Stripe API fallback for period failed: {_e}")

            logger.info(
                f"💰 Payment succeeded - Customer: {customer_id}, "
                f"Subscription: {subscription_id}, "
                f"period={period_start}→{period_end}"
            )

            # En pagos exitosos, resetear quota si es inicio de nuevo período
            if period_start and period_end:
                conn = get_db_connection()
                if not conn:
                    return {'success': False, 'error': 'Database connection failed'}
                
                cur = conn.cursor()
                period_start_dt = datetime.fromtimestamp(period_start)
                period_end_dt = datetime.fromtimestamp(period_end)
                from quota_manager import compute_next_quota_reset_date
                next_reset = compute_next_quota_reset_date(
                    period_start=period_start_dt,
                    period_end=period_end_dt,
                    last_reset=None,
                    now=period_start_dt
                )

                cur.execute('''
                    UPDATE users 
                    SET 
                        quota_used = 0,
                        quota_reset_date = %s,
                        billing_status = 'active',
                        current_period_start = %s,
                        current_period_end = %s,
                        updated_at = NOW()
                    WHERE stripe_customer_id = %s
                    RETURNING id
                ''', (next_reset, 
                      period_start_dt,
                      period_end_dt, 
                      customer_id))
                row = cur.fetchone()
                
                conn.commit()
                if row and row.get('id'):
                    resume_quota_pauses_for_user(row['id'])
                conn.close()
                
                logger.info(f"✅ Quota reset for customer {customer_id} - new period")
            
            return {'success': True, 'message': 'Payment succeeded processed'}
            
        except Exception as e:
            logger.error(f"❌ Error handling payment succeeded: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_payment_failed(self, invoice: dict) -> dict:
        """Maneja invoice.payment.failed"""
        try:
            customer_id = invoice.get('customer')
            subscription_id = invoice.get('subscription')
            
            logger.warning(f"💳 Payment failed - Customer: {customer_id}, Subscription: {subscription_id}")
            
            # Marcar como past_due
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Database connection failed'}
            
            cur = conn.cursor()
            cur.execute('''
                UPDATE users 
                SET 
                    billing_status = 'past_due',
                    updated_at = NOW()
                WHERE stripe_customer_id = %s
            ''', (customer_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"⚠️ Customer {customer_id} marked as past_due")
            return {'success': True, 'message': 'Payment failed processed'}
            
        except Exception as e:
            logger.error(f"❌ Error handling payment failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_plan_from_price_id(self, price_id: str, product_id: str) -> str:
        """Determina el plan basado en price_id o product_id"""
        # Primero, probar con mapa inverso (mensual/anual + legacy)
        try:
            price_to_plan = self.config.get_price_to_plan_map()
            if price_id in price_to_plan:
                return price_to_plan[price_id]
        except Exception as _e:
            logger.warning(f"No se pudo resolver price_to_plan map: {_e}")

        # Fallback: mapeo legacy de un único price por plan
        price_ids = self.config.get_plan_price_ids()
        for plan, plan_price_id in price_ids.items():
            if price_id == plan_price_id:
                return plan
        
        # Enterprise (basado en product_id)
        if self.config.is_enterprise_product(product_id):
            return 'enterprise'
        
        # Fallback
        logger.warning(f"⚠️ Unknown price_id {price_id} for product {product_id}")
        return 'free'

# Global instance
webhook_handler = StripeWebhookHandler()

def handle_stripe_webhook(payload: bytes, signature: str) -> dict:
    """Función helper para manejar webhooks"""
    return webhook_handler.handle_webhook(payload, signature)

# Flask route function
def create_webhook_route(app):
    """Crear la ruta de webhook en Flask"""
    
    @app.route('/webhooks/stripe', methods=['POST'])
    def stripe_webhook():
        """Endpoint para recibir webhooks de Stripe.

        HTTP semantics for Stripe (per Stripe docs):
          * 2xx  → event processed, won't retry
          * 4xx  → permanent error, won't retry (use for malformed input)
          * 5xx  → transient error, retries with backoff for up to 3 days

        We map our internal `success` flag and error codes accordingly so
        Stripe's retry behaviour matches our intent (customer-not-found is
        treated as transient because it can be a signup race).
        """
        try:
            payload = request.get_data()
            signature = request.headers.get('Stripe-Signature')

            if not signature:
                logger.error("❌ Missing Stripe signature")
                return jsonify({'error': 'Missing signature'}), 400

            result = handle_stripe_webhook(payload, signature)

            if result.get('success'):
                return jsonify(result), 200

            # Failed: decide retryable vs permanent based on error code
            err_code = result.get('error', '')
            transient_errors = {
                'customer_not_found',     # signup race condition
                'cannot_claim_event',     # DB transient failure
            }
            if err_code in transient_errors:
                # 503 Service Unavailable → Stripe retries with backoff
                return jsonify(result), 503
            # Default: 400 for permanent errors (malformed payload, etc.)
            return jsonify(result), 400

        except Exception as e:
            # Truly unexpected — return 500 so Stripe retries (could be DB
            # outage or transient infra failure). Note the previous code
            # returned 200 here, which silently dropped the event.
            logger.error(f"❌ Webhook endpoint error: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500

    # Endpoint de salud (GET) para pruebas rápidas desde el Dashboard
    @app.route('/webhooks/stripe', methods=['GET'])
    def stripe_webhook_health():
        try:
            return jsonify({'ok': True, 'message': 'Stripe webhook endpoint is up'}), 200
        except Exception:
            return jsonify({'ok': False}), 200

# Testing function
def test_webhook_handler():
    """Función para probar el webhook handler"""
    print("🧪 TESTING STRIPE WEBHOOK HANDLER")
    print("=" * 50)
    
    try:
        handler = StripeWebhookHandler()
        config = handler.config
        
        print(f"🔑 Webhook secret configured: {'Yes' if config.webhook_secret else 'No'}")
        print(f"🌍 Environment: {config.app_env}")
        print(f"🏢 Enterprise product ID: {config.enterprise_product_id}")
        
        price_ids = config.get_plan_price_ids()
        print(f"\n📊 Plan price mappings:")
        for plan, price_id in price_ids.items():
            print(f"   {plan}: {price_id}")
        
        print(f"\n✅ Webhook handler initialized successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing webhook handler: {e}")
        return False

if __name__ == "__main__":
    test_webhook_handler()
