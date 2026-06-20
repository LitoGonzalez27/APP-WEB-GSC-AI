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
