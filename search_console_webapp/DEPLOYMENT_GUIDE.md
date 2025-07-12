# 🚀 Guía de Despliegue en Producción

## Railway + GitHub + PostgreSQL

Esta guía te ayudará a desplegar tu aplicación Clicandseo en Railway con todas las funcionalidades de autenticación funcionando perfectamente.

## 📋 Prerrequisitos

### 1. **Cuentas Necesarias**
- ✅ Cuenta de GitHub
- ✅ Cuenta de Railway
- ✅ Proyecto de Google Cloud Console (para OAuth)
- ✅ Cuenta de SerpAPI

### 2. **Archivos Requeridos en el Repositorio**
- ✅ `client_secret.json` (credenciales de Google OAuth)
- ✅ Todas las dependencias en `requirements.txt`
- ✅ Variables de entorno configuradas en Railway

## 🔧 Configuración de Variables de Entorno en Railway

En tu proyecto de Railway, configura estas variables:

### **Variables Obligatorias:**

```bash
# Flask
FLASK_SECRET_KEY=tu-clave-super-secreta-256-bits-aqui

# Google OAuth
GOOGLE_REDIRECT_URI=https://tu-app.up.railway.app/auth/callback
CLIENT_SECRETS_FILE=client_secret.json

# SerpAPI
SERPAPI_KEY=tu-clave-serpapi

# Sesiones (opcional)
SESSION_TIMEOUT_MINUTES=45
SESSION_WARNING_MINUTES=5
```

### **Variables Automáticas de Railway:**
```bash
# Estas las proporciona Railway automáticamente:
DATABASE_URL=postgresql://postgres:...  # PostgreSQL URL
PORT=5001                               # Puerto de la app
RAILWAY_ENVIRONMENT=production          # Indicador de entorno
```

## 🗄️ Configuración de PostgreSQL

### **En Railway:**
1. Ve a tu proyecto en Railway
2. Agrega un servicio **PostgreSQL**
3. Railway generará automáticamente `DATABASE_URL`
4. La base de datos se inicializará automáticamente al hacer deploy

### **Inicialización Automática:**
El sistema incluye auto-inicialización que:
- ✅ Crea las tablas necesarias
- ✅ Crea el usuario administrador inicial
- ✅ Configura índices optimizados

## 👨‍💻 Configuración de Google OAuth

### **1. Google Cloud Console:**
```bash
# Orígenes JavaScript autorizados:
https://tu-app.up.railway.app

# URIs de redirección autorizadas:
https://tu-app.up.railway.app/auth/callback
```

### **2. Archivo `client_secret.json`:**
- ✅ Debe estar en la raíz del repositorio
- ✅ Se incluye en el despliegue (no en .gitignore para producción)
- ✅ Railway lo usará automáticamente

## 📁 Estructura de Archivos para Railway

```
search_console_webapp/
├── app.py                 # ✅ Archivo principal
├── auth.py               # ✅ Sistema de autenticación
├── database.py           # ✅ Gestión de PostgreSQL
├── init_database.py      # ✅ Inicialización de BD
├── requirements.txt      # ✅ Dependencias Python
├── Procfile             # ✅ Comandos de Railway
├── nixpacks.toml        # ✅ Configuración de build
├── client_secret.json   # ✅ Credenciales Google
├── templates/           # ✅ Templates HTML
├── static/             # ✅ CSS y JS
└── services/           # ✅ Servicios adicionales
```

## 🚀 Proceso de Despliegue

### **1. Preparar el Repositorio:**
```bash
# 1. Asegurar que client_secret.json esté en el repo
git add client_secret.json

# 2. Commit de todos los cambios
git add .
git commit -m "feat: sistema completo de autenticación para producción"

# 3. Push a GitHub
git push origin main
```

### **2. Configurar Railway:**
1. **Conectar Repositorio:**
   - Ve a Railway Dashboard
   - Crea nuevo proyecto
   - Conecta con GitHub
   - Selecciona el repositorio

2. **Agregar PostgreSQL:**
   - Add Service → PostgreSQL
   - Railway configurará automáticamente `DATABASE_URL`

3. **Configurar Variables de Entorno:**
   - Ve a Variables
   - Agrega todas las variables listadas arriba
   - ⚠️ **IMPORTANTE**: Cambia `GOOGLE_REDIRECT_URI` a tu dominio de Railway

### **3. Verificar el Despliegue:**
```bash
# El proceso automático incluye:
1. Build de la aplicación
2. Instalación de dependencias
3. Inicialización de PostgreSQL
4. Creación del usuario admin
5. Inicio del servidor Flask
```

## 🔐 Configuraciones de Seguridad para Producción

### **1. Variables Críticas:**
```python
# En auth.py, estas configuraciones cambian automáticamente:
app.config['SESSION_COOKIE_SECURE'] = True    # En HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Seguridad XSS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Protección CSRF
```

### **2. Credenciales Seguras:**
- ✅ `FLASK_SECRET_KEY` debe ser único y complejo
- ✅ `DATABASE_URL` es generada automáticamente por Railway
- ✅ Contraseña del admin se debe cambiar tras primer login

### **3. HTTPS Automático:**
Railway proporciona HTTPS automáticamente para todos los dominios.

## 📊 Monitoreo y Logs

### **En Railway Dashboard:**
- **Deployments**: Historial de despliegues
- **Metrics**: CPU, memoria, requests
- **Logs**: Logs en tiempo real de la aplicación
- **Database**: Métricas de PostgreSQL

### **Logs de la Aplicación:**
```python
# El sistema incluye logging detallado:
- Autenticación de usuarios
- Errores de base de datos
- Métricas de rendimiento
- Eventos de administración
```

## 🔄 Actualizaciones Automáticas

Railway redespliega automáticamente cuando:
- ✅ Haces push a la rama `main`
- ✅ Cambias variables de entorno
- ✅ Actualizas el código

## 🎯 URLs de Producción

Una vez desplegado, tendrás:
```bash
# App principal
https://tu-app.up.railway.app

# Login
https://tu-app.up.railway.app/login

# Registro
https://tu-app.up.railway.app/signup

# Dashboard
https://tu-app.up.railway.app/dashboard

# Admin (solo administradores)
https://tu-app.up.railway.app/admin/users
```

## 👤 Usuario Administrador Inicial

Al desplegar, se crea automáticamente:
- **Email**: `admin@clicandseo.com`
- **Contraseña**: `admin123456`
- **Rol**: `admin`
- **Estado**: `activo`

**⚠️ CRÍTICO**: Cambiar la contraseña inmediatamente tras el primer login.

## 🆘 Solución de Problemas

### **Error de Base de Datos:**
```bash
# En Railway Logs, busca:
"Error conectando a la base de datos"

# Solución:
1. Verifica que PostgreSQL esté ejecutándose
2. Confirma que DATABASE_URL esté configurada
3. Reinicia el servicio
```

### **Error de OAuth:**
```bash
# Error: "invalid_redirect_uri"

# Solución:
1. Verifica GOOGLE_REDIRECT_URI en Railway
2. Confirma la configuración en Google Cloud Console
3. Asegúrate de usar HTTPS en producción
```

### **Error de Sesiones:**
```bash
# Error: "Session expired"

# Solución:
1. Verifica FLASK_SECRET_KEY esté configurada
2. Confirma que sea la misma entre despliegues
3. Revisa configuración de cookies
```

## 📈 Métricas de Éxito

Tu aplicación está funcionando correctamente cuando:
- ✅ La página `/login` carga sin errores
- ✅ El registro manual funciona
- ✅ El registro con Google funciona
- ✅ Los usuarios pueden hacer login
- ✅ El panel de administración es accesible
- ✅ La base de datos responde correctamente

## 🎯 Siguientes Pasos

1. **Configurar Dominio Personalizado** (opcional)
2. **Integrar Stripe** para pagos
3. **Configurar Emails** para notificaciones
4. **Agregar Monitoreo** avanzado
5. **Configurar Respaldos** de base de datos

## 🚨 Checklist Final

Antes de lanzar a producción:

- [ ] ✅ Variables de entorno configuradas
- [ ] ✅ `client_secret.json` en el repositorio
- [ ] ✅ Google OAuth configurado para dominio de producción
- [ ] ✅ PostgreSQL funcionando
- [ ] ✅ Usuario admin creado
- [ ] ✅ Contraseña de admin cambiada
- [ ] ✅ Todas las rutas funcionando
- [ ] ✅ SSL/HTTPS activo
- [ ] ✅ Logs monitoreándose

**¡Tu aplicación está lista para producción!** 🎉

---

**💡 Tip**: Railway proporciona un dominio gratuito, pero también puedes configurar tu propio dominio personalizado en la configuración del proyecto. 