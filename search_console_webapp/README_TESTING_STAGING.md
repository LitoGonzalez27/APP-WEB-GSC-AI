# 🧪 GUÍA COMPLETA DE TESTING - STAGING

## 📋 OVERVIEW

Esta guía te llevará paso a paso para probar **completamente** tu sistema de administración mejorado y la integración con Stripe en el entorno de **staging**.

---

## 🎯 OBJETIVOS DE LAS PRUEBAS

✅ **Verificar que el panel admin mejorado funciona**  
✅ **Confirmar que las barras progresivas de RU funcionan**  
✅ **Validar que el modal "Ver" muestra información completa**  
✅ **Verificar integración con Stripe**  
✅ **Confirmar sincronización con base de datos**  
✅ **Asegurar que está listo para producción**

---

## 🚀 FLUJO DE TESTING RECOMENDADO

### **PASO 1: CONFIGURACIÓN INICIAL**

#### A. **Configurar Variables de Entorno**
```bash
# Base de datos de staging
export DATABASE_URL="postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

# Stripe (TEST keys)
export STRIPE_SECRET_KEY="sk_test_..."
export STRIPE_PUBLISHABLE_KEY="pk_test_..."
```

#### B. **Instalar Dependencias de Testing**
```bash
pip install psycopg2 stripe requests
```

---

### **PASO 2: TESTS AUTOMATIZADOS**

#### A. **Test Rápido - Todo en Uno**
```bash
python3 run_full_staging_tests.py
```
**✅ Este script ejecuta todos los tests automáticamente**

#### B. **Tests Individuales (Opcional)**

**🔧 Solo Panel Admin:**
```bash
python3 test_admin_panel_staging.py
```

**💳 Solo Stripe:**
```bash
python3 test_stripe_integration.py
```

---

### **PASO 3: TESTING MANUAL**

#### **Ejecutar Checklist Completo**
1. **Abrir**: `checklist_manual_testing.md`
2. **Ir a**: `https://clicandseo.up.railway.app/admin/users`
3. **Seguir paso a paso** cada item del checklist
4. **Marcar** ✅ cada test completado

---

## 📁 ARCHIVOS DE TESTING

### **🤖 Scripts Automatizados**

| Archivo | Propósito | Tiempo |
|---------|-----------|---------|
| `run_full_staging_tests.py` | **TEST PRINCIPAL** - Ejecuta todo | ~3-5 min |
| `test_admin_panel_staging.py` | Tests del panel admin y Railway | ~2 min |
| `test_stripe_integration.py` | Tests de Stripe API y configuración | ~2 min |

### **📋 Documentación Manual**

| Archivo | Propósito | Tiempo |
|---------|-----------|---------|
| `checklist_manual_testing.md` | **CHECKLIST COMPLETO** - Testing manual | ~15-20 min |
| `README_TESTING_STAGING.md` | Esta guía | - |

---

## 🎯 CRITERIOS DE ÉXITO

### **✅ TESTS AUTOMATIZADOS DEBEN PASAR:**

#### **🔧 Panel Admin Tests:**
- ✅ Acceso a `/admin/users` (200 OK)
- ✅ Contiene barras progresivas
- ✅ Endpoint `/admin/users/<id>/billing-details` existe
- ✅ Base de datos conecta correctamente
- ✅ Columnas de billing existen
- ✅ Assets frontend se cargan

#### **💳 Stripe Tests:**
- ✅ Conexión a Stripe API
- ✅ Productos Basic y Premium configurados
- ✅ Precios 29.99€ y 59.99€ configurados
- ✅ Webhook endpoint existe
- ✅ Webhooks configurados para staging

### **✅ TESTING MANUAL DEBE INCLUIR:**

#### **📊 Barras Progresivas:**
- ✅ Se muestran correctamente
- ✅ Colores cambian según porcentaje (verde/amarillo/rojo)
- ✅ Datos coinciden con base de datos

#### **🔍 Modal "Ver" Mejorado:**
- ✅ 4 secciones se cargan
- ✅ Información básica completa
- ✅ Plan y facturación con período específico
- ✅ Cuotas y uso con barra progresiva
- ✅ Custom quota (si aplica)

#### **🛠️ Funcionalidades Admin:**
- ✅ Cambiar roles funciona
- ✅ Cambiar estados funciona
- ✅ Cambiar planes actualiza barras progresivas
- ✅ Asignar custom quota funciona
- ✅ Reset quota funciona

---

## 🛠️ TROUBLESHOOTING

### **❌ Si Tests Automatizados Fallan:**

#### **🔧 Error de Base de Datos:**
```bash
# Verificar que DATABASE_URL está configurado
echo $DATABASE_URL

# Si está vacío:
export DATABASE_URL="postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"
```

#### **💳 Error de Stripe:**
```bash
# Verificar que STRIPE_SECRET_KEY está configurado
echo $STRIPE_SECRET_KEY

# Si está vacío, ir a Stripe Dashboard:
# 1. https://dashboard.stripe.com/test/apikeys
# 2. Copiar "Secret key" (sk_test_...)
export STRIPE_SECRET_KEY="sk_test_..."
```

#### **📦 Error de Dependencias:**
```bash
pip install psycopg2-binary stripe requests
```

### **❌ Si Testing Manual Falla:**

#### **🔧 Barras Progresivas No Aparecen:**
1. **Abrir consola del navegador** (F12)
2. **Buscar errores** JavaScript
3. **Verificar** que aparece: "🔄 Inicializando barras progresivas de cuotas..."
4. **Si no aparece** → revisar que `initializeQuotaProgressBars()` se llama

#### **🔍 Modal No Carga Datos Completos:**
1. **Verificar** que `/admin/users/<id>/billing-details` responde
2. **Revisar consola** para errores de red
3. **Verificar** en Railway logs si hay errores

#### **📊 Datos Incorrectos:**
1. **Verificar** que la ruta `/admin/users` usa `get_users_with_billing()`
2. **Revisar** base de datos directamente:
```sql
SELECT id, email, plan, quota_used, quota_limit, current_period_start, current_period_end FROM users LIMIT 5;
```

---

## 📊 EJEMPLO DE RESULTADOS ESPERADOS

### **✅ Tests Automatizados Exitosos:**
```
🧪 TESTING ADMIN PANEL STAGING - COMPREHENSIVE
=============================================================
✅ PASS Acceso a /admin/users
✅ PASS Contiene barras progresivas
✅ PASS Endpoint billing-details existe
✅ PASS Conexión a base de datos
✅ PASS Columnas de billing existen
✅ PASS Usuarios en base de datos
✅ PASS Assets frontend

📊 Tests ejecutados: 7
✅ Tests exitosos: 7
📈 Tasa de éxito: 100.0%

🎊 TODOS LOS TESTS PASARON - STAGING LISTO
```

### **✅ Testing Manual Exitoso:**
- **Panel se carga**: ✅ Inmediato, sin errores
- **Barras progresivas**: ✅ Todas con colores correctos
- **Modal "Ver"**: ✅ 4 secciones completas
- **Funcionalidades**: ✅ Cambios se aplican correctamente

---

## 🎯 NEXT STEPS DESPUÉS DE TESTING

### **🎊 Si Todo Pasa:**
1. ✅ **Sistema verificado** y listo
2. 🚀 **Continuar con Fase 5** (siguiente desarrollo)
3. 📋 **Documentar** cualquier observación
4. 🎯 **Preparar** despliegue a producción cuando sea el momento

### **⚠️ Si Hay Issues:**
1. 🛠️ **Corregir** problemas identificados
2. 🔄 **Re-ejecutar** tests afectados
3. 📋 **Documentar** cambios realizados
4. ✅ **Verificar** que corrección no rompe otras funcionalidades

---

## 🎯 COMANDO RÁPIDO PARA EMPEZAR

```bash
# Configurar variables (reemplaza con tus valores reales)
export DATABASE_URL="postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"
export STRIPE_SECRET_KEY="sk_test_..."

# Ejecutar test completo
python3 run_full_staging_tests.py

# Si todo pasa → continuar con testing manual
# Si hay fallos → revisar logs y corregir
```

---

## 📞 SOPORTE

Si encuentras problemas durante el testing:

1. **Revisar** logs de Railway en tiempo real
2. **Verificar** variables de entorno en Railway dashboard
3. **Consultar** este README para troubleshooting
4. **Documentar** cualquier issue para futuras mejoras

**¡Listo para empezar el testing! 🚀**
