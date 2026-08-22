"""
Pasada de completitud del cron LLM Monitoring (Fase B).

Problema que resuelve: cuando un análisis termina incompleto (p.ej. cascada de
529 de Anthropic → circuit breaker → huecos), el snapshot del día queda corto
para siempre — la siguiente oportunidad era el cron de 24h después, que crea
resultados para OTRA fecha.

Diseño (escalable a muchos proyectos/clientes):
- Coste CERO cuando todo está completo: solo se activa para proyectos cuyo
  análisis reportó `incomplete_llms`.
- Quirúrgica: reintenta SOLO los pares (query_id, llm) que faltan o quedaron
  como filas de error — nunca re-analiza un proyecto entero (la reconciliación
  antigua de daily_llm_monitoring_cron.py duplicaba el coste API del proyecto).
- Acotada: deadline global (LLM_COMPLETION_MAX_SECONDS), cap de pares por
  proyecto (LLM_COMPLETION_MAX_PAIRS) con log explícito si trunca, y un solo
  intento por proyecto y run.
- Espera de asentamiento (LLM_COMPLETION_SETTLE_SECONDS) antes de empezar:
  si el batch terminó con un provider sobrecargado/breaker abierto, reintentar
  al instante repite el fallo.

Las funciones de este módulo son puras (sin BD) para poder testearse en
aislamiento; la orquestación con BD vive en llm_monitoring_service.py
(run_completion_pass) y en engine.analyze_project(restrict_pairs=...).
"""

import os
from typing import Dict, List, Optional, Sequence, Set, Tuple

# Defaults de configuración (todos ajustables por env sin deploy)
DEFAULT_MAX_SECONDS = 900        # presupuesto total de la pasada (15 min)
DEFAULT_SETTLE_SECONDS = 120     # espera antes de empezar (= 1 cooldown del breaker)
DEFAULT_MAX_PAIRS_PER_PROJECT = 200  # cap de pares reintentados por proyecto


def get_completion_config() -> Dict:
    """Lee la configuración de la pasada de completitud desde env (con defaults)."""
    def _int_env(name, default):
        try:
            return int(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default

    return {
        'enabled': os.getenv('LLM_COMPLETION_PASS_ENABLED', 'true').lower() != 'false',
        'max_seconds': _int_env('LLM_COMPLETION_MAX_SECONDS', DEFAULT_MAX_SECONDS),
        'settle_seconds': _int_env('LLM_COMPLETION_SETTLE_SECONDS', DEFAULT_SETTLE_SECONDS),
        'max_pairs_per_project': _int_env('LLM_COMPLETION_MAX_PAIRS', DEFAULT_MAX_PAIRS_PER_PROJECT),
    }


def task_allowed(restrict_pairs: Optional[Dict[str, Sequence[int]]],
                 llm_name: str, query_id: int) -> bool:
    """
    ¿Debe ejecutarse el par (llm, query) dado el modo restringido?

    Sin restrict_pairs (análisis normal) todo pasa. Con restrict_pairs, solo
    los pares listados — un llm ausente del dict no ejecuta nada.
    """
    if restrict_pairs is None:
        return True
    allowed_ids = restrict_pairs.get(llm_name)
    if not allowed_ids:
        return False
    return query_id in allowed_ids


def count_planned_tasks(queries: Sequence[Dict],
                        active_provider_names: Sequence[str],
                        restrict_pairs: Optional[Dict[str, Sequence[int]]] = None) -> int:
    """
    Número de tareas que realmente se van a ejecutar (para el chequeo de cuota
    mensual). En modo restringido cuenta solo los pares válidos: ids que
    existen en las queries activas × providers activos.
    """
    if restrict_pairs is None:
        return len(queries) * len(active_provider_names)

    active_ids = {q['id'] for q in queries}
    total = 0
    for llm_name in active_provider_names:
        ids = restrict_pairs.get(llm_name) or []
        total += sum(1 for qid in ids if qid in active_ids)
    return total


def compute_missing_pairs(
    active_query_ids: Sequence[int],
    ok_pairs: Set[Tuple[int, str]],
    llms: Sequence[str],
    max_pairs: Optional[int] = None,
) -> Tuple[Dict[str, List[int]], int]:
    """
    Calcula los pares (query, llm) que faltan por completar.

    Args:
        active_query_ids: ids de queries activas del proyecto HOY (ya excluidos
            los sets fuera de ventana — misma regla que usó el análisis).
        ok_pairs: pares (query_id, llm) con resultado OK guardado en BD para la
            fecha (las filas con has_error=TRUE NO cuentan como OK y por tanto
            se reintentan).
        llms: providers a considerar (los que terminaron incompletos).
        max_pairs: cap opcional del total de pares devueltos.

    Returns:
        (missing, truncated): dict {llm: [query_ids]} y cuántos pares se
        quedaron fuera por el cap (0 si no truncó). El orden de llms y de
        queries se preserva para que el truncado sea determinista.
    """
    missing: Dict[str, List[int]] = {}
    total = 0
    truncated = 0

    for llm in llms:
        for qid in active_query_ids:
            if (qid, llm) in ok_pairs:
                continue
            if max_pairs is not None and total >= max_pairs:
                truncated += 1
                continue
            missing.setdefault(llm, []).append(qid)
            total += 1

    return missing, truncated
