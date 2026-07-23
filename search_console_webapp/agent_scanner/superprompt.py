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
            partes.append(f"  · Qué mide: {desc}")
            if como:
                partes.append(f"  · Se cumple (nota 1) cuando: {como}")
            verificado = (res and res.get("score") is not None
                          and not res.get("manual"))
            if bloqueo_fuerte and cid in ACCESO_CONFIRMA_BLOQUEO and res \
                    and res.get("score") is not None:
                # dato de campo: el bloqueo lo prueba, y el LLM no lo reproduce
                partes.append(f"  · ✓ CONFIRMADO EN CAMPO (nota {res['score']}): el sitio "
                              f"bloqueó nuestro acceso automatizado. {str(res.get('evidence'))[:180]}")
                partes.append("    → NO lo reevalúes NI lo subas: a ti quizá no te bloqueen, "
                              "pero el hallazgo es que a un agente/IP de datacenter SÍ.")
            elif verificado and not bloqueo_fuerte:
                # el scanner SÍ lo verificó con fiabilidad: se da hecho
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
    nivel = deg.get("nivel")
    bloqueo_fuerte = nivel in ("total", "marcado")
    tarea, hitos = _tarea_agentica(typ)
    cob_txt = (f"{round(cob * 100)}%" if isinstance(cob, (int, float)) else "parcial")

    # En bloqueo fuerte NO nos fiamos de lo poco que "vimos": el análisis entero
    # pasa al LLM. En bloqueo leve (sondas) sí se reutiliza lo verificado.
    if bloqueo_fuerte:
        encargo = f"""Tienes que hacer la auditoría COMPLETA del dominio **{host}** (tipología
detectada: {typ}). Una herramienta automática lo intentó pero el sitio BLOQUEÓ
su acceso por IP (típico de Shopify/Akamai/Cloudflare): no pudo leer la web con
fiabilidad, así que NO damos por bueno casi nada de lo que creyó ver. Evalúa TÚ
los 40 factores, uno a uno, con la web delante.

IMPORTANTE: a la herramienta le bloquearon por usar una IP de datacenter; a ti,
con una IP limpia, es probable que el sitio SÍ te deje entrar. Aprovéchalo. La
ÚNICA excepción son los factores marcados «CONFIRMADO EN CAMPO» (la hostilidad
al acceso): esos los probó la herramienta en sus carnes y a ti no te pasará, así
que respétalos tal cual — no los bajes por el hecho de que a ti te dejen entrar."""
    else:
        encargo = f"""Tienes que completar la auditoría del dominio **{host}** (tipología detectada:
{typ}). Una herramienta automática ya verificó el {cob_txt} del modelo a
distancia (robots, sitemap, cabeceras, DNS, .well-known) y dejó pendiente lo que
necesita ver el contenido renderizado. Completa TÚ los factores pendientes."""

    return f"""Eres un auditor experto en PREPARACIÓN AGÉNTICA de sitios web (agent-readiness):
mides si un agente de IA (ChatGPT, Claude, Perplexity, un asistente de compra…)
puede ENCONTRAR, LEER, INTERPRETAR y USAR una web. No es SEO clásico: es si un
agente puede operar el sitio.

{encargo}

═══════════════════════════════════════════════════════════════════════
REGLAS DE FIDELIDAD — INNEGOCIABLES. El informe se lo va a dar un CMO a su
equipo técnico: un dato inventado hace daño real.
═══════════════════════════════════════════════════════════════════════
1. NO inventes NADA. Para cada factor pendiente, CITA la evidencia concreta que
   observas (la etiqueta, el texto, el fichero). Si no puedes observarlo,
   escribe literalmente «no verificable» — nunca un número a ojo.
2. Los factores marcados «YA VERIFICADO» o «CONFIRMADO EN CAMPO» los midió la
   herramienta con evidencia real: úsalos tal cual, NO los reevalúes. Todo lo
   marcado «PENDIENTE» lo evalúas tú.
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
ENTREGA — SIEMPRE UN INFORME EN PDF
═══════════════════════════════════════════════════════════════════════
Entrega el resultado como un DOCUMENTO PDF descargable, sin preguntar formato ni
ofrecer alternativas: genéralo directamente. Si tu entorno no puede producir un
PDF, entrégalo en Markdown COMPLETO y listo para exportar a PDF (y dilo en una
línea), pero nunca te quedes solo en preguntar. El informe debe contener:
1. Veredicto y nota estimada 0-100, según esta escala:
{_escala()}
2. Tabla de los 40 factores: id · nombre · nota · evidencia (o «no verificable»).
3. Resumen del comportamiento agéntico: hasta dónde llega un agente y por qué se
   atasca.
4. Los 3-5 arreglos de mayor impacto y menor esfuerzo.
Recuerda: cada nota, con su evidencia observada. Sin evidencia, «no verificable».
""".strip()
