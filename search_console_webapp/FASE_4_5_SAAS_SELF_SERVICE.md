# FASE 4.5 - FLUJO SaaS SELF-SERVICE
## Convertir sistema manual a estándar SaaS

### 🎯 **OBJETIVO**
Implementar el flujo SaaS estándar donde usuarios pueden registrarse, pagar y usar el servicio sin intervención manual, conservando la intención de plan con parámetro `next`.

---

## 🔄 **CAMBIOS FUNDAMENTALES**

### **DE SISTEMA MANUAL → SaaS SELF-SERVICE**

| Aspecto | Actual (Manual) | Target (Self-Service) |
|---------|-----------------|----------------------|
| **Activación** | Manual por admin | Automática para Free/Basic/Premium |
| **Control acceso** | Por roles (`AI User`) | Por plan (`basic`, `premium`) |
| **Registro** | Inactivo + esperar admin | Activo + plan `free` automático |
| **Checkout** | No existe | `/billing/checkout/<plan>` |
| **Gestión billing** | Solo admin panel | Usuario + admin panel |
| **Paywalls** | No hay | Integrados en módulos |

---

## 📱 **FLUJO USUARIO ESTÁNDAR**

### **A) CTA "Start Free" en clicandseo.com/pricing**
```
Botón → https://app.clicandseo.com/signup?next=/
Usuario se registra → plan='free' ACTIVO automáticamente
En app: toca AI Overview → paywall con "Upgrade a Basic/Premium"
```

### **B) CTA "Basic - Empieza ahora"**  
```
Botón → https://app.clicandseo.com/login?next=/billing/checkout/basic
Si no tiene cuenta → "Crear cuenta" en misma pantalla
Tras auth → redirige a /billing/checkout/basic
Checkout → crea session y redirige a Stripe
Tras pago → webhook activa plan='basic', quota_limit=1225
```

### **C) CTA "Premium - Empieza ahora"**
```
Botón → https://app.clicandseo.com/login?next=/billing/checkout/premium
Mismo flujo que Basic pero con plan='premium', quota_limit=2950
```

### **D) Usuario ya logueado**
```
Si tiene sesión activa → salta login, va directo a /billing/checkout/<plan>
```

---

## 🛠️ **IMPLEMENTACIÓN TÉCNICA**

### **1. MODIFICAR AUTENTICACIÓN (auth.py)**

#### **A) Soporte parámetro `next`:**
```python
@app.route('/login')
def login_page():
    # Guardar parámetro next en sesión
    next_url = request.args.get('next', '/')
    session['auth_next'] = next_url
    
    if is_user_authenticated():
        return redirect(session.pop('auth_next', '/'))
    
    return render_template('login.html')

@app.route('/auth/callback')  
def auth_callback():
    # Tras autenticación exitosa
    next_url = session.pop('auth_next', '/')
    return redirect(next_url)
```

#### **B) Activación automática self-service:**
```python
def create_user(email, name, password=None, google_id=None, picture=None):
    # Para self-service: activar automáticamente con plan free
    is_active = True  # CAMBIO CRÍTICO
    plan = 'free'     # Plan por defecto
    
    cur.execute('''
        INSERT INTO users (email, name, password_hash, google_id, picture, 
                          role, is_active, plan, quota_limit, quota_used)
        VALUES (%s, %s, %s, %s, %s, 'user', %s, %s, 0, 0)
    ''', (email, name, password_hash, google_id, picture, is_active, plan))
```

### **2. CREAR RUTAS DE BILLING (billing_routes.py)**

#### **A) Rutas de checkout:**
```python
@app.route('/billing/checkout/<plan>')
@auth_required
def billing_checkout(plan):
    # Crear Stripe Checkout Session
    stripe_session = stripe.checkout.Session.create(
        customer=get_or_create_stripe_customer(),
        payment_method_types=['card'],
        line_items=[{
            'price': get_price_id_for_plan(plan),
            'quantity': 1,
        }],
        mode='subscription',
        success_url=url_for('billing_success', _external=True),
        cancel_url=url_for('billing_page', _external=True),
    )
    return redirect(stripe_session.url)

@app.route('/billing/portal')
@auth_required
def billing_portal():
    # Customer Portal Session
    portal_session = stripe.billing_portal.Session.create(
        customer=get_stripe_customer_id(),
        return_url=url_for('billing_page', _external=True),
    )
    return redirect(portal_session.url)

@app.route('/billing')
@auth_required
def billing_page():
    # Página principal de gestión de billing del usuario
    user = get_current_user()
    return render_template('billing.html', user=user)
```

### **3. IMPLEMENTAR PAYWALLS**

#### **A) Modificar AI Overview (app.py):**
```python
@app.route('/api/analyze-ai-overview', methods=['POST'])
@auth_required
def analyze_ai_overview():
    user = get_current_user()
    
    # PAYWALL: Verificar plan
    if user['plan'] == 'free':
        return jsonify({
            'error': 'paywall',
            'message': 'AI Overview requires a paid plan',
            'upgrade_options': ['basic', 'premium']
        }), 402  # Payment Required
    
    # QUOTA: Verificar límites
    if user['quota_used'] >= user['quota_limit']:
        return jsonify({
            'error': 'quota_exceeded', 
            'message': 'You have reached your monthly limit',
            'action_required': 'upgrade'
        }), 429  # Too Many Requests
    
    # Continuar con análisis normal...
```

#### **B) Modificar Manual AI (manual_ai_system.py):**
```python
@manual_ai_bp.route('/dashboard')
@auth_required
def manual_ai_dashboard():
    user = get_current_user()
    
    # PAYWALL: Solo Basic/Premium
    if user['plan'] == 'free':
        return render_template('paywall_manual_ai.html', 
                             upgrade_options=['basic', 'premium'])
    
    return render_template('manual_ai_dashboard.html')
```

### **4. CREAR TEMPLATES DE BILLING**

#### **A) billing.html:**
```html
<!-- Página principal de gestión de billing -->
<div class="billing-container">
  <h1>Manage Your Subscription</h1>
  
  <div class="current-plan">
    <h2>Current Plan: {{ user.plan|title }}</h2>
    <div class="quota-usage">
      <progress value="{{ user.quota_used }}" max="{{ user.quota_limit }}"></progress>
      <span>{{ user.quota_used }}/{{ user.quota_limit }} RU used</span>
    </div>
  </div>
  
  <div class="billing-actions">
    {% if user.plan == 'free' %}
      <a href="/billing/checkout/basic" class="btn btn-primary">Upgrade to Basic</a>
      <a href="/billing/checkout/premium" class="btn btn-primary">Upgrade to Premium</a>
    {% else %}
      <a href="/billing/portal" class="btn btn-secondary">Manage Billing</a>
    {% endif %}
  </div>
</div>
```

#### **B) paywall_modal.html:**
```html
<!-- Modal de paywall para módulos -->
<div class="paywall-modal">
  <h3>🚀 Unlock AI Overview</h3>
  <p>This feature requires a paid plan</p>
  
  <div class="upgrade-options">
    <a href="/billing/checkout/basic" class="plan-card">
      <h4>Basic - €29.99/mo</h4>
      <p>1,225 RU/month</p>
    </a>
    <a href="/billing/checkout/premium" class="plan-card">
      <h4>Premium - €49.99/mo</h4>
      <p>2,950 RU/month</p>
    </a>
  </div>
</div>
```

### **5. MODIFICAR FRONTEND**

#### **A) Integrar paywalls en UI:**
```javascript
// ui-ai-overview.js
async function analyzeAIOverview(keywords, siteUrl) {
  try {
    const response = await fetch('/api/analyze-ai-overview', {
      method: 'POST',
      body: formData
    });
    
    if (response.status === 402) {
      // Paywall - mostrar modal de upgrade
      const data = await response.json();
      showPaywallModal(data.upgrade_options);
      return;
    }
    
    if (response.status === 429) {
      // Quota exceeded - mostrar modal de límite
      const data = await response.json();
      showQuotaExceededModal(data);
      return;
    }
    
    // Continuar análisis normal...
  }
}
```

---

## 📋 **CHECKLIST DE IMPLEMENTACIÓN**

### **BACKEND:**
- [ ] Modificar `auth.py` para soporte `next` parameter
- [ ] Modificar `create_user()` para activación automática
- [ ] Crear `billing_routes.py` con rutas `/billing/*`
- [ ] Implementar paywalls en `app.py` (AI Overview)
- [ ] Implementar paywalls en `manual_ai_system.py`
- [ ] Modificar decoradores para control por plan

### **FRONTEND:**
- [ ] Crear `templates/billing.html`
- [ ] Crear `templates/paywall_modal.html`
- [ ] Modificar `ui-ai-overview.js` para paywalls
- [ ] Modificar `manual-ai-system.js` para paywalls
- [ ] Crear `billing.css` para estilos

### **CONFIGURACIÓN:**
- [ ] Añadir `PRICE_ID_BASIC` y `PRICE_ID_PREMIUM` en Railway
- [ ] Configurar success/cancel URLs en Stripe
- [ ] Crear Customer Portal configuration

### **TESTING:**
- [ ] Test flujo Free → Basic
- [ ] Test flujo Premium → downgrade
- [ ] Test paywalls en ambos módulos
- [ ] Test parámetro `next` funciona
- [ ] Test activación automática

---

## ⚠️ **CONSIDERACIONES IMPORTANTES**

### **1. Backwards Compatibility:**
- Usuarios existentes mantienen activación manual (admin los puede migrar)
- Enterprise users siguen siendo especiales (custom quotas)

### **2. Security:**
- Validar plan en backend, no solo frontend
- Webhooks siguen actualizando planes automáticamente

### **3. UX:**
- Paywalls deben ser claros y helpful
- No perder contexto tras auth con `next`
- Success/error messages consistentes

---

## 🎯 **RESULTADO FINAL**

Tras esta fase tendrás:

✅ **Flujo SaaS estándar** como grandes players  
✅ **Self-service completo** sin intervención manual  
✅ **Paywalls integrados** en todos los módulos  
✅ **Gestión de billing** para usuarios finales  
✅ **Activación automática** para nuevos usuarios  
✅ **Backwards compatibility** con usuarios existentes  

**¡Sistema listo para escalar sin intervención manual!** 🚀
