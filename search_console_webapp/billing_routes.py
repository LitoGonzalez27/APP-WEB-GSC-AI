#!/usr/bin/env python3
"""
Billing Routes - Rutas self-service para checkout y gestión de billing
======================================================================

Implementa el flujo SaaS estándar:
- /billing/checkout/<plan> → Stripe Checkout
- /billing/portal → Customer Portal  
- /billing → Página gestión usuario
- /billing/success → Confirmación post-pago
"""

import os
import stripe
import logging
from datetime import datetime
from flask import request, jsonify, redirect, url_for, render_template, session
from auth import auth_required, get_current_user
from database import get_db_connection
from stripe_config import get_stripe_config

logger = logging.getLogger(__name__)

# Configurar Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def get_price_id_for_plan(plan):
    """Obtener Price ID de Stripe según el plan"""
    price_ids = {
        'basic': os.getenv('PRICE_ID_BASIC'),
        'premium': os.getenv('PRICE_ID_PREMIUM')
    }
    return price_ids.get(plan)

def get_price_id_for_plan_interval(plan, interval):
    """Obtiene el price_id para (plan, interval) usando la config centralizada.
    Mantiene compatibilidad con variables legacy si faltan las nuevas.
    interval: 'monthly' | 'annual'
    """
    try:
        config = get_stripe_config()
        price_id = config.get_price_id(plan, interval)
        if not price_id and interval == 'monthly':
            # Fallback a legacy PRICE_ID_<PLAN>
            legacy = config.get_plan_price_ids().get(plan)
            return legacy
        return price_id
    except Exception as _e:
        logger.warning(f"No se pudo obtener price_id para {plan}/{interval}: {_e}")
        return None

def get_or_create_stripe_customer(user):
    """Obtener o crear customer de Stripe para el usuario"""
    if user.get('stripe_customer_id'):
        return user['stripe_customer_id']
    
    # Crear nuevo customer
    try:
        customer = stripe.Customer.create(
            email=user['email'],
            name=user['name'],
            metadata={
                'user_id': user['id'],
                'app_name': 'clicandseo'
            }
        )
        
        # Guardar customer_id en base de datos
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'UPDATE users SET stripe_customer_id = %s WHERE id = %s',
            (customer.id, user['id'])
        )
        conn.commit()
        conn.close()
        
        return customer.id
        
    except Exception as e:
        logger.error(f"Error creando Stripe customer: {e}")
        return None

def setup_billing_routes(app):
    """Configurar todas las rutas de billing"""
    
    @app.route('/billing/checkout/<plan>')
    @auth_required
    def billing_checkout(plan):
        """Crear Stripe Checkout Session para un plan específico - Con validaciones de seguridad"""
        
        # ✅ SEGURIDAD: Whitelist de planes permitidos (no confiar en query params)
        ALLOWED_PLANS = ['basic', 'premium', 'business']
        if plan not in ALLOWED_PLANS:
            logger.warning(f"Plan inválido intentado: {plan}")
            return redirect('/billing?error=invalid_plan')
        
        # ✅ ENTERPRISE: Bloquear self-serve para Enterprise
        if plan == 'enterprise':
            logger.info("Plan Enterprise detectado - redirigiendo a contacto")
            return redirect('https://clicandseo.com/contact?plan=enterprise')
        
        user = get_current_user()
        if not user:
            return redirect('/login?next=' + request.url)
        
        # ✅ CRÍTICO: Verificar suscripción existente ANTES de crear checkout
        current_plan = user.get('plan', 'free')
        current_status = user.get('billing_status', 'inactive')
        
        # Si ya tiene el mismo plan activo → redirigir al portal
        if current_plan == plan and current_status == 'active':
            logger.info(f"Usuario {user['email']} ya tiene plan {plan} activo - redirigiendo a portal")
            return redirect('/billing/portal?message=already_subscribed')
        
        # Si tiene plan diferente pero activo → usar Customer Portal para upgrade/downgrade
        if current_status == 'active' and current_plan != 'free':
            logger.info(f"Usuario {user['email']} plan {current_plan} → {plan} - usando Customer Portal")
            return redirect(f'/billing/portal?intended_plan={plan}&message=use_portal_for_changes')
        
        # Intervalo mensual/anual (por defecto mensual)
        interval = request.args.get('interval', 'monthly').lower()
        if interval not in ['monthly', 'annual']:
            interval = 'monthly'

        # ✅ Continuar con checkout para usuarios Free o inactive
        price_id = get_price_id_for_plan_interval(plan, interval)
        
        if not price_id:
            logger.error(f"Price ID not configured for plan: {plan}")
            return jsonify({'error': 'Plan not available'}), 500
        
        customer_id = get_or_create_stripe_customer(user)
        if not customer_id:
            return jsonify({'error': 'Could not create customer'}), 500
        
        try:
            # Crear Checkout Session
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                client_reference_id=str(user['id']),  # ✅ CRÍTICO: Para identificar usuario en webhook
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=url_for('billing_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=url_for('billing_cancel', _external=True) + f'?plan={plan}&interval={interval}',
                metadata={
                    'user_id': user['id'],
                    'plan': plan,
                    'interval': interval,
                    'source': request.args.get('source', 'direct')
                }
            )
            
            logger.info(f"Checkout session creada para usuario {user['email']}, plan {plan}")
            return redirect(checkout_session.url)
            
        except Exception as e:
            logger.error(f"Error creando checkout session: {e}")
            return jsonify({'error': 'Could not create checkout session'}), 500
    
    @app.route('/billing/portal')
    @auth_required  
    def billing_portal():
        """Crear Customer Portal Session"""
        
        user = get_current_user()
        
        # Asegurar que existe un customer de Stripe. Para usuarios free es esperable que no exista.
        customer_id = user.get('stripe_customer_id')
        if not customer_id:
            customer_id = get_or_create_stripe_customer(user)
            if not customer_id:
                logger.warning(f"No se pudo crear Stripe customer para {user['email']}")
                return redirect(url_for('billing_page'))
        
        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                # Retorno a Settings > Billing para mejor UX
                return_url=url_for('user_profile', _external=True) + '?tab=billing',
            )
            
            return redirect(portal_session.url)
            
        except Exception as e:
            logger.error(f"Error creando portal session: {e}")
            return jsonify({'error': 'Could not access billing portal'}), 500
    
    @app.route('/billing')
    @auth_required
    def billing_page():
        """Página principal de gestión de billing del usuario"""
        
        user = get_current_user()
        
        # Calcular datos de quota
        quota_percentage = 0
        if user.get('quota_limit', 0) > 0:
            quota_percentage = (user.get('quota_used', 0) / user['quota_limit']) * 100
        
        # Determinar próxima renovación
        next_renewal = None
        if user.get('current_period_end'):
            try:
                from datetime import datetime
                next_renewal = datetime.fromtimestamp(user['current_period_end']).strftime('%Y-%m-%d')
            except:
                pass
        
        return render_template('billing.html', 
                             user=user,
                             quota_percentage=quota_percentage,
                             next_renewal=next_renewal)
    
    @app.route('/billing/success')
    @auth_required
    def billing_success():
        """Página de confirmación post-pago - PROFESIONAL según feedback experto"""
        
        session_id = request.args.get('session_id')
        user = get_current_user()
        
        # ✅ CRÍTICO: Limpiar sesiones de signup tras éxito
        session.pop('signup_plan', None)
        session.pop('signup_source', None)
        
        # ✅ PROFESIONAL: Obtener información completa de transacción
        transaction_data = None
        payment_status = 'processing'  # Default: en proceso
        
        if session_id:
            # ✅ Asegurar que siempre tenemos datos básicos
            transaction_data = {
                'session_id': session_id,
                'transaction_id': session_id,
                'plan': user.get('plan', 'basic'),
                'created_at': datetime.now(),
                'payment_status': 'unknown',
                'amount_total': None,
                'currency': 'EUR',
                'customer_email': user.get('email'),
                'customer_name': user.get('name'),
                'invoice_url': None,
                'current_period_end': None
            }
            try:
                # Obtener checkout session completo
                checkout_session = stripe.checkout.Session.retrieve(session_id, expand=['subscription', 'invoice'])
                
                # Obtener customer para email y detalles
                customer = stripe.Customer.retrieve(checkout_session.customer)
                
                # Determinar estado del pago
                if checkout_session.payment_status == 'paid' and user.get('billing_status') == 'active':
                    payment_status = 'confirmed'
                elif checkout_session.payment_status == 'paid':
                    payment_status = 'webhook_pending'
                elif checkout_session.payment_status == 'unpaid':
                    payment_status = 'failed'
                
                # Actualizar con datos completos de transacción de Stripe
                subscription = checkout_session.subscription
                invoice = checkout_session.invoice
                
                # ✅ Actualizar datos básicos con información real de Stripe
                transaction_data.update({
                    # Identificadores
                    'transaction_id': checkout_session.id,
                    'customer_id': checkout_session.customer,
                    'subscription_id': subscription.id if subscription else None,
                    'invoice_id': invoice.id if invoice else None,
                    
                    # Detalles del pago
                    'amount_total': getattr(checkout_session, 'amount_total', None),
                    'amount_subtotal': getattr(checkout_session, 'amount_subtotal', None),
                    'currency': getattr(checkout_session, 'currency', 'eur').upper(),
                    'payment_status': getattr(checkout_session, 'payment_status', 'unknown'),
                    
                    # Plan y periodicidad
                    'plan': checkout_session.metadata.get('plan', user.get('plan', 'basic')),
                    'source': checkout_session.metadata.get('source', 'direct'),
                    
                    # Fechas
                    'created_at': datetime.fromtimestamp(checkout_session.created) if hasattr(checkout_session, 'created') else datetime.now(),
                    'current_period_start': datetime.fromtimestamp(subscription.current_period_start) if subscription and hasattr(subscription, 'current_period_start') else None,
                    'current_period_end': datetime.fromtimestamp(subscription.current_period_end) if subscription and hasattr(subscription, 'current_period_end') else None,
                    
                    # Customer info
                    'customer_email': getattr(customer, 'email', user.get('email')),
                    'customer_name': checkout_session.customer_details.get('name') if checkout_session.customer_details else getattr(customer, 'name', user.get('name')),
                    
                    # URLs importantes
                    'invoice_url': getattr(invoice, 'hosted_invoice_url', None) if invoice else None,
                    'receipt_url': getattr(invoice, 'invoice_pdf', None) if invoice else None,
                })
                
                logger.info(f"Success page - transacción completa para {user['email']}: {transaction_data['plan']}")
                
            except Exception as e:
                logger.error(f"Error obteniendo datos de transacción: {e}")
                # Fallback con datos básicos seguros
                transaction_data = {
                    'session_id': session_id,
                    'transaction_id': session_id,
                    'plan': user.get('plan', 'basic'),
                    'created_at': datetime.now(),
                    'payment_status': 'unknown',
                    'amount_total': None,
                    'currency': 'EUR',
                    'customer_email': user.get('email'),
                    'customer_name': user.get('name'),
                    'invoice_url': None,
                    'current_period_end': None
                }
        
        # ✅ Estado actual del usuario (para verificación)
        user_status = {
            'plan': user.get('plan', 'free'),
            'billing_status': user.get('billing_status', 'inactive'),
            'quota_limit': user.get('quota_limit', 0),
            'quota_used': user.get('quota_used', 0),
            'subscription_id': user.get('subscription_id'),
            'current_period_end': user.get('current_period_end')
        }
        
        return render_template('billing_success.html', 
                             session_id=session_id,
                             transaction_data=transaction_data,
                             payment_status=payment_status,
                             user_status=user_status,
                             user=user)
    
    @app.route('/billing/cancel')
    @auth_required
    def billing_cancel():
        """Manejo de cancelación en Stripe Checkout - Limpia sesiones pegajosas"""
        
        plan = request.args.get('plan', 'unknown')
        user = get_current_user()
        
        # ✅ CRÍTICO: Limpiar sesiones pegajosas para evitar loops
        session.pop('signup_plan', None)
        session.pop('signup_source', None)
        session.pop('auth_next', None)
        
        logger.info(f"Usuario {user['email']} canceló checkout para plan {plan} - sesiones limpiadas")
        
        # Redirigir a billing con mensaje de cancelación
        return redirect('/billing?message=checkout_cancelled&attempted_plan=' + plan)
    
    @app.route('/api/billing/verify-activation')
    @auth_required
    def verify_plan_activation():
        """API para verificar si el plan del usuario realmente se activó via webhook"""
        
        user = get_current_user()
        
        return jsonify({
            'user_id': user['id'],
            'email': user['email'],
            'plan': user.get('plan', 'free'),
            'billing_status': user.get('billing_status', 'inactive'),
            'quota_limit': user.get('quota_limit', 0),
            'quota_used': user.get('quota_used', 0),
            'subscription_id': user.get('subscription_id'),
            'current_period_end': user.get('current_period_end'),
            'activated': user.get('billing_status') == 'active' and user.get('plan') != 'free'
        })
