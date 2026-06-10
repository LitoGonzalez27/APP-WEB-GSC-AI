# CLAUDE-staging.md — Entorno Staging

> Manual del **entorno staging**: para qué sirve, cómo desplegar cambios, cómo probar antes de subir a producción, y cómo recuperar staging si se ensucia.
>
> Última actualización: 2026-05-17 (tras la reconfiguración completa post-incidentes Stripe/pool/period).
>
> Manuales relacionados: `CLAUDE-deploy-railway.md`, `CLAUDE-stripe-cuotas-crons.md`, `CLAUDE-base-de-datos.md`. Índice maestro: `CLAUDE-INDEX.md`.

---

## Índice

1. [Visión general en 3 minutos](#1-visión-general-en-3-minutos)
2. [Lo que es staging y lo que NO es](#2-lo-que-es-staging-y-lo-que-no-es)
3. [URLs y accesos](#3-urls-y-accesos)
4. [Diferencias clave vs producción](#4-diferencias-clave-vs-producción)
5. [Workflow de desarrollo: cómo desplegar a staging](#5-workflow-de-desarrollo-cómo-desplegar-a-staging)
6. [Cómo probar cosas en staging](#6-cómo-probar-cosas-en-staging)
7. [Cómo promover staging → main (producción)](#7-cómo-promover-staging--main-producción)
8. [Cron schedules en staging](#8-cron-schedules-en-staging)
9. [Stripe testing en staging](#9-stripe-testing-en-staging)
10. [Datos de testing en BD staging](#10-datos-de-testing-en-bd-staging)
11. [Cómo "resetear" staging si se ensucia](#11-cómo-resetear-staging-si-se-ensucia)
12. [Troubleshooting y casos comunes](#12-troubleshooting-y-casos-comunes)

---

## 1. Visión general en 3 minutos

**Staging es un entorno completo y aislado** de producción, con:

- Su **propia base de datos** PostgreSQL (independiente, 21 usuarios de prueba, 3 proyectos LLM, ~288 análisis históricos).
- Sus **propias variables de entorno** (Stripe en modo TEST, billing desactivado, alertas silenciadas).
- Sus **propios crones** Bun (todos reducidos a 1×/semana los sábados, para gastar mínimo en APIs externas).
- El **mismo código** que producción (la rama `staging` se sincroniza con `main`).

**Para qué sirve**: probar cambios antes de mergearlos a `main`/producción. Si en staging algo no funciona, descubres el problema sin afectar a tus clientes reales.

**Reglas de oro**:
1. **Nunca conectar Stripe LIVE en staging**. Usar siempre `sk_test_...` y test webhook secret.
2. **`BILLING_ENABLED=false` siempre en staging**. Nunca cobrar dinero real desde staging.
3. **No copiar datos de producción a staging** (PII de clientes reales). Crear datos sintéticos si hace falta.
4. **El cron de staging es 1×/semana sábado** (excepto quota-reset diario). Si necesitas dispararlo ahora, hazlo manualmente.

---

## 2. Lo que es staging y lo que NO es

### Lo que SÍ es

- Un entorno **a producción-paralela** con BD aislada.
- El sitio donde **probar cambios de código** antes de mergearlos a main.
- El sitio donde **validar el flujo Stripe** con tarjetas de test antes de tocar billing real.
- El sitio donde **probar migraciones** de BD sin riesgo a tus clientes.

### Lo que NO es

- ❌ **No es una réplica de los datos de producción**. Tiene sus propios users/proyectos sintéticos.
- ❌ **No procesa pagos reales**. `BILLING_ENABLED=false` y Stripe en modo test.
- ❌ **No envía emails a clientes reales** (alertas de cron desactivadas: `CRON_ALERTS_ENABLED=false`).
- ❌ **No reemplaza tests automáticos**. Es testing manual end-to-end. Los tests unitarios viven aparte.

---

## 3. URLs y accesos

| Recurso | URL / valor |
|---|---|
| App staging | https://clicandseo.up.railway.app |
| App producción | https://app.clicandseo.com |
| Repo GitHub | https://github.com/LitoGonzalez27/APP-WEB-GSC-AI |
| Rama staging | `staging` |
| Rama producción | `main` |
| Railway project | `clicandseo` (147a0208-4f26-4b95-b0bf-2f6ee1868297) |
| Environment staging | `3492b27c-9778-4183-a67a-17ff246c36c1` |
| Environment producción | `b752c083-453b-4912-8290-c88d572ec505` |

---

## 4. Diferencias clave vs producción

| | Producción | Staging |
|---|---|---|
| Branch que despliega | `main` | `staging` |
| URL | app.clicandseo.com | clicandseo.up.railway.app |
| Base de datos | Postgres propio (~141 users) | Postgres propio (~21 users de prueba) |
| Stripe keys | `sk_live_...` | `sk_test_...` |
| `BILLING_ENABLED` | `true` | `false` |
| `CRON_ALERTS_ENABLED` | `true` | `false` |
| `LLM_PROJECT_PARALLELISM` | `1` (subir a 3 cuando estable) | `1` |
| Cron LLM | `0 04 * * 2,5` (mar/vie) | `0 4 * * 6` (sáb solamente) |
| Cron Quota reset | `30 1 * * *` (diario) | `30 1 * * *` (diario) — barato |
| Cron Watchdog LLM | `0 8 * * 2,5` (mar/vie 08:00) | `0 8 * * 6` (sáb 08:00) |

Resto de env vars: idénticas o equivalentes (mismas keys de OpenAI/Claude/Gemini/Perplexity, mismo encryption key, mismo Brevo SMTP).

---

## 5. Workflow de desarrollo: cómo desplegar a staging

### Paso a paso (con git desde tu terminal)

1. **Empieza desde una rama nueva basada en main**:
   ```
   git checkout main
   git pull origin main
   git checkout -b feature/mi-cambio
   ```

2. **Haces tus cambios, commiteas**.

3. **Mergea tu rama a staging** (PR o directo, según prefieras):
   ```
   git checkout staging
   git pull origin staging
   git merge feature/mi-cambio
   git push origin staging
   ```

4. **Railway auto-despliega staging** en ~2-3 minutos. El deploy aparece en el dashboard del environment staging.

5. **Pruebas en https://clicandseo.up.railway.app** que tu cambio funciona.

### Si prefieres usar PRs (más seguro)

1. Push de tu rama: `git push -u origin feature/mi-cambio`
2. `gh pr create --base staging --head feature/mi-cambio --title "..."` o desde la UI de GitHub.
3. Mergeas el PR contra staging → Railway despliega staging.

---

## 6. Cómo probar cosas en staging

### Probar el frontend
- Abre https://clicandseo.up.railway.app y navega normalmente.
- Login con cualquiera de las cuentas de test (revisa la tabla `users` en BD staging).

### Probar el flujo de pago Stripe
Ver sección 9 más abajo.

### Disparar un cron manualmente (sin esperar al sábado)
```bash
# Cron LLM Monitoring (todos los proyectos)
curl -X POST -H "Authorization: Bearer K7r#92pQx!bZ4wLm" \
  "https://clicandseo.up.railway.app/api/llm-monitoring/cron/daily-analysis?async=1"

# Cron Quota reset
curl -X POST -H "Authorization: Bearer K7r#92pQx!bZ4wLm" \
  "https://clicandseo.up.railway.app/api/cron/quota-reset?async=0"

# Health check
curl https://clicandseo.up.railway.app/api/llm-monitoring/health

# Watchdog
curl -X POST -H "Authorization: Bearer K7r#92pQx!bZ4wLm" \
  "https://clicandseo.up.railway.app/api/llm-monitoring/cron/watchdog"
```

### Probar una migración SQL
1. Aplica la migración a staging primero (conecta con `caboose.proxy.rlwy.net:13631`).
2. Verifica que no rompe nada.
3. Cuando confirmes, aplica a producción.

---

## 7. Cómo promover staging → main (producción)

### Workflow estándar (recomendado)

1. **Validas tu cambio en staging** (Paso 6).
2. **Creas un PR de staging → main**:
   ```
   gh pr create --base main --head staging --title "deploy: ..."
   ```
3. **Revisas el diff** en GitHub.
4. **Mergeas el PR**. Railway auto-despliega producción en 2-3 min.

### Workflow rápido (solo si el cambio es trivial y bien probado)

```
git checkout main
git pull origin main
git merge staging
git push origin main
```

→ Railway despliega producción inmediatamente.

⚠️ **Recomendación**: usa el flujo de PR para que quede registro en GitHub y puedas hacer rollback fácil si algo sale mal (`gh pr view <num>` → revert merge).

---

## 8. Cron schedules en staging

| Cron | Schedule | Frecuencia | Por qué así |
|---|---|---|---|
| `function-bun-LLMs` | `0 4 * * 6` | Sábado 06:00 Madrid | Coste: ~$2 por run de 7 proyectos. 1×/sem = ~$8/mes |
| `function-bun-AI-Mode` | `30 4 * * 6` | Sábado 06:30 Madrid | SerpAPI: barato. Espaciado para no concurrir |
| `function-bun-AI-Overview` | `0 5 * * 6` | Sábado 07:00 Madrid | Manual AI cron. Espaciado |
| `function-bun-Quota-Reset` | `30 1 * * *` | Diario 03:30 Madrid | Solo SQL, sin coste API. Necesario para que el flujo de cuotas funcione |
| `function-bun-LLM-Watchdog` | `0 8 * * 6` | Sábado 10:00 Madrid | 4h después del cron LLM. Detecta si el cron LLM no completó |
| `function-bun-model-discovery` | `0 9 1,15 * *` | Días 1 y 15 (bimensual) | Igual que prod |

### Si necesitas más frecuencia temporal (testing intensivo)

Cambia el schedule via Railway dashboard:
1. Entra al servicio (ej. `function-bun-LLMs`) en el environment `staging`.
2. Settings → Cron Schedule → cambia el valor.
3. Save → Railway re-deploya automáticamente.

O via API GraphQL (las mutaciones que usa Claude):
```graphql
mutation {
  serviceInstanceUpdate(
    serviceId: "f1c7d988-f9e7-4e36-8f66-c5267c5d51b0",
    environmentId: "3492b27c-9778-4183-a67a-17ff246c36c1",
    input: { cronSchedule: "0 4 * * *" }   # diario para testing rápido
  )
}
```

⚠️ **Acuérdate de volverlo a 1×/sem** cuando termines la prueba intensiva, o gastas dinero.

---

## 9. Stripe testing en staging

### Cómo está configurado

- `STRIPE_SECRET_KEY=sk_test_...` (modo test)
- `STRIPE_PUBLISHABLE_KEY=pk_test_...`
- `STRIPE_WEBHOOK_SECRET=whsec_ghEi...` (test webhook secret, **distinto** del de producción)
- `STRIPE_ENTERPRISE_PRODUCT_ID=prod_SwH1...` (producto de TEST en Stripe)
- `BILLING_ENABLED=false` (la app no enfuerza paywall en staging)

### Tarjetas de test que sí funcionan

Stripe acepta estas tarjetas en modo test:

| Tarjeta | Resultado |
|---|---|
| `4242 4242 4242 4242` | ✅ Pago exitoso (cualquier CVC, cualquier expiry futuro) |
| `4000 0027 6000 3184` | ✅ Pago exitoso con 3D Secure |
| `4000 0000 0000 9995` | ❌ Pago fallido — insufficient_funds |
| `4000 0000 0000 0341` | ⚠️ Pago éxito pero falla al renovar |

[Documentación completa de Stripe](https://stripe.com/docs/testing).

### Probar el flujo de webhook completo

1. **Stripe Dashboard (modo Test)** → Developers → Webhooks → tu endpoint staging.
2. Click "Send test webhook" → elige `customer.subscription.updated` (o cualquier evento).
3. Verifica que tu endpoint staging responde 200.
4. Verifica en BD staging que los datos se actualizaron.

### Probar el flujo end-to-end (signup + cobro)

1. Abre https://clicandseo.up.railway.app/signup
2. Regístrate con un email distinto al de prod.
3. Elige plan → te lleva a Stripe Checkout (modo test).
4. Usa tarjeta `4242 4242 4242 4242`.
5. Stripe te redirige de vuelta a staging app.
6. Verifica en BD staging que tu user tiene `plan` y `subscription_id` correctos.
7. (Opcional) En Stripe Dashboard, fuerza una renovación del cliente para probar `invoice.payment.succeeded`.

---

## 10. Datos de testing en BD staging

### Lo que hay ahora (snapshot)

- **21 usuarios** (18 plan free, 1 basic, 1 premium, 1 business)
- **3 proyectos LLM Monitoring**:
  - `id=10` "test" (inactivo)
  - `id=11` "[TEST locale] UK Banking Audit" (activo, brand=Monzo)
  - `id=12` "[TEST locale] FR Banques en ligne" (activo, brand=Boursorama)
- **2 proyectos manual_ai**
- **0 proyectos ai_mode**
- **288 análisis LLM** en `llm_monitoring_results` (8 abr → 16 may)

### Si necesitas más datos sintéticos

Pídeselo a Claude. Ejemplos de fixtures útiles:
- Un user con plan trial activo para probar el email "trial started".
- Un user con `current_period_end` próximo para probar el flujo de renovación.
- Un proyecto con `is_paused_by_quota=TRUE` para probar el resume.

---

## 11. Cómo "resetear" staging si se ensucia

### Limpieza ligera (datos de testing acumulados)

Conecta a la BD staging (`caboose.proxy.rlwy.net:13631` con la password de las env vars) y ejecuta:

```sql
-- Borrar resultados de análisis viejos (mantener últimos 30 días)
DELETE FROM llm_monitoring_results WHERE analysis_date < CURRENT_DATE - INTERVAL '30 days';

-- Borrar webhook events viejos
DELETE FROM stripe_webhook_events WHERE received_at < NOW() - INTERVAL '7 days';

-- Resetear quotas usadas (volver todos a cero)
UPDATE users SET quota_used = 0 WHERE quota_used > 0;
```

⚠️ **NO** borres rows de `users`, `llm_monitoring_projects` ni similares — perderás tu setup de testing.

### Limpieza completa (nuke and reset)

Solo si realmente necesitas empezar de cero. Conecta a staging DB y haz `TRUNCATE` selectivo. Recuerda mantener los users base (los 21 actuales) y los 3 proyectos test, o tendrás que recrearlos.

---

## 12. Troubleshooting y casos comunes

### "Mi cambio funciona en staging pero falla en producción"

Causas comunes:
1. **Env vars distintas**: revisa que no estés usando una env var que solo existe en staging.
2. **Datos distintos**: staging tiene 21 users con condiciones distintas que prod (141 users).
3. **Stripe live vs test**: prod usa Stripe live API que tiene comportamientos sutilmente distintos.

### "Staging arranca pero el cron LLM no se dispara nunca"

- Verifica que estás esperando al **sábado** (es 1×/sem en staging).
- O dispáralo manualmente con `curl` (sección 6).

### "Quiero ver los logs del backend staging"

```bash
railway environment staging
railway logs --service Clicandseo
```

O via dashboard: Railway → environment `staging` → service `Clicandseo` → Logs.

### "Necesito que staging sea idéntico a prod por un momento"

Sube temporalmente la frecuencia de los crones y activa alertas:
```bash
# En Railway dashboard → variables del environment staging
CRON_ALERTS_ENABLED=true
# Y cambia schedules de los crones via GraphQL o dashboard
```

⚠️ Vuelve a la config de bajo coste cuando termines.

---

## TL;DR para una futura sesión de Claude

1. **Staging es un entorno paralelo a prod**, con BD propia, Stripe TEST keys, `BILLING_ENABLED=false`, alertas off, crones 1×/sem los sábados.
2. **Workflow**: push a branch `staging` → Railway auto-despliega → probar en https://clicandseo.up.railway.app → mergear a `main` cuando OK.
3. **No conectar Stripe LIVE en staging jamás**.
4. **No copiar datos reales de clientes** a staging.
5. **Antes de tocar producción, valida en staging primero**.

— Fin del manual —
