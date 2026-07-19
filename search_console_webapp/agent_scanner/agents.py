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
         "url": r"/(productos?|products?|item|dp|p|produkte?|produits?|prodotti?)/|-p-\d+",
         # el marcado Product es la señal más fiable de que estamos en una ficha:
         # noel.es abría un producto y no lo contábamos porque su URL y su texto
         # no encajaban con los patrones en español que teníamos
         "html": r"(?i)(a[ñn]adir al carrito|add to cart|a[ñn]adir a la cesta|"
                 r"a[ñn]adir a la bolsa|in den warenkorb|ajouter au panier|"
                 r"aggiungi al carrello|adicionar ao carrinho|in winkelwagen|"
                 r"\"@type\"\s*:\s*\"Product\")"},
        {"clave": "anadir_carrito", "nombre": "Añadir el producto al carrito",
         # PREORDER/reservar son el botón de compra en preventa: pompeii lo
         # pulsó y no se lo contábamos.
         # DE/FR/IT/PT/NL: sin ellos, un agente que SÍ añade al carrito en una
         # tienda alemana quedaba registrado como "no lo consiguió" — acusar a
         # la web de un atasco que solo estaba en nuestros patrones.
         "accion": r"(?i)(a[ñn]adir|add to (cart|bag)|comprar|cesta|bolsa|"
                   r"pre-?order|preventa|reservar|"
                   r"warenkorb|einkaufswagen|kaufen|"          # DE
                   r"panier|acheter|"                          # FR
                   r"carrello|acquista|"                       # IT
                   r"carrinho|"                                # PT
                   r"winkelwagen)"},                           # NL
        # El carrito de Shopify y muchos temas modernos se abre como PANEL
        # LATERAL sin cambiar la URL: comprobar solo la URL daba el hito por no
        # alcanzado aunque el agente lo hubiera abierto correctamente.
        {"clave": "ver_carrito", "nombre": "Abrir el carrito",
         "url": r"/(carrito|cart|cesta|basket|warenkorb|panier|carrello|carrinho|winkelwagen)",
         "html": r"(?i)(cart-drawer|cart__drawer|mini-?cart|drawer--cart|"
                 r"id=[\"']?CartDrawer|(subtotal|total)[^<]{0,40}(carrito|cart|cesta))"},
        {"clave": "checkout", "nombre": "Llegar al checkout",
         "url": r"/(checkout|pago|caja|finalizar|payment|kasse|bezahlen|"
                r"commande|paiement|pagamento|cassa|betalen)"},
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
# Estas tres expresiones son la defensa EN CÓDIGO, no una preferencia de estilo:
# si no matchean, el agente puede pulsar de verdad un botón de compra o escribir
# en un campo de tarjeta. Estaban solo en ES/EN, así que en una tienda alemana
# ("Kostenpflichtig bestellen", "Kartennummer") la defensa sencillamente no
# existía. Ampliadas a DE/FR/IT/PT/NL antes de auditar dominios de esos países.
FORBIDDEN_CLICK = re.compile(
    r"(?i)\b(pagar|finalizar (compra|pedido|pago)|realizar pedido|confirmar pago|"
    r"place order|pay now|complete (order|purchase)|checkout now|comprar ahora|"
    r"crear cuenta|create account|sign ?up|registrarme|suscribirme|subscribe"
    # DE — "kostenpflichtig bestellen" es la fórmula legal obligatoria del
    # botón de compra en Alemania (§312j BGB): es EL botón que nunca se pulsa.
    r"|kostenpflichtig bestellen|jetzt kaufen|jetzt bestellen|zahlungspflichtig"
    r"|kaufen und bezahlen|konto erstellen|registrieren|abonnieren"
    # FR
    r"|payer( maintenant)?|commander( et payer)?|valider (la )?commande"
    r"|acheter maintenant|cr[ée]er un compte|s'inscrire|s abonner"
    # IT
    r"|paga( ora| adesso)?|acquista ora|conferma (ordine|acquisto)"
    r"|crea un account|registrati|abbonati"
    # PT
    r"|pagar agora|finalizar (compra|pedido)|comprar agora|criar conta|registar"
    # NL
    r"|nu betalen|bestelling plaatsen|account aanmaken|aanmelden"
    r")\b")
SUBMIT_HINT = re.compile(
    r"(?i)\b(enviar|send|submit|contactar|solicitar"
    r"|senden|absenden|abschicken|anfragen"          # DE
    r"|envoyer|soumettre|contacter"                  # FR
    r"|invia|inviare|contattaci|richiedi"            # IT
    r"|enviar|contactar"                             # PT
    r"|verzenden|versturen"                          # NL
    r")\b")

# Campos de pago: NUNCA se escribe en ellos, ni aunque el LLM lo pida. Es la
# defensa en código de "llegamos al pago pero jamás pagamos": el agente puede
# rellenar contacto y envío, pero la tarjeta es territorio prohibido.
CARD_FIELD = re.compile(
    r"(?i)\b(tarjeta|card ?(number|holder)?|cvv|cvc|caducidad|expir|"
    r"numero de tarjeta|titular|iban|cuenta bancaria"
    r"|karte|kartennummer|karteninhaber|kreditkarte|g[üu]ltig bis|pr[üu]fziffer"  # DE
    r"|carte|num[ée]ro de carte|titulaire|date d'expiration|cryptogramme"          # FR
    r"|carta|numero (della )?carta|intestatario|scadenza"                          # IT
    r"|cart[ãa]o|n[úu]mero do cart[ãa]o|validade"                                  # PT
    r"|kaart|kaartnummer|vervaldatum"                                              # NL
    r")\b")

SYSTEM = (
    "Eres un agente que navega una web real para comprobar si una tarea puede completarse. "
    "En cada paso recibes la URL actual y una lista NUMERADA de elementos interactivos. "
    "Respondes SOLO con un JSON válido, sin texto alrededor, con esta forma:\n"
    '{\"accion\": \"click\"|\"type\"|\"done\", \"indice\": <n>, \"texto\": \"<si type>\", '
    '\"friccion\": \"<describe cualquier dificultad, o vacío>\", '
    '\"resultado\": \"<solo si done: CONSEGUIDO o NO_CONSEGUIDO y por qué>\"}\n'
    "Reglas: rechaza cookies si aparecen. No pagues ni crees cuentas. Si una acción falla, "
    "PRUEBA OTRA RUTA antes de rendirte (el buscador, el menú, otra categoría, otro "
    "producto): tienes pasos de sobra y abandonar pronto falsea el resultado. Solo "
    "responde done con NO_CONSEGUIDO cuando hayas agotado al menos 4 alternativas "
    "distintas, y explica cuáles probaste."
)

_ELEMENTS_JS = r"""
() => {
  const out = [];
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, [role=button], [onclick]';
  let i = 0;
  document.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    // Los controles ocultos con etiqueta visible (tallas, colores) SÍ entran:
    // se clican por su <label>, que es lo que haría un agente con visión.
    const tieneLabel = el.id && document.querySelector(`label[for='${CSS.escape(el.id)}']`);
    const vis = (r.width > 0 && r.height > 0 && cs.visibility !== 'hidden'
                 && cs.display !== 'none') || tieneLabel;
    if (!vis) return;
    // Tope alto: con 60 en orden del DOM, en una tienda solo entraban cabecera
    // y menú, y los productos nunca llegaban a la lista. El agente no podía
    // encontrar lo que no le enseñábamos.
    if (i >= 110) return;
    el.setAttribute('data-agent-idx', i);
    // El texto visible manda; si no hay (enlaces que son solo imagen, típicos
    // de las fichas de producto), se usa el alt de la imagen antes que caer en
    // atributos internos como name, que no dicen nada al modelo.
    const img = el.querySelector('img');
    const name = (el.innerText || (img && (img.alt || img.title)) || el.value
      || el.getAttribute('aria-label') || el.getAttribute('title')
      || el.getAttribute('placeholder') || el.getAttribute('name') || ''
      ).trim().replace(/\s+/g, ' ').slice(0, 70);
    // El destino del enlace orienta muchísimo: /products/... delata una ficha
    let href = '';
    if (el.tagName === 'A') {
      try { href = new URL(el.href, location.href).pathname.slice(0, 45); } catch (e) {}
    }
    out.push({i, tag: el.tagName.toLowerCase(), type: el.getAttribute('type') || '',
      name, href});
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

# Presupuesto de salida. Los modelos con razonamiento gastan tokens PENSANDO y
# esos tokens salen de aquí: con 400, gemini-3.5-flash devolvía un fragmento del
# medio del JSON ('": "59,99 EUR",\n "contacto": "info') que no se podía parsear.
# El JSON de una acción ocupa ~80 tokens; el resto es margen para el pensamiento.
# No encarece nada: solo se paga lo que se genera de verdad.
_MAX_SALIDA = 2000


def _ask_openai(messages, key):
    import openai
    client = openai.OpenAI(api_key=key)
    model = _model_for("chatgpt")
    # GPT-5.x usa max_completion_tokens y no admite temperature; GPT-4o usa max_tokens
    params = {"model": model, "messages": messages}
    if model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3"):
        params["max_completion_tokens"] = _MAX_SALIDA
    else:
        params["max_tokens"] = 800
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
        max_tokens=_MAX_SALIDA, temperature=0)
    return r.content[0].text


def _ask_gemini(messages, key):
    import google.generativeai as genai
    genai.configure(api_key=key)
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    model = genai.GenerativeModel(_model_for("gemini"), system_instruction=system)
    convo = "\n\n".join(f"{m['role']}: {m['content']}"
                        for m in messages if m["role"] != "system")
    r = model.generate_content(
        convo, generation_config={"temperature": 0, "max_output_tokens": _MAX_SALIDA})
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


_LABEL_JS = r"""
(idx) => {
  // Devuelve un selector para la ETIQUETA visible de un control oculto.
  // Los selectores de talla/color son <input> con opacidad 0 o recortados,
  // con su <label> encima: lo clicable de verdad es la etiqueta.
  const el = document.querySelector(`[data-agent-idx='${idx}']`);
  if (!el) return null;
  let lab = null;
  if (el.id) lab = document.querySelector(`label[for='${CSS.escape(el.id)}']`);
  if (!lab) lab = el.closest('label');
  if (!lab) return null;
  const r = lab.getBoundingClientRect();
  if (r.width < 1 || r.height < 1) return null;
  lab.setAttribute('data-agent-label', idx);
  return true;
}
"""


def _click_via_label(page, idx):
    """Clica la etiqueta asociada a un control oculto. True si lo consiguió."""
    try:
        if not page.evaluate(_LABEL_JS, idx):
            return False
        page.click(f"[data-agent-label='{idx}']", timeout=5000)
        return True
    except Exception:
        return False


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
    reached, fallidos = {}, {}
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
        # ¿Hemos llegado a tener alguna vez una página con la que operar? Sin
        # esto, un bloqueo del WAF al navegador headless se registraba como
        # "la web no dejó al agente" (ver el retorno no_verificable más abajo).
        pasos_con_elementos = 0
        for _ in range(MAX_STEPS):
            try:
                page.wait_for_timeout(700)
                elements = page.evaluate(_ELEMENTS_JS)
            except Exception:
                elements = []
            if elements:
                pasos_con_elementos += 1
            # evidencia de hitos ANTES de decidir el siguiente paso
            try:
                _check_milestones(hitos, reached, page.url, page.content(),
                                  steps[-1] if steps else None)
            except Exception:
                pass
            listing = "\n".join(
                f"[{e['i']}] <{e['tag']}{('/'+e['type']) if e['type'] else ''}> "
                f"{e['name'] or '(sin texto)'}"
                + (f"  -> {e['href']}" if e.get("href") else "")
                for e in elements) or "(sin elementos)"
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

            def _parar_por_guardarrail(motivo):
                """Un guardarraíl detiene la prueba por ética. Que eso cuente
                como ÉXITO depende de lo lejos que hubiéramos llegado: toparse
                con un botón 'Enviar' de una newsletter en el primer paso no es
                haber completado una compra. Sin recorrido no hay éxito."""
                steps.append(motivo)
                p = _progress()
                suficiente = p["total"] and p["alcanzados"] >= max(1, p["total"] // 2)
                return "conseguido" if suficiente else "no_conseguido"
            # GUARDARRAÍL: jamás se escribe en un campo de pago, aunque el LLM
            # lo pida. Rellenar contacto y envío sí; tarjeta nunca.
            if action == "type" and CARD_FIELD.search(label):
                steps.append(f"BLOQUEADO campo de pago: '{label[:50]}' — no se escriben "
                             "datos de tarjeta bajo ninguna circunstancia")
                outcome = "conseguido"  # llegar al pago ES el éxito de la prueba
                break
            # GUARDARRAÍL en código: nunca pagar/crear cuenta
            if action == "click" and FORBIDDEN_CLICK.search(label):
                outcome = _parar_por_guardarrail(
                    f"BLOQUEADO por ética (pago/cuenta): '{label[:50]}' — se detiene aquí")
                break
            # GUARDARRAÍL: submit solo si autorizado
            if action == "click" and not allow_submit and SUBMIT_HINT.search(label) \
                    and (target or {}).get("tag") in ("button", "input", "a"):
                outcome = _parar_por_guardarrail(
                    f"BLOQUEADO envío (no autorizado): '{label[:50]}' — se detiene aquí")
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
                        # 2º intento: despejar lo que tape. Si ahora funciona, el
                        # obstáculo era un overlay: fricción real de la web (un
                        # agente pierde un paso), no "tarea imposible".
                        try:
                            _despejar(page)
                            page.click(f"[data-agent-idx='{idx}']", timeout=6000)
                            steps.append(f"click [{idx}] '{label[:50]}' (tras cerrar un overlay)")
                            frictions.append(
                                f"un elemento superpuesto tapaba '{label[:35]}': hubo que "
                                "cerrarlo antes de poder pulsar")
                        except Exception:
                            # 3º intento: los selectores de talla/color son
                            # <input> visualmente ocultos con su <label> al lado.
                            # Un agente con visión clica la ETIQUETA, que es lo
                            # visible; clicar el input oculto es imposible hasta
                            # para un humano. Esto es emulación fiel, no trampa.
                            if not _click_via_label(page, idx):
                                raise
                            steps.append(f"click [{idx}] '{label[:50]}' (vía su etiqueta)")
                else:
                    steps.append(f"acción inválida o índice inexistente: {act}")
            except Exception as exc:
                steps.append(f"fallo al ejecutar [{idx}]: {type(exc).__name__}")
                frictions.append(f"el elemento '{label[:40]}' no respondió")
                # Sin decírselo, el modelo reintenta el mismo elemento una y otra
                # vez (hawkersco: 6 intentos sobre el mismo botón) y quema los
                # pasos disponibles sin explorar alternativas.
                fallidos[idx] = fallidos.get(idx, 0) + 1
                if fallidos[idx] >= 2:
                    messages.append({"role": "user", "content":
                                     f"AVISO: el elemento [{idx}] ha fallado "
                                     f"{fallidos[idx]} veces y no va a funcionar. "
                                     "NO lo vuelvas a intentar: busca otra ruta "
                                     "(el buscador, el menú, otro producto)."})
            # el hito puede consumarse por la acción recién ejecutada
            try:
                _check_milestones(hitos, reached, page.url, page.content(),
                                  steps[-1] if steps else None)
            except Exception:
                pass
        # Lo último que se mira antes de cerrar: ¿nos han enseñado la web?
        try:
            cascara = page.evaluate(
                "() => ({t: document.title || '', n: document.documentElement"
                ".outerHTML.length, txt: (document.body ? document.body.innerText "
                ": '').slice(0, 300)})")
        except Exception:
            cascara = {"t": "", "n": 0, "txt": ""}
        browser.close()

    # NUNCA hubo una página con la que operar. Eso NO es "la web no dejó al
    # agente": es que no llegamos a ver la web, y afirmar lo primero es el mismo
    # sesgo que perseguimos en el escáner estático, aquí en el único check que
    # dice literalmente "un agente no pudo usar tu web".
    # Caso real (validación jul 2026): mango.com devolvió al navegador headless
    # un "Access Denied" de 294 bytes y coolblue.nl una cáscara de 257 bytes.
    # Ambas salieron con 0% de recorrido y "no_conseguido" atribuido a la web,
    # con limite_de_metodo=False, porque `limitado` solo miraba los timeouts de
    # clic y sin elementos no se llega a clicar nada: cero timeouts.
    if not pasos_con_elementos:
        bloqueo = re.search(r"(?i)access denied|forbidden|are you a robot|"
                            r"unusual traffic|captcha|acceso denegado",
                            (cascara.get("t", "") + " " + cascara.get("txt", "")))
        motivo = (f"el navegador recibió una página de bloqueo "
                  f"(«{cascara.get('t', '')[:60]}»)" if bloqueo else
                  f"la página no expuso un solo control con el que operar "
                  f"({cascara.get('n', 0)} bytes de HTML)")
        return {"outcome": "no_verificable",
                "detail": ("NO VERIFICABLE — " + motivo + ". No es posible afirmar "
                           "que un agente no pueda usar esta web: no hemos llegado a "
                           "verla. Compruébalo a mano o repite desde otra red."),
                "steps": len(steps), "action_log": steps[:25], "progreso": _progress(),
                "limite_de_metodo": True, "timeouts": 0}

    if outcome == "conseguido" and frictions:
        outcome = "conseguido_con_friccion"
    prog = _progress()
    # Honestidad sobre el método: si la tarea se cayó por controles que no
    # respondieron al clic programático (selectores de talla, componentes JS a
    # medida), NO podemos afirmar que la web sea inoperable para un agente.
    # Nuestro harness clica por selector; Operator y Atlas usan visión y son
    # más tolerantes a esos controles. Es un límite NUESTRO y hay que decirlo.
    timeouts = sum(1 for s in steps if "TimeoutError" in s)
    # Un paso quemado porque NUESTRO modelo devolvió algo ilegible no dice nada
    # de la web. Caso real: gemini-3.5-flash con el presupuesto de salida corto
    # perdía el 39% de sus pasos así (mailchimp.com, 13 de 14), y la web cargaba
    # con el "no conseguido". Si una parte grande de la tarea se fue en eso, el
    # intento no es concluyente aunque la web nunca diera un problema.
    ilegibles = sum(1 for s in steps if "no parseable" in s)
    ruido_llm = bool(steps) and ilegibles / len(steps) >= 0.3
    limitado = (not outcome.startswith("conseguido")) and (timeouts >= 2 or ruido_llm)
    detail = ("OBJETIVO CONSEGUIDO. " if outcome.startswith("conseguido") else "NO CONSEGUIDO. ")
    if total_hitos:
        detail += f"Recorrido: {prog['alcanzados']}/{total_hitos} pasos completados"
        if prog["pendientes"]:
            detail += f" (se atascó en: {prog['pendientes'][0]})"
        detail += ". "
    detail += ("Fricciones: " + "; ".join(dict.fromkeys(frictions))) if frictions else "Sin fricciones."
    if ruido_llm and not outcome.startswith("conseguido"):
        detail += (f" AVISO DE MÉTODO: {ilegibles} de {len(steps)} pasos se perdieron "
                   "porque el modelo que pilota al agente devolvió una respuesta "
                   "ilegible. Eso es un límite NUESTRO, no un problema de la web: "
                   "el intento no es concluyente.")
    elif limitado:
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
    # "no_verificable" (nunca vimos la web) no es un intento fallido: es un
    # intento que no llegó a hacerse. Promediarlo con los demás convertiría
    # nuestra ceguera en una nota baja para el dominio.
    novers = [r for r in runs if r.get("outcome") == "no_verificable"]
    validos = [r for r in runs
               if r.get("outcome") not in ("error", "no_verificable", None)]
    if not validos and novers:
        return {"outcome": "no_verificable", "intentos": len(runs), "exitos": 0,
                "limite_de_metodo": True, "consistencia": None,
                "detail": novers[0].get("detail"), "progreso": novers[0].get("progreso"),
                "runs": [{"outcome": r.get("outcome"), "steps": r.get("steps"),
                          "alcanzados": (r.get("progreso") or {}).get("alcanzados")}
                         for r in runs]}
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
