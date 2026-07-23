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
        "ecommerce": ("Como si fueras un agente de compra de un usuario: busca un "
                      "producto del catálogo, ábrelo, añádelo al carrito, abre el "
                      "carrito y avanza hasta el checkout. NO completes el pago ni "
                      "introduzcas datos de tarjeta: describe hasta dónde llega un "
                      "agente y dónde se atasca."),
        "saas": ("Como si fueras un agente: encuentra la página de precios, "
                 "identifica el plan de pago más barato e inicia su contratación. "
                 "NO crees cuenta ni introduzcas datos de pago: describe hasta "
                 "dónde llega y dónde se rompe el flujo."),
        "corporativo": ("Como si fueras un agente: localiza la página de contacto, "
                        "identifica un teléfono o email, y localiza el formulario. "
                        "NO envíes nada: describe si un agente podría rellenarlo y "
                        "operarlo, y qué se lo impediría."),
    }
    hitos = [m["nombre"] for m in MILESTONES.get(typology, MILESTONES["corporativo"])]
    return tareas.get(typology, tareas["corporativo"]), hitos


def _bloque_factores(client):
    """Un bloque por categoría con los 40 factores: los verificados con su
    evidencia real (no re-evaluar) y los pendientes con su metodología."""
    por_check = {c["id"]: c for c in (client.get("checks") or [])}
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
            partes.append(f"  · Qué mide: {desc}")
            if como:
                partes.append(f"  · Se cumple (nota 1) cuando: {como}")
            if res and res.get("score") is not None and not res.get("manual"):
                # el scanner SÍ lo verificó: se da hecho, con su evidencia real
                partes.append(f"  · ✓ YA VERIFICADO por el scanner (nota {res['score']}): "
                              f"{str(res.get('evidence'))[:220]}")
                partes.append("    → NO lo reevalúes: usa este resultado tal cual.")
            else:
                partes.append("  · ⧗ PENDIENTE: complétalo tú con la web delante. Puntúa "
                              "1 (cumple) / 0,5 (parcial) / 0 (no cumple) / N/A (no aplica "
                              "a este tipo de negocio). CITA la evidencia exacta que ves; "
                              "si no puedes observarlo, escribe «no verificable».")
    return "\n".join(partes)


def construir(data):
    """Genera el super prompt a partir del resultado del análisis."""
    client = data.get("client") or {}
    host = client.get("host", "el dominio")
    typ = client.get("typology", "corporativo")
    cob = client.get("cobertura_score")
    deg = client.get("acceso_degradado") or {}
    tarea, hitos = _tarea_agentica(typ)
    cob_txt = (f"{round(cob * 100)}%" if isinstance(cob, (int, float)) else "parcial")

    return f"""Eres un auditor experto en PREPARACIÓN AGÉNTICA de sitios web (agent-readiness):
mides si un agente de IA (ChatGPT, Claude, Perplexity, un asistente de compra…)
puede ENCONTRAR, LEER, INTERPRETAR y USAR una web. No es SEO clásico: es si un
agente puede operar el sitio.

Tienes que completar la auditoría del dominio **{host}** (tipología detectada:
{typ}). Una herramienta automática ya lo intentó pero el sitio BLOQUEÓ su acceso
por IP (típico de Shopify/Akamai): pudo verificar el {cob_txt} del modelo a
distancia (robots, sitemap, cabeceras, DNS, .well-known), pero NO pudo leer el
contenido renderizado de las páginas. Tu trabajo es completar lo que falta.

═══════════════════════════════════════════════════════════════════════
REGLAS DE FIDELIDAD — INNEGOCIABLES. El informe se lo va a dar un CMO a su
equipo técnico: un dato inventado hace daño real.
═══════════════════════════════════════════════════════════════════════
1. NO inventes NADA. Para cada factor pendiente, CITA la evidencia concreta que
   observas (la etiqueta, el texto, el fichero). Si no puedes observarlo,
   escribe literalmente «no verificable» — nunca un número a ojo.
2. Los factores marcados «YA VERIFICADO» los midió la herramienta con su
   evidencia real: úsalos tal cual, NO los reevalúes.
3. Para VER el contenido: intenta abrir {host} tú mismo. Si tu acceso también
   está bloqueado, PIDE al usuario que pegue aquí el HTML de la portada y de una
   página clave (una ficha de producto si es tienda, la de precios si es SaaS,
   la de contacto si es corporativa). Trabaja solo con lo que tengas delante.
4. Puntúa cada factor: 1 = cumple · 0,5 = parcial · 0 = no cumple · N/A = no
   aplica a este tipo de negocio.

═══════════════════════════════════════════════════════════════════════
LOS 40 FACTORES (los ✓ ya están hechos; completa los ⧗)
═══════════════════════════════════════════════════════════════════════
{_bloque_factores(client)}

═══════════════════════════════════════════════════════════════════════
COMPORTAMIENTO AGÉNTICO REAL (factor 6.3 — el más importante)
═══════════════════════════════════════════════════════════════════════
Reproduce, con la web delante, lo que haría un agente:
{tarea}
Hitos que hay que ir alcanzando (marca cuáles se logran y dónde se atasca):
{chr(10).join('  · ' + h for h in hitos)}
Describe el recorrido PASO A PASO y en qué eslabón se rompe (esa rotura es el
hallazgo). Un agente se pierde cuando un control no tiene nombre claro, cuando
pulsa algo y no pasa lo que esperaba, o cuando un flujo exige registro/JS.

═══════════════════════════════════════════════════════════════════════
ENTREGA
═══════════════════════════════════════════════════════════════════════
Devuelve un informe con:
1. Veredicto y nota estimada 0-100, según esta escala:
{_escala()}
2. Tabla de los 40 factores: id · nombre · nota · evidencia (o «no verificable»).
3. Resumen del comportamiento agéntico: hasta dónde llega un agente y por qué se
   atasca.
4. Los 3-5 arreglos de mayor impacto y menor esfuerzo.
Recuerda: cada nota, con su evidencia observada. Sin evidencia, «no verificable».
""".strip()
