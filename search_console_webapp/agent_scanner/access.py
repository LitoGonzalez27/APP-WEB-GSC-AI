# -*- coding: utf-8 -*-
"""Control de acceso al panel Agent Readiness por lista de emails.

Regla: tienen acceso los ADMIN (siempre) + los emails de la allowlist.
Persistencia: tabla nueva y AISLADA `agent_scanner_access` (no toca ninguna
tabla existente de clicandseo). Se crea sola la primera vez (idempotente).
"""
import logging

logger = logging.getLogger(__name__)

_TABLE_READY = False


def _conn():
    from database import get_db_connection
    return get_db_connection()


def ensure_table():
    """Crea la tabla si no existe. Idempotente y barato (flag en memoria)."""
    global _TABLE_READY
    if _TABLE_READY:
        return
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_scanner_access (
                    email       TEXT PRIMARY KEY,
                    added_by    TEXT,
                    added_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
        _TABLE_READY = True
    except Exception as exc:
        logger.warning(f"agent_scanner_access: no se pudo crear la tabla: {exc}")


def list_emails():
    ensure_table()
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT email, added_by, added_at FROM agent_scanner_access "
                        "ORDER BY added_at DESC")
            rows = cur.fetchall()
        out = []
        for r in rows:
            # compatible con RealDictCursor (dict) o tupla
            if isinstance(r, dict):
                out.append({"email": r["email"], "added_by": r.get("added_by"),
                            "added_at": str(r.get("added_at", ""))[:19]})
            else:
                out.append({"email": r[0], "added_by": r[1], "added_at": str(r[2])[:19]})
        return out
    except Exception as exc:
        logger.warning(f"agent_scanner_access.list: {exc}")
        return []


def add_email(email, added_by=None):
    ensure_table()
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "email no válido"
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO agent_scanner_access (email, added_by) VALUES (%s, %s) "
                "ON CONFLICT (email) DO NOTHING", (email, added_by))
            conn.commit()
        return True, email
    except Exception as exc:
        logger.warning(f"agent_scanner_access.add: {exc}")
        return False, str(exc)[:120]


def remove_email(email):
    ensure_table()
    email = (email or "").strip().lower()
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM agent_scanner_access WHERE email = %s", (email,))
            conn.commit()
        return True
    except Exception as exc:
        logger.warning(f"agent_scanner_access.remove: {exc}")
        return False


def _allowed_emails():
    return {e["email"] for e in list_emails()}


def user_has_access(user):
    """True si el usuario es admin o su email está en la allowlist."""
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    email = (user.get("email") or "").strip().lower()
    return bool(email) and email in _allowed_emails()


def _agent_url():
    import os
    base = (os.getenv("PUBLIC_BASE_URL") or "https://app.clicandseo.com").rstrip("/")
    return f"{base}/agent/"


def send_invitation_email(email, invited_by_name=None):
    """Envía el email de invitación reutilizando el servicio SMTP de la app.
    Devuelve True si se envió, False si no (sin romper el flujo de acceso)."""
    try:
        from email_service import send_email, LOGO_URL
    except Exception as exc:
        logger.warning(f"invitación agent: email_service no disponible: {exc}")
        return False
    url = _agent_url()
    quien = f" por {invited_by_name}" if invited_by_name else ""
    subject = "Tienes acceso a Agent Readiness en Clicandseo"
    html_body = f"""
<div style="font-family:'Inter Tight',Arial,sans-serif;max-width:560px;margin:0 auto;color:#0F172A">
  <div style="text-align:center;padding:24px 0"><img src="{LOGO_URL}" alt="Clicandseo" style="height:28px"></div>
  <div style="background:#0A0A0B;border-radius:16px;padding:36px 32px;color:#F8FAFC">
    <p style="font-family:Georgia,serif;font-style:italic;color:#94A3B8;margin:0 0 10px">Auditoría de preparación agéntica</p>
    <h1 style="font-size:24px;font-weight:800;letter-spacing:-.02em;margin:0 0 14px;color:#F8FAFC">
      Se te ha dado acceso a <span style="color:#D9F9B8">Agent Readiness</span></h1>
    <p style="color:#94A3B8;font-size:15px;line-height:1.6;margin:0 0 24px">
      Ya puedes usar la nueva herramienta de Clicandseo para auditar si una web está preparada
      para la era de los agentes de IA{quien}. Analiza tu dominio y el de tus competidores,
      con informe visual, comparativa y hasta 3 IAs probando la web en un navegador real.</p>
    <a href="{url}" style="display:inline-block;background:#D9F9B8;color:#0A0A0B;font-weight:800;
      text-decoration:none;border-radius:12px;padding:14px 28px;font-size:15px">Entrar a Agent Readiness →</a>
    <p style="color:#64748B;font-size:13px;line-height:1.6;margin:24px 0 0">
      Si el botón no funciona, copia este enlace: <br><span style="color:#94A3B8">{url}</span><br><br>
      Usa la cuenta de Clicandseo asociada a este email. Si aún no has iniciado sesión, te pedirá login primero.</p>
  </div>
  <p style="text-align:center;color:#94A3B8;font-size:12px;padding:18px 0">Clicandseo · Agent Readiness</p>
</div>"""
    text_body = (f"Se te ha dado acceso a Agent Readiness en Clicandseo{quien}.\n\n"
                 f"Entra aquí: {url}\n\nUsa la cuenta de Clicandseo asociada a este email.")
    try:
        return bool(send_email(email, subject, html_body, text_body))
    except Exception as exc:
        logger.warning(f"invitación agent: fallo al enviar email a {email}: {exc}")
        return False
