"""
Regresión 2026-09-13: init_database() forzaba gemini-3.5-flash como current de
Google en cada arranque y deshacía cualquier cambio de modelo (migraciones,
aprobaciones del discovery o del admin). El registry no debe tocarse al arrancar.
"""

import inspect
import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import database  # noqa: E402


def test_init_database_does_not_write_model_registry():
    source = inspect.getsource(database.init_database)
    assert 'llm_model_registry' not in source
