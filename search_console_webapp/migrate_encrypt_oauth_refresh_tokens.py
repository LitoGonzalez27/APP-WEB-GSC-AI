#!/usr/bin/env python3
"""
Migración de seguridad: re-cifrar refresh tokens de OAuth guardados en texto plano.

Contexto
--------
Históricamente `_get_fernet()` leía la variable TOKEN_ENCRYPTION_KEY, pero el
entorno define ENCRYPTION_KEY, por lo que el cifrado quedaba desactivado y la
columna `oauth_connections.refresh_token_encrypted` almacenaba el token EN CLARO.

Tras el fix (leer también ENCRYPTION_KEY), los NUEVOS tokens se cifran. Este
script re-cifra los que ya estaban guardados en claro.

Seguridad de la migración
-------------------------
- IDEMPOTENTE: si el valor ya está cifrado (Fernet lo descifra sin error) se omite.
- NO DESTRUCTIVO: solo actualiza filas cuyo valor NO es un token Fernet válido.
- Requiere que exista la clave de cifrado; si no, aborta sin tocar nada.
- Cada fila se actualiza en su propia transacción (un fallo no arrastra al resto).

Uso (en Railway, intencionadamente — NO se ejecuta en cada deploy):
    railway run --service <servicio> python3 migrate_encrypt_oauth_refresh_tokens.py
    # añade --dry-run para solo contar sin escribir
"""
import os
import sys

from database import get_db_connection, _get_fernet


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    fernet = _get_fernet()
    if fernet is None:
        print("❌ No hay clave de cifrado disponible (TOKEN_ENCRYPTION_KEY/ENCRYPTION_KEY). Aborta.")
        return 1

    conn = get_db_connection()
    if conn is None:
        print("❌ Sin conexión a la base de datos. Aborta.")
        return 1

    scanned = already_encrypted = re_encrypted = empty = errors = 0
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, refresh_token_encrypted FROM oauth_connections "
            "WHERE refresh_token_encrypted IS NOT NULL"
        )
        rows = cur.fetchall()

        for row in rows:
            scanned += 1
            conn_id = row["id"]
            value = row["refresh_token_encrypted"]

            if not value:
                empty += 1
                continue

            # ¿Ya está cifrado? Si Fernet lo descifra sin error, no tocar.
            try:
                fernet.decrypt(value.encode("utf-8"))
                already_encrypted += 1
                continue
            except Exception:
                pass  # No es un token Fernet válido → está en texto plano.

            if dry_run:
                re_encrypted += 1
                continue

            try:
                encrypted = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
                upd = conn.cursor()
                upd.execute(
                    "UPDATE oauth_connections SET refresh_token_encrypted = %s, updated_at = NOW() "
                    "WHERE id = %s",
                    (encrypted, conn_id),
                )
                conn.commit()
                re_encrypted += 1
            except Exception as e:
                conn.rollback()
                errors += 1
                print(f"  ⚠️ Error re-cifrando conexión id={conn_id}: {e}")

        print("─" * 60)
        print(f"Filas escaneadas:        {scanned}")
        print(f"Ya cifradas (omitidas):  {already_encrypted}")
        print(f"Vacías (omitidas):       {empty}")
        print(f"{'Re-cifrables' if dry_run else 'Re-cifradas'}:            {re_encrypted}")
        print(f"Errores:                 {errors}")
        if dry_run:
            print("\n(dry-run: no se escribió nada)")
        return 0 if errors == 0 else 2
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
