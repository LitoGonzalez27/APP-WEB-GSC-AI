# -*- coding: utf-8 -*-
"""Catálogo de factores analizados: la lista que se muestra en el formulario.

Fuente de verdad para la UI (transparencia de qué se analiza y selección
granular). Se valida contra checks.py con `python3 -m agent_scanner.catalog`.
"""

CATEGORIES = {
    "C1": "Descubribilidad y acceso",
    "C2": "Identidad y control de bots",
    "C3": "Datos estructurados",
    "C4": "Renderizado y arquitectura",
    "C5": "Contenido para LLMs",
    "C6": "Capacidades y acciones",
    "C7": "Comercio agéntico",
}

# (id, categoría, nombre, qué comprueba en una línea)
CHECKS = [
    ("1.1", "C1", "robots.txt válido", "Que exista y sea parseable (no HTML de una SPA)"),
    ("1.2", "C1", "Política de bots de IA", "Reglas nominales por bot; no bloquear los de búsqueda en vivo"),
    ("1.3", "C1", "Bloqueo declarado vs real", "Peticiones reales con el UA de cada bot vs lo que dice robots.txt"),
    ("1.4", "C1", "sitemap.xml fresco", "Existe, referenciado y con lastmod reciente"),
    ("1.5", "C1", "Link headers (RFC 8288)", "Cabeceras Link de descubrimiento"),
    ("1.6", "C1", "Contenido accesible sin login", "Las páginas clave rinden contenido sin sesión"),
    ("1.7", "C1", "DNS-AID", "Registros TXT _aid/_agent (estándar experimental)"),

    ("2.1", "C2", "Content Signals declarados", "search / ai-input / ai-train en robots.txt"),
    ("2.2", "C2", "Gestión activa de crawl", "CDN/WAF que vigile y controle los bots de IA"),
    ("2.3", "C2", "Web Bot Auth", "Verificación criptográfica de agentes (RFC 9421)"),
    ("2.4", "C2", "Rate limiting razonable", "10 peticiones seguidas: ¿banea o throttlea con criterio?"),

    ("3.1", "C3", "JSON-LD presente y válido", "Extracción y validación del marcado en las plantillas"),
    ("3.2", "C3", "Entidad Organization completa", "name, url, logo, sameAs, contactPoint"),
    ("3.3", "C3", "Product/Offer operativo", "price, priceCurrency, availability en fichas"),
    ("3.4", "C3", "Atributos ricos en el marcado", "GTIN, brand, reviews, fechas, specs"),
    ("3.5", "C3", "HTML semántico", "Jerarquía de headings, landmarks, botones reales"),
    ("3.6", "C3", "Elementos fantasma", "div/span clicables invisibles en el árbol de accesibilidad"),

    ("4.1", "C4", "Contenido sin ejecutar JS", "HTML crudo vs renderizado: lo que ven los bots de IA"),
    ("4.2", "C4", "Precio y CTA sin JS", "El precio y el botón de compra existen sin JavaScript"),
    ("4.3", "C4", "Velocidad para bots (TTFB)", "Tiempo de respuesta medido en todas las páginas"),
    ("4.4", "C4", "Deep-linking estable", "URLs directas y sin sesión para cada estado"),
    ("4.5", "C4", "API pública detectable", "OpenAPI/Swagger en rutas estándar"),
    ("4.6", "C4", "Estabilidad visual (CLS)", "Saltos de layout que confunden a los agentes"),
    ("4.7", "C4", "Zonas de clic operables", "Tamaño real de los controles (≥24px) medido en el render"),
    ("4.8", "C4", "Estados de error correctos", "URL inexistente: ¿404 real o soft-404 que engaña al agente?"),

    ("5.1", "C5", "Respuesta directa arriba", "Densidad de datos vs relleno de marketing tras el H1"),
    ("5.2", "C5", "Estructura chunkeable", "Secciones H2/H3 autocontenidas y citables"),
    ("5.3", "C5", "E-E-A-T verificable", "Autoría, fechas y fuentes en el contenido"),
    ("5.5", "C5", "llms.txt (higiene)", "Fichero guía para LLMs (peso bajo: casi nadie lo lee)"),
    ("5.6", "C5", "Negociación Markdown", "Accept: text/markdown → ¿sirve versión ligera?"),

    ("6.1", "C6", "Superficie agéntica", "MCP Server Card, A2A, WebMCP, API Catalog, OAuth"),
    ("6.2", "C6", "Formularios operables", "label for=id verificado, autocomplete, submit real"),
    ("6.3", "C6", "Tarea con agente real", "ChatGPT/Gemini/Claude pilotando un navegador de verdad"),
    ("6.4", "C6", "Autenticación operable por agentes", "OAuth delegado o formulario de acceso que un agente sepa rellenar"),

    ("7.1", "C7", "Feed/catálogo estructurado", "Plataforma e-commerce y Product schema en fichas"),
    ("7.2", "C7", "Consistencia de precio", "Precio del JSON-LD vs el visible (anti-alucinación)"),
    ("7.3", "C7", "Preparación ACP", "PSP compatible con checkout agéntico (Stripe/Shopify)"),
    ("7.4", "C7", "Protocolos emergentes", "x402/UCP/MPP (informativo, no puntúa)"),
    ("7.5", "C7", "Política de envío legible", "OfferShippingDetails: plazo y coste antes de comprar"),
    ("7.6", "C7", "Política de devoluciones legible", "MerchantReturnPolicy: días y condiciones en el marcado"),
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
    print("catálogo:", len(mine), "· motor:", len(real))
    print("FALTAN en catálogo:", sorted(faltan) or "ninguno")
    print("SOBRAN en catálogo:", sorted(sobran) or "ninguno")
