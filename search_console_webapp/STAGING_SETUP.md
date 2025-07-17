# 🎭 Configuración de Entorno STAGING

## 📋 Variables de Entorno Requeridas para Staging

Ve a tu proyecto en Railway y agrega estas variables de entorno:

### ✅ Variables Críticas
```bash
RAILWAY_ENVIRONMENT=staging
GOOGLE_REDIRECT_URI=https://clicandseo.up.railway.app/auth/callback
FLASK_SECRET_KEY=tu-clave-super-secreta-para-staging-diferente-a-produccion
SERPAPI_KEY=tu-clave-serpapi
```

### ✅ Variables Opcionales (con valores por defecto)
```bash
CLIENT_SECRETS_FILE=client_secret.json
SESSION_TIMEOUT_MINUTES=45
SESSION_WARNING_MINUTES=5
```

### ✅ Variables Automáticas (Railway las proporciona)
```bash
DATABASE_URL=postgresql://...    # Automática con PostgreSQL service
PORT=puerto                      # Automático
```

## 🔧 Pasos de Configuración

### 1. **En Railway Dashboard**
1. Ve a tu proyecto de staging
2. Accede a la pestaña "Variables"
3. Agrega todas las variables listadas arriba
4. **IMPORTANTE**: Asegúrate de que `RAILWAY_ENVIRONMENT=staging`

### 2. **En Google Cloud Console**
1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto "ai-overview-checker"
3. Ve a **APIs y servicios → Credenciales**
4. Edita tu cliente OAuth 2.0
5. En **Orígenes JavaScript autorizados**, agrega:
   ```
   https://clicandseo.up.railway.app
   ```
6. En **URI de redirección autorizados**, agrega:
   ```
   https://clicandseo.up.railway.app/auth/callback
   ```

### 3. **Verificar Configuración**
Una vez desplegado, visita:
```
https://clicandseo.up.railway.app/auth/status
```

Deberías ver una respuesta JSON indicando el estado de autenticación.

## 🚨 Diferencias entre Entornos

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `RAILWAY_ENVIRONMENT` | (ninguna) | `staging` | `production` |
| `GOOGLE_REDIRECT_URI` | `http://localhost:5001/auth/callback` | `https://clicandseo.up.railway.app/auth/callback` | `https://tu-dominio-prod.com/auth/callback` |
| `SESSION_COOKIE_SECURE` | `False` | `True` | `True` |
| HTTPS | No | Sí | Sí |

## 🔍 Cómo Verificar que Todo Funciona

### Test 1: Endpoint de Estado
```bash
curl https://clicandseo.up.railway.app/auth/status
```

### Test 2: Página de Login
1. Ve a `https://clicandseo.up.railway.app/login`
2. Haz clic en "Iniciar sesión con Google"
3. Deberías ser redirigido a Google correctamente

### Test 3: Logs de Railway
Revisa los logs en Railway para ver:
```
🌍 Entorno detectado: staging
📊 Configuración: Production=False, Staging=True, Development=False
✅ Configuración HTTPS habilitada para entorno no-development
```

## ⚠️ Problemas Comunes

### Error: "invalid_redirect_uri"
- **Causa**: La URL no está configurada en Google Cloud Console
- **Solución**: Agregar `https://clicandseo.up.railway.app/auth/callback` en Google Cloud Console

### Error: "Configuration error"  
- **Causa**: Variables de entorno faltantes
- **Solución**: Verificar que todas las variables estén configuradas en Railway

### Error: Páginas no cargan
- **Causa**: Base de datos no inicializada
- **Solución**: Verificar que el `Procfile` se ejecute correctamente

## 📞 Siguiente Paso
Una vez configurado todo, ejecuta:
```bash
python check_production_ready.py
```

Para verificar que la configuración es correcta antes del despliegue. 