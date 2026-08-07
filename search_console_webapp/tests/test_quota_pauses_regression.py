"""Regresión: invariantes del sistema de cuotas/pausas y webhooks de Stripe.

Estos tests blindan tres fallos reales encontrados y corregidos:

1. Stripe enviaba `invoice.payment_succeeded` / `invoice.payment_failed`
   (guion bajo) pero el dispatcher comprobaba `invoice.payment.succeeded`
   (punto), por lo que el handler de reset de cuota + reanudación NUNCA se
   ejecutaba para clientes de pago al renovar.

2. El cron de LLM Monitoring y el engine ignoraban `paused_until`: un proyecto
   pausado por cuota no se reanudaba aunque su ventana hubiera expirado
   (a diferencia de Manual AI / AI Mode). Eso dejaba clientes de pago con su
   LLM permanentemente parado.

Son guardas a nivel de fuente: baratas, deterministas y sin red/DB.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stripe_dispatch_uses_underscore_event_names():
    """El dispatcher debe usar los nombres REALES de Stripe (guion bajo)."""
    src = _read("stripe_webhooks.py")
    assert "event_type == 'invoice.payment_succeeded'" in src
    assert "event_type == 'invoice.payment_failed'" in src


def test_stripe_dispatch_has_no_dotted_event_names():
    """No debe reaparecer el nombre erróneo con punto."""
    src = _read("stripe_webhooks.py")
    assert "invoice.payment.succeeded" not in src
    assert "invoice.payment.failed" not in src


def test_llm_cron_filter_honors_paused_until_expiry():
    """El filtro de proyectos elegibles del cron LLM debe reanudar cuando
    paused_until ya expiró (mismo criterio que Manual AI)."""
    src = _read("services/llm_monitoring_service.py")
    # tolerante a espacios: busca la cláusula paused_until <= NOW() junto al flag
    norm = re.sub(r"\s+", " ", src)
    assert "paused_until IS NOT NULL AND p.paused_until <= NOW()" in norm or \
           "p.paused_until IS NOT NULL AND p.paused_until <= NOW()" in norm


def test_llm_engine_resumes_on_expired_pause():
    """analyze_project debe: bloquear si paused_until futuro/None, pero limpiar
    el flag y continuar si ya expiró (auto-reanudación)."""
    src = _read("services/llm_monitoring/engine.py")
    norm = re.sub(r"\s+", " ", src)
    # bloquea solo si la ventana no expiró
    assert "if paused_until is None or paused_until > now_cmp:" in norm
    # al expirar, limpia el flag del proyecto
    assert "UPDATE llm_monitoring_projects SET is_paused_by_quota = FALSE" in norm


def test_llm_pause_never_sets_null_paused_until():
    """Al pausar por cuota, LLM debe tener fallback a +30d si reset_date es None,
    igual que Manual AI / AI Mode. Un paused_until NULL = pausa indefinida no
    auto-reanudable (solo saldría por webhook de pago)."""
    src = _read("services/llm_monitoring/engine.py")
    norm = re.sub(r"\s+", " ", src)
    # justo antes de pause_llm_projects_for_quota debe garantizarse no-NULL
    assert "if paused_until is None: paused_until = datetime.utcnow() + timedelta(days=30)" in norm
    # timedelta debe estar importado para que el fallback funcione
    assert re.search(r"from datetime import .*\btimedelta\b", src)


# ─────────────────────────────────────────────────────────────────────────────
# Regresión suscripciones ANUALES (bug real 2026-08-07, user 665719):
# el backfill del cron de reset copiaba el current_period_end vivo de Stripe
# a quota_reset_date. En un plan anual eso es una fecha a un año vista →
# cuota congelada 12 meses, proyectos pausados hasta la renovación, y ni el
# cron (filtraba por period_end futuro) ni el health-check (solo miraba
# fechas pasadas) podían detectarlo o repararlo.
# ─────────────────────────────────────────────────────────────────────────────

def test_quota_cron_does_not_exclude_annual_mid_period_users():
    """La query de selección del cron debe elegir por quota_reset_date
    vencido, SIN exigir current_period_end NULL/pasado: los planes anuales
    tienen period_end hasta un año en el futuro y sus resets mensuales
    intermedios dependen de este cron (solo hay una factura al año)."""
    src = _read("daily_quota_reset_cron.py")
    norm = re.sub(r"\s+", " ", src)
    assert "(quota_reset_date IS NULL OR quota_reset_date <= NOW())" in norm
    # el gate antiguo por periodo Stripe no debe reaparecer en la selección
    assert "OR current_period_end <= NOW()" not in norm


def test_quota_cron_backfill_never_copies_period_end_to_reset_date():
    """El backfill de period_end vivo NUNCA debe usarse como quota_reset_date
    directamente — en anuales congela la cuota un año. La fecha de reset debe
    salir siempre de compute_next_quota_reset_date (30d, cap en period_end)."""
    src = _read("daily_quota_reset_cron.py")
    norm = re.sub(r"\s+", " ", src)
    # el UPDATE antiguo escribía (live_period_end, live_period_end, user_id)
    assert "(live_period_end, live_period_end, user_id)" not in norm
    # la inicialización usa compute con el period_end vivo como cap
    assert "compute_next_quota_reset_date( period_end=live_period_end" in norm


def test_health_check_flags_far_future_reset_dates():
    """El health-check debe alertar también de quota_reset_date demasiado
    futuro (>35d es imposible con ciclos mensuales de 30d), no solo pasado."""
    src = _read("cron_routes.py")
    norm = re.sub(r"\s+", " ", src)
    assert "quota_reset_date > NOW() + INTERVAL '35 days'" in norm


def test_compute_next_reset_annual_subscription_behavior():
    """compute_next_quota_reset_date con period_end anual debe dar el próximo
    ciclo de ~30 días, jamás el period_end lejano; y debe seguir haciendo cap
    en period_end cuando este cae dentro del ciclo (mensuales)."""
    import os as _os
    import sys as _sys
    from datetime import datetime
    _os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5/dummy")
    _sys.path.insert(0, str(ROOT))
    from quota_manager import compute_next_quota_reset_date

    # Anual: inicialización a mitad de periodo → now+30d, no jun-2027
    r = compute_next_quota_reset_date(
        period_end=datetime(2027, 6, 10, 8, 40, 42), now=datetime(2026, 6, 15)
    )
    assert r == datetime(2026, 7, 15)

    # Anual: reset vencido → avanza en ventanas de 30d, nunca salta al period_end
    r = compute_next_quota_reset_date(
        last_reset=datetime(2026, 7, 10), period_end=datetime(2027, 6, 10),
        now=datetime(2026, 8, 10)
    )
    assert r == datetime(2026, 9, 8)

    # Mensual: cap en period_end cuando base+30d lo sobrepasa
    r = compute_next_quota_reset_date(
        last_reset=datetime(2026, 8, 1), period_end=datetime(2026, 8, 20),
        now=datetime(2026, 8, 2)
    )
    assert r == datetime(2026, 8, 20)
