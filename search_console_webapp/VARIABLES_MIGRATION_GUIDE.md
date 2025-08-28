# GUÍA DE MIGRACIÓN VARIABLES: STAGING → PRODUCTION

**⚠️ CRÍTICO: Esta guía asegura que no perdamos usuarios en production**

---

## 📊 **VARIABLES QUE **DEBEN CAMBIAR** EN PRODUCTION**

### **🔑 STRIPE KEYS (Test → Live)**
| Variable | Staging (Test) | Production (Live) | Status |
|----------|----------------|-------------------|---------|
| `STRIPE_SECRET_KEY` | `sk_test_51Ro59P...` | **`sk_live_...`** ⚠️ | 🔄 Cambiar |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_51Ro59P...` | **`pk_live_...`** ⚠️ | 🔄 Cambiar |
| `STRIPE_WEBHOOK_SECRET` | `whsec_qhEi0vs...` | **`whsec_[NEW]`** ⚠️ | 🔄 Cambiar |

### **💰 PRICE IDs (Test → Live)**
| Variable | Staging | Production | Status |
|----------|---------|------------|---------|
| `PRICE_ID_BASIC` | `price_1S0NxmG...` | **`price_[LIVE]`** ⚠️ | 🔄 Cambiar |
| `PRICE_ID_PREMIUM` | `price_1S0NvaG...` | **`price_[LIVE]`** ⚠️ | 🔄 Cambiar |
| `STRIPE_ENTERPRISE_PRODUCT_ID` | `prod_SwH15yO...` | **`prod_[LIVE]`** ⚠️ | 🔄 Cambiar |

### **🌐 URLs Y ENTORNO**
| Variable | Staging | Production | Status |
|----------|---------|------------|---------|
| `CUSTOMER_PORTAL_RETURN_URL` | `https://clicandseo.up.railway.app/dashboard` | **`https://app.clicandseo.com/dashboard`** ⚠️ | 🔄 Cambiar |
| `APP_ENV` | `staging` | **`production`** ⚠️ | 🔄 Cambiar |
| `DATABASE_URL` | `postgresql://...caboose...` | **`postgresql://...switchyard...`** ⚠️ | 🔄 Cambiar |

### **🎛️ CONTROL FLAGS (Inicialmente iguales, luego activar)**
| Variable | Staging | Production (Inicial) | Production (Final) | Status |
|----------|---------|---------------------|-------------------|---------|
| `BILLING_ENABLED` | `false` | **`false`** → **`true`** | 🔄 Activar gradual |
| `ENFORCE_QUOTAS` | `false` | **`false`** → **`true`** | 🔄 Activar gradual |

---

## ✅ **VARIABLES QUE **NO CAMBIAN****

### **🔧 CONFIGURACIÓN TÉCNICA**
| Variable | Valor | Comentario |
|----------|-------|------------|
| `AIO_MODULE_ENABLED` | `true` | ✅ Igual |
| `QUOTA_SOFT_LIMIT_PCT` | `80` | ✅ Igual |
| `QUOTA_GRACE_PERIOD_HOURS` | `24` | ✅ Igual |
| `FLASK_SECRET_KEY` | `[ACTUAL]` | ✅ Igual |
| `CRON_TOKEN` | `[ACTUAL]` | ✅ Igual |

### **🔑 APIs EXTERNAS**
| Variable | Valor | Comentario |
|----------|-------|------------|
| `SERPAPI_KEY` | `[ACTUAL]` | ✅ Igual (funciona test/live) |
| `GOOGLE_CLIENT_ID` | `[ACTUAL]` | ✅ Igual |
| `GOOGLE_CLIENT_SECRET` | `[ACTUAL]` | ✅ Igual |
| `GOOGLE_REDIRECT_URI` | `[ACTUAL]` | ✅ Igual |

---

## 🚀 **PLAN DE MIGRACIÓN SEGURA**

### **FASE 6: Preparar Production (sin encender)**
```bash
# 1. Crear productos en Stripe LIVE
# 2. Obtener nuevas keys/price_ids
# 3. Configurar variables en Railway Production
# 4. Deploy código con FLAGS APAGADOS
```

### **📋 CHECKLIST PRE-DEPLOY**
- [ ] ✅ Backup completo BD Production
- [ ] 🔑 Stripe Live keys obtenidas
- [ ] 💰 Price IDs Live creados
- [ ] 📡 Webhook Live configurado
- [ ] 🌐 URLs actualizadas
- [ ] 🎛️ Flags en `false` (seguridad)
- [ ] 🧪 Variables verificadas

### **⚠️ ORDEN CRÍTICO DE ACTIVACIÓN**
```
1. Deploy código (flags OFF)
2. Verificar usuarios intactos
3. BILLING_ENABLED=true
4. Testing pequeño grupo
5. ENFORCE_QUOTAS=true
6. Monitor 48h
7. Full rollout
```

---

## 🛡️ **PROTECCIÓN USUARIOS PRODUCTION**

### **🔒 GARANTÍAS**
- ✅ **Migración BD aditiva** (solo ADD COLUMN)
- ✅ **Flags de control** para rollback
- ✅ **Backup completo** antes de cambios
- ✅ **Variables separadas** por entorno
- ✅ **Testing gradual** por cohortes

### **📞 ROLLBACK PLAN**
```bash
# Si algo falla:
BILLING_ENABLED=false
ENFORCE_QUOTAS=false
# Restaurar BD desde backup si necesario
```

---

## 📝 **NOTAS IMPORTANTES**

1. **🔄 Doble check**: Verificar cada variable manualmente
2. **🧪 Test mode**: Stripe detecta automáticamente test vs live
3. **📊 Monitoring**: Alertas en variables críticas
4. **👥 Team access**: Solo admin puede cambiar variables production
5. **📋 Documentation**: Actualizar esta guía con cambios

---

**📅 Última actualización**: 2025-08-25  
**👨‍💻 Responsable**: Carlos González  
**🎯 Fase actual**: 3 (Stripe Test configurado)  
**⏭️ Próximo**: Fase 4 (Reglas de acceso y quotas)

---

## ⚡ **RESUMEN EJECUTIVO**

**Variables a cambiar: 9 críticas**
- 🔑 3 Stripe keys
- 💰 3 Price IDs  
- 🌐 3 URLs/environment

**Variables iguales: 8 técnicas**
- APIs, configuración, flags

**Riesgo**: ⚠️ MEDIO (con procedimiento correcto)  
**Tiempo estimado**: 2-3 horas con verificaciones  
**Usuarios afectados**: 0 (con flags de control)
