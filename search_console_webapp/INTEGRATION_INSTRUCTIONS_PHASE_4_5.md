
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
