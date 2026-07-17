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
