"""Sonda de renderizado: se ejecuta DENTRO del venv de scraping (Scrapling+Camoufox).

Uso: .venv-seo-scraping/bin/python3 render_probe.py <url>
Imprime una linea JSON: {"ok": true, "status": 200, "html": "..."}
"""
import json
import sys


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "falta URL"}))
        return
    url = sys.argv[1]
    try:
        from scrapling.fetchers import StealthyFetcher
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=90000)
        html = ""
        for attr in ("html_content", "body", "text"):
            val = getattr(page, attr, None)
            if val:
                html = val.decode("utf-8", "replace") if isinstance(val, bytes) else str(val)
                if len(html) > 100:
                    break
        status = getattr(page, "status", 200)
        print(json.dumps({"ok": True, "status": status, "html": html[:2_000_000]}))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:500]}))


if __name__ == "__main__":
    main()
