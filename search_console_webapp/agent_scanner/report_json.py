# -*- coding: utf-8 -*-
"""JSON estructurado del informe, optimizado para consumo por IA.

Frente al volcado crudo, este formato:
  - Se autodescribe (bloque `_meta` con qué es cada cosa y cómo leer los valores).
  - Normaliza los checks (estado legible + categoría con nombre + consejo desglosado).
  - Separa claramente: resumen · categorías · checks · hallazgos accionables ·
    competencia · pruebas agénticas · trazabilidad.
Así se puede pegar en un prompt y pedir "hazme un plan", "compara", "prioriza".
"""

# Los nombres de categoría viven en catalog.py, que es la fuente de verdad
# del catálogo de factores. Tenerlos duplicados en tres módulos era pedir
# que se desincronizaran al renombrar una categoría.
from .catalog import CATEGORIES as CAT_NAMES
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


def _bloque_llms(a):
    """Capa 2 del informe: qué pasó al soltar LLMs reales sobre la web.

    Se presenta aparte de la verificación de factores porque responde a otra
    pregunta y con otro tipo de evidencia: la capa 1 comprueba si los ficheros
    están y están bien; esta ejecuta una tarea y mira si se completa.
    """
    at = a.get("agent_tests")
    if not at:
        return {"ejecutada": False,
                "como_ejecutarla": "Pulsa «Simular agentes» en el informe (10-15 min).",
                "por_que_importa": ("La verificación de factores dice si tienes las "
                                    "piezas puestas; esta prueba dice si un agente "
                                    "real consigue completar la tarea.")}
    agentes = at.get("agents") or {}
    medidos = {k: v for k, v in agentes.items()
               if v.get("outcome") not in ("no_disponible", "no_verificable", None)}
    ciegos = [k for k, v in agentes.items() if v.get("outcome") == "no_verificable"]
    return {
        "ejecutada": True,
        "tarea": at.get("typology"),
        "hitos_de_la_tarea": at.get("hitos_tarea"),
        "modelos_usados": sorted(agentes),
        "repeticiones_por_modelo": at.get("repeticiones"),
        "resultado_por_modelo": {
            k: {"desenlace": v.get("outcome"),
                "intentos": v.get("intentos"),
                "exitos": v.get("exitos"),
                "consistencia_0_a_1": v.get("consistencia"),
                "recorrido": v.get("progreso"),
                "limite_de_nuestro_metodo": bool(v.get("limite_de_metodo")),
                "detalle": v.get("detail")}
            for k, v in agentes.items()},
        "sin_evidencia_por_bloqueo": ciegos,
        "lectura": ("Ningún modelo pudo ver la web: esta capa no aporta evidencia "
                    "ni a favor ni en contra." if not medidos else
                    "Compara este resultado con la nota de factores: una web puede "
                    "tener las piezas puestas y aun así atascar al agente."),
        "envio_de_formularios_reales": at.get("envios_reales", 0),
    }


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

    # Fiabilidad primero: si el sitio bloqueó el acceso, cualquier IA que consuma
    # este JSON debe toparse con el aviso ANTES que con la puntuación.
    parcial = bool((a.get("level") or {}).get("cobertura_parcial"))
    fiable = a.get("score_fiable", True)
    fiabilidad = {"puntuacion_fiable": fiable}
    deg = a.get("acceso_degradado")
    if deg:
        # El texto del aviso sale del veredicto (scoring.py) cuando lo hay: mismo
        # mensaje en web, PDF y JSON. "NO FIABLE: no usar" afirmaba de más — un
        # bloqueo desde nuestra red no es un veredicto sobre la web auditada.
        if parcial:
            aviso = ((a.get("level") or {}).get("msg")
                     or "No evaluable desde nuestra red: la nota cubre solo lo verificado")
        elif not fiable:
            aviso = ("Lectura limitada: parte del contenido no fue observable desde "
                     "nuestra red. Los factores afectados figuran como «no verificable», "
                     "no como fallo. La nota cubre lo que sí se pudo comprobar")
        else:
            aviso = ("Puntuación utilizable, con matiz: algunas sondas fueron "
                     "bloqueadas y esas ausencias concretas no son afirmables")
        fiabilidad.update({
            "aviso": aviso,
            "nivel_degradacion": deg.get("nivel"),
            "motivo": deg.get("motivo"),
            "factores_degradados_a_no_verificable": deg.get("degradados"),
            "http_acceso_humano": deg.get("human_status"),
            "via_de_lectura": deg.get("via"),
            "que_hacer": ("Repetir el análisis más tarde o desde otra red."
                          if not fiable else
                          "Los factores marcados 'no verificable' requieren revisión manual."),
        })

    return {
        "dominio": a.get("domain"),
        "host": a.get("host"),
        "fiabilidad": fiabilidad,
        "tipologia": a.get("typology"),
        "tipologia_evidencia": a.get("typology_evidence"),
        # Si el sitio nos cerró la puerta NO hay nota: se envía null en vez del
        # número, para que una IA que consuma esto no pueda promediarlo ni
        # compararlo con otros dominios como si midieran lo mismo.
        "puntuacion": {
            "global_0_a_100": a.get("score"),
            # La nota se entrega SIEMPRE, pero cuando la cobertura es parcial hay
            # que decirlo aquí mismo: ocultarla dejaba al cliente sin informe, y
            # darla sin contexto era el bug contrario.
            "cobertura_parcial": parcial,
            "aviso_cobertura": ((a.get("level") or {}).get("msg") if parcial else None),
            # qué fracción del modelo cubre la nota (1.0 = todo lo que aplica).
            # Baja cuando hubo categorías que no se pudieron medir.
            "cobertura_del_modelo": a.get("cobertura_score"),
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
        # DOS CAPAS SEPARADAS a propósito (ver `_meta.dos_capas`):
        #  1) verificación de factores -> todo lo de arriba, comprobación objetiva
        #  2) prueba con LLMs reales   -> esto, evidencia empírica aparte
        # Estaban mezcladas: el resultado de los agentes entraba en la nota como
        # un factor más (6.3) y no se leía como lo que es, una prueba de campo.
        "prueba_con_llms": _bloque_llms(a),
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
                "fiabilidad": "Cada dominio lleva un bloque 'fiabilidad'. Si "
                              "'puntuacion_fiable' es false, el sitio bloqueó nuestro acceso: "
                              "NO uses su puntuación ni lo compares contra otros. Los factores "
                              "no comprobables figuran como 'no_aplica_o_no_medido', no como fallo.",
                "dos_capas": {
                    "1_verificacion_de_factores": "Comprobación objetiva de qué tiene "
                        "la web y si está bien puesto (robots, llms.txt, datos "
                        "estructurados, formularios…). De aquí sale la puntuación.",
                    "2_prueba_con_llms": "Se sueltan modelos reales a completar una "
                        "tarea en la web y se mide qué consiguen. Va en "
                        "'prueba_con_llms' de cada dominio. Es evidencia empírica, "
                        "no una comprobación de ficheros: léelas por separado.",
                },
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

    # comparativa rápida ya calculada (evita que la IA tenga que derivarla).
    # Los dominios con puntuación no fiable quedan FUERA: comparar contra un
    # score construido a ciegas fabricaría brechas que no existen.
    excluidos = [c.get("host") for c in [client] + comps
                 if "error" not in (c or {}) and c.get("score_fiable") is False]
    validos = [a for a in [client] + [c for c in comps if "error" not in c]
               if a.get("score_fiable", True)]
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
        if excluidos:
            out["comparativa"]["excluidos_por_fiabilidad"] = {
                "hosts": excluidos,
                "motivo": ("Estos dominios bloquearon el análisis: su puntuación no es "
                           "comparable y se han dejado fuera para no fabricar brechas falsas."),
            }
    elif excluidos:
        out["comparativa_no_disponible"] = {
            "motivo": ("No hay suficientes dominios con puntuación fiable para comparar. "
                       f"Excluidos por bloqueo de acceso: {', '.join(h for h in excluidos if h)}."),
        }
    return out
