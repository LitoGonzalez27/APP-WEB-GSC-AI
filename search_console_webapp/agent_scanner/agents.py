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

TASKS = {
    "ecommerce": ("Añade cualquier producto al carrito y avanza hasta la página de "
                  "checkout/pago. Cuando veas el formulario de pago, marca la tarea como "
                  "terminada: NO introduzcas datos de tarjeta ni completes la compra."),
    "corporativo": ("Encuentra el formulario de contacto y rellénalo con: nombre "
                    "'Test Auditoria', email 'test-auditoria@example.com', mensaje "
                    "'Prueba de auditoria tecnica, ignorar por favor'. {submit_rule}"),
    "saas": ("Encuentra la página de precios, identifica el plan de pago más barato e "
             "inicia su contratación. Cuando se pidan datos de pago o crear cuenta, marca "
             "la tarea como terminada: NO registres cuenta ni introduzcas datos de pago."),
}
SUBMIT_OK = "Cuando esté relleno, envíalo con el botón de enviar."
SUBMIT_NO = "Cuando esté relleno, marca la tarea como terminada SIN pulsar enviar."

# Controles que NUNCA se pulsan (defensa en código, no confiamos solo en el LLM)
FORBIDDEN_CLICK = re.compile(
    r"(?i)\b(pagar|finalizar (compra|pedido|pago)|realizar pedido|confirmar pago|"
    r"place order|pay now|complete (order|purchase)|checkout now|comprar ahora|"
    r"crear cuenta|create account|sign ?up|registrarme|suscribirme|subscribe)\b")
SUBMIT_HINT = re.compile(r"(?i)\b(enviar|send|submit|contactar|solicitar)\b")

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
    return t.format(submit_rule=SUBMIT_OK if allow_submit else SUBMIT_NO)


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


def _parse_action(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


# ----------------------------------------------------------- bucle navegador

def _browser_task(url, task, ask, key, allow_submit):
    from playwright.sync_api import sync_playwright
    steps, frictions, outcome = [], [], "no_conseguido"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:
            browser.close()
            return {"outcome": "error", "detail": f"no se pudo abrir la web: {exc}"[:200],
                    "steps": 0, "action_log": []}
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Tarea: {task}"}]
        for _ in range(MAX_STEPS):
            try:
                page.wait_for_timeout(700)
                elements = page.evaluate(_ELEMENTS_JS)
            except Exception:
                elements = []
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
                    page.click(f"[data-agent-idx='{idx}']", timeout=6000)
                    steps.append(f"click [{idx}] '{label[:50]}'")
                else:
                    steps.append(f"acción inválida o índice inexistente: {act}")
            except Exception as exc:
                steps.append(f"fallo al ejecutar [{idx}]: {type(exc).__name__}")
                frictions.append(f"el elemento '{label[:40]}' no respondió")
        browser.close()
    if outcome == "conseguido" and frictions:
        outcome = "conseguido_con_friccion"
    detail = ("OBJETIVO CONSEGUIDO. " if outcome.startswith("conseguido") else "NO CONSEGUIDO. ")
    detail += ("Fricciones: " + "; ".join(dict.fromkeys(frictions))) if frictions else "Sin fricciones."
    return {"outcome": outcome, "detail": detail[:600], "steps": len(steps),
            "action_log": steps[:25]}


def run_agent_tests(url, typology, providers=("chatgpt", "gemini", "claude"),
                    allow_submit=False, log=None):
    """Ejecuta la tarea con cada proveedor disponible. Devuelve dict de resultados."""
    def _log(m):
        if log is not None:
            log.append(m)
    task = build_task(typology, allow_submit)
    agents = {}
    for prov in providers:
        key = get_key(_KEY_NAMES[prov])
        if not key:
            agents[prov] = {"outcome": "no_disponible", "detail": f"sin API key de {prov}"}
            continue
        _log(f"agente {prov} intentando la tarea…")
        try:
            agents[prov] = _browser_task(url, task, _ADAPTERS[prov], key, allow_submit)
        except Exception as exc:
            agents[prov] = {"outcome": "error", "detail": str(exc)[:200]}
        _log(f"  {prov}: {agents[prov].get('outcome')}")
    return {"url": url, "typology": typology, "allow_submit": allow_submit, "agents": agents}
