# FASE 1 - Plan de Migración Completo
## ClicandSEO Billing System

### 🎯 **OBJETIVO**
Preparar la base de datos para el sistema de billing con Stripe, usando los valores reales de tus planes.

---

## 📊 **PLANES STRIPE CONFIRMADOS**

| Plan | Precio | RU/mes | Acceso AI Overview | Acceso Manual AI |
|------|--------|---------|-------------------|------------------|
| **Free** | €0.00 | 0 | ❌ No | ❌ No |
| **Basic** | €29.99 | 1,225 | ✅ Sí | ✅ Sí |
| **Premium** | €2 precios | 2,950 | ✅ Sí | ✅ Sí |

---

## 🔄 **SIMPLIFICACIÓN DE ROLES**

### **ANTES:**
- `user` - acceso básico
- `AI User` - acceso a funcionalidades AI (confuso)
- `admin` - acceso completo

### **DESPUÉS:**
- `user` - usuario normal (permisos según plan de pago)
- `admin` - administrador (acceso completo + panel admin)

### **LÓGICA:**
✅ **Rol** = permisos administrativos  
✅ **Plan** = funcionalidades y límites de uso  
❌ Ya no hay "AI User" role - todos los users pueden tener AI según su plan

---

## 🗃️ **MIGRACIÓN DE USUARIOS EXISTENTES**

### **Estrategia propuesta:**
```sql
-- Usuarios actuales → Plan según rol
user        → free     (0 RU, sin AI)
AI User     → basic    (1,225 RU, con AI) + cupón 100% x 2-3 meses
admin       → premium  (2,950 RU, con AI) + interno

-- Simplificación de roles
AI User     → user     (funcionalidades dependen del plan)
admin       → admin    (sin cambios)
```

---

## 🚀 **SCRIPTS DE MIGRACIÓN**

### **1. Preparar BD con campos billing**
```bash
python migrate_billing_phase1.py
```
**Hace:**
- Añade 12 campos nuevos a tabla `users`
- Crea tablas `quota_usage_events` y `subscriptions`
- Backfill: todos → `plan='free'`
- En staging: admins/AI Users → `plan='premium'` (beta testing)

### **2. Simplificar roles**
```bash
python migrate_roles_phase1b.py
```
**Hace:**
- `AI User` → `user`
- Actualiza constraints para permitir solo `user` y `admin`
- Preserva total de usuarios

### **3. Verificar resultado**
```bash
python check_billing_migration.py
```

---

## 📋 **CAMPOS AÑADIDOS A TABLA USERS**

```sql
-- Stripe integration
stripe_customer_id VARCHAR(255)
subscription_id VARCHAR(255)

-- Plan management  
plan VARCHAR(20) DEFAULT 'free'           -- free, basic, premium
current_plan VARCHAR(20) DEFAULT 'free'   -- plan activo ahora
pending_plan VARCHAR(20)                  -- para downgrades (Opción B)
pending_plan_date TIMESTAMPTZ            -- cuándo se activa pending

-- Billing status
billing_status VARCHAR(20) DEFAULT 'active'  -- active, past_due, canceled, beta

-- Quota management
quota_limit INTEGER DEFAULT 0             -- RU permitidas por mes
quota_used INTEGER DEFAULT 0              -- RU consumidas este mes  
quota_reset_date TIMESTAMPTZ             -- cuándo se resetea cuota

-- Stripe periods
current_period_start TIMESTAMPTZ
current_period_end TIMESTAMPTZ
```

---

## 🔍 **ÓRDENES DE EJECUCIÓN**

### **EN STAGING:**
```bash
# 1. Verificar estado actual
python check_billing_migration.py

# 2. Migrar billing
python migrate_billing_phase1.py

# 3. Simplificar roles  
python migrate_roles_phase1b.py

# 4. Verificar resultado final
python check_billing_migration.py
```

### **EN PRODUCCIÓN (Fase 6):**
Los mismos pasos, pero con confirmación adicional de seguridad.

---

## ✅ **RESULTADO ESPERADO**

### **Usuarios en staging después de migración:**
- **4 usuarios totales** (sin pérdidas)
- **Roles:** solo `user` y `admin` 
- **Planes:** 
  - 2 users → `free` (0 RU)
  - 2 admins/AI Users → `premium` (2,950 RU, beta)

### **Usuarios en producción (Fase 6):**
- **35 usuarios totales** (sin pérdidas)
- **Migración sugerida:**
  - `user` → `free` (pueden upgradearse)
  - `AI User` → `basic` + cupón 100% x 3 meses
  - `admin` → `premium` (cuentas internas)

---

## 🎯 **PRÓXIMOS PASOS**

1. ✅ **Fase 1:** Migrar BD (este documento)
2. ⏳ **Fase 2:** Variables de entorno Stripe
3. ⏳ **Fase 3:** Stripe Test + webhooks
4. ⏳ **Fase 4:** Punto único consumo SERP + reglas cuotas
5. ⏳ **Fase 5:** Testing exhaustivo + modo sombra

---

**¿TODO LISTO PARA EJECUTAR? 🚀**
