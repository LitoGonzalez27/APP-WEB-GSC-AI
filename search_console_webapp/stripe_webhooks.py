#!/usr/bin/env python3
"""
STRIPE WEBHOOKS HANDLER
======================

Maneja los webhooks de Stripe para sincronizar eventos de billing
con nuestra base de datos local.
"""

import os
import config
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
            elif event_type == 'invoice.payment_succeeded':
                result = self._handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
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
            return {'success': False, 'error': 'internal_error'}

    def _handle_checkout_completed(self, session: dict) -> dict:
        """Maneja checkout.session.completed"""
        conn = None
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
            _ensure_users_column(conn, cur, 'trial_used', 'BOOLEAN DEFAULT FALSE')
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
            
            logger.info(f"✅ User {client_reference_id} updated with Stripe customer {customer_id}")
            return {'success': True, 'message': 'Checkout completed successfully'}
            
        except Exception as e:
            logger.error(f"❌ Error handling checkout completion: {e}")
            return {'success': False, 'error': 'internal_error'}
        finally:
            # Cerrar SIEMPRE: antes, con un usuario inexistente o un error, la
            # conexión quedaba abierta con la transacción viva (y con el bloqueo
            # del ALTER TABLE sobre users) hasta el timeout de 15 minutos.
            _close_quietly(conn)
    
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

            # Robust period extraction (fix 2026-05-17):
            # In Stripe API version 2025-06-30.basil onwards, current_period_start/end
            # MOVED from the subscription root to subscription.items[N]. Without this
            # multi-route extraction, _update_subscription wrote NULL to
            # users.current_period_end whenever a customer.subscription.updated event
            # came in on the modern API. Mirrors the existing pattern in
            # _handle_payment_succeeded for invoice events.
            current_period_start = (subscription.get('current_period_start')
                                    or items[0].get('current_period_start'))
            current_period_end = (subscription.get('current_period_end')
                                  or items[0].get('current_period_end'))
            # Last-resort fallback: live fetch via Stripe API in case the event was
            # delivered without period info at any level (rare but possible).
            if not (current_period_start and current_period_end):
                try:
                    import stripe as _stripe
                    if os.getenv('STRIPE_SECRET_KEY'):
                        _stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
                    sub_live = _stripe.Subscription.retrieve(subscription_id)
                    current_period_start = current_period_start or sub_live.get('current_period_start')
                    current_period_end = current_period_end or sub_live.get('current_period_end')
                    if not (current_period_start and current_period_end):
                        items_live = (sub_live.get('items') or {}).get('data') or []
                        if items_live:
                            current_period_start = current_period_start or items_live[0].get('current_period_start')
                            current_period_end = current_period_end or items_live[0].get('current_period_end')
                    logger.info(f"📡 Fetched period from Stripe API fallback for sub {subscription_id}")
                except Exception as _e:
                    logger.warning(f"⚠️ Stripe API period fallback failed for sub {subscription_id}: {_e}")

            # Convertir timestamps
            period_start = datetime.fromtimestamp(current_period_start) if current_period_start else None
            period_end = datetime.fromtimestamp(current_period_end) if current_period_end else None
            
            logger.info(f"🔄 Subscription {action} - Customer: {customer_id}, Plan: {plan}, Status: {status}")
            
            # Actualizar en base de datos
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Database connection failed'}

            try:
                cur = conn.cursor()
                # Filas de USERS afectadas. Antes se miraba cur.rowcount al final,
                # que en una cancelación era el del último UPDATE de proyectos
                # (llm_monitoring_projects): sin proyectos LLM daba 0 y se
                # respondía 503 + alerta de "customer no encontrado" aunque la
                # cancelación ya estuviera hecha.
                users_updated = 0

                if action == 'deleted':
                    # Solo se cancela si la suscripción borrada es la VIGENTE del
                    # usuario (o si no tiene ninguna registrada). Antes se filtraba
                    # solo por cliente: al borrarse una suscripción antigua (p. ej.
                    # tras contratar otro plan con un checkout nuevo) el usuario
                    # pasaba a free aunque tuviera otra suscripción activa.
                    # Los usuarios beta sin suscripción tampoco se cancelan: su
                    # acceso no depende de Stripe. Si el cliente existe pero no hay
                    # nada que cancelar, se responde 200 (no es un cliente perdido).
                    cur.execute('''
                        SELECT id FROM users WHERE stripe_customer_id = %s LIMIT 1
                    ''', (customer_id,))
                    cliente_conocido = cur.fetchone()
                    cur.execute('''
                        SELECT id FROM users
                        WHERE stripe_customer_id = %s
                          AND (subscription_id = %s
                               OR (subscription_id IS NULL AND COALESCE(billing_status, '') <> 'beta'))
                    ''', (customer_id, subscription_id))
                    a_cancelar = cur.fetchone()
                    if cliente_conocido and not a_cancelar:
                        logger.info(
                            f"ℹ️ subscription.deleted {subscription_id} ignorado: no es la "
                            f"suscripción vigente del cliente {customer_id}"
                        )
                        return {'success': True, 'message': 'Deleted subscription is not the current one; ignored'}

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
                          AND (subscription_id = %s
                               OR (subscription_id IS NULL AND COALESCE(billing_status, '') <> 'beta'))
                        RETURNING id
                    ''', (customer_id, subscription_id))
                    cancelados = [r['id'] for r in (cur.fetchall() or [])]
                    users_updated = len(cancelados)

                    # Desactivar los proyectos del usuario en los TRES sistemas para
                    # evitar que sus crons sigan corriendo tras cancelar. (Los crons
                    # ya excluyen a usuarios canceled/free, pero esto es defensa en
                    # profundidad y mantiene el estado coherente entre los 3.)
                    _desactivar_proyectos(cur, cancelados)
                else:
                    # Evento de una suscripción que no es la vigente del cliente y
                    # que no está activa (p. ej. la antigua que Stripe sigue
                    # intentando cobrar tras contratar otra): no pisa la vigente.
                    if status not in ('active', 'trialing') and \
                            _otra_suscripcion_vigente(cur, customer_id, subscription_id):
                        logger.info(
                            f"ℹ️ subscription.{action} {subscription_id} ({status}) ignorado: el cliente "
                            f"{customer_id} tiene otra suscripción vigente"
                        )
                        return {'success': True, 'message': 'Subscription is not the current one; ignored'}
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
                    # COALESCE en el periodo: si el evento llega sin periodo y la API
                    # de Stripe tampoco responde, se conserva el que había en vez de
                    # escribir NULL encima.
                    cur.execute('''
                        UPDATE users 
                        SET 
                            plan = %s,
                            current_plan = %s,
                            billing_status = %s,
                            quota_limit = %s,
                            subscription_id = %s,
                            current_period_start = COALESCE(%s, current_period_start),
                            current_period_end = COALESCE(%s, current_period_end),
                            quota_reset_date = COALESCE(quota_reset_date, %s),
                            trial_used = CASE WHEN %s THEN true ELSE trial_used END,
                            updated_at = NOW()
                        WHERE stripe_customer_id = %s
                    ''', (plan, plan, billing_status, quota_limit, subscription_id, 
                          period_start, period_end, next_reset, is_trialing, customer_id))
                    users_updated = cur.rowcount
                
                if users_updated == 0:
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
                                RETURNING id
                            ''', (subscription_id,))
                            cancelados = [r['id'] for r in (cur.fetchall() or [])]
                            _desactivar_proyectos(cur, cancelados)
                        else:
                            cur.execute('''
                                UPDATE users 
                                SET 
                                    plan = %s,
                                    current_plan = %s,
                                    billing_status = %s,
                                    quota_limit = %s,
                                    subscription_id = %s,
                                    current_period_start = COALESCE(%s, current_period_start),
                                    current_period_end = COALESCE(%s, current_period_end),
                                    trial_used = CASE WHEN %s THEN true ELSE trial_used END,
                                    updated_at = NOW()
                                WHERE subscription_id = %s
                            ''', (plan, plan, billing_status, quota_limit, subscription_id, 
                                  period_start, period_end, is_trialing, subscription_id))
                        users_updated = cur.rowcount if action != 'deleted' else len(cancelados)
                    except Exception as _e_fb1:
                        logger.warning(f"Fallback by subscription_id failed: {_e_fb1}")

                    # Fallback 2: intentar por email del Customer en Stripe
                    if users_updated == 0:
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
                                          AND (stripe_customer_id IS NULL OR stripe_customer_id = %s)
                                          AND (subscription_id = %s
                                               OR (subscription_id IS NULL AND COALESCE(billing_status, '') <> 'beta'))
                                        RETURNING id
                                    ''', (customer_id, cust_email, customer_id, subscription_id))
                                    cancelados = [r['id'] for r in (cur.fetchall() or [])]
                                    _desactivar_proyectos(cur, cancelados)
                                else:
                                    cur.execute('''
                                        UPDATE users 
                                        SET 
                                            plan = %s,
                                            current_plan = %s,
                                            billing_status = %s,
                                            quota_limit = %s,
                                            subscription_id = %s,
                                            current_period_start = COALESCE(%s, current_period_start),
                                            current_period_end = COALESCE(%s, current_period_end),
                                            trial_used = CASE WHEN %s THEN true ELSE trial_used END,
                                            stripe_customer_id = %s,
                                            updated_at = NOW()
                                        WHERE lower(email) = lower(%s)
                                          AND (%s OR subscription_id IS NULL OR subscription_id = %s)
                                    ''', (plan, plan, billing_status, quota_limit, subscription_id, 
                                          period_start, period_end, is_trialing, customer_id, cust_email,
                                          status in ('active', 'trialing'), subscription_id))
                                users_updated = cur.rowcount if action != 'deleted' else len(cancelados)
                                if users_updated == 0 and action != 'deleted' and \
                                        status not in ('active', 'trialing'):
                                    cur.execute('''
                                        SELECT 1 FROM users
                                        WHERE lower(email) = lower(%s)
                                          AND subscription_id IS NOT NULL AND subscription_id <> %s
                                        LIMIT 1
                                    ''', (cust_email, subscription_id))
                                    if cur.fetchone():
                                        logger.info(
                                            f"ℹ️ subscription.{action} {subscription_id} ({status}) ignorado: "
                                            f"el usuario de {customer_id} tiene otra suscripción vigente"
                                        )
                                        return {'success': True, 'message': 'Subscription is not the current one; ignored'}
                            except Exception as _e_fb3:
                                logger.warning(f"Fallback by customer email failed: {_e_fb3}")

                    if users_updated == 0:
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
            finally:
                _close_quietly(conn)
            
            logger.info(f"✅ Subscription {action} processed successfully for customer {customer_id}")

            # Si esta suscripción sustituye a otra (marca puesta en el checkout),
            # se cancela la antigua en Stripe cuando esta queda activa. Nunca
            # rompe el webhook: los fallos se avisan por email.
            if action in ('created', 'updated') and status in _ESTADOS_PAGANDO:
                try:
                    _cancelar_suscripcion_sustituida(subscription)
                except Exception as _e_sust:
                    logger.error(f"❌ Error inesperado al revisar la suscripción sustituida: {_e_sust}", exc_info=True)
            
            # Enviar email de inicio de trial (una sola vez) - en inglés usando helpers
            # Refactor 2026-05-25: try/finally to GUARANTEE conn2.close().
            conn2 = None
            try:
                if status == 'trialing' and action in ['created', 'updated']:
                    conn2 = get_db_connection()
                    if conn2:
                        cur2 = conn2.cursor()
                        # Asegurar columna para idempotencia (sin bloquear users si ya existe)
                        _ensure_users_column(conn2, cur2, 'trial_started_email_sent_at', 'TIMESTAMPTZ')
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
            except Exception as _e:
                logger.warning(f"Post-processing (trial email) falló: {_e}")
            finally:
                if conn2 is not None:
                    try:
                        conn2.close()
                    except Exception:
                        pass
            return {'success': True, 'message': f'Subscription {action} processed'}
            
        except Exception as e:
            logger.error(f"❌ Error handling subscription {action}: {e}")
            return {'success': False, 'error': 'internal_error'}
    
    def _handle_payment_succeeded(self, invoice: dict) -> dict:
        """Maneja invoice.payment_succeeded"""
        conn = None
        try:
            customer_id = invoice.get('customer')
            # En la API 2025-06-30.basil el invoice ya no trae `subscription`
            # en la raíz: vive en parent.subscription_details.subscription.
            subscription_id = _subscription_id_de_factura(invoice)

            # Robust period extraction (fixed 2026-08-07):
            # lines.data[0].period PRIMERO. En una renovación
            # (billing_reason=subscription_cycle) el period_start/end top-level
            # del invoice describe el ciclo ANTERIOR (el que se factura), no el
            # nuevo — el ciclo nuevo va en lines.data[0].period. El orden
            # antiguo (top-level primero) hacía que cada renovación escribiera
            # el current_period_end VIEJO en users, pisando el valor correcto
            # que customer.subscription.updated acababa de escribir, y dejaba
            # quota_reset_date en el pasado (lo recogía el cron al día
            # siguiente con un segundo reset redundante).
            period_start = None
            period_end = None
            try:
                lines = (invoice.get('lines') or {}).get('data') or []
                if lines:
                    line_period = (lines[0] or {}).get('period') or {}
                    period_start = line_period.get('start')
                    period_end = line_period.get('end')
            except Exception as _e:
                logger.warning(f"⚠️ Could not extract period from invoice.lines: {_e}")
            if not (period_start and period_end):
                period_start = period_start or invoice.get('period_start')
                period_end = period_end or invoice.get('period_end')
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
                # La primera factura de una suscripción (subscription_create) nunca
                # es un reintento de la antigua: se aplica siempre. El billing_status
                # de BD no basta para saberlo (un usuario bajado a free desde el
                # admin conserva 'active' y su subscription_id antiguo).
                if invoice.get('billing_reason') != 'subscription_create' and \
                        _otra_suscripcion_vigente(cur, customer_id, subscription_id, solo_si_pagando=True):
                    logger.info(
                        f"ℹ️ invoice.payment_succeeded de {subscription_id} ignorado: el cliente "
                        f"{customer_id} tiene otra suscripción vigente"
                    )
                    return {'success': True, 'message': 'Invoice is not for the current subscription; ignored'}
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
                    logger.info(f"✅ Quota reset for customer {customer_id} - new period")
                else:
                    # El UPDATE no tocó ninguna fila: ningún usuario con ese
                    # stripe_customer_id. El cliente pagó pero NO se le reseteó la
                    # cuota ni se le despausó. Hay que reconciliar manualmente.
                    logger.error(
                        f"🚨 invoice.payment_succeeded sin usuario para "
                        f"stripe_customer_id={customer_id} (sub={subscription_id}): "
                        f"cuota NO reseteada. Revisar reconciliación de cliente."
                    )
            else:
                # No se pudo resolver el período de facturación por ninguna vía
                # (top-level, lines.data, ni la API live de Stripe). Devolvemos
                # success para no forzar reintentos infinitos, pero alertamos:
                # este pago NO reseteó la cuota → posible cliente sin servicio.
                logger.error(
                    f"🚨 invoice.payment_succeeded sin período resoluble para "
                    f"customer={customer_id} (sub={subscription_id}): cuota NO "
                    f"reseteada. Revisar manualmente."
                )

            return {'success': True, 'message': 'Payment succeeded processed'}
            
        except Exception as e:
            logger.error(f"❌ Error handling payment succeeded: {e}")
            return {'success': False, 'error': 'internal_error'}
        finally:
            _close_quietly(conn)
    
    def _handle_payment_failed(self, invoice: dict) -> dict:
        """Maneja invoice.payment_failed"""
        conn = None
        try:
            customer_id = invoice.get('customer')
            subscription_id = _subscription_id_de_factura(invoice)
            
            logger.warning(f"💳 Payment failed - Customer: {customer_id}, Subscription: {subscription_id}")
            
            # Marcar como past_due
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Database connection failed'}
            
            cur = conn.cursor()
            if _otra_suscripcion_vigente(cur, customer_id, subscription_id):
                logger.info(
                    f"ℹ️ invoice.payment_failed de {subscription_id} ignorado: el cliente "
                    f"{customer_id} tiene otra suscripción vigente"
                )
                return {'success': True, 'message': 'Invoice is not for the current subscription; ignored'}
            cur.execute('''
                UPDATE users 
                SET 
                    billing_status = 'past_due',
                    updated_at = NOW()
                WHERE stripe_customer_id = %s
            ''', (customer_id,))
            
            conn.commit()
            
            logger.info(f"⚠️ Customer {customer_id} marked as past_due")
            return {'success': True, 'message': 'Payment failed processed'}
            
        except Exception as e:
            logger.error(f"❌ Error handling payment failed: {e}")
            return {'success': False, 'error': 'internal_error'}
        finally:
            _close_quietly(conn)
    
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


# ---------------------------------------------------------------------------
# Module-level helpers: webhook idempotency tracking + unmatched-customer alert
# (kept as module-level — not class methods — because they're shared
#  infrastructure used both by the class and the route layer.)
# ---------------------------------------------------------------------------

def _close_quietly(conn):
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _otra_suscripcion_vigente(cur, customer_id, subscription_id, solo_si_pagando=False) -> bool:
    """True si el cliente tiene guardada OTRA suscripción distinta de la del evento.

    Un cliente puede tener dos suscripciones a la vez: con la antigua en
    past_due el checkout deja contratar otra, y Stripe sigue reintentando
    cobrar la antigua. Los eventos de la antigua no deben pisar la vigente.

    solo_si_pagando: cuenta solo si la guardada está active/trialing. Lo usa el
    pago correcto: el primer cobro de la suscripción nueva llega a menudo antes
    que el checkout, con la antigua (past_due) aún guardada, y no debe perderse."""
    if not subscription_id or not customer_id:
        return False
    cur.execute(f'''
        SELECT 1 FROM users
        WHERE stripe_customer_id = %s
          AND subscription_id IS NOT NULL AND subscription_id <> %s
          {"AND billing_status IN ('active', 'trialing')" if solo_si_pagando else ""}
        LIMIT 1
    ''', (customer_id, subscription_id))
    return cur.fetchone() is not None


def _subscription_id_de_factura(invoice: dict):
    """En la API 2025-06-30.basil la factura ya no trae `subscription` en la raíz."""
    return (invoice.get('subscription')
            or ((invoice.get('parent') or {}).get('subscription_details') or {}).get('subscription'))


def _desactivar_proyectos(cur, user_ids):
    """Desactiva los proyectos de los usuarios en los tres módulos.

    Un SAVEPOINT por tabla: en Postgres un error dentro de la transacción la
    aborta entera y el commit posterior deshace también la cancelación del
    usuario sin avisar; así un fallo en una tabla solo pierde esa tabla."""
    if not user_ids:
        return
    for _tbl in ('manual_ai_projects', 'ai_mode_projects', 'llm_monitoring_projects'):
        try:
            cur.execute('SAVEPOINT desactivar_proyectos')
            cur.execute(f'''
                UPDATE {_tbl}
                SET is_active = false, updated_at = NOW()
                WHERE user_id = ANY(%s)
            ''', (list(user_ids),))
            cur.execute('RELEASE SAVEPOINT desactivar_proyectos')
        except Exception as _e:
            logger.warning(f"⚠️ Could not deactivate user's {_tbl} on cancellation: {_e}")
            try:
                cur.execute('ROLLBACK TO SAVEPOINT desactivar_proyectos')
            except Exception:
                pass


def _ensure_users_column(conn, cur, column: str, ddl_type: str):
    """Añade la columna a users solo si falta.

    `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` toma un bloqueo exclusivo sobre
    users aunque la columna ya exista; hacerlo en cada webhook bloqueaba la
    tabla (logins, pagos) mientras durase la transacción. Se consulta antes
    information_schema, que no bloquea.
    """
    try:
        cur.execute('''
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = %s
        ''', (column,))
        if cur.fetchone():
            return
        cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} {ddl_type}")
    except Exception as e:
        logger.warning(f"No se pudo asegurar la columna users.{column}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def _ensure_webhook_events_table(cur):
    """Idempotente: crea la tabla la primera vez que se llama.

    Antes lanzaba CREATE INDEX IF NOT EXISTS en cada webhook: toma un bloqueo
    aunque el índice exista y dos claims simultáneos podían acabar en deadlock.
    Ahora se comprueba antes con to_regclass, que no bloquea."""
    cur.execute('''
        SELECT to_regclass('stripe_webhook_events') IS NOT NULL AS tabla,
               to_regclass('idx_stripe_webhook_events_received') IS NOT NULL AS indice
    ''')
    existe = cur.fetchone() or {}
    if existe.get('tabla') and existe.get('indice'):
        return
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


# Errores de un intento anterior que pueden resolverse en un reintento de Stripe
# (el usuario aún no existía, la BD falló...). Un evento que falló por uno de
# ellos se vuelve a procesar; los errores permanentes (payload sin usuario, sin
# items...) se siguen confirmando sin reprocesar.
_REPROCESSABLE_ERRORS = ('customer_not_found', 'internal_error', 'Database connection failed')
# Un evento 'in_progress' más antiguo que esto se considera abandonado (el
# proceso murió a mitad) y se puede reclamar de nuevo.
_STALE_IN_PROGRESS_MINUTES = 10


def _claim_webhook_event(event_id: str, event_type: str):
    """Intenta reclamar la propiedad del evento. Devuelve (already_processed, claim_ok).

    Returns:
      (True, True)  → ya estaba procesado, no hay que hacer nada
      (False, True) → reclamado con éxito (nuevo, o reintento de un fallo pasajero), procede a procesar
      (False, False)→ no se pudo reclamar (BD inaccesible, u otro proceso lo está tratando ahora) — 5xx para que Stripe reintente

    Antes, cualquier fila existente contaba como "ya procesado": el reintento que
    Stripe hace tras un 503 (p. ej. customer_not_found por una carrera en el alta)
    recibía 200 y el evento no se procesaba nunca.
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
        if row is not None:
            conn.commit()
            return False, True

        # Ya existía: se reclama (de forma atómica) si el intento anterior falló
        # por un error pasajero o se quedó colgado en 'in_progress'.
        cur.execute('''
            UPDATE stripe_webhook_events
               SET status = 'in_progress', received_at = NOW(), processed_at = NULL
             WHERE event_id = %s
               AND (
                    (status = 'failed' AND error_message = ANY(%s))
                    OR (status = 'in_progress'
                        AND received_at < NOW() - (%s * INTERVAL '1 minute'))
               )
            RETURNING event_id
        ''', (event_id, list(_REPROCESSABLE_ERRORS), _STALE_IN_PROGRESS_MINUTES))
        reclaimed = cur.fetchone()
        conn.commit()
        if reclaimed is not None:
            logger.info(f"🔁 Webhook event {event_id}: reintento de un intento anterior fallido — se reprocesa")
            return False, True

        cur.execute('SELECT status FROM stripe_webhook_events WHERE event_id = %s', (event_id,))
        current = cur.fetchone() or {}
        if current.get('status') == 'in_progress':
            # Otro proceso lo está tratando ahora mismo: que Stripe reintente más tarde.
            logger.info(f"⏳ Webhook event {event_id} en curso en otro proceso — se pide reintento")
            return False, False
        # 'processed', o 'failed' por un error permanente: confirmar sin reprocesar.
        return True, True
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


# Estados en que la suscripción sustituida se cancela (no está pagando) y en
# que la nueva cuenta como vigente.
_ESTADOS_ANTIGUA_A_CANCELAR = ('past_due', 'unpaid', 'paused')
_ESTADOS_PAGANDO = ('active', 'trialing')


def _cancelar_suscripcion_sustituida(subscription):
    """Cancela en Stripe la suscripción a la que sustituye `subscription`.

    Orden de Carlos (29-sep-2026). Con la suscripción en past_due el checkout
    deja contratar otra, y Stripe seguiría intentando cobrar la antigua: doble
    cobro. El checkout marca la nueva con `metadata.replaces_subscription` (la
    que tenía el usuario). Cuando la nueva queda activa o en prueba, se
    comprueban las dos en vivo y se cancela la antigua solo si sigue sin pagar
    (past_due, unpaid, paused) y es anterior a la nueva. Al cancelar, Stripe
    deja de cobrar automáticamente sus facturas. Solo actúa sobre la marcada:
    nunca sobre otras suscripciones del cliente.

    Se decide una sola vez: tomada la decisión (cancelada, ya cancelada, o la
    antigua sigue pagando y se avisa de posible doble cobro) se quita la marca
    de la nueva y queda `replaced_subscription` como rastro. Si algo falla, la
    marca se conserva (se vuelve a intentar con el siguiente evento de la nueva)
    y se avisa por email. Nunca lanza ni pide reintento del webhook: repetir el
    evento entero pisaría cambios posteriores. Los avisos se envían siempre.
    Interruptor: STRIPE_AUTO_CANCEL_OLD_SUBSCRIPTIONS=false.
    """
    if os.getenv('STRIPE_AUTO_CANCEL_OLD_SUBSCRIPTIONS', 'true').lower() == 'false':
        return
    nueva_id = subscription.get('id')
    antigua_id = (subscription.get('metadata') or {}).get('replaces_subscription')
    if not antigua_id or not nueva_id:
        return
    customer_id = subscription.get('customer')
    if antigua_id == nueva_id:
        _quitar_marca_de_sustitucion(nueva_id, antigua_id)
        return

    try:
        nueva = stripe.Subscription.retrieve(nueva_id)
    except Exception as e:
        logger.error(f"❌ No se pudo consultar la suscripción nueva {nueva_id}: {e}")
        _alertar_suscripciones_antiguas(customer_id, nueva_id, [], [], [(
            nueva_id, f'no se pudo consultar la suscripción nueva (la antigua {antigua_id} sigue sin revisar): {e}')])
        return
    if nueva.get('status') not in _ESTADOS_PAGANDO:
        return  # evento antiguo o reenviado: la nueva ya no está activa
    # La marca vale la de Stripe ahora, no la del evento: un evento viejo
    # reenviado no reabre una decisión ya tomada.
    antigua_id = (nueva.get('metadata') or {}).get('replaces_subscription')
    if not antigua_id:
        return

    try:
        antigua = stripe.Subscription.retrieve(antigua_id)
    except stripe.error.InvalidRequestError as e:
        # No existe en esta cuenta: no se arreglará solo. Se avisa una vez.
        logger.error(f"❌ La suscripción sustituida {antigua_id} no existe: {e}")
        _alertar_suscripciones_antiguas(customer_id, nueva_id, [], [], [(antigua_id, f'no existe en Stripe: {e}')])
        _quitar_marca_de_sustitucion(nueva_id, antigua_id)
        return
    except Exception as e:
        logger.error(f"❌ No se pudo consultar la suscripción sustituida {antigua_id}: {e}")
        _alertar_suscripciones_antiguas(customer_id, nueva_id, [], [], [(antigua_id, f'no se pudo consultar: {e}')])
        return

    estado = antigua.get('status')
    if estado in _ESTADOS_PAGANDO:
        logger.warning(f"⚠️ {antigua_id} ({estado}) sigue pagando además de {nueva_id}: posible doble cobro")
        _alertar_suscripciones_antiguas(customer_id, nueva_id, [], [(antigua_id, estado)], [])
        _quitar_marca_de_sustitucion(nueva_id, antigua_id)
        return
    if estado == 'canceled':
        _antigua_ya_cancelada(antigua, antigua_id, nueva_id, customer_id)
        return
    if estado not in _ESTADOS_ANTIGUA_A_CANCELAR:
        _quitar_marca_de_sustitucion(nueva_id, antigua_id)  # caducada o sin completar
        return
    if (antigua.get('created') or 0) > (nueva.get('created') or 0):
        _alertar_suscripciones_antiguas(customer_id, nueva_id, [], [], [(
            antigua_id, f'{estado}: es más reciente que {nueva_id}; no se cancela, revisar a mano')])
        _quitar_marca_de_sustitucion(nueva_id, antigua_id)
        return

    try:
        stripe.Subscription.cancel(antigua_id, cancellation_details={
            'comment': f'Sustituida por {nueva_id}: cancelación automática de Clicandseo',
        })
    except Exception as e:
        # ¿La canceló a la vez otro evento de la nueva (created y updated en paralelo)?
        try:
            ahora = stripe.Subscription.retrieve(antigua_id)
            if ahora.get('status') == 'canceled':
                _antigua_ya_cancelada(ahora, antigua_id, nueva_id, customer_id)
                return
        except Exception:
            pass
        logger.error(f"❌ No se pudo cancelar la suscripción sustituida {antigua_id}: {e}")
        _alertar_suscripciones_antiguas(customer_id, nueva_id, [], [], [(antigua_id, f'{estado}: {e}')])
        return

    logger.warning(f"🧹 Suscripción {antigua_id} ({estado}) cancelada: sustituida por {nueva_id}")
    _alertar_suscripciones_antiguas(customer_id, nueva_id, [(antigua_id, estado)], [], [])
    _quitar_marca_de_sustitucion(nueva_id, antigua_id)


def _antigua_ya_cancelada(antigua, antigua_id, nueva_id, customer_id):
    """La antigua ya está cancelada. Si la canceló otra suscripción nueva (dos
    checkouts), el cliente puede estar pagando dos: se avisa. Si la canceló esta
    misma o se canceló por otra vía, no hay nada que hacer."""
    comentario = ((antigua.get('cancellation_details') or {}).get('comment') or '')
    if comentario.startswith('Sustituida por ') and nueva_id not in comentario:
        otra = comentario[len('Sustituida por '):].split(':')[0]
        _alertar_suscripciones_antiguas(customer_id, nueva_id, [], [(otra, f'también sustituye a {antigua_id}')], [])
    _quitar_marca_de_sustitucion(nueva_id, antigua_id)


def _quitar_marca_de_sustitucion(nueva_id, antigua_id):
    """Quita la marca de la nueva para no repetir la comprobación en cada evento;
    deja `replaced_subscription` como rastro. Si falla, solo se repite la
    comprobación con el siguiente evento (es idempotente)."""
    try:
        stripe.Subscription.modify(nueva_id, metadata={
            'replaces_subscription': '',
            'replaced_subscription': antigua_id,
        })
    except Exception as e:
        logger.warning(f"⚠️ No se pudo quitar la marca de sustitución de {nueva_id}: {e}")


def _alertar_suscripciones_antiguas(customer_id, subscription_id, canceladas, pagando, fallos):
    """Email al admin con lo que hizo (o no pudo hacer) _cancelar_suscripcion_sustituida.

    Se envía siempre, también con CRON_ALERTS_ENABLED=false: es el registro de
    una acción sobre el dinero de un cliente."""
    try:
        from email_service import send_email
    except Exception as e:
        logger.warning(f"Cannot import email_service for subscription alert: {e}")
        return
    from html import escape

    if fallos:
        asunto = 'Stripe: fallo al cancelar una suscripción antigua'
    elif pagando:
        asunto = 'Stripe: cliente con dos suscripciones pagando (posible doble cobro)'
    else:
        asunto = 'Stripe: suscripción antigua cancelada automáticamente'

    def _filas(titulo, elementos):
        if not elementos:
            return ''
        filas = ''.join(
            f'<tr><td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{escape(str(a))}</td>'
            f'<td style="padding:6px;border:1px solid #e5e7eb">{escape(str(b))}</td></tr>'
            for a, b in elementos
        )
        return f'<h3>{titulo}</h3><table style="border-collapse:collapse;font-size:14px">{filas}</table>'

    to = config.email_alertas()
    env_name = config.etiqueta_entorno()
    html = f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
        <h2 style="margin-top:0">{escape(asunto)}</h2>
        <p><strong>Entorno:</strong> {escape(env_name)}<br>
           <strong>Cliente:</strong> <code>{escape(str(customer_id))}</code><br>
           <strong>Suscripción vigente:</strong> <code>{escape(str(subscription_id))}</code></p>
        {_filas('Cancelada (Stripe deja de cobrar automáticamente sus facturas)', canceladas)}
        {_filas('Sigue pagando: no se ha tocado, revisar en Stripe', pagando)}
        {_filas('No se ha cancelado: revisar y hacerlo a mano en Stripe', fallos)}
        <p style="color:#6b7280;font-size:12px;margin-top:24px">
            Para desactivar la cancelación automática: <code>STRIPE_AUTO_CANCEL_OLD_SUBSCRIPTIONS=false</code>.
        </p>
    </body></html>
    """
    try:
        send_email(to, f"[{env_name.upper()}] {asunto}", html)
    except Exception as e:
        logger.warning(f"Failed to send subscription alert: {e}")


def _alert_unmatched_customer(customer_id: str, subscription_id: str, action: str):
    """Send alert email when a webhook arrives for a customer not in our DB.

    Gated by CRON_ALERTS_ENABLED so it can be silenced. Also rate-limited
    to avoid spam: at most one alert per (customer_id, hour).
    """
    if not config.alertas_cron_activas():
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
                SELECT to_regclass('stripe_webhook_alerts_sent') IS NOT NULL AS tabla,
                       to_regclass('idx_stripe_webhook_alerts_key') IS NOT NULL AS indice
            ''')
            _existe = cur.fetchone() or {}
            # Solo DDL si falta algo: CREATE ... IF NOT EXISTS bloquea aunque exista.
            if not (_existe.get('tabla') and _existe.get('indice')):
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

    to = config.email_alertas()
    env_name = config.etiqueta_entorno()

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
            # Nota: 'internal_error' sale como 400, pero Stripe reintenta cualquier
            # respuesta que no sea 2xx y _claim_webhook_event lo reprocesa.
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
