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
from database import get_db_connection

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
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            logger.info(f"✅ Webhook signature verified - Event: {event['type']}")
            return event
        except ValueError as e:
            logger.error(f"❌ Invalid payload: {e}")
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"❌ Invalid signature: {e}")
            raise ValueError("Invalid signature")
    
    def handle_webhook(self, payload: bytes, signature: str) -> dict:
        """Maneja un webhook de Stripe"""
        try:
            # Verificar firma
            event = self.verify_webhook_signature(payload, signature)
            
            # Procesar evento según tipo
            event_type = event['type']
            event_data = event['data']['object']
            
            logger.info(f"🔄 Processing event: {event_type}")
            
            if event_type == 'checkout.session.completed':
                return self._handle_checkout_completed(event_data)
            elif event_type == 'customer.subscription.created':
                return self._handle_subscription_created(event_data)
            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event_data)
            elif event_type == 'invoice.payment.succeeded':
                return self._handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment.failed':
                return self._handle_payment_failed(event_data)
            else:
                logger.info(f"ℹ️ Unhandled event type: {event_type}")
                return {'success': True, 'message': f'Event {event_type} received but not processed'}
                
        except Exception as e:
            logger.error(f"❌ Error processing webhook: {e}")
            return {'success': False, 'error': str(e)}
    
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
                        updated_at = NOW()
                    WHERE stripe_customer_id = %s
                ''', (plan, plan, billing_status, quota_limit, subscription_id, 
                      period_start, period_end, customer_id))
            
            if cur.rowcount == 0:
                logger.warning(f"⚠️ Customer {customer_id} not found for subscription {action}")
                return {'success': False, 'error': 'Customer not found'}
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Subscription {action} processed successfully for customer {customer_id}")
            return {'success': True, 'message': f'Subscription {action} processed'}
            
        except Exception as e:
            logger.error(f"❌ Error handling subscription {action}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_payment_succeeded(self, invoice: dict) -> dict:
        """Maneja invoice.payment.succeeded"""
        try:
            customer_id = invoice.get('customer')
            subscription_id = invoice.get('subscription')
            period_start = invoice.get('period_start')
            period_end = invoice.get('period_end')
            
            logger.info(f"💰 Payment succeeded - Customer: {customer_id}, Subscription: {subscription_id}")
            
            # En pagos exitosos, resetear quota si es inicio de nuevo período
            if period_start and period_end:
                conn = get_db_connection()
                if not conn:
                    return {'success': False, 'error': 'Database connection failed'}
                
                cur = conn.cursor()
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
                ''', (datetime.fromtimestamp(period_end), 
                      datetime.fromtimestamp(period_start),
                      datetime.fromtimestamp(period_end), 
                      customer_id))
                
                conn.commit()
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
        """Endpoint para recibir webhooks de Stripe"""
        try:
            payload = request.get_data()
            signature = request.headers.get('Stripe-Signature')
            
            if not signature:
                logger.error("❌ Missing Stripe signature")
                return jsonify({'error': 'Missing signature'}), 400
            
            result = handle_stripe_webhook(payload, signature)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"❌ Webhook endpoint error: {e}")
            return jsonify({'error': 'Internal server error'}), 500

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
