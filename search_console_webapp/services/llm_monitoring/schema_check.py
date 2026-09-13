"""
Comprobación cacheada de que una migración ya se ejecutó en el entorno.

Permite desplegar código que escribe columnas nuevas sin romper un entorno donde la
migración aún no se ha lanzado: mientras falte, el código sigue por el camino antiguo.
El True se cachea para siempre; el False se vuelve a comprobar cada
SCHEMA_RECHECK_SECONDS (tras migrar empieza a usarse sin reiniciar y, mientras falte,
no se consulta el catálogo en cada tarea).
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

SCHEMA_RECHECK_SECONDS = 300


class SchemaFeature:
    """`sql` debe devolver una fila con la columna booleana `available`."""

    def __init__(self, name: str, sql: str, migration: str):
        self.name = name
        self.sql = sql
        self.migration = migration
        self._lock = threading.Lock()
        self._available = False
        self._checked_at = 0.0

    def available(self, get_connection) -> bool:
        if self._available:
            return True
        with self._lock:
            if self._available or time.monotonic() - self._checked_at < SCHEMA_RECHECK_SECONDS:
                return self._available
            self._checked_at = time.monotonic()
            conn = get_connection()
            if not conn:
                return False
            try:
                cur = conn.cursor()
                cur.execute(self.sql)
                row = cur.fetchone()
                self._available = bool(row and row['available'])
            except Exception as e:
                logger.warning(f"No se pudo comprobar el esquema de {self.name}: {e}")
                self._available = False
            finally:
                conn.close()
            if not self._available:
                logger.warning(f"Esquema de {self.name} ausente: ejecutar {self.migration}")
            return self._available

    def reset(self) -> None:
        """Olvida el resultado cacheado (tests)."""
        with self._lock:
            self._available = False
            self._checked_at = 0.0


def column_exists_sql(table: str, column: str) -> str:
    return f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = '{table}' AND column_name = '{column}'
        ) AS available
    """
