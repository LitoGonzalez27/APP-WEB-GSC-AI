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

# Un sitio que cierra la puerta a todo acceso automatizado no pertenece a la
# escala: ponerle un 59.6 y la etiqueta "Agent-aware" (caso real: allegro.pl)
# describe lo poco que dejó medir, no lo que un agente encontraría. Y ponerle un
# 0 tampoco sería cierto cuando su llms.txt y su OAuth SÍ funcionan. Sale con
# veredicto propio y sin nota.
NIVEL_BLOQUEADO = {
    "emoji": "🚫",
    "name": "Puerta cerrada a agentes",
    "msg": ("El sitio no sirve contenido a accesos automatizados. Un agente de IA "
            "sale del mismo tipo de red que nosotros, así que se encontraría el "
            "mismo muro. No hay nota: lo que no se ha podido ver no se puntúa."),
    "sin_nota": True,
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


def level_for(score, bloqueado=False):
    """Veredicto. `bloqueado` = no se pudo ver el sitio (nivel de degradacion
    'total'): entonces no hay nota que interpretar, hay un muro que reportar.
    Nace aqui a proposito: web, PDF y JSON leen todos `level`, asi que el
    veredicto nuevo llega a los tres canales sin poder desincronizarse."""
    if bloqueado:
        return dict(NIVEL_BLOQUEADO)
    for lo, hi, emoji, name, msg in LEVELS:
        if lo <= score <= hi:
            return {"emoji": emoji, "name": name, "msg": msg}
    return {"emoji": "⚪", "name": "?", "msg": ""}
