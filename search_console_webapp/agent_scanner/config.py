# -*- coding: utf-8 -*-
"""Configuración central del scanner: claves, user-agents, rutas sondeadas.

Resolución de claves ENV-FIRST: primero variables de entorno (producción,
Railway), luego el API Vault local como fallback (desarrollo). Nunca se
imprimen valores de claves.
"""
import os
import re

# User-agents reales de los principales bots/agentes de IA (Anexo B del informe).
UA_HUMAN = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Peldaños EXTRA de la escalera de lectura, solo para la capa 1 (verificar qué
# tiene la web). NUNCA se usan en la matriz de acceso ni en la capa agéntica:
# allí el UA es el objeto de la medición y falsearlo destruiría el dato.
#
# Googlebot va aparte y DESACTIVADO por defecto a propósito. Google publica sus
# rangos y recomienda verificar por DNS inverso; los WAF serios lo comprueban,
# así que un "soy Googlebot" desde una IP de centro de datos es una firma de
# suplantación y puede bloquearse MÁS que un visitante anónimo. Además, esto
# audita también dominios de terceros: se activa por decisión explícita de quien
# audita, para su propio dominio o con permiso del cliente.
UA_ESCALERA = {
    "Bingbot": ("Mozilla/5.0 (compatible; bingbot/2.0; "
                "+http://www.bing.com/bingbot.htm)"),
}
UA_GOOGLEBOT = {
    "Googlebot-Smartphone": (
        "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile "
        "Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
}

BOT_UAS = {
    "GPTBot": ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
               "GPTBot/1.2; +https://openai.com/gptbot"),
    "OAI-SearchBot": ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
                      "OAI-SearchBot/1.0; +https://openai.com/searchbot"),
    "ChatGPT-User": ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
                     "ChatGPT-User/1.0; +https://openai.com/bot"),
    "ClaudeBot": ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
                  "ClaudeBot/1.0; +claudebot@anthropic.com)"),
    "PerplexityBot": ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
                      "PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
    "Google-Extended": "Google-Extended",
}

WELLKNOWN_PATHS = [
    "/.well-known/mcp.json", "/.well-known/api-catalog",
    "/.well-known/oauth-authorization-server", "/.well-known/ai-plugin.json",
    "/.well-known/http-message-signatures-directory",
    "/.well-known/agent.json", "/.well-known/agent-card.json",
    "/.well-known/oauth-protected-resource",
    "/auth.md", "/.well-known/skills",
    "/.well-known/x402", "/.well-known/ucp", "/.well-known/mpp",
    "/mcp", "/ask", "/agents.json", "/llms.txt", "/llms-full.txt",
    "/openapi.json", "/swagger.json", "/api-docs",
]

# Presupuestos por defecto (segundos). Configurables por entorno.
TIMEOUT_DEFAULT = int(os.environ.get("AGENT_SCANNER_TIMEOUT", "20"))
SITEMAP_URL_CAP = int(os.environ.get("AGENT_SCANNER_SITEMAP_CAP", "800"))
SAMPLE_MAX = int(os.environ.get("AGENT_SCANNER_SAMPLE_MAX", "10"))

_VAULT = os.environ.get(
    "API_VAULT_PATH", os.path.expanduser("~/Desktop/proyectos/api-vault/apis.md"))


def _vault_text():
    try:
        with open(_VAULT) as f:
            return f.read()
    except OSError:
        return ""


def get_key(name):
    """Resuelve una clave por nombre lógico. ENV primero, vault como fallback."""
    env_map = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "pagespeed": "PAGESPEED_API_KEY",
    }
    val = os.environ.get(env_map.get(name, ""))
    if val:
        return val.strip()
    # fallback vault (solo desarrollo local)
    raw = _vault_text()
    if not raw:
        return None
    if name == "openai":
        m = re.search(r"\b(sk-(?!ant-)[A-Za-z0-9_\-]{20,})", raw)
        return m.group(1) if m else None
    if name == "anthropic":
        m = re.search(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})", raw)
        return m.group(1) if m else None
    if name in ("gemini", "pagespeed"):
        sec_name = "Gemini" if name == "gemini" else "PageSpeed"
        sec = re.search(rf"## {sec_name}.*?(?=\n## |\Z)", raw, re.S)
        if sec:
            m = re.search(r"\*\*key:\*\*\s*`([^`]+)`", sec.group(0))
            if m:
                return m.group(1).strip()
        if name == "gemini":
            m = re.search(r"\bAIza[A-Za-z0-9_\-]{30,}", raw)
            return m.group(0) if m else None
    return None


def render_backend():
    """Qué motor de render usar. 'playwright' en servidor, 'camoufox' en local, 'none'."""
    forced = os.environ.get("AGENT_SCANNER_RENDER")
    if forced:
        return forced
    try:
        import playwright  # noqa: F401
        return "playwright"
    except ImportError:
        pass
    if os.path.exists(os.path.expanduser("~/Desktop/proyectos/.venv-seo-scraping/bin/python3")):
        return "camoufox"
    return "none"
