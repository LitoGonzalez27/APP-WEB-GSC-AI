# 🔍 AUDITORÍA COMPLETA: SISTEMA ANTIGUO vs SISTEMA NUEVO

## 📋 Comparación de Endpoints

### Sistema Antiguo (manual_ai_system.py.backup)
Total endpoints identificados: **27**

| # | Endpoint | Método | Línea |
|---|----------|--------|-------|
| 1 | `/api/health` | GET | 83 |
| 2 | `/` | GET | 135 |
| 3 | `/api/projects` | GET | 146 |
| 4 | `/api/projects` | POST | 163 |
| 5 | `/api/projects/<id>` | GET | 207 |
| 6 | `/api/projects/<id>` | PUT | 227 |
| 7 | `/api/projects/<id>` | DELETE | 286 |
| 8 | `/api/projects/<id>/keywords` | GET | 368 |
| 9 | `/api/projects/<id>/keywords` | POST | 388 |
| 10 | `/api/projects/<id>/keywords/<kid>` | DELETE | 433 |
| 11 | `/api/projects/<id>/keywords/<kid>` | PUT | 654 |
| 12 | `/api/annotations` | POST | 512 |
| 13 | `/api/projects/<id>/notes` | POST | 589 |
| 14 | `/api/projects/<id>/analyze` | POST | 726 |
| 15 | `/api/projects/<id>/results` | GET | 821 |
| 16 | `/api/projects/<id>/stats` | GET | 847 |
| 17 | `/api/projects/<id>/ai-overview-table` | GET | 873 |
| 18 | `/api/projects/<id>/top-domains` | GET | 894 |
| 19 | `/api/projects/<id>/global-domains-ranking` | GET | 913 |
| 20 | `/api/projects/<id>/stats-latest` | GET | 939 |
| 21 | `/api/projects/<id>/ai-overview-table-latest` | GET | 990 |
| 22 | `/api/projects/<id>/download-excel` | POST | 1006 |
| 23 | `/api/projects/<id>/competitors-charts` | GET | 1076 |
| 24 | `/api/projects/<id>/comparative-charts` | GET | 1097 |
| 25 | `/api/projects/<id>/competitors` | GET | 1118 |
| 26 | `/api/projects/<id>/competitors` | PUT | 1183 |
| 27 | `/api/projects/<id>/export` | GET | 1310 |
| 28 | `/api/cron/daily-analysis` | POST | 2177 |

### Sistema Nuevo (manual_ai/)
Total endpoints verificados: **26**

| # | Endpoint | Método | Archivo |
|---|----------|--------|---------|
| 1 | `/api/health` | GET | routes/health.py |
| 2 | `/api/projects` | GET | routes/projects.py |
| 3 | `/api/projects` | POST | routes/projects.py |
| 4 | `/api/projects/<id>` | GET | routes/projects.py |
| 5 | `/api/projects/<id>` | PUT | routes/projects.py |
| 6 | `/api/projects/<id>` | DELETE | routes/projects.py |
| 7 | `/api/projects/<id>/keywords` | GET | routes/keywords.py |
| 8 | `/api/projects/<id>/keywords` | POST | routes/keywords.py |
| 9 | `/api/projects/<id>/keywords/<kid>` | DELETE | routes/keywords.py |
| 10 | `/api/projects/<id>/keywords/<kid>` | PUT | routes/keywords.py |
| 11 | `/api/projects/<id>/analyze` | POST | routes/analysis.py |
| 12 | `/api/projects/<id>/results` | GET | routes/results.py |
| 13 | `/api/projects/<id>/stats` | GET | routes/results.py |
| 14 | `/api/projects/<id>/ai-overview-table` | GET | routes/results.py |
| 15 | `/api/projects/<id>/top-domains` | GET | routes/results.py |
| 16 | `/api/projects/<id>/global-domains-ranking` | GET | routes/results.py |
| 17 | `/api/projects/<id>/stats-latest` | GET | routes/results.py |
| 18 | `/api/projects/<id>/ai-overview-table-latest` | GET | routes/results.py |
| 19 | `/api/projects/<id>/download-excel` | POST | routes/exports.py |
| 20 | `/api/projects/<id>/competitors-charts` | GET | routes/competitors.py |
| 21 | `/api/projects/<id>/comparative-charts` | GET | routes/competitors.py |
| 22 | `/api/projects/<id>/competitors` | GET | routes/competitors.py |
| 23 | `/api/projects/<id>/competitors` | PUT | routes/competitors.py |
| 24 | `/api/projects/<id>/export` | GET | routes/exports.py |
| 25 | `/api/cron/daily-analysis` | POST | routes/analysis.py |

## ⚠️ ENDPOINTS FALTANTES EN SISTEMA NUEVO

### 1. ❌ `/` (Dashboard Home)
- **Sistema Antiguo:** Línea 135
- **Sistema Nuevo:** NO EXISTE
- **Función:** `render_template('manual_ai_dashboard.html')`
- **Impacto:** BAJO - La ruta raíz probablemente se maneja desde app.py
- **Acción:** ✅ No necesario - El dashboard se renderiza desde otra ruta

### 2. ❌ `/api/annotations` (POST)
- **Sistema Antiguo:** Línea 512
- **Sistema Nuevo:** NO EXISTE
- **Función:** Crear anotaciones en eventos
- **Impacto:** MEDIO - Funcionalidad de notas/anotaciones
- **Acción:** ⚠️ VERIFICAR SI SE USA

### 3. ❌ `/api/projects/<id>/notes` (POST)
- **Sistema Antiguo:** Línea 589
- **Sistema Nuevo:** NO EXISTE
- **Función:** Agregar notas a proyectos
- **Impacto:** MEDIO - Funcionalidad de notas
- **Acción:** ⚠️ VERIFICAR SI SE USA

## ✅ ANÁLISIS DETALLADO

Ahora voy a verificar si estos endpoints faltantes son realmente usados...

