# 🔐 VARIABLES DE ENTORNO - SISTEMA MULTI-LLM BRAND MONITORING

## Variables Requeridas para Despliegue en Railway

### 📋 Checklist de Variables

#### Variables Existentes (Ya configuradas)
- [x] `DATABASE_URL` - PostgreSQL connection string
- [x] `SECRET_KEY` - Flask secret key
- [x] `FLASK_ENV` - production/staging
- [x] Otras variables de tu app existente

#### Variables Nuevas para LLM Monitoring (Opcionales - Configurables por Usuario)

**IMPORTANTE**: Las API keys de LLMs **NO se requieren como variables de entorno** en Railway. Los usuarios las configuran desde la UI del sistema una vez desplegado.

El sistema almacena las API keys de forma encriptada en la tabla `user_llm_api_keys` de PostgreSQL.

---

## 🎯 Variables de Entorno por Prioridad

### 🔴 CRÍTICAS (Requeridas)

#### 1. Base de Datos
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```
**Descripción**: Conexión a PostgreSQL  
**Ejemplo**: `postgresql://postgres:kITzKfjMoMcwVhjOCspAHepsflpSkeyu@interchange.proxy.rlwy.net:14875/railway`  
**Status**: ✅ Ya configurada

#### 2. Flask
```bash
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
```
**Descripción**: Secret key de Flask y entorno  
**Status**: ✅ Ya configuradas

---

### 🟡 OPCIONALES (Mejoradas para usuarios)

#### API Keys de LLMs (Configurables desde UI)

Los usuarios pueden añadir sus propias API keys desde:
- **Ruta**: `/llm-monitoring` → Settings → API Keys
- **Endpoint**: `POST /api/llm-monitoring/api-keys`

**Formato en BD** (tabla `user_llm_api_keys`):
```sql
CREATE TABLE user_llm_api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    llm_provider VARCHAR(50),  -- 'openai', 'anthropic', 'google', 'perplexity'
    api_key_encrypted TEXT,     -- Encriptada
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Providers Soportados**:
1. **OpenAI** (GPT-5)
   - Key format: `sk-proj-...` o `sk-...`
   - Obtenible en: https://platform.openai.com/api-keys

2. **Anthropic** (Claude Sonnet 4.5)
   - Key format: `sk-ant-...`
   - Obtenible en: https://console.anthropic.com/settings/keys

3. **Google** (Gemini 2.0 Flash)
   - Key format: `AIza...`
   - Obtenible en: https://makersuite.google.com/app/apikey

4. **Perplexity** (Sonar Large)
   - Key format: `pplx-...`
   - Obtenible en: https://www.perplexity.ai/settings/api

---

### 🟢 OPCIONALES (Para Administrador)

#### API Keys Globales (Fallback)

Si quieres que el sistema tenga API keys por defecto para todos los usuarios (no recomendado por costes), puedes configurar:

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google
GOOGLE_API_KEY=AIza...

# Perplexity
PERPLEXITY_API_KEY=pplx-...
```

**⚠️ ADVERTENCIA**: Solo usar para testing o demos. En producción, los usuarios deben configurar sus propias keys para evitar costes excesivos.

---

## 📊 Configuración de Cron Jobs (Railway)

Las cron jobs ya están configuradas en `railway.json`:

```json
{
  "crons": [
    {
      "command": "python3 daily_analysis_cron.py",
      "schedule": "0 2 * * *"
    },
    {
      "command": "python3 daily_ai_mode_cron.py",
      "schedule": "0 3 * * *"
    },
    {
      "command": "BREVO_CONTACT_LIST_ID=8 python3 sync_users_to_brevo.py",
      "schedule": "15 3 * * *"
    },
    {
      "command": "python3 daily_llm_monitoring_cron.py",
      "schedule": "0 4 * * *"
    },
    {
      "command": "python3 weekly_model_check_cron.py",
      "schedule": "0 0 * * 0"
    }
  ]
}
```

**✅ Listo para Railway** - No requiere configuración adicional.

---

## 🔒 Seguridad de API Keys

### Encriptación en BD

El sistema usa encriptación para almacenar API keys:

```python
from cryptography.fernet import Fernet

# Generar key de encriptación (una vez, guardar en variable de entorno)
encryption_key = Fernet.generate_key()

# Encriptar API key antes de guardar
cipher_suite = Fernet(encryption_key)
encrypted_key = cipher_suite.encrypt(api_key.encode())

# Desencriptar al usar
decrypted_key = cipher_suite.decrypt(encrypted_key).decode()
```

### Variable de Entorno para Encriptación (Recomendada)

```bash
ENCRYPTION_KEY=<base64-encoded-fernet-key>
```

**Generar Key**:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

**Status**: 🟡 Opcional pero recomendada. Si no existe, el sistema puede usar SECRET_KEY como fallback.

---

## 📝 Variables de Entorno - Resumen Completo

### Para Railway Deployment

```bash
# ============================================
# CRÍTICAS (Requeridas) ✅
# ============================================
DATABASE_URL=postgresql://...
SECRET_KEY=your-secret-key
FLASK_ENV=production

# ============================================
# OPCIONALES (Para admin/testing) 🟡
# ============================================

# API Keys Globales (solo para demos/testing)
# OPENAI_API_KEY=sk-proj-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIza...
# PERPLEXITY_API_KEY=pplx-...

# Encriptación (recomendada)
# ENCRYPTION_KEY=<fernet-key>

# ============================================
# YA CONFIGURADAS (No tocar) ✅
# ============================================
# Todas las demás variables de tu app existente
```

---

## 🚀 Pasos para Configurar Variables en Railway

### 1. Acceder a Railway Dashboard
```
https://railway.app/dashboard
→ Seleccionar proyecto
→ Variables
```

### 2. Variables Críticas (Verificar que existan)
- ✅ `DATABASE_URL`
- ✅ `SECRET_KEY`
- ✅ `FLASK_ENV`

### 3. Variables Opcionales (Añadir si necesario)

**Para Testing/Demos** (Añadir API keys globales):
```
+ Add Variable
  Key: OPENAI_API_KEY
  Value: sk-proj-...
```

**Para Encriptación** (Recomendado):
```
+ Add Variable
  Key: ENCRYPTION_KEY
  Value: <generar con Fernet.generate_key()>
```

### 4. Redeploy (si añadiste variables)
```
→ Deployments
→ Redeploy latest
```

---

## ✅ Checklist de Configuración

### Pre-Despliegue
- [x] `DATABASE_URL` configurada
- [x] `SECRET_KEY` configurada
- [x] `FLASK_ENV=production` configurada
- [ ] `ENCRYPTION_KEY` configurada (opcional pero recomendada)
- [ ] API keys globales configuradas (solo si quieres fallback)

### Post-Despliegue
- [ ] Ejecutar `create_llm_monitoring_tables.py` en producción
- [ ] Verificar que las tablas se crearon correctamente
- [ ] Probar UI en `/llm-monitoring`
- [ ] Probar endpoints API
- [ ] Verificar cron jobs en Railway logs
- [ ] Documentar para usuarios cómo añadir sus API keys

---

## 📖 Documentación para Usuarios

### Cómo Añadir API Keys (Post-Despliegue)

**Paso 1**: Acceder a LLM Monitoring
```
Login → Dashboard → LLM Visibility
```

**Paso 2**: Configurar API Keys
```
Settings → API Keys → Add New Key
```

**Paso 3**: Seleccionar Provider
```
- OpenAI (GPT-5)
- Anthropic (Claude Sonnet 4.5)
- Google (Gemini 2.0 Flash)
- Perplexity (Sonar Large)
```

**Paso 4**: Pegar API Key
```
API Key: [sk-proj-...]
[Test Connection]
[Save]
```

**Paso 5**: Crear Proyecto
```
New Project → 
  Nombre: Mi Marca SEO
  Brand: MiMarca
  Industry: SEO tools
  Competitors: Semrush, Ahrefs
  LLMs habilitados: ✓ OpenAI ✓ Google
```

---

## 🔍 Troubleshooting

### Error: "No API key configured"
**Solución**: Usuario debe añadir su API key desde UI en `/llm-monitoring`

### Error: "Failed to decrypt API key"
**Solución**: Verificar que `ENCRYPTION_KEY` está configurada o que `SECRET_KEY` es consistente

### Error: "Database connection failed"
**Solución**: Verificar `DATABASE_URL` en Railway variables

### Cron jobs no se ejecutan
**Solución**: 
1. Verificar `railway.json` está en root
2. Verificar logs en Railway dashboard
3. Verificar que los scripts tienen permisos de ejecución

---

## 📊 Monitoreo Post-Despliegue

### Logs a Monitorear

```bash
# Railway CLI
railway logs

# Filtrar por servicio
railway logs | grep "llm_monitoring"

# Filtrar cron jobs
railway logs | grep "daily_llm_monitoring_cron"
```

### Métricas Clave

1. **Ejecución de Cron Jobs**
   - Daily analysis: debe ejecutar a las 04:00 AM
   - Weekly model check: debe ejecutar Domingos 00:00

2. **API Endpoints**
   - Response time < 500ms
   - Error rate < 1%

3. **Costes LLM**
   - Monitorear `llm_monitoring_snapshots.total_cost`
   - Alertar si excede presupuesto mensual

---

## 🎯 Conclusión

**Variables de Entorno Mínimas para Despliegue**:
- ✅ `DATABASE_URL` (ya configurada)
- ✅ `SECRET_KEY` (ya configurada)
- ✅ `FLASK_ENV=production` (ya configurada)

**Sistema Listo para Desplegar** sin variables adicionales. Las API keys las configuran los usuarios desde la UI.

**Opcional pero Recomendado**:
- 🟡 `ENCRYPTION_KEY` para mayor seguridad

**Solo para Testing/Demos**:
- 🟢 API keys globales (`OPENAI_API_KEY`, etc.)

---

**✅ SISTEMA PREPARADO PARA RAILWAY DEPLOYMENT**

