# -*- coding: utf-8 -*-
"""JSON estructurado del informe, optimizado para consumo por IA.

Frente al volcado crudo, este formato:
  - Se autodescribe (bloque `_meta` con qué es cada cosa y cómo leer los valores).
  - Normaliza los checks (estado legible + categoría con nombre + consejo desglosado).
  - Separa claramente: resumen · categorías · checks · hallazgos accionables ·
    competencia · pruebas agénticas · trazabilidad.
Así se puede pegar en un prompt y pedir "hazme un plan", "compara", "prioriza".
"""

CAT_NAMES = {
    "C1": "Descubribilidad y acceso", "C2": "Identidad y control de bots",
    "C3": "Datos estructurados", "C4": "Renderizado y arquitectura",
    "C5": "Contenido para LLMs", "C6": "Capacidades y acciones",
    "C7": "Comercio agéntico",
}
STAGES = [("leer", "¿Te leen?", ["C1", "C2"]),
          ("entender", "¿Te entienden?", ["C3", "C4", "C5"]),
          ("usar", "¿Pueden usarte?", ["C6", "C7"])]


def _estado(score, manual=False):
    if score is None:
        return "no_aplica_o_no_medido"
    if score >= 1:
        return "cumple"
    if score > 0:
        return "parcial"
    return "falla"


def _domain_block(a):
    if not a or "error" in (a or {}):
        return {"error": (a or {}).get("error", "sin datos"), "domain": (a or {}).get("domain")}
    cats = a.get("category_scores") or {}
    checks = []
    for c in a.get("checks") or []:
        item = {
            "id": c.get("id"),
            "nombre": c.get("name"),
            "categoria": c.get("cat"),
            "categoria_nombre": CAT_NAMES.get(c.get("cat")),
            "estado": _estado(c.get("score")),
            "puntuacion_0_a_1": c.get("score"),
            "evidencia": c.get("evidence"),
            "requiere_revision_humana": bool(c.get("manual")),
        }
        adv = c.get("advice")
        if adv:
            item["accion"] = {
                "titulo": adv.get("titulo"),
                "por_que_importa": adv.get("por_que"),
                "como_se_arregla": adv.get("como"),
                "impacto": adv.get("impacto"),
                "esfuerzo": adv.get("esfuerzo"),
            }
        checks.append(item)

    etapas = {}
    for key, label, cs in STAGES:
        vals = [cats[c] for c in cs if c in cats]
        if vals:
            etapas[key] = {"pregunta": label, "categorias": cs,
                           "porcentaje": round(sum(vals) / len(vals) * 100)}

    return {
        "dominio": a.get("domain"),
        "host": a.get("host"),
        "tipologia": a.get("typology"),
        "tipologia_evidencia": a.get("typology_evidence"),
        "puntuacion": {
            "global_0_a_100": a.get("score"),
            "antes_de_penalizaciones": a.get("score_pre_gate"),
            "penalizaciones": [{"motivo": p[0], "puntos": p[1]} for p in (a.get("penalties") or [])],
            "nivel": (a.get("level") or {}).get("name"),
            "nivel_significado": (a.get("level") or {}).get("msg"),
        },
        "categorias": {c: {"nombre": CAT_NAMES.get(c), "porcentaje": round(v * 100),
                           "peso_en_score": (a.get("category_weights") or {}).get(c)}
                       for c, v in cats.items()},
        "viaje_del_agente": etapas,
        "resumen_checks": {
            "total": len(checks),
            "cumplen": sum(1 for c in checks if c["estado"] == "cumple"),
            "parciales": sum(1 for c in checks if c["estado"] == "parcial"),
            "fallan": sum(1 for c in checks if c["estado"] == "falla"),
            "no_aplican": sum(1 for c in checks if c["estado"] == "no_aplica_o_no_medido"),
        },
        "checks": checks,
        "hallazgos_accionables": [c for c in checks if c.get("accion")],
        "acceso_de_bots_ia": a.get("bot_matrix"),
        "superficie_agentica_encontrada": list((a.get("wellknown") or {}).keys()),
        "paginas_muestreadas": a.get("pages_sampled"),
        "cobertura": a.get("coverage"),
        "pruebas_agenticas": a.get("agent_tests"),
        "trazabilidad_procesos": a.get("trail"),
    }


def build_json(data):
    client = data.get("client") or {}
    comps = data.get("competitors") or []
    out = {
        "_meta": {
            "informe": "Agent Readiness — auditoría de preparación de una web para la era agéntica",
            "generado_por": "Clicandseo · Agent-Ready Scanner",
            "generado_en": data.get("generated"),
            "framework": data.get("framework_version"),
            "como_leer_esto": {
                "puntuacion": "0-100. 0-25 invisible para agentes · 26-50 legible pero no operable · "
                              "51-75 agent-aware · 76-100 agent-ready.",
                "checks": "Cada check tiene estado (cumple/parcial/falla/no_aplica_o_no_medido), "
                          "evidencia bruta y, si no se cumple, un bloque 'accion' con por qué "
                          "importa y cómo se arregla.",
                "categorias": "C1 acceso · C2 control de bots · C3 datos estructurados · "
                              "C4 renderizado · C5 contenido para LLMs · C6 capacidades/acciones · "
                              "C7 comercio agéntico.",
                "viaje_del_agente": "Continuum leer → entender → usar. La cadena se rompe en el "
                                    "eslabón más débil.",
                "trazabilidad_procesos": "Qué procesos corrieron y con qué evidencia. status ok/warn/"
                                         "fail/skipped. Un 404 del sitio es un hallazgo, no un fallo "
                                         "del análisis.",
                "sugerencias_de_uso_con_ia": [
                    "Genera un plan de implementación priorizado por impacto/esfuerzo a partir de 'hallazgos_accionables'.",
                    "Redacta tickets técnicos usando 'accion.como_se_arregla' y 'evidencia' de cada check.",
                    "Compara 'cliente' contra 'competidores' categoría a categoría y explica las brechas.",
                    "Estima el score alcanzable si se resuelven solo los hallazgos de esfuerzo Bajo.",
                ],
            },
        },
        "cliente": _domain_block(client),
        "competidores": [_domain_block(c) for c in comps],
    }

    # comparativa rápida ya calculada (evita que la IA tenga que derivarla)
    validos = [client] + [c for c in comps if "error" not in c]
    if len(validos) > 1:
        comparativa = {}
        for cat in CAT_NAMES:
            fila = {}
            for a in validos:
                v = (a.get("category_scores") or {}).get(cat)
                if v is not None:
                    fila[a.get("host")] = round(v * 100)
            if fila:
                comparativa[cat] = {"nombre": CAT_NAMES[cat], "porcentajes": fila}
        brechas = []
        for cat, info in comparativa.items():
            mine = info["porcentajes"].get(client.get("host"))
            if mine is None:
                continue
            for host, val in info["porcentajes"].items():
                if host != client.get("host") and val - mine >= 15:
                    brechas.append({"categoria": cat, "nombre": CAT_NAMES[cat],
                                    "competidor": host, "su_valor": val,
                                    "tu_valor": mine, "diferencia": val - mine})
        out["comparativa"] = {
            "puntuaciones_globales": {a.get("host"): a.get("score") for a in validos},
            "por_categoria": comparativa,
            "brechas_donde_te_superan": brechas,
        }
    return out
