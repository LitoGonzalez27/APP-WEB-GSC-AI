# -*- coding: utf-8 -*-
"""Super prompt de rescate: cuando el scanner NO pudo leer un dominio (bloqueo
por IP que ni el VPS ni Jina esquivan — Shopify, Akamai…), genera un prompt
exhaustivo para que el usuario lo pegue en un LLM potente y complete el análisis.

Filosofía (idea de Carlos): la única IP que Shopify no bloquea es la del propio
cliente. El prompt es la versión que funciona hoy: el humano, con su navegador
de IP limpia, aporta lo que el servidor no pudo ver, y el LLM lo interpreta.

Dos garantías de FIDELIDAD, que son el alma del proyecto:
  1. El prompt ARRANCA de lo que el scanner YA verificó (no de cero): esos
     factores van con su evidencia real y NO se re-evalúan.
  2. El prompt PROHÍBE inventar: para cada factor pendiente exige citar la
     evidencia observada, o declararlo "no verificable". Un informe con números
     sin evidencia es justo el falso positivo que perseguimos.

Se genera desde las fuentes de verdad del código (catálogo, base de
conocimiento, tareas agénticas, escala), así que refleja SIEMPRE los factores
reales y su metodología: si se añade o cambia un factor, el prompt se actualiza
solo.
"""
from .catalog import CHECKS, CATEGORIES
from .knowledge import KB
from .scoring import LEVELS


def _escala():
    filas = [f"  {lo}-{hi}: {name} — {msg}" for lo, hi, _e, name, msg in LEVELS]
    return "\n".join(filas)


def _tarea_agentica(typology):
    """La prueba de comportamiento agéntico (check 6.3): la tarea real y sus
    hitos, tal como los ejecuta el harness de agentes. Que el LLM la reproduzca
    o describa paso a paso con la web delante."""
    from .agents import MILESTONES, datos_prueba
    tareas = {
        "ecommerce": ("Act as a user's shopping agent: search for a product in "
                      "the catalog, open it, add it to the cart, open the cart and "
                      "proceed to checkout. Do NOT complete the payment or enter "
                      "card details: describe how far an agent gets and where it "
                      "gets stuck."),
        "saas": ("Act as an agent: find the pricing page, identify the cheapest "
                 "paid plan and start signing up for it. Do NOT create an account "
                 "or enter payment details: describe how far you get and where "
                 "the flow breaks."),
        "corporativo": ("Act as an agent: find the contact page, identify a phone "
                        "number or email, and find the form. Do NOT submit anything: "
                        "describe whether an agent could fill it in and operate it, "
                        "and what would stop it."),
    }
    hitos = [m["nombre"] for m in MILESTONES.get(typology, MILESTONES["corporativo"])]
    return tareas.get(typology, tareas["corporativo"]), hitos


# Factores que miden la HOSTILIDAD al acceso automatizado (el bloqueo mismo).
# El engine los deja FUERA de CHECKS_POR_AUSENCIA a propósito (engine.py ~684):
# que el sitio nos bloquee ES el hallazgo, no ruido. Son los únicos que NO se
# delegan al LLM cuando hay bloqueo fuerte: el LLM navega con IP limpia y a él
# NO le bloquean, así que reproducirlos daría un falso "no bloquea" y perdería
# el hallazgo real (a un agente/IP de datacenter sí le cierran la puerta).
ACCESO_CONFIRMA_BLOQUEO = {"1.6", "2.4", "4.4"}


def _bloque_factores(client):
    """Un bloque por categoría con los 40 factores.

    Regla de delegación (idea de Carlos: si el scanner se bloqueó, TODO el
    análisis pasa al LLM, sin excepción):
      · sin bloqueo o solo "sondas" → se reutiliza lo que el scanner verificó
        fiablemente y solo se piden los pendientes.
      · bloqueo "total"/"marcado" → NO nos fiamos de lo que "vimos": TODOS los
        factores se delegan al LLM, salvo los de hostilidad de acceso, que el
        bloqueo confirma de primera mano y el LLM no puede reproducir.
    """
    por_check = {c["id"]: c for c in (client.get("checks") or [])}
    nivel = (client.get("acceso_degradado") or {}).get("nivel")
    bloqueo_fuerte = nivel in ("total", "marcado")
    partes = []
    for cat_id, cat_nombre in CATEGORIES.items():
        factores_cat = [c for c in CHECKS if c[1] == cat_id]
        if not factores_cat:
            continue
        partes.append(f"\n### {cat_id} · {cat_nombre}")
        for cid, _cat, nombre, desc in factores_cat:
            kb = KB.get(cid, {})
            como = kb.get("como", "")
            res = por_check.get(cid)
            partes.append(f"\n[{cid}] {nombre}")
            partes.append(f"  · What it measures: {desc}")
            if como:
                partes.append(f"  · Passes (score 1) when: {como}")
            verificado = (res and res.get("score") is not None
                          and not res.get("manual"))
            if bloqueo_fuerte and cid in ACCESO_CONFIRMA_BLOQUEO and res \
                    and res.get("score") is not None:
                # dato de campo: el bloqueo lo prueba, y el LLM no lo reproduce
                partes.append(f"  · ✓ CONFIRMED IN THE FIELD (score {res['score']}): the site "
                              f"blocked our automated access. {str(res.get('evidence'))[:180]}")
                partes.append("    → Do NOT re-evaluate it or raise it: you may not be blocked, "
                              "but the finding is that an agent/datacenter IP IS.")
            elif verificado and not bloqueo_fuerte:
                # el scanner SÍ lo verificó con fiabilidad: se da hecho
                partes.append(f"  · ✓ ALREADY VERIFIED by the scanner (score {res['score']}): "
                              f"{str(res.get('evidence'))[:220]}")
                partes.append("    → Do NOT re-evaluate it: use this result as is.")
            else:
                partes.append("  · ⧗ PENDING: complete it yourself with the site in front of you. "
                              "Score 1 (passes) / 0.5 (partial) / 0 (fails) / N/A (not applicable "
                              "to this type of business). QUOTE the exact evidence you see; "
                              "if you can't observe it, write «not verifiable».")
    return "\n".join(partes)


def _competidores_validos(data):
    """Competidores que sí se pueden auditar (los que fallaron traen 'error')."""
    return [c for c in (data.get("competitors") or [])
            if c and not c.get("error") and c.get("host")]


def _bloque_competidores(competitors):
    """Si el cliente añadió competidores, el LLM también los audita: la comparativa
    ES el entregable de esta herramienta. Cada competidor lleva sus 40 factores con
    la MISMA regla de delegación (reusa _bloque_factores, que mira el nivel de
    bloqueo de cada dominio por separado: uno puede estar bloqueado y otro no)."""
    validos = _competidores_validos({"competitors": competitors})
    if not validos:
        return ""
    partes = [f"""
═══════════════════════════════════════════════════════════════════════
COMPETITORS — AUDIT THEM TOO ({len(validos)}). The comparison is the deliverable.
═══════════════════════════════════════════════════════════════════════
The client added competitors to compare against. Apply EXACTLY the same fidelity
rules and the same 0-100 scale to them: the 40 factors, reusing what is «ALREADY
VERIFIED»/«CONFIRMED IN THE FIELD» and completing the «PENDING» ones with the site
in front of you. For each competitor's factor 6.3, reproduce the same agentic task
described above but on THEIR site. Without a comparison against the client there
is no report."""]
    for i, comp in enumerate(validos, 1):
        chost = comp.get("host", "competitor")
        ctyp = comp.get("typology", "corporativo")
        partes.append(f"""
───────────────────────────────────────────────────────────────────────
COMPETITOR {i}: {chost}  (site type: {ctyp})
───────────────────────────────────────────────────────────────────────
{_bloque_factores(comp)}""")
    return "\n".join(partes)


def construir(data):
    """Genera el super prompt a partir del resultado del análisis."""
    client = data.get("client") or {}
    host = client.get("host", "the domain")
    typ = client.get("typology", "corporativo")
    cob = client.get("cobertura_score")
    deg = client.get("acceso_degradado") or {}
    nivel = deg.get("nivel")
    bloqueo_fuerte = nivel in ("total", "marcado")
    tarea, hitos = _tarea_agentica(typ)
    cob_txt = (f"{round(cob * 100)}%" if isinstance(cob, (int, float)) else "partial")

    comp_validos = _competidores_validos(data)
    comp_hosts = [c["host"] for c in comp_validos]
    con_comp = (f" The client added {len(comp_hosts)} competitor(s) to compare "
                f"against ({', '.join(comp_hosts)}): you must audit them TOO "
                f"(their section is further down) — the comparison is the goal."
                if comp_hosts else "")

    # En bloqueo fuerte NO nos fiamos de lo poco que "vimos": el análisis entero
    # pasa al LLM. En bloqueo leve (sondas) sí se reutiliza lo verificado.
    if bloqueo_fuerte:
        encargo = f"""You must carry out the FULL audit of the domain **{host}** (detected
site type: {typ}). An automated tool tried, but the site BLOCKED its access by
IP (typical of Shopify/Akamai/Cloudflare): it couldn't read the site reliably,
so we accept almost nothing of what it thought it saw. YOU evaluate the 40
factors, one by one, with the site in front of you.

IMPORTANT: the tool was blocked for using a datacenter IP; you, with a clean IP,
will probably be let IN by the site. Make the most of it. The ONLY exception is
the factors marked «CONFIRMED IN THE FIELD» (hostility to access): the tool
experienced those first-hand and it won't happen to you, so respect them as they
are — don't lower them just because the site lets you in.{con_comp}"""
    else:
        encargo = f"""You must complete the audit of the domain **{host}** (detected site type:
{typ}). An automated tool already verified {cob_txt} of the model remotely
(robots, sitemap, headers, DNS, .well-known) and left pending what requires
seeing the rendered content. YOU complete the pending factors.{con_comp}"""

    return f"""You are an expert auditor of websites' AGENT READINESS: you measure
whether an AI agent (ChatGPT, Claude, Perplexity, a shopping assistant…) can
FIND, READ, INTERPRET and USE a website. This isn't classic SEO: it's whether
an agent can operate the site.

{encargo}

═══════════════════════════════════════════════════════════════════════
FIDELITY RULES — NON-NEGOTIABLE. A CMO is going to hand this report to their
technical team: a made-up data point does real damage.
═══════════════════════════════════════════════════════════════════════
1. Do NOT make ANYTHING up. For each pending factor, QUOTE the specific evidence
   you observe (the tag, the text, the file). If you can't observe it, write
   literally «not verifiable» — never a number by eye.
2. The factors marked «ALREADY VERIFIED» or «CONFIRMED IN THE FIELD» were
   measured by the tool with real evidence: use them as they are, do NOT
   re-evaluate them. Everything marked «PENDING» is for you to evaluate.
3. To SEE the content: try to open {host} yourself. If your access is also
   blocked, ASK the user to paste here the HTML of the home page and of a key
   page (a product page if it's a store, the pricing page if it's SaaS, the
   contact page if it's corporate). Work only with what you have in front of you.
4. Score each factor: 1 = passes · 0.5 = partial · 0 = fails · N/A = not
   applicable to this type of business.

═══════════════════════════════════════════════════════════════════════
THE 40 FACTORS (the ✓ ones are done; complete the ⧗ ones)
═══════════════════════════════════════════════════════════════════════
{_bloque_factores(client)}

═══════════════════════════════════════════════════════════════════════
REAL AGENTIC BEHAVIOR (factor 6.3 — the most important one)
═══════════════════════════════════════════════════════════════════════
With the site in front of you, reproduce what an agent would do:
{tarea}
Milestones to reach along the way (mark which are achieved and where it gets stuck):
{chr(10).join('  · ' + h for h in hitos)}
Describe the journey STEP BY STEP and at which link it breaks (that break is the
finding). An agent gets lost when a control has no clear name, when it presses
something and what it expected doesn't happen, or when a flow requires sign-up/JS.
{_bloque_competidores(comp_validos)}
═══════════════════════════════════════════════════════════════════════
DELIVERY — ALWAYS A PDF REPORT
═══════════════════════════════════════════════════════════════════════
Deliver the result as a downloadable PDF DOCUMENT, without asking about the format
or offering alternatives: generate it directly. If your environment can't produce
a PDF, deliver it as COMPLETE Markdown ready to export to PDF (and say so in one
line), but never stop at just asking. The report must contain:
1. Verdict and estimated 0-100 score for the client ({host}), using this scale:
{_escala()}
2. Table of the client's 40 factors: id · name · score · evidence (or «not verifiable»).
3. Summary of agentic behavior: how far an agent gets and why it gets stuck.
4. The 3-5 fixes with the highest impact and lowest effort.{_bloque_entrega_comp(comp_hosts, host)}
Remember: every score, with its observed evidence. No evidence, «not verifiable».
""".strip()


def _bloque_entrega_comp(comp_hosts, host):
    """Punto extra de la entrega cuando hay competidores: nota de cada uno y la
    comparativa cliente↔competidores, que es el valor diferencial del análisis."""
    if not comp_hosts:
        return ""
    return (f"""
5. 0-100 score and table of the 40 factors for each competitor ({', '.join(comp_hosts)}),
   with the same evidence requirement.
6. COMPARISON {host} vs competitors: table by category (C1-C7) with each domain's
   score, who wins each category, and the gaps where the client LOSES to a
   competitor and why (that's the actionable finding).""")
