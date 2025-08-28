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
from flask import request, jsonify, redirect, url_for, render_template, session
from auth import auth_required, get_current_user
from database import get_db_connection

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
        """Crear Stripe Checkout Session para un plan específico"""
        
        if plan not in ['basic', 'premium']:
            return jsonify({'error': 'Invalid plan'}), 400
        
        user = get_current_user()
        price_id = get_price_id_for_plan(plan)
        
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
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=url_for('billing_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=url_for('billing_page', _external=True),
                metadata={
                    'user_id': user['id'],
                    'plan': plan
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
        
        if not user.get('stripe_customer_id'):
            logger.warning(f"Usuario {user['email']} sin stripe_customer_id")
            return redirect(url_for('billing_page'))
        
        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=user['stripe_customer_id'],
                return_url=url_for('billing_page', _external=True),
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
        """Página de confirmación post-pago"""
        
        session_id = request.args.get('session_id')
        
        if session_id:
            try:
                # Verificar session en Stripe
                checkout_session = stripe.checkout.Session.retrieve(session_id)
                plan = checkout_session.metadata.get('plan', 'unknown')
                
                return render_template('billing_success.html', 
                                     session_id=session_id,
                                     plan=plan)
            except Exception as e:
                logger.error(f"Error verificando checkout session: {e}")
        
        return render_template('billing_success.html')
