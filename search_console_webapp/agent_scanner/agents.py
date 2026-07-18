# -*- coding: utf-8 -*-
"""Check 6.3 — pruebas agénticas reales, SIN browser-use.

Mini-harness propio: Playwright (ya instalado) pilotado por cada LLM con los
SDKs que la app ya fija (openai <2, anthropic 0.39, google-generativeai 0.8).
Cero conflicto de dependencias, cero venv extra, cero bloat de build.

Los 3 "agentes" son 3 proveedores (chatgpt/claude/gemini) resolviendo la misma
tarea en el mismo bucle de navegación.

REGLAS ÉTICAS CABLEADAS (no dependen del LLM, se imponen en código):
  - Nunca se pulsa un control de PAGO / finalizar compra / crear cuenta.
  - El ENVÍO de formularios solo se permite con allow_submit=True (dominio
    cliente autorizado); si es False, se bloquea el submit aunque el LLM lo pida.
"""
import json
import re

from .config import get_key

MAX_STEPS = 14

# Modelos por defecto (los mismos que usa la app). Se resuelven en runtime con
# el helper de la app si está disponible, para no desactualizarse nunca.
_FALLBACK_MODELS = {"chatgpt": "gpt-4o", "claude": "claude-sonnet-4-6",
                    "gemini": "gemini-3.5-flash"}


def _model_for(provider):
    prov_key = {"chatgpt": "openai", "claude": "anthropic", "gemini": "google"}[provider]
    try:
        from services.llm_providers.base_provider import get_current_model_for_provider
        m = get_current_model_for_provider(prov_key)
        if m:
            return m
    except Exception:
        pass
    return _FALLBACK_MODELS[provider]

# Datos de relleno. Configurables por entorno para que quien opera decida qué
# buzón recibe las pruebas sin tocar código. El defecto usa example.com, que es
# un dominio RESERVADO por la RFC 2606: no puede pertenecer a nadie, así que
# ningún tercero recibe correo por accidente.
def datos_prueba():
    import os
    g = os.environ.get
    return {
        "nombre": g("AGENT_SCANNER_TEST_NOMBRE", "Test Auditoria"),
        "email": g("AGENT_SCANNER_TEST_EMAIL", "test-auditoria@example.com"),
        "telefono": g("AGENT_SCANNER_TEST_TEL", "600000000"),
        "direccion": g("AGENT_SCANNER_TEST_DIR", "Calle de Prueba 1"),
        "cp": g("AGENT_SCANNER_TEST_CP", "28001"),
        "ciudad": g("AGENT_SCANNER_TEST_CIUDAD", "Madrid"),
    }


TASKS = {
    "ecommerce": ("Busca un producto del catálogo, ábrelo, añádelo al carrito, abre el "
                  "carrito y avanza hasta el checkout. En el checkout RELLENA los datos "
                  "de contacto y envío: nombre '{nombre}', email '{email}', teléfono "
                  "'{telefono}', dirección '{direccion}', código postal '{cp}', ciudad "
                  "'{ciudad}'. Avanza todo lo que puedas SIN pagar. Cuando llegues a los "
                  "datos de tarjeta, marca la tarea como terminada: NO introduzcas "
                  "NINGÚN dato de pago ni completes la compra."),
    "corporativo": ("Localiza la página de contacto, identifica un teléfono o email de "
                    "contacto, y rellena el formulario con: nombre 'Test Auditoria', "
                    "email 'test-auditoria@example.com', mensaje 'Prueba de auditoria "
                    "tecnica, ignorar por favor'. {submit_rule}"),
    "saas": ("Encuentra la página de precios, identifica el plan de pago más barato e "
             "inicia su contratación. Cuando se pidan datos de pago o crear cuenta, marca "
             "la tarea como terminada: NO registres cuenta ni introduzcas datos de pago."),
}

# Hitos intermedios: la tarea deja de ser un binario y pasa a ser un recorrido.
# Se detectan por EVIDENCIA OBSERVADA (URL, contenido de la página, acción
# ejecutada), no por lo que el LLM diga haber hecho: si el agente se cree en el
# carrito pero la URL no lo confirma, el hito no cuenta.
MILESTONES = {
    "ecommerce": [
        {"clave": "ficha_producto", "nombre": "Abrir una ficha de producto",
         "url": r"/(producto|product|item|dp|p)/|-p-\d+",
         "html": r"(?i)(a[ñn]adir al carrito|add to cart|a[ñn]adir a la cesta)"},
        {"clave": "anadir_carrito", "nombre": "Añadir el producto al carrito",
         "accion": r"(?i)(a[ñn]adir|add to cart|comprar|cesta)"},
        {"clave": "ver_carrito", "nombre": "Abrir el carrito",
         "url": r"/(carrito|cart|cesta|basket)"},
        {"clave": "checkout", "nombre": "Llegar al checkout",
         "url": r"/(checkout|pago|caja|finalizar|payment)"},
        # se detecta por haber escrito un email: es el campo que pide todo
        # checkout y no aparece al buscar producto (evita falsos positivos
        # con el buscador, que también genera acciones "type")
        {"clave": "datos_checkout", "nombre": "Rellenar los datos del checkout",
         "accion": r"(?i)^type .*@"},
    ],
    "corporativo": [
        {"clave": "pagina_contacto", "nombre": "Llegar a la página de contacto",
         "url": r"/(contacto|contact|contactanos|contactenos)"},
        {"clave": "datos_contacto", "nombre": "Encontrar teléfono o email de contacto",
         "html": r"(?i)(mailto:|tel:|\+34[\s\d]{9,})"},
        {"clave": "formulario_relleno", "nombre": "Rellenar el formulario",
         "accion": r"^type "},
        # Solo se evalúa si el envío está autorizado: si se lo prohibimos
        # nosotros, marcarlo como "no alcanzado" acusaría a la web de un
        # atasco que en realidad es una restricción NUESTRA.
        {"clave": "envio", "nombre": "Alcanzar el botón de envío",
         "requiere_submit": True,
         "accion": r"(?i)(BLOQUEADO env[ií]o|click.*(enviar|send|submit))"},
    ],
    "saas": [
        {"clave": "pagina_precios", "nombre": "Llegar a la página de precios",
         "url": r"/(precios|pricing|planes|plans)"},
        {"clave": "precio_visible", "nombre": "Ver los precios de los planes",
         "html": r"(€|\$|USD|EUR)\s*\d+|\d+\s*(€|\$)\s*/\s*(mes|month|user)"},
        {"clave": "plan_elegido", "nombre": "Seleccionar un plan",
         "accion": r"(?i)click.*(plan|contratar|empezar|elegir|comenzar|get started|choose)"},
        {"clave": "alta", "nombre": "Alcanzar el alta o el pago",
         "url": r"/(signup|sign-up|registro|register|checkout|subscribe)",
         "accion": r"(?i)BLOQUEADO por ética"},
    ],
}
SUBMIT_OK = "Cuando esté relleno, envíalo con el botón de enviar."
SUBMIT_NO = "Cuando esté relleno, marca la tarea como terminada SIN pulsar enviar."


def hitos_aplicables(typology, allow_submit):
    """Hitos que SÍ se pueden evaluar según la política de la prueba."""
    return [m for m in MILESTONES.get(typology, [])
            if allow_submit or not m.get("requiere_submit")]


def _check_milestones(hitos, reached, url, html, last_action):
    """Marca hitos recién alcanzados con la evidencia que los prueba."""
    for m in hitos:
        if m["clave"] in reached:
            continue
        if m.get("url") and re.search(m["url"], url or "", re.I):
            reached[m["clave"]] = {"nombre": m["nombre"], "via": f"URL: {url[:90]}"}
        elif m.get("html") and re.search(m["html"], (html or "")[:400_000]):
            reached[m["clave"]] = {"nombre": m["nombre"], "via": "contenido de la página"}
        elif m.get("accion") and last_action and re.search(m["accion"], last_action):
            reached[m["clave"]] = {"nombre": m["nombre"], "via": f"acción: {last_action[:70]}"}

# Controles que NUNCA se pulsan (defensa en código, no confiamos solo en el LLM)
FORBIDDEN_CLICK = re.compile(
    r"(?i)\b(pagar|finalizar (compra|pedido|pago)|realizar pedido|confirmar pago|"
    r"place order|pay now|complete (order|purchase)|checkout now|comprar ahora|"
    r"crear cuenta|create account|sign ?up|registrarme|suscribirme|subscribe)\b")
SUBMIT_HINT = re.compile(r"(?i)\b(enviar|send|submit|contactar|solicitar)\b")

# Campos de pago: NUNCA se escribe en ellos, ni aunque el LLM lo pida. Es la
# defensa en código de "llegamos al pago pero jamás pagamos": el agente puede
# rellenar contacto y envío, pero la tarjeta es territorio prohibido.
CARD_FIELD = re.compile(
    r"(?i)\b(tarjeta|card ?(number|holder)?|cvv|cvc|caducidad|expir|"
    r"numero de tarjeta|titular|iban|cuenta bancaria)\b")

SYSTEM = (
    "Eres un agente que navega una web real para comprobar si una tarea puede completarse. "
    "En cada paso recibes la URL actual y una lista NUMERADA de elementos interactivos. "
    "Respondes SOLO con un JSON válido, sin texto alrededor, con esta forma:\n"
    '{\"accion\": \"click\"|\"type\"|\"done\", \"indice\": <n>, \"texto\": \"<si type>\", '
    '\"friccion\": \"<describe cualquier dificultad, o vacío>\", '
    '\"resultado\": \"<solo si done: CONSEGUIDO o NO_CONSEGUIDO y por qué>\"}\n'
    "Reglas: rechaza cookies si aparecen. No pagues ni crees cuentas. Si te atascas 2 veces, "
    "responde done con NO_CONSEGUIDO explicando la fricción."
)

_ELEMENTS_JS = r"""
() => {
  const out = [];
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, [role=button], [onclick]';
  let i = 0;
  document.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    const vis = r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'
      && getComputedStyle(el).display !== 'none';
    if (!vis) return;
    if (i > 60) return;
    el.setAttribute('data-agent-idx', i);
    const name = (el.innerText || el.value || el.getAttribute('aria-label')
      || el.getAttribute('placeholder') || el.getAttribute('name') || '').trim().slice(0, 70);
    out.push({i, tag: el.tagName.toLowerCase(), type: el.getAttribute('type') || '',
      name});
    i++;
  });
  return out;
}
"""


def build_task(typology, allow_submit):
    t = TASKS.get(typology, TASKS["corporativo"])
    return t.format(submit_rule=SUBMIT_OK if allow_submit else SUBMIT_NO,
                    **datos_prueba())


# ----------------------------------------------------------- adaptadores LLM

def _ask_openai(messages, key):
    import openai
    client = openai.OpenAI(api_key=key)
    model = _model_for("chatgpt")
    # GPT-5.x usa max_completion_tokens y no admite temperature; GPT-4o usa max_tokens
    params = {"model": model, "messages": messages}
    if model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3"):
        params["max_completion_tokens"] = 600
    else:
        params["max_tokens"] = 400
        params["temperature"] = 0
    r = client.chat.completions.create(**params)
    return r.choices[0].message.content


def _ask_anthropic(messages, key):
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    convo = [m for m in messages if m["role"] != "system"]
    r = client.messages.create(
        model=_model_for("claude"), system=system, messages=convo,
        max_tokens=400, temperature=0)
    return r.content[0].text


def _ask_gemini(messages, key):
    import google.generativeai as genai
    genai.configure(api_key=key)
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    model = genai.GenerativeModel(_model_for("gemini"), system_instruction=system)
    convo = "\n\n".join(f"{m['role']}: {m['content']}"
                        for m in messages if m["role"] != "system")
    r = model.generate_content(convo, generation_config={"temperature": 0, "max_output_tokens": 400})
    return r.text


_ADAPTERS = {"chatgpt": _ask_openai, "claude": _ask_anthropic, "gemini": _ask_gemini}
_KEY_NAMES = {"chatgpt": "openai", "claude": "anthropic", "gemini": "gemini"}


_CERRAR_JS = r"""
() => {
  // Cierra banners de cookies y paneles superpuestos. Un agente con visión los
  // vería y los cerraría; el nuestro recibe una lista de elementos y no sabe
  // que algo los tapa, así que los clics fallaban por "elemento no accionable"
  // y acabábamos atribuyendo a la web un atasco que era nuestro.
  const PATRON = /^(aceptar|accept|entendido|got it|ok|cerrar|close|rechazar|
                    reject|continuar|dismiss|x)$/i;
  let cerrados = 0;
  for (const el of document.querySelectorAll('button,a,[role=button],[aria-label]')) {
    const txt = (el.innerText || el.getAttribute('aria-label') || '').trim();
    if (!txt || txt.length > 20) continue;
    if (!PATRON.test(txt)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    try { el.click(); cerrados++; } catch (e) {}
    if (cerrados >= 3) break;
  }
  return cerrados;
}
""".replace("\n                    ", "")


def _despejar(page):
    """Quita lo que tape la interfaz antes de dejar actuar al agente."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        n = page.evaluate(_CERRAR_JS)
        if n:
            page.wait_for_timeout(400)
        return n
    except Exception:
        return 0


def _parse_action(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


# ----------------------------------------------------------- bucle navegador

def _browser_task(url, task, ask, key, allow_submit, typology="corporativo"):
    from playwright.sync_api import sync_playwright
    steps, frictions, outcome = [], [], "no_conseguido"
    reached = {}
    hitos = hitos_aplicables(typology, allow_submit)
    total_hitos = len(hitos)
    omitidos = [m["nombre"] for m in MILESTONES.get(typology, []) if m not in hitos]

    def _progress():
        return {"alcanzados": len(reached), "total": total_hitos,
                "hitos": [{"clave": k, **v} for k, v in reached.items()],
                "pendientes": [m["nombre"] for m in hitos if m["clave"] not in reached],
                "no_evaluados": omitidos}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:
            browser.close()
            return {"outcome": "error", "detail": f"no se pudo abrir la web: {exc}"[:200],
                    "steps": 0, "action_log": [], "progreso": _progress()}
        # cookies y paneles abiertos fuera antes de empezar: si no, los clics
        # fallan por "elemento tapado" y el informe culpa a la web
        page.wait_for_timeout(1200)
        if _despejar(page):
            steps.append("cerrado un banner/overlay inicial para poder operar")
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Tarea: {task}"}]
        for _ in range(MAX_STEPS):
            try:
                page.wait_for_timeout(700)
                elements = page.evaluate(_ELEMENTS_JS)
            except Exception:
                elements = []
            # evidencia de hitos ANTES de decidir el siguiente paso
            try:
                _check_milestones(hitos, reached, page.url, page.content(),
                                  steps[-1] if steps else None)
            except Exception:
                pass
            listing = "\n".join(f"[{e['i']}] <{e['tag']}{('/'+e['type']) if e['type'] else ''}> "
                                f"{e['name'] or '(sin texto)'}" for e in elements) or "(sin elementos)"
            messages.append({"role": "user",
                             "content": f"URL: {page.url}\nElementos:\n{listing}\n"
                                        "Responde con el JSON de la próxima acción."})
            try:
                raw = ask(messages, key)
            except Exception as exc:
                return {"outcome": "error", "detail": f"fallo del LLM: {exc}"[:200],
                        "steps": len(steps), "action_log": steps}
            messages.append({"role": "assistant", "content": raw[:500]})
            act = _parse_action(raw)
            if not act:
                steps.append(f"respuesta no parseable: {raw[:80]}")
                continue
            if act.get("friccion"):
                frictions.append(act["friccion"])
            action = act.get("accion")
            idx = act.get("indice")
            target = next((e for e in elements if e["i"] == idx), None)

            if action == "done":
                res = (act.get("resultado") or "").upper()
                outcome = "conseguido" if "CONSEGUIDO" in res and "NO_CONSEGUIDO" not in res \
                    else "no_conseguido"
                steps.append(f"done: {act.get('resultado', '')[:120]}")
                break

            label = (target or {}).get("name", "")
            # GUARDARRAÍL: jamás se escribe en un campo de pago, aunque el LLM
            # lo pida. Rellenar contacto y envío sí; tarjeta nunca.
            if action == "type" and CARD_FIELD.search(label):
                steps.append(f"BLOQUEADO campo de pago: '{label[:50]}' — no se escriben "
                             "datos de tarjeta bajo ninguna circunstancia")
                outcome = "conseguido"  # llegar al pago ES el éxito de la prueba
                break
            # GUARDARRAÍL en código: nunca pagar/crear cuenta
            if action == "click" and FORBIDDEN_CLICK.search(label):
                steps.append(f"BLOQUEADO por ética (pago/cuenta): '{label[:50]}' — se detiene aquí")
                outcome = "conseguido"  # llegar hasta aquí ES el éxito de la prueba
                break
            # GUARDARRAÍL: submit solo si autorizado
            if action == "click" and not allow_submit and SUBMIT_HINT.search(label) \
                    and (target or {}).get("tag") in ("button", "input", "a"):
                steps.append(f"BLOQUEADO envío (no autorizado): '{label[:50]}' — se detiene aquí")
                outcome = "conseguido"
                break

            try:
                if action == "type" and target is not None:
                    page.fill(f"[data-agent-idx='{idx}']", act.get("texto", ""))
                    steps.append(f"type [{idx}] '{act.get('texto','')[:40]}' en '{label[:40]}'")
                elif action == "click" and target is not None:
                    try:
                        page.click(f"[data-agent-idx='{idx}']", timeout=6000)
                        steps.append(f"click [{idx}] '{label[:50]}'")
                    except Exception:
                        # segundo intento tras despejar lo que estuviera tapando:
                        # si ahora funciona, el obstáculo era un overlay, y eso
                        # es fricción real de la web (un agente pierde un paso),
                        # pero NO un "no se puede completar la tarea"
                        _despejar(page)
                        page.click(f"[data-agent-idx='{idx}']", timeout=6000)
                        steps.append(f"click [{idx}] '{label[:50]}' (tras cerrar un overlay)")
                        frictions.append(
                            f"un elemento superpuesto tapaba '{label[:35]}': hubo que "
                            "cerrarlo antes de poder pulsar")
                else:
                    steps.append(f"acción inválida o índice inexistente: {act}")
            except Exception as exc:
                steps.append(f"fallo al ejecutar [{idx}]: {type(exc).__name__}")
                frictions.append(f"el elemento '{label[:40]}' no respondió")
            # el hito puede consumarse por la acción recién ejecutada
            try:
                _check_milestones(hitos, reached, page.url, page.content(),
                                  steps[-1] if steps else None)
            except Exception:
                pass
        browser.close()
    if outcome == "conseguido" and frictions:
        outcome = "conseguido_con_friccion"
    prog = _progress()
    # Honestidad sobre el método: si la tarea se cayó por controles que no
    # respondieron al clic programático (selectores de talla, componentes JS a
    # medida), NO podemos afirmar que la web sea inoperable para un agente.
    # Nuestro harness clica por selector; Operator y Atlas usan visión y son
    # más tolerantes a esos controles. Es un límite NUESTRO y hay que decirlo.
    timeouts = sum(1 for s in steps if "TimeoutError" in s)
    limitado = (not outcome.startswith("conseguido")) and timeouts >= 2
    detail = ("OBJETIVO CONSEGUIDO. " if outcome.startswith("conseguido") else "NO CONSEGUIDO. ")
    if total_hitos:
        detail += f"Recorrido: {prog['alcanzados']}/{total_hitos} pasos completados"
        if prog["pendientes"]:
            detail += f" (se atascó en: {prog['pendientes'][0]})"
        detail += ". "
    detail += ("Fricciones: " + "; ".join(dict.fromkeys(frictions))) if frictions else "Sin fricciones."
    if limitado:
        detail += (f" AVISO DE MÉTODO: {timeouts} controles no respondieron al clic "
                   "programático. Puede ser hostilidad real al automatismo, pero también "
                   "un límite de nuestro harness (clicamos por selector; los agentes "
                   "comerciales usan visión y toleran mejor los controles a medida). "
                   "No concluyas que la web es inoperable sin comprobarlo a mano.")
    return {"outcome": outcome, "detail": detail[:800], "steps": len(steps),
            "action_log": steps[:25], "progreso": prog,
            "limite_de_metodo": limitado, "timeouts": timeouts}


def _aggregate(runs):
    """Resume N intentos del mismo agente. La CONSISTENCIA es el dato clave:
    un agente LLM es estocástico, así que una sola pasada no prueba nada. Que
    una web funcione 1 de cada 3 veces no es 'funciona': es un hallazgo."""
    validos = [r for r in runs if r.get("outcome") not in ("error", None)]
    if not validos:
        return {"outcome": "error", "intentos": len(runs),
                "detail": (runs[0].get("detail") if runs else "sin ejecuciones"),
                "runs": runs}
    exitos = [r for r in validos if str(r["outcome"]).startswith("conseguido")]
    limpios = [r for r in validos if r["outcome"] == "conseguido"]
    n = len(validos)
    if len(exitos) == n:
        outcome = "conseguido" if len(limpios) == n else "conseguido_con_friccion"
    elif exitos:
        outcome = "inconsistente"
    else:
        outcome = "no_conseguido"
    progs = [r.get("progreso") or {} for r in validos]
    ratios = [p["alcanzados"] / p["total"] for p in progs if p.get("total")]
    mejor = max(validos, key=lambda r: (r.get("progreso") or {}).get("alcanzados", 0))
    detail = f"{len(exitos)}/{n} intentos con éxito"
    if ratios:
        detail += f" · recorrido medio {sum(ratios)/len(ratios):.0%}"
    if outcome == "inconsistente":
        detail += (". LA WEB FUNCIONA A VECES: para un agente esto es peor que un fallo "
                   "claro, porque el resultado no es predecible")
    detail += ". " + (mejor.get("detail") or "")
    limitado = all(r.get("limite_de_metodo") for r in validos) and not exitos
    return {"outcome": outcome, "intentos": n, "exitos": len(exitos),
            "limite_de_metodo": limitado,
            "consistencia": round(len(exitos) / n, 2),
            "steps": mejor.get("steps"), "detail": detail[:700],
            "progreso": mejor.get("progreso"), "action_log": mejor.get("action_log"),
            "runs": [{"outcome": r.get("outcome"), "steps": r.get("steps"),
                      "alcanzados": (r.get("progreso") or {}).get("alcanzados")}
                     for r in runs]}


def run_agent_tests(url, typology, providers=("chatgpt", "gemini", "claude"),
                    allow_submit=False, log=None, repeticiones=3):
    """Ejecuta la tarea con cada proveedor disponible, N veces cada uno.

    Las repeticiones existen por rigor, no por exceso: los agentes LLM no son
    deterministas y una única pasada no distingue "la web funciona" de "esa vez
    tuvo suerte".
    """
    def _log(m):
        if log is not None:
            log.append(m)
    reps = max(1, min(int(repeticiones or 1), 5))
    agents = {}
    # UN solo envío real por análisis, no uno por pasada. Con 3 agentes x 3
    # repeticiones se enviaban hasta 9 formularios: quien marca la casilla
    # espera "un formulario de prueba", no nueve leads en su CRM. Las demás
    # pasadas rellenan y se detienen ante el botón, así que la medición de
    # consistencia se conserva intacta.
    envio_disponible = bool(allow_submit)
    for prov in providers:
        key = get_key(_KEY_NAMES[prov])
        if not key:
            agents[prov] = {"outcome": "no_disponible", "detail": f"sin API key de {prov}"}
            continue
        runs = []
        for i in range(reps):
            envia_esta = envio_disponible
            envio_disponible = False       # se consume en la primera pasada
            _log(f"agente {prov} intentando la tarea… (intento {i+1}/{reps})"
                 + (" [con envío real autorizado]" if envia_esta else ""))
            try:
                runs.append(_browser_task(url, build_task(typology, envia_esta),
                                          _ADAPTERS[prov], key, envia_esta, typology))
            except Exception as exc:
                runs.append({"outcome": "error", "detail": str(exc)[:200]})
            prog = (runs[-1].get("progreso") or {})
            _log(f"  {prov} #{i+1}: {runs[-1].get('outcome')}"
                 + (f" ({prog.get('alcanzados')}/{prog.get('total')} hitos)"
                    if prog.get("total") else ""))
        agents[prov] = _aggregate(runs)
        _log(f"  {prov}: {agents[prov]['outcome']} "
             f"({agents[prov].get('exitos')}/{agents[prov].get('intentos')} intentos)")
    return {"url": url, "typology": typology, "allow_submit": allow_submit,
            "envios_reales": 1 if allow_submit else 0,
            "repeticiones": reps, "agents": agents,
            "hitos_tarea": [m["nombre"] for m in hitos_aplicables(typology, allow_submit)],
            "hitos_no_evaluados": [m["nombre"] for m in MILESTONES.get(typology, [])
                                   if m.get("requiere_submit") and not allow_submit]}
