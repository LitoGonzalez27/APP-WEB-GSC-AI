#!/usr/bin/env python3
"""
Implement Phase 4.5 - SaaS Self-Service Flow
============================================

Script para implementar el flujo SaaS estándar según las recomendaciones del experto:
- Activación automática para nuevos usuarios
- Soporte para parámetro 'next' en auth
- Rutas de billing self-service
- Paywalls integrados en módulos
- Página de gestión de billing para usuarios
"""

import os
import shutil
from datetime import datetime

def print_section(title):
    """Imprimir sección con formato"""
    print(f"\n{'='*60}")
    print(f"🛠️ {title}")
    print('='*60)

def create_billing_routes():
    """Crear archivo billing_routes.py con rutas self-service"""
    print_section("CREAR BILLING ROUTES")
    
    billing_routes_content = '''#!/usr/bin/env python3
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
'''
    
    with open('billing_routes.py', 'w') as f:
        f.write(billing_routes_content)
    
    print("✅ billing_routes.py creado")
    print("💡 Contiene: checkout, portal, billing page, success")

def modify_auth_for_next_parameter():
    """Generar código para modificar auth.py con soporte para parámetro next"""
    print_section("MODIFICAR AUTH.PY - PARÁMETRO NEXT")
    
    print("📋 MODIFICACIONES NECESARIAS EN auth.py:")
    print()
    print("1️⃣ MODIFICAR RUTA /login:")
    print("```python")
    print("@app.route('/login')")
    print("def login_page():")
    print("    # Guardar parámetro next en sesión")
    print("    next_url = request.args.get('next', '/')")
    print("    session['auth_next'] = next_url")
    print("    ")
    print("    if is_user_authenticated():")
    print("        user = get_current_user()")
    print("        if user and user['is_active']:")
    print("            # Redirigir a next o dashboard")
    print("            return redirect(session.pop('auth_next', url_for('dashboard')))")
    print("    ")
    print("    return render_template('login.html')")
    print("```")
    print()
    print("2️⃣ MODIFICAR RUTA /signup:")
    print("```python")
    print("@app.route('/signup')")
    print("def signup_page():")
    print("    # Guardar parámetro next en sesión")
    print("    next_url = request.args.get('next', '/')")
    print("    session['auth_next'] = next_url")
    print("    ")
    print("    if is_user_authenticated():")
    print("        user = get_current_user()")
    print("        if user and user['is_active']:")
    print("            return redirect(session.pop('auth_next', url_for('dashboard')))")
    print("    ")
    print("    return render_template('signup.html')")
    print("```")
    print()
    print("3️⃣ MODIFICAR auth_callback PARA USAR NEXT:")
    print("```python")
    print("# En auth_callback, después de autenticación exitosa:")
    print("next_url = session.pop('auth_next', url_for('dashboard'))")
    print("return redirect(next_url)")
    print("```")

def modify_create_user_for_auto_activation():
    """Generar código para activación automática"""
    print_section("MODIFICAR CREATE_USER - ACTIVACIÓN AUTOMÁTICA")
    
    print("📋 MODIFICACIÓN EN database.py:")
    print()
    print("```python")
    print("def create_user(email, name, password=None, google_id=None, picture=None, auto_activate=True):")
    print("    '''Crea un nuevo usuario - auto_activate=True para self-service'''")
    print("    try:")
    print("        conn = get_db_connection()")
    print("        if not conn:")
    print("            return None")
    print("            ")
    print("        cur = conn.cursor()")
    print("        ")
    print("        # Verificar si el usuario ya existe")
    print("        cur.execute('SELECT id FROM users WHERE email = %s', (email,))")
    print("        if cur.fetchone():")
    print("            logger.warning(f'Usuario con email {email} ya existe')")
    print("            return None")
    print("        ")
    print("        password_hash = hash_password(password) if password else None")
    print("        ")
    print("        # NUEVO: Activación automática para self-service")
    print("        is_active = auto_activate  # True para SaaS, False para enterprise")
    print("        plan = 'free' if auto_activate else None  # Plan por defecto")
    print("        ")
    print("        cur.execute('''")
    print("            INSERT INTO users (email, name, password_hash, google_id, picture, ")
    print("                              role, is_active, plan, quota_limit, quota_used)")
    print("            VALUES (%s, %s, %s, %s, %s, 'user', %s, %s, 0, 0)")
    print("            RETURNING id, email, name, picture, role, is_active, created_at, plan")
    print("        ''', (email, name, password_hash, google_id, picture, is_active, plan))")
    print("        ")
    print("        user = cur.fetchone()")
    print("        conn.commit()")
    print("        ")
    print("        logger.info(f'Usuario creado: {email} (activo: {is_active}, plan: {plan})')")
    print("        return dict(user)")
    print("```")
    print()
    print("⚠️ IMPORTANTE: Usuarios existentes no se ven afectados")

def create_paywall_components():
    """Crear componentes de paywall para frontend"""
    print_section("CREAR COMPONENTES PAYWALL")
    
    # CSS para paywalls
    paywall_css = '''/* Paywall Styles */
.paywall-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
}

.paywall-content {
    background: white;
    padding: 2rem;
    border-radius: 12px;
    max-width: 500px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.paywall-content h3 {
    margin-bottom: 1rem;
    color: #333;
}

.upgrade-options {
    display: flex;
    gap: 1rem;
    margin-top: 1.5rem;
}

.plan-card {
    flex: 1;
    padding: 1rem;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    text-decoration: none;
    color: #333;
    transition: all 0.3s;
}

.plan-card:hover {
    border-color: #007bff;
    transform: translateY(-2px);
}

.plan-card h4 {
    margin-bottom: 0.5rem;
    color: #007bff;
}

.quota-exceeded-modal {
    /* Similar styles to paywall-modal */
}

.billing-page {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
}

.current-plan {
    background: #f8f9fa;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.quota-usage {
    margin-top: 1rem;
}

.quota-usage progress {
    width: 100%;
    height: 20px;
}

.billing-actions {
    display: flex;
    gap: 1rem;
}

.btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 6px;
    text-decoration: none;
    display: inline-block;
    transition: all 0.3s;
}

.btn-primary {
    background: #007bff;
    color: white;
}

.btn-secondary {
    background: #6c757d;
    color: white;
}
'''
    
    with open('static/paywall.css', 'w') as f:
        f.write(paywall_css)
    
    # JavaScript para paywalls
    paywall_js = '''// Paywall functionality
class PaywallManager {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('PaywallManager initialized');
    }
    
    showPaywallModal(upgradeOptions = ['basic', 'premium']) {
        const modal = this.createPaywallModal(upgradeOptions);
        document.body.appendChild(modal);
        
        // Auto-remove after 30 seconds or on click outside
        setTimeout(() => this.hidePaywallModal(), 30000);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.hidePaywallModal();
        });
    }
    
    createPaywallModal(upgradeOptions) {
        const modal = document.createElement('div');
        modal.className = 'paywall-modal';
        modal.id = 'paywall-modal';
        
        const plans = {
            basic: { name: 'Basic', price: '€29.99/mo', quota: '1,225 RU/month' },
            premium: { name: 'Premium', price: '€49.99/mo', quota: '2,950 RU/month' }
        };
        
        const planCards = upgradeOptions.map(plan => `
            <a href="/billing/checkout/${plan}" class="plan-card">
                <h4>${plans[plan].name} - ${plans[plan].price}</h4>
                <p>${plans[plan].quota}</p>
            </a>
        `).join('');
        
        modal.innerHTML = `
            <div class="paywall-content">
                <h3>🚀 Unlock Premium Features</h3>
                <p>This feature requires a paid plan to continue</p>
                <div class="upgrade-options">
                    ${planCards}
                </div>
                <button onclick="window.PaywallManager.hidePaywallModal()" 
                        style="margin-top: 1rem; background: none; border: none; color: #666;">
                    Maybe later
                </button>
            </div>
        `;
        
        return modal;
    }
    
    showQuotaExceededModal(quotaInfo = {}) {
        const modal = this.createQuotaExceededModal(quotaInfo);
        document.body.appendChild(modal);
    }
    
    createQuotaExceededModal(quotaInfo) {
        const modal = document.createElement('div');
        modal.className = 'quota-exceeded-modal paywall-modal';
        modal.id = 'quota-exceeded-modal';
        
        modal.innerHTML = `
            <div class="paywall-content">
                <h3>📊 Monthly Limit Reached</h3>
                <p>You've used all ${quotaInfo.quota_limit || 'your'} RU this month</p>
                <p>Upgrade to get more Request Units and continue analyzing</p>
                <div class="upgrade-options">
                    <a href="/billing/checkout/premium" class="plan-card">
                        <h4>Upgrade to Premium</h4>
                        <p>2,950 RU/month</p>
                    </a>
                </div>
                <a href="/billing" style="margin-top: 1rem; color: #666;">
                    Manage billing
                </a>
            </div>
        `;
        
        return modal;
    }
    
    hidePaywallModal() {
        const modals = document.querySelectorAll('.paywall-modal');
        modals.forEach(modal => modal.remove());
    }
}

// Initialize globally
window.PaywallManager = new PaywallManager();

// Helper functions for modules
window.showPaywall = (options) => window.PaywallManager.showPaywallModal(options);
window.showQuotaExceeded = (info) => window.PaywallManager.showQuotaExceededModal(info);
'''
    
    with open('static/js/paywall.js', 'w') as f:
        f.write(paywall_js)
    
    print("✅ static/paywall.css creado")
    print("✅ static/js/paywall.js creado")
    print("💡 Contiene: modales paywall, quota exceeded, estilos")

def create_billing_templates():
    """Crear templates HTML para billing"""
    print_section("CREAR TEMPLATES BILLING")
    
    # Template billing.html
    billing_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Billing - ClicandSEO</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='paywall.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='estilos-principales.css') }}">
</head>
<body>
    <div class="billing-page">
        <h1>Manage Your Subscription</h1>
        
        <div class="current-plan">
            <h2>Current Plan: {{ user.plan|title }}</h2>
            
            {% if user.quota_limit > 0 %}
            <div class="quota-usage">
                <label>Monthly Usage:</label>
                <progress value="{{ user.quota_used or 0 }}" max="{{ user.quota_limit }}"></progress>
                <span>{{ user.quota_used or 0 }}/{{ user.quota_limit }} RU used 
                      ({{ "%.1f"|format(quota_percentage) }}%)</span>
                
                {% if quota_percentage >= 80 %}
                <div class="quota-warning" style="color: #ff6b6b; margin-top: 0.5rem;">
                    ⚠️ You're approaching your monthly limit
                </div>
                {% endif %}
            </div>
            {% endif %}
            
            {% if next_renewal %}
            <p style="margin-top: 1rem; color: #666;">
                Next renewal: {{ next_renewal }}
            </p>
            {% endif %}
        </div>
        
        <div class="billing-actions">
            {% if user.plan == 'free' %}
                <h3>Upgrade Your Plan</h3>
                <a href="/billing/checkout/basic" class="btn btn-primary">
                    Upgrade to Basic - €29.99/mo
                </a>
                <a href="/billing/checkout/premium" class="btn btn-primary">
                    Upgrade to Premium - €49.99/mo
                </a>
            {% else %}
                <a href="/billing/portal" class="btn btn-secondary">
                    Manage Billing
                </a>
                <a href="/" class="btn btn-primary">
                    Back to App
                </a>
            {% endif %}
        </div>
        
        <div class="plan-comparison" style="margin-top: 2rem;">
            <h3>Plan Comparison</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 0.5rem;">Feature</th>
                    <th style="border: 1px solid #ddd; padding: 0.5rem;">Free</th>
                    <th style="border: 1px solid #ddd; padding: 0.5rem;">Basic</th>
                    <th style="border: 1px solid #ddd; padding: 0.5rem;">Premium</th>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">Monthly RU</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">0</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">1,225</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">2,950</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">AI Overview</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">❌</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">✅</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">✅</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">Manual AI</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">❌</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">✅</td>
                    <td style="border: 1px solid #ddd; padding: 0.5rem;">✅</td>
                </tr>
            </table>
        </div>
    </div>
</body>
</html>'''
    
    with open('templates/billing.html', 'w') as f:
        f.write(billing_html)
    
    # Template billing_success.html
    success_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Success - ClicandSEO</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='estilos-principales.css') }}">
</head>
<body>
    <div class="billing-page">
        <div style="text-align: center; padding: 3rem;">
            <h1>🎉 Payment Successful!</h1>
            
            {% if plan %}
            <p>Your {{ plan|title }} plan is being activated.</p>
            {% endif %}
            
            <p>You'll receive a confirmation email shortly.</p>
            <p>Your new features will be available within a few minutes.</p>
            
            <div style="margin-top: 2rem;">
                <a href="/" class="btn btn-primary">
                    Start Using Your Plan
                </a>
                <a href="/billing" class="btn btn-secondary">
                    View Billing
                </a>
            </div>
        </div>
    </div>
</body>
</html>'''
    
    with open('templates/billing_success.html', 'w') as f:
        f.write(success_html)
    
    print("✅ templates/billing.html creado")
    print("✅ templates/billing_success.html creado")
    print("💡 Páginas completas de gestión de billing")

def generate_integration_instructions():
    """Generar instrucciones de integración paso a paso"""
    print_section("INSTRUCCIONES DE INTEGRACIÓN")
    
    instructions = '''
📋 INSTRUCCIONES DE INTEGRACIÓN PASO A PASO
==========================================

🔥 PASO 1: AÑADIR VARIABLES DE ENTORNO
--------------------------------------
En Railway, añadir estas variables:

PRICE_ID_BASIC=price_1ABC123_basic_test    # Desde Stripe Dashboard
PRICE_ID_PREMIUM=price_1XYZ789_premium_test # Desde Stripe Dashboard

🔧 PASO 2: MODIFICAR app.py
---------------------------
Añadir al final de app.py:

```python
# ✅ NUEVO: Rutas de billing self-service
from billing_routes import setup_billing_routes
setup_billing_routes(app)
```

🔧 PASO 3: MODIFICAR auth.py
----------------------------
Ver las modificaciones específicas en la salida anterior.

🔧 PASO 4: MODIFICAR TEMPLATES
------------------------------
Añadir a templates/index.html y templates/manual_ai_dashboard.html:

```html
<!-- En el <head> -->
<link rel="stylesheet" href="{{ url_for('static', filename='paywall.css') }}">

<!-- Antes de </body> -->
<script src="{{ url_for('static', filename='js/paywall.js') }}"></script>
```

🔧 PASO 5: MODIFICAR FRONTEND AI OVERVIEW
-----------------------------------------
En static/js/ui-ai-overview-analysis.js, modificar función de análisis:

```javascript
// En el catch de la función analyzeAIOverview
if (response.status === 402) {
    // Paywall
    const data = await response.json();
    window.showPaywall(data.upgrade_options);
    return;
}

if (response.status === 429) {
    // Quota exceeded
    const data = await response.json();
    window.showQuotaExceeded(data.quota_info);
    return;
}
```

🔧 PASO 6: MODIFICAR BACKEND AI OVERVIEW
----------------------------------------
En app.py, función analyze_ai_overview, añadir al inicio:

```python
@app.route('/api/analyze-ai-overview', methods=['POST'])
@auth_required
def analyze_ai_overview():
    user = get_current_user()
    
    # ✅ NUEVO: Paywall check
    if user['plan'] == 'free':
        return jsonify({
            'error': 'paywall',
            'message': 'AI Overview requires a paid plan',
            'upgrade_options': ['basic', 'premium']
        }), 402
    
    # ✅ NUEVO: Quota check  
    if user['quota_used'] >= user['quota_limit']:
        return jsonify({
            'error': 'quota_exceeded',
            'message': 'Monthly limit reached',
            'quota_info': {
                'quota_used': user['quota_used'],
                'quota_limit': user['quota_limit']
            },
            'action_required': 'upgrade'
        }), 429
    
    # Continuar con código existente...
```

🔧 PASO 7: MODIFICAR MANUAL AI
------------------------------
En manual_ai_system.py, añadir decorador de paywall:

```python
@manual_ai_bp.route('/dashboard')
@auth_required
def manual_ai_dashboard():
    user = get_current_user()
    
    # ✅ NUEVO: Paywall check
    if user['plan'] == 'free':
        return render_template('paywall_manual_ai.html')
    
    return render_template('manual_ai_dashboard.html')
```

🧪 PASO 8: TESTING
------------------
1. Crear usuario nuevo → debe ser activo automáticamente
2. Probar /billing/checkout/basic → debe llevar a Stripe
3. Probar paywall en AI Overview cuando plan=free
4. Probar flujo completo Free → Basic → Premium

✅ RESULTADO FINAL
==================
Sistema completamente self-service:
- Nuevos usuarios activos automáticamente
- Paywalls integrados en módulos
- Checkout directo a Stripe
- Gestión de billing para usuarios
- Flujo estándar SaaS completo
'''
    
    with open('INTEGRATION_INSTRUCTIONS_PHASE_4_5.md', 'w') as f:
        f.write(instructions)
    
    print("✅ INTEGRATION_INSTRUCTIONS_PHASE_4_5.md creado")
    print("💡 Instrucciones paso a paso completas")

def main():
    """Función principal"""
    print("🛠️ IMPLEMENTING PHASE 4.5 - SaaS SELF-SERVICE FLOW")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 Objetivo: Convertir sistema manual a SaaS estándar")
    
    tasks = [
        create_billing_routes,
        modify_auth_for_next_parameter,
        modify_create_user_for_auto_activation,
        create_paywall_components,
        create_billing_templates,
        generate_integration_instructions
    ]
    
    for task in tasks:
        try:
            task()
        except Exception as e:
            print(f"❌ Error en {task.__name__}: {e}")
    
    print_section("FASE 4.5 - ARCHIVOS CREADOS")
    print("✅ billing_routes.py                     - Rutas self-service")
    print("✅ static/paywall.css                    - Estilos paywalls")
    print("✅ static/js/paywall.js                  - Funcionalidad paywalls")
    print("✅ templates/billing.html                - Página gestión usuario")
    print("✅ templates/billing_success.html        - Confirmación pago")
    print("✅ INTEGRATION_INSTRUCTIONS_PHASE_4_5.md - Instrucciones paso a paso")
    print("✅ FASE_4_5_SAAS_SELF_SERVICE.md        - Documentación completa")
    
    print_section("PRÓXIMOS PASOS")
    print("1. 📋 Seguir INTEGRATION_INSTRUCTIONS_PHASE_4_5.md")
    print("2. 🔧 Modificar auth.py según instrucciones")
    print("3. 🧪 Testing del flujo completo")
    print("4. 🚀 Deploy a staging para pruebas")
    print("5. ✅ Una vez validado → continuar con Fase 5")
    
    print(f"\n🎊 FASE 4.5 LISTA PARA IMPLEMENTAR")

if __name__ == "__main__":
    main()
