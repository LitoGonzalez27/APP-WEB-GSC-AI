# -*- coding: utf-8 -*-
"""Catálogo de factores analizados: la lista que se muestra en el formulario.

Fuente de verdad para la UI (transparencia de qué se analiza y selección
granular). Se valida contra checks.py con `python3 -m agent_scanner.catalog`.
"""

CATEGORIES = {
    "C1": "Discoverability & access",
    "C2": "Identity & bot control",
    "C3": "Structured data",
    "C4": "Rendering & architecture",
    "C5": "Content for LLMs",
    "C6": "Capabilities & actions",
    "C7": "Agentic commerce",
}

# (id, categoría, nombre, qué comprueba en una línea)
CHECKS = [
    ("1.1", "C1", "Valid robots.txt", "Exists and is parseable (not a SPA's HTML)"),
    ("1.2", "C1", "AI bot policy", "Per-bot rules; don't block live-search bots"),
    ("1.3", "C1", "Declared vs actual blocking", "Real requests with each bot's UA vs what robots.txt says"),
    ("1.4", "C1", "Fresh sitemap.xml", "Exists, is referenced and has a recent lastmod"),
    ("1.5", "C1", "Link headers (RFC 8288)", "Discovery Link headers"),
    ("1.6", "C1", "Content accessible without login", "Key pages render content without a session"),
    ("1.7", "C1", "DNS-AID", "_aid/_agent TXT records (experimental standard)"),
    ("1.8", "C1", "Citation metadata", "canonical, lang and Open Graph: what prevents broken citations and previews"),

    ("2.1", "C2", "Declared Content Signals", "search / ai-input / ai-train in robots.txt"),
    ("2.2", "C2", "Active crawl management", "A CDN/WAF that monitors and controls AI bots"),
    ("2.3", "C2", "Web Bot Auth", "Cryptographic agent verification (RFC 9421)"),
    ("2.4", "C2", "Reasonable rate limiting", "10 requests in a row: does it ban or throttle sensibly?"),

    ("3.1", "C3", "JSON-LD present and valid", "Extraction and validation of the markup on templates"),
    ("3.2", "C3", "Complete Organization entity", "name, url, logo, sameAs, contactPoint"),
    ("3.3", "C3", "Operational Product/Offer", "price, priceCurrency, availability on product pages"),
    ("3.4", "C3", "Rich attributes in the markup", "GTIN, brand, reviews, dates, specs"),
    ("3.5", "C3", "Semantic HTML", "Heading hierarchy, landmarks, real buttons"),
    ("3.6", "C3", "Agent-readable controls", "Accessibility-tree controls without an accessible name: the agent sees them but doesn't know what they do"),
    ("3.7", "C3", "Wikipedia/Wikidata entity", "Wikidata item with P856 pointing to the domain: identity verifiable from outside"),

    ("4.1", "C4", "Content without running JS", "Raw vs rendered HTML: what AI bots see"),
    ("4.2", "C4", "Price and CTA without JS", "The price and the buy button exist without JavaScript"),
    ("4.3", "C4", "Speed for bots (TTFB)", "Response time measured on every page"),
    ("4.4", "C4", "Stable deep-linking", "Direct, session-free URLs for every state"),
    ("4.5", "C4", "Detectable public API", "OpenAPI/Swagger on standard paths"),
    ("4.6", "C4", "Visual stability (CLS)", "Layout shifts that confuse agents"),
    ("4.7", "C4", "Operable click targets", "Actual control size (≥24px) measured in the render"),
    ("4.8", "C4", "Correct error states", "Non-existent URL: a real 404 or a soft-404 that misleads the agent?"),
    ("4.9", "C4", "Redirect hygiene", "No meta-refresh/JS stubs or domain hops that lose an agent without JS"),

    ("5.1", "C5", "Direct answer up top", "Data density vs marketing filler after the H1"),
    ("5.2", "C5", "Chunkable structure", "Self-contained, citable H2/H3 sections"),
    ("5.3", "C5", "Verifiable E-E-A-T", "Authorship, dates and sources in the content"),
    ("5.5", "C5", "llms.txt (hygiene)", "Guide file for LLMs (low weight: almost nobody reads it)"),
    ("5.6", "C5", "Markdown negotiation", "Accept: text/markdown → does it serve a lightweight version?"),
    ("5.7", "C5", "Trust pages", "About/Contact/Privacy verified with real content (multilingual)"),
    ("5.8", "C5", "Token budget per page", "Each page fits in ~25K tokens: read in full, without truncation"),

    ("6.1", "C6", "Agentic surface", "MCP Server Card, A2A, WebMCP, API Catalog, OAuth"),
    ("6.2", "C6", "Operable forms", "Verified label for=id, autocomplete, real submit"),
    ("6.3", "C6", "Task with a real agent", "ChatGPT/Gemini/Claude driving a real browser"),
    ("6.4", "C6", "Agent-operable authentication", "Delegated OAuth or a login form an agent can fill in"),

    ("7.1", "C7", "Structured feed/catalog", "E-commerce platform and Product schema on product pages"),
    ("7.2", "C7", "Price consistency", "JSON-LD price vs visible price (anti-hallucination)"),
    ("7.3", "C7", "ACP readiness", "PSP compatible with agentic checkout (Stripe/Shopify)"),
    ("7.4", "C7", "Emerging protocols", "x402/UCP/MPP (informational, not scored)"),
    ("7.5", "C7", "Readable shipping policy", "OfferShippingDetails: delivery time and cost before buying"),
    ("7.6", "C7", "Readable returns policy", "MerchantReturnPolicy: days and conditions in the markup"),
]


def as_dict():
    """Estructura lista para la UI: categorías con sus factores."""
    out = []
    for cat, nombre in CATEGORIES.items():
        items = [{"id": i, "nombre": n, "descripcion": d}
                 for i, c, n, d in CHECKS if c == cat]
        out.append({"categoria": cat, "nombre": nombre, "factores": items})
    return out


def check_ids():
    return [i for i, _c, _n, _d in CHECKS]


if __name__ == "__main__":
    # Valida que el catálogo no se desincronice de checks.py
    import os
    import re
    path = os.path.join(os.path.dirname(__file__), "checks.py")
    real = set(re.findall(r'R\("(\d+\.\d+)"', open(path).read()))
    mine = set(check_ids())
    faltan, sobran = real - mine, mine - real
    print("catalog:", len(mine), "· engine:", len(real))
    print("MISSING from catalog:", sorted(faltan) or "none")
    print("EXTRA in catalog:", sorted(sobran) or "none")
