# 📧 Configuración Brevo (Sendinblue) para ClicandSEO

## 🎯 Configuración SMTP de Brevo

### **Variables para Railway:**

```bash
# Configuración Brevo SMTP
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=tu_email_brevo@clicandseo.com
SMTP_PASSWORD=tu_smtp_key_de_brevo
USE_STARTTLS=true

# Configuración del remitente
FROM_EMAIL=info@clicandseo.com
FROM_NAME=ClicandSEO
```

## 🔑 Obtener Credenciales de Brevo

### **Paso 1: Acceder a SMTP**
1. Login en tu cuenta de Brevo
2. Ve a **Settings** → **SMTP & API**
3. En la sección **SMTP**, encontrarás:
   - **SMTP Server:** smtp-relay.brevo.com
   - **Port:** 587
   - **Login:** tu email de Brevo
   - **SMTP Key:** (generar nueva si no tienes)

### **Paso 2: Generar SMTP Key**
1. En **SMTP & API** → **SMTP**
2. Click en **Generate a new SMTP key**
3. Copia la clave generada

### **Paso 3: Verificar Dominio**
1. Ve a **Settings** → **Senders & IP**
2. Verifica que `clicandseo.com` esté verificado
3. Si no, agrégalo y verifica vía DNS

## ✅ Ventajas de Brevo vs SMTP Propio

- ✅ **99.9% Deliverability** - Los emails llegan siempre
- ✅ **Compatible con Railway** - Sin bloqueos de puertos
- ✅ **25,000 emails/mes gratis** - Suficiente para password reset
- ✅ **Reputación de dominio** - Mejor que SMTP propio
- ✅ **Analytics** - Estadísticas de entrega
- ✅ **Plantillas** - Sistema de templates avanzado

## 🚀 Plan Gratuito de Brevo

- 📧 **300 emails/día**
- 📊 **Tracking completo**
- 🔒 **SMTP seguro**
- 📱 **API REST** (opcional)
- ⚡ **Entrega instantánea**
