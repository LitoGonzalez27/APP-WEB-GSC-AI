# CLAUDE-enterprise-agencias.md — Clientes Enterprise / agencias (runbook)

> Manual operativo para **dar de alta, escalar y controlar** un cliente con plan a medida que funciona como agencia (varios clientes finales dentro de una sola cuenta). Todo se controla desde el panel admin, sin tocar código.
>
> Creado: 2026-09-11 (primer cliente: cuenta `accesos@albertopalazuelos.com`). Índice maestro: `CLAUDE-INDEX.md`. Base técnica: `CLAUDE-quota-system.md` §9.

---

## TL;DR en 1 minuto

- Un cliente enterprise es un usuario normal con `plan = 'enterprise'` y una serie de **números en el admin**: cuota RU, cuota LLM, topes de proyectos por módulo, topes de keywords/prompts por proyecto, y **límite y ciclo por proyecto**.
- Cuando el cliente pide más (otro proyecto, más consumo), **subes los números en el admin**. Efecto inmediato. Stripe no mueve estos números: son dos pasos manuales independientes.
- Cuando un proyecto agota **su** límite, se pausa **solo ese proyecto** hasta el próximo ciclo (30 días). Cuando el usuario agota su cuota global, se pausan todos los de ese módulo. Subir el límite reanuda.
- Todo lo de este manual vive en: `enterprise_limits.py` (topes por módulo), `project_quota.py` (límite y ciclo por proyecto), `admin_billing_panel.py` + `templates/admin_simple.html` (panel), `tests/test_enterprise_module_limits.py` + `tests/test_project_quota.py`.

---

## 1. Los tres niveles de control

| Nivel | Dónde se configura | Qué controla | Qué pasa al agotarse |
|---|---|---|---|
| **Usuario (cuota global)** | Admin → usuario → "Assign Custom Quota" → *Custom RU Limit* y *LLM units per month* | Consumo total de Manual AI + AI Mode (RU, contador compartido) y de LLM (units) en la ventana de 30 días | Se pausan **todos** los proyectos activos del módulo hasta el reset. Reset automático cada 30 días (cron) o al pagar en Stripe. |
| **Módulo (topes)** | Mismo modal → bloque *Project caps per module* | Máx. proyectos activos por módulo; máx. keywords/prompts por proyecto | No se puede crear ni reanudar un proyecto más (HTTP 402 con mensaje claro). Los pausados a mano no cuentan. |
| **Proyecto (límite y ciclo)** | Admin → usuario → ficha → tabla *Límite y ciclo por proyecto* | Tope propio de consumo del proyecto en la ventana y cada cuántos días lo analiza el cron | Se pausa **solo ese proyecto** hasta el próximo ciclo. Subir/quitar el límite desde el admin lo reanuda en el acto. |

La ventana es siempre la misma para los tres niveles: **30 días que terminan en `quota_reset_date`** del usuario. Al resetear, todos los contadores (usuario y proyectos) empiezan de cero.

---

## 2. Alta de un cliente nuevo (paso a paso)

1. El cliente crea su cuenta en la app (Google o email + contraseña). Queda en `free`.
2. `/admin` → buscar el email → botón **Assign Custom Quota**. Rellenar:

| Campo | Ejemplo cliente 5+5+5 | Cómo se calcula |
|---|---|---|
| Custom RU Limit per month | 3.500 | Manual AI: proyectos × kws × pasadas/mes. AI Mode: proyectos × prompts × pasadas/mes. Los crons de AI Overview y AI Mode corren **lun/jue/sáb (~13 pasadas/mes)**, no a diario. Suma y +35% (el AIO "collapsed" cuesta +1 RU y hay re-análisis manuales). Ej.: 5×30×13 + 5×10×13 = 2.600 → 3.500 |
| LLM max prompts per project | 10 | Lo pactado |
| LLM units per month | 2.400 | proyectos × prompts × nº LLMs × pasadas/mes + ~30%. El cron LLM corre **2 veces/semana (~cada 3 días, ~9 pasadas/mes)**, no a diario. Ej.: 5×10×4×9 = 1.800 → 2.400 |
| Manual AI: max projects / keywords | 5 / 30 | Lo pactado |
| AI Mode: max projects / prompts | 5 / 10 | Lo pactado |
| LLM Monitoring: max projects | 5 | Lo pactado |

3. Guardar. El usuario pasa a `enterprise`, `billing_status = active`. La primera pasada del cron diario le fija `quota_reset_date` a +30 días.
4. **Opcional, por proyecto**: cuando el cliente cree sus proyectos, abre su ficha y en la tabla *Límite y ciclo por proyecto* pon a cada uno su tope (p. ej. 500 RU ≈ 30 kws × 13 pasadas + margen; LLM 500 units ≈ 10 prompts × 4 LLMs × 9 pasadas + margen) y su frecuencia (1 = cada pasada del cron, 3 = cada 3 días).
5. **Facturación**:
   - **Stripe** (recomendado): crear en el Dashboard la suscripción con un precio colgado del **producto Enterprise** (`STRIPE_ENTERPRISE_PRODUCT_ID`) y el **mismo email** que la cuenta. Hacerlo **después** del paso 2 (si el webhook llega antes, el límite efectivo es 0 y pausaría todo). Cada cobro resetea la cuota; impago → `past_due`; cancelación → `free` y proyectos desactivados.
   - **Manual**: no hay paso 5. El cron resetea cada 30 días. Si deja de pagar: "Remove Custom Quota" (vuelve a free).

> ⚠️ Un precio de otro producto que no sea el Enterprise degrada al usuario a `free` en el webhook (`stripe_webhooks._get_plan_from_price_id`).

---

## 3. Escalar: "quiero un proyecto más para otro cliente"

1. Ficha del usuario → **Assign Custom Quota** → sube el tope del módulo (5 → 6) y la cuota (RU y/o units) en proporción. Guardar.
2. Cuando el cliente cree el proyecto nuevo, ponle su límite y su frecuencia en la tabla por proyecto.
3. Sube el precio en Stripe (o factura aparte). Independiente del paso 1.

Regla rápida por tramo de 5 proyectos con la configuración base: **+3.500 RU** y **+2.400 units**.

Si el cliente pausa a mano un proyecto, deja de contar para el tope del módulo y puede crear otro en su lugar (rotación de clientes finales sin pedirte nada).

---

## 4. Qué ve el cliente cuando choca con un límite

| Situación | Mensaje / efecto |
|---|---|
| Intenta crear el proyecto N+1 | 402: "You have reached the maximum number of active projects for your plan (5/5). Pause or delete a project..., or contact support". |
| Intenta añadir la keyword 31 | 400: "Project would exceed 30 keywords limit. Current: 30, Adding: 1". |
| Un proyecto agota **su** límite | Ese proyecto queda "paused by quota" hasta la fecha de reset (`paused_reason = project_quota_exceeded`). Los demás siguen. |
| El usuario agota la cuota global | Todos los proyectos del módulo en pausa hasta el reset (`paused_reason = quota_exceeded`). |
| Llega el reset (30 días) | Se despausa todo automáticamente (cron / webhook / auto-reanudación por `paused_until`). |

---

## 5. Cómo se mide el consumo por proyecto

- **Manual AI y AI Mode**: suma de `quota_usage_events.ru_consumed` con `metadata->>'project_id'` en la ventana. Incluye re-análisis manuales. El +1 RU del AIO "collapsed" va por `serp_api` sin proyecto: cuenta para el usuario, no para el proyecto.
- **LLM Monitoring**: filas de `llm_monitoring_results` del proyecto en la ventana (1 prompt × 1 LLM = 1 unit), igual que el contador por usuario.
- El gate por proyecto usa un contador local durante el análisis (consumo previo + gastado en este run), así que un run largo no se pasa del tope.
- **Frecuencia**: los crons saltan el proyecto si ya tiene resultados dentro de los últimos N días (`analysis_frequency_days`). Los crons de Manual AI / AI Mode corren lun/jue/sáb y el de LLM 2 veces/semana (~cada 3 días), así que frecuencia 1 = "cada pasada", no "cada día". Verificado con las fechas de resultados en prod (2026-09-11).

---

## 6. Verificar que funciona (checklist)

1. **Tests**: `python3 -m pytest tests/test_enterprise_module_limits.py tests/test_project_quota.py tests/test_quota_pauses_regression.py -q`.
2. **Ficha admin**: abrir el usuario → la tabla *Límite y ciclo por proyecto* lista sus proyectos con consumo `usado / límite`, estado y frecuencia. Guardar un límite → alerta "Guardado".
3. **Tope de proyectos**: con 5 activos, crear el sexto desde la app → 402 con el mensaje de arriba.
4. **Límite por proyecto**: poner límite 1 a un proyecto con consumo ≥ 1 y lanzar análisis → el proyecto queda pausado por `project_quota_exceeded`; subir el límite → reanudado (la fila cambia a "Activo").
5. **BD**: `SELECT id, name, monthly_ru_limit, analysis_frequency_days, is_paused_by_quota, paused_reason FROM manual_ai_projects WHERE user_id = <id>;`

---

## 7. Gotchas

- **Asignar la cuota antes que la suscripción Stripe** (ver §2.5).
- **Margen en las cuotas**: el gate es `usado + previsto > límite`. Un cliente se pausó al llegar exactamente a 640/640. Deja 10-25%.
- **RU compartidas**: Manual AI y AI Mode comparten el contador del usuario. Los límites por proyecto son la forma de que un proyecto no deje sin cuota a los demás.
- **Admins nunca se limitan** (`role = 'admin'`), ni por módulo ni por tope de keywords. Para probar límites usa un usuario no-admin.
- **Migraciones**: `migrate_enterprise_module_limits.py` y `migrate_project_quota_limits.py` son idempotentes y `init_database()` crea las mismas columnas al arrancar, así que un deploy nuevo no depende del orden. Staging migrado el 2026-09-11.
- **`remove_custom_quota`** vuelve al usuario a `free` y limpia todos los topes de usuario; **no** toca los límites por proyecto (quedan guardados por si vuelve).

---

## 8. Mapa de código

| Qué | Dónde |
|---|---|
| Topes por módulo (resolución pura) | `enterprise_limits.py` |
| Enforcement de topes | `manual_ai/routes/projects.py`, `ai_mode_projects/routes/projects.py` (create + resume), `manual_ai/routes/keywords.py`, `ai_mode_projects/routes/keywords.py`, `llm_monitoring_routes._get_effective_plan_limits`, `llm_monitoring_limits.get_llm_limits_summary`, cron LLM `services/llm_monitoring_service.py` |
| Límite y ciclo por proyecto | `project_quota.py`; gates en `manual_ai/services/analysis_service.py`, `ai_mode_projects/services/analysis_service.py`, `services/llm_monitoring/engine.py`; frecuencia LLM en `services/llm_monitoring_service.py` (Manual AI / AI Mode ya la tenían en sus `cron_service.py`) |
| Panel admin | `admin_billing_panel.assign_custom_quota` (+ `MODULE_LIMIT_FIELDS`), rutas en `auth.py` (`/admin/users/<id>/assign-custom-quota`, `/admin/users/<id>/project-limits`, `/admin/projects/<module>/<id>/limits`), UI en `templates/admin_simple.html` |
| Columnas BD | `users.custom_manual_ai_max_projects`, `custom_manual_ai_keywords_limit`, `custom_ai_mode_max_projects`, `custom_ai_mode_keywords_limit`, `custom_llm_max_projects` (+ `custom_quota_limit`, `custom_llm_prompts_limit`, `custom_llm_monthly_units_limit` previas); `manual_ai_projects.monthly_ru_limit`, `ai_mode_projects.monthly_ru_limit`, `llm_monitoring_projects.monthly_units_limit`, `llm_monitoring_projects.analysis_frequency_days` |
| Migraciones | `migrate_enterprise_module_limits.py`, `migrate_project_quota_limits.py` (ambas también en `database.init_database`) |
| Tests | `tests/test_enterprise_module_limits.py`, `tests/test_project_quota.py` |
