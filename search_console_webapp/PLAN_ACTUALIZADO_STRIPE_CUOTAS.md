# Implementación Stripe + Cuotas ClicandSEO (PLAN ACTUALIZADO)

**Manual paso a paso, por fases, para poner en marcha pagos y límites por peticiones a la SERP API sin perder usuarios.**

---

## Resumen ejecutivo

ClicandSEO adoptará un modelo freemium con **cuatro planes**: 
- **Free** (0€, 0 RU/mes) - Sin acceso AI
- **Basic** (29,99€, 1.225 RU/mes) - Acceso completo  
- **Premium** (59,99€, 2.950 RU/mes) - Acceso completo
- **Enterprise** (Custom, Custom RU) - Contacto personalizado

El acceso a AI Overview y Manual AI Overview estará bloqueado en Free y habilitado en Basic/Premium/Enterprise hasta agotar cuotas. Se trabajará con dos entornos separados (Staging y Producción).

---

## **✅ Fase 0 — Pre-flight y seguridad (COMPLETADA)**

**Objetivo**: dejarlo todo listo para que los cambios sean seguros y reversibles.

### Completado:
- ✅ **APP_ENV=staging** configurado en Railway
- ✅ **Bases de datos separadas** confirmadas (Staging ≠ Producción)
- ✅ **Mensajes UX** definidos en inglés para soft-limit (80%) y bloqueo (100%)
- ✅ **Política de downgrade**: aplica nuevo límite en el próximo ciclo de facturación (Option B)

### Pendiente:
- ⏳ **Rotación de credenciales** si alguna vez se compartieron en texto

**🎯 Hito**: entornos y políticas claras; seguridad de base confirmada.

---

## **✅ Fase 1 — Preparar la base de datos (COMPLETADA)**

**Objetivo**: añadir los campos necesarios para planes y cuotas sin tocar datos existentes.

### Completado:
- ✅ **Campos añadidos** en tabla users:
  - `stripe_customer_id`, `plan`, `billing_status`
  - `quota_limit`, `quota_used`, `quota_reset_date` 
  - `subscription_id`, `current_period_start`, `current_period_end`
  - `current_plan`, `pending_plan`, `pending_plan_date`

- ✅ **Tabla quota_usage_events** creada para tracking
- ✅ **Tabla subscriptions** creada para histórico  
- ✅ **Backfill inicial**: todos en plan=free; betas con quota_limit=2950
- ✅ **Verificación**: 4 usuarios preservados sin pérdida de datos
- ✅ **Roles simplificados**: admin/user (eliminado "AI User")

**🎯 Hito**: BD de Staging lista con campos nuevos y sin pérdida de usuarios.

---

## **✅ Fase 1B — Enterprise + Admin Panel (COMPLETADA)** ⭐ **NUEVA**

**Objetivo**: extender el sistema con funcionalidad Enterprise y visibilidad admin.

### Completado:
- ✅ **Plan Enterprise** añadido con custom quotas:
  - `custom_quota_limit`, `custom_quota_notes`
  - `custom_quota_assigned_by`, `custom_quota_assigned_date`
  
- ✅ **Quota Manager** central implementado:
  - `get_user_effective_quota_limit()` - Prioriza custom sobre estándar
  - `get_user_quota_status()` - Estado completo de quota
  - `get_user_access_permissions()` - Permisos por plan

- ✅ **Admin Panel** actualizado:
  - Nueva columna "Plan & Quota" en `/admin/users`
  - Badges visuales por plan (Free, Basic, Premium, Enterprise)
  - Funciones backend: `assign_custom_quota()`, `remove_custom_quota()`

- ✅ **Testing Enterprise** funcional:
  - Usuario c.gonzalez@koomori.com con 5000 RU custom
  - Badge púrpura "Enterprise" visible

**🎯 Hito**: Sistema Enterprise operativo y admin panel con visibilidad completa.

---

## **⏳ Fase 2 — Configurar entornos y variables (EN PROGRESO)**

**Objetivo**: separar claramente Staging (Test) y Producción (Live) y activar flags de control.

### Por hacer:
- 🔄 **En Railway > Staging > Variables**:
  - `STRIPE_SECRET_KEY` (test)
  - `STRIPE_PUBLISHABLE_KEY` (test)
  - `STRIPE_WEBHOOK_SECRET` (staging)
  - `PRICE_ID_FREE/BASIC/PREMIUM` (test)
  - `CUSTOMER_PORTAL_RETURN_URL` (staging)

- 🔄 **En Railway > Producción > Variables**: 
  - Mismo set con valores live
  - `APP_ENV=production`

- 🔄 **Flags de control**:
  - `BILLING_ENABLED=false` (pagos apagados)
  - `ENFORCE_QUOTAS=false` (límites apagados)  
  - `AIO_MODULE_ENABLED=true`

- 🔄 **Variables de experiencia**:
  - `QUOTA_SOFT_LIMIT_PCT=80`
  - `QUOTA_GRACE_PERIOD_HOURS=24`

**🎯 Hito**: entornos aislados y controlables por flags.

---

## **📋 Fases 3-9 (SIN CAMBIOS)**

### Fase 3 — Stripe en modo Test (Staging)
- Productos y Precios (Free, Basic, Premium)
- Checkout y Customer Portal
- Webhooks para eventos billing
- Test Clocks para pruebas temporales

### Fase 4 — Reglas de acceso y control de cuotas (Staging)  
- Integrar Quota Manager con SERP API
- Punto único de consumo RU
- Bloqueos por cuota con mensajes UX

### Fase 5 — Pruebas completas y 'modo sombra' (Staging)
- Tests end-to-end de todos los escenarios
- Modo sombra: billing ON, quotas OFF

### Fase 6 — Preparar Producción (Live, sin encender nada)
- Backup completo
- Stripe Live setup
- Migración BD Production

### Fase 7 — Encendido gradual en Producción
- BILLING_ENABLED=true por cohortes
- ENFORCE_QUOTAS=true gradual

### Fase 8 — Go-Live total y operación diaria
- 100% usuarios con quotas activas
- Métricas y alertas operativas

### Fase 9 — Migración de usuarios existentes (opcional)
- Asignación de planes históricos
- Comunicación a betas y transición

---

## **📊 Matriz de Planes Actualizada**

| Plan | Precio/mes | Límite RU | AI Overview | Manual AI | Método |
|------|------------|-----------|-------------|-----------|---------|
| **Free** | 0€ | 0 | ❌ | ❌ | N/A |
| **Basic** | 29,99€ | 1.225 | ✅ | ✅ | Stripe |
| **Premium** | 59,99€ | 2.950 | ✅ | ✅ | Stripe |
| **Enterprise** | Custom | Custom | ✅ | ✅ | Admin manual |

---

## **🏗️ Arquitectura Enterprise (Nuevo)**

**Flujo Enterprise:**
```
clicandseo.com → "Contact Sales" → Negociación → 
Admin asigna custom quota → Plan automático = 'enterprise'
```

**Lógica de Quotas (Prioridad):**
1. `custom_quota_limit` (Enterprise personalizado)
2. `quota_limit` (Plan estándar)  
3. `PLAN_LIMITS[plan]` (Valores por defecto)

---

## **📈 Estado Actual**

- ✅ **Fase 0**: Completada (menos rotación credenciales)
- ✅ **Fase 1**: Completada (database + backfill)
- ✅ **Fase 1B**: Completada (Enterprise + admin panel) ⭐ **NUEVA**
- ⏳ **Fase 2**: En progreso (variables entorno)
- 📋 **Fases 3-9**: Pendientes según plan original

**📍 Próximo paso**: Completar Fase 2 con variables Stripe y flags de control.

---

*Documento actualizado: 2025-08-25 18:20*  
*Cambios: Añadida Fase 1B con Enterprise + Admin Panel*
