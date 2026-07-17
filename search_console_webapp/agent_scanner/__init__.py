"""Agent-Ready Scanner — motor de auditoría de preparación agéntica de webs.

Paquete autocontenido y portable:
- Sin dependencias de curl/dig del sistema (usa requests + dnspython).
- Render enchufable: Playwright (servidor) / Camoufox (local) / ninguno.
- Config env-first: lee claves de variables de entorno y, como fallback en
  local, del API Vault.

Uso programático:
    from agent_scanner.engine import audit_domain
    result = audit_domain("https://ejemplo.com")

Uso como servicio: ver agent_routes.py (blueprint Flask).
"""
from .engine import audit_domain, run_audit  # noqa: F401

__version__ = "2.0.0"
