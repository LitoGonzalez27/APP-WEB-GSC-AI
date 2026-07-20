"""Scoring 0-100 segun la seccion 11 del informe.

Pesos por categoria segun tipologia. C7 solo puntua en e-commerce;
en el resto su peso se redistribuye proporcionalmente.
Los checks con score None (N/A o manuales sin medida) no puntuan.
"""

WEIGHTS = {
    "generico": {"C1": 18, "C2": 10, "C3": 20, "C4": 17, "C5": 20, "C6": 15},
    "ecommerce": {"C1": 15, "C2": 8, "C3": 18, "C4": 14, "C5": 15, "C6": 12, "C7": 18},
}

# peso relativo de cada check dentro de su categoria (los criticos pesan mas)
CHECK_WEIGHTS = {
    "1.1": 2, "1.2": 3, "1.3": 3, "1.4": 2, "1.5": 1, "1.6": 3, "1.7": 1,
    "2.1": 2, "2.2": 2, "2.3": 1, "2.4": 2,
    "3.1": 3, "3.2": 3, "3.3": 3, "3.4": 2, "3.5": 2, "3.6": 2,
    "4.1": 4, "4.2": 3, "4.3": 2, "4.4": 2, "4.5": 2, "4.6": 1, "4.7": 2, "4.8": 2,
    "5.1": 3, "5.2": 3, "5.3": 3, "5.5": 1, "5.6": 2,
    "6.1": 3, "6.2": 2, "6.3": 3, "6.4": 2,  # 6.3 puntua cuando corren los agentes reales
    "7.1": 3, "7.2": 4, "7.3": 2, "7.4": 0,  # 7.4 informativo: nunca puntua
    "7.5": 2, "7.6": 2,
}

LEVELS = [
    (0, 25, "🔴", "Invisible para agentes", "Ni te leen ni te usan. Riesgo alto."),
    (26, 50, "🟠", "Legible, no operable", "Te leen, no te entienden bien, no te usan."),
    (51, 75, "🟡", "Agent-aware", "Bien posicionado; faltan capacidades ejecutables."),
    (76, 100, "🟢", "Agent-ready", "Ventaja competitiva real. A mantener trimestralmente."),
]

# Dos situaciones que ANTES se confundían en un solo veredicto, y no son lo
# mismo ni de lejos (caso real: argal.com y noel.es salían "puerta cerrada" en
# producción y desde otra red servían 136 KB y 85 KB sin problema).
#
# 1) PUERTA CERRADA: sí vimos la web con UA de navegador, y vimos cómo rechaza
#    a los bots de IA. Es un hallazgo AGÉNTICO y está evidenciado: tenemos las
#    dos mitades de la prueba.
NIVEL_PUERTA_CERRADA = {
    "emoji": "🚫",
    "name": "Puerta cerrada a agentes",
    "msg": ("La web se sirve con normalidad a un navegador, pero rechaza a los "
            "bots de IA. No es un problema de nuestra red: hemos visto las dos "
            "caras. Un agente que intente leerla se topa con el muro."),
}
# 2) NO EVALUABLE: nos bloquearon a NOSOTROS, y también a los bots de IA que
#    probamos. No podemos distinguir "bloquea toda automatización" de "bloquea
#    el rango de IPs desde el que escaneamos". Afirmar lo primero sería inventar:
#    la nota se entrega con lo que sí se pudo verificar y su cobertura a la vista.
NIVEL_NO_EVALUABLE = {
    "emoji": "⚠️",
    "name": "No evaluable desde nuestra red",
    "msg": ("No hemos podido leer el contenido desde donde escaneamos. Puede ser "
            "que el sitio bloquee toda automatización, o solo el rango de IPs de "
            "nuestro servidor: no podemos distinguirlo, así que no lo afirmamos. "
            "La nota cubre únicamente lo verificado (robots, sitemap, cabeceras, "
            ".well-known, DNS); mira el porcentaje de cobertura antes de usarla."),
    "cobertura_parcial": True,
}


def category_scores(results):
    """Media ponderada de los checks puntuables por categoria -> 0..1"""
    cats = {}
    for r in results:
        if r["score"] is None:
            continue
        w = CHECK_WEIGHTS.get(r["id"], 1)
        if w == 0:
            continue
        cats.setdefault(r["cat"], []).append((r["score"], w))
    return {
        cat: round(sum(s * w for s, w in vals) / sum(w for _, w in vals), 4)
        for cat, vals in cats.items()
    }


def total_score(results, typology):
    """Nota 0-100. Devuelve (total, scores por categoria, pesos, cobertura).

    "No aplica" y "no lo se" NO son lo mismo, y tratarlos igual inflaba la nota
    de los sitios opacos. El peso de una categoria que no aplica (C7 en una web
    corporativa: no tiene fichas de producto) SI se reparte entre las demas,
    porque no hay nada que medir ahi y la nota sigue siendo sobre 100. El peso
    de una categoria que no pudimos medir NO se reparte: repartirlo hacia
    aumentar el valor de lo poco que quedaba en pie.

    Caso real (bateria 6, allegro.pl): nos bloqueo entera la categoria de datos
    estructurados (C3, peso 20). Su peso se repartio entre las demas, que
    subieron un 25%, y las dos que allegro tenia perfectas (llms.txt y OAuth)
    pasaron a aportar 43.75 de 64.6 puntos. Cuanto menos podiamos medir, mas
    pesaba lo poco medido. Ahora esos 20 puntos se quedan fuera del alcanzable
    y `cobertura` dice que la nota solo cubre el 80% del modelo.
    """
    mode = "ecommerce" if typology == "ecommerce" else "generico"
    weights = dict(WEIGHTS[mode])
    cat_scores = category_scores(results)
    # categorias perdidas por CEGUERA nuestra, no por no aplicar
    ciegas = {r["cat"] for r in results if r.get("no_verificable")} - set(cat_scores)
    active = {c: w for c, w in weights.items() if c in cat_scores}
    na_weight = sum(w for c, w in weights.items()
                    if c not in cat_scores and c not in ciegas)
    if active and na_weight:
        boost = na_weight / sum(active.values())
        active = {c: w * (1 + boost) for c, w in active.items()}
    total = sum(cat_scores[c] * w for c, w in active.items())
    # cuanto del modelo cubre de verdad esta nota (1.0 = todo lo que aplica)
    alcanzable = sum(active.values())
    cobertura = round(alcanzable / 100, 4) if alcanzable else 0.0
    return round(total, 1), cat_scores, active, cobertura


def apply_governance_gate(total, results, typology):
    """Penalizaciones de la puerta de seguridad (seccion 11)."""
    penalties = []
    by_id = {r["id"]: r for r in results}
    if typology == "ecommerce" and by_id.get("7.2", {}).get("inconsistent"):
        penalties.append(("Precio inconsistente (riesgo de alucinacion)", -10))
    if by_id.get("1.2", {}).get("score") == 0.5:
        penalties.append(("Sin politica de bots documentada", -5))
    adjusted = max(0, total + sum(p for _, p in penalties))
    return round(adjusted, 1), penalties


def level_for(score, bloqueado=False, veredicto=None):
    """Veredicto. `veredicto` fuerza uno de los especiales:
      'puerta_cerrada' -> vimos la web y la vimos rechazar bots de IA.
      'no_evaluable'   -> no pudimos leerla desde nuestra red; la nota es parcial
                          y se entrega con su cobertura, no se oculta.
    Nace aqui a proposito: web, PDF y JSON leen todos `level`, asi que el
    veredicto llega a los tres canales sin poder desincronizarse.
    `bloqueado` se mantiene por compatibilidad y equivale a 'no_evaluable'."""
    if veredicto == "puerta_cerrada":
        return dict(NIVEL_PUERTA_CERRADA)
    if veredicto == "no_evaluable" or bloqueado:
        return dict(NIVEL_NO_EVALUABLE)
    for lo, hi, emoji, name, msg in LEVELS:
        if lo <= score <= hi:
            return {"emoji": emoji, "name": name, "msg": msg}
    return {"emoji": "⚪", "name": "?", "msg": ""}
