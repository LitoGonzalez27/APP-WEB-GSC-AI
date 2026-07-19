# -*- coding: utf-8 -*-
"""Persistencia de informes del Agent-Ready Scanner.

Hasta ahora los análisis vivían SOLO en memoria del proceso web: un deploy o un
reinicio de Railway los borraba, y con ellos los enlaces de descarga de PDF y
JSON que el cliente ya tuviera abiertos. Para poder entregar con garantías hace
falta que un informe siga existiendo mañana.

Diseño, en la línea de access.py:
  - Tabla NUEVA y AISLADA `agent_scanner_reports`. No toca ni lee ninguna tabla
    existente de clicandseo.
  - Se crea sola la primera vez (idempotente, con flag en memoria).
  - TODO fallo de base de datos se traga y se registra: si Postgres no está
    disponible, el scanner sigue funcionando exactamente como antes, con los
    informes en memoria. La persistencia mejora el producto pero nunca puede
    ser el motivo de que un análisis falle.
"""
import json
import logging

logger = logging.getLogger(__name__)

_TABLE_READY = False
DISPONIBLE = None   # None = aún no se sabe; True/False tras el primer intento


def _conn():
    from database import get_db_connection
    return get_db_connection()


def ensure_table():
    """Crea la tabla si no existe. Idempotente y barato."""
    global _TABLE_READY, DISPONIBLE
    if _TABLE_READY:
        return True
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_scanner_reports (
                    id            TEXT PRIMARY KEY,
                    user_email    TEXT,
                    client_host   TEXT,
                    competitors   TEXT,
                    typology      TEXT,
                    score         REAL,
                    score_fiable  BOOLEAN,
                    agents_estado TEXT,
                    data          JSONB NOT NULL,
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    updated_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # el historial se consulta por usuario y por fecha
            cur.execute("""CREATE INDEX IF NOT EXISTS idx_agent_reports_user
                           ON agent_scanner_reports (user_email, created_at DESC)""")
            conn.commit()
        _TABLE_READY = True
        DISPONIBLE = True
        return True
    except Exception as exc:
        DISPONIBLE = False
        logger.warning(f"agent_scanner_reports: no se pudo crear la tabla: {exc}")
        return False


def guardar(job_id, data, user_email=None):
    """Guarda (o actualiza) un informe. Devuelve True si se persistió."""
    if not ensure_table():
        return False
    try:
        cliente = data.get("client") or {}
        comps = [c.get("host") for c in (data.get("competitors") or []) if c.get("host")]
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO agent_scanner_reports
                    (id, user_email, client_host, competitors, typology, score,
                     score_fiable, agents_estado, data, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    data = EXCLUDED.data,
                    score = EXCLUDED.score,
                    score_fiable = EXCLUDED.score_fiable,
                    agents_estado = EXCLUDED.agents_estado,
                    updated_at = NOW()
            """, (job_id, user_email, cliente.get("host"), ", ".join(comps),
                  cliente.get("typology"), cliente.get("score"),
                  cliente.get("score_fiable", True),
                  (data.get("agentes") or {}).get("estado"),
                  json.dumps(data, ensure_ascii=False)))
            conn.commit()
        return True
    except Exception as exc:
        logger.warning(f"agent_scanner_reports: fallo al guardar {job_id}: {exc}")
        return False


def cargar(job_id):
    """Recupera un informe guardado. None si no existe o si la BD no responde."""
    if not ensure_table():
        return None
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM agent_scanner_reports WHERE id = %s", (job_id,))
            fila = cur.fetchone()
        if not fila:
            return None
        bruto = fila[0] if not isinstance(fila, dict) else fila.get("data")
        return json.loads(bruto) if isinstance(bruto, str) else bruto
    except Exception as exc:
        logger.warning(f"agent_scanner_reports: fallo al cargar {job_id}: {exc}")
        return None


def historial(user_email=None, limite=30):
    """Lista de informes anteriores (sin el JSON completo, solo la cabecera)."""
    if not ensure_table():
        return []
    try:
        with _conn() as conn:
            cur = conn.cursor()
            if user_email:
                cur.execute("""
                    SELECT id, client_host, competitors, typology, score, score_fiable,
                           agents_estado, created_at
                    FROM agent_scanner_reports WHERE user_email = %s
                    ORDER BY created_at DESC LIMIT %s""", (user_email, limite))
            else:
                cur.execute("""
                    SELECT id, client_host, competitors, typology, score, score_fiable,
                           agents_estado, created_at
                    FROM agent_scanner_reports
                    ORDER BY created_at DESC LIMIT %s""", (limite,))
            filas = cur.fetchall()
        out = []
        for f in filas:
            v = list(f.values()) if isinstance(f, dict) else list(f)
            out.append({"id": v[0], "host": v[1], "competidores": v[2], "tipologia": v[3],
                        "score": v[4], "fiable": v[5], "agentes": v[6],
                        "fecha": v[7].isoformat() if v[7] else None})
        return out
    except Exception as exc:
        logger.warning(f"agent_scanner_reports: fallo al listar historial: {exc}")
        return []


def borrar(job_id, user_email=None):
    """Borra un informe. Si se pasa user_email, solo borra si es suyo."""
    if not ensure_table():
        return False
    try:
        with _conn() as conn:
            cur = conn.cursor()
            if user_email:
                cur.execute("DELETE FROM agent_scanner_reports WHERE id = %s AND user_email = %s",
                            (job_id, user_email))
            else:
                cur.execute("DELETE FROM agent_scanner_reports WHERE id = %s", (job_id,))
            borradas = cur.rowcount
            conn.commit()
        return borradas > 0
    except Exception as exc:
        logger.warning(f"agent_scanner_reports: fallo al borrar {job_id}: {exc}")
        return False
