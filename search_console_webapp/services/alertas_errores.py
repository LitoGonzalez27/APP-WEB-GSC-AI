"""Avisos por email de los errores de la aplicación (oct-2026).

Hasta ahora los errores solo quedaban en los logs de Railway: si algo fallaba
de madrugada, nadie se enteraba hasta que un cliente lo notaba. Este handler
recoge los registros de nivel ERROR o superior (también las excepciones sin
capturar de las rutas y de los hilos) y envía un resumen por email:

- agrupa por tipo de error (logger, fichero, línea y tipo de excepción) y cuenta;
- espera AGRUPAR_SEGUNDOS tras el primer error para juntar ráfagas y no manda
  más de un email cada INTERVALO_MINIMO_SEGUNDOS ni más de MAX_EMAILS_DIA al día
  (lo que no cabe se cuenta y se resume en el primer email del día siguiente);
- ignora el ruido conocido (IGNORAR) y los errores de su propio envío;
- oculta secretos de URL (services.log_seguro) y enmascara emails;
- nunca bloquea ni lanza: emit() solo apunta en memoria; el envío va en un hilo.

Solo se instala en Railway (config.desplegado()) y se apaga con
ERROR_ALERTS_ENABLED=false. Destinatario: config.email_alertas().
"""

import logging
import os
import re
import threading
import time
import traceback
from datetime import datetime, timezone
from html import escape

AGRUPAR_SEGUNDOS = int(os.getenv('ERROR_ALERTS_GROUP_SECONDS', '60'))
INTERVALO_MINIMO_SEGUNDOS = int(os.getenv('ERROR_ALERTS_MIN_INTERVAL_SECONDS', '900'))
# Tope diario: aunque algo provoque errores en bucle, no más de estos emails al día.
MAX_EMAILS_DIA = int(os.getenv('ERROR_ALERTS_MAX_PER_DAY', '12'))
MAX_TIPOS = 50
# Ruido conocido: cualquiera puede provocarlo desde fuera y no indica un fallo.
IGNORAR = (
    'Missing Stripe signature',
    'Redis no disponible',
)
_EMAIL = re.compile(r'([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})')


def _limpiar(texto):
    from services.log_seguro import ocultar_secretos_en_url
    return _EMAIL.sub(r'\1***@\2', ocultar_secretos_en_url(str(texto)))


class AvisoErrores(logging.Handler):
    def __init__(self, enviar, etiqueta_entorno, agrupar=AGRUPAR_SEGUNDOS, intervalo=INTERVALO_MINIMO_SEGUNDOS,
                 reloj=time.monotonic, max_dia=MAX_EMAILS_DIA, hoy=lambda: datetime.now(timezone.utc).date()):
        super().__init__(level=logging.ERROR)
        self._enviar = enviar
        self._etiqueta = etiqueta_entorno
        self._agrupar = agrupar
        self._intervalo = intervalo
        self._reloj = reloj
        self._cerrojo = threading.Lock()
        self._pendientes = {}          # firma -> dict
        self._primero = None           # instante del primer error pendiente
        self._ultimo_envio = None
        self._hilo_envio = None
        self._despertar = threading.Event()
        self._max_dia = max_dia
        self._hoy = hoy
        self._dia = None
        self._enviados_dia = 0

    # --- recogida (en el hilo que registra: rápido y sin excepciones) ---------------
    def emit(self, record):
        try:
            if threading.current_thread() is self._hilo_envio:
                return  # errores del propio envío: no realimentar
            mensaje = record.getMessage()
            if any(ruido in mensaje for ruido in IGNORAR):
                return
            tipo_exc = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else ''
            firma = (record.name, os.path.basename(record.pathname or ''), record.lineno, tipo_exc)
            ahora = datetime.now(timezone.utc)
            with self._cerrojo:
                entrada = self._pendientes.get(firma)
                if entrada is None:
                    if len(self._pendientes) >= MAX_TIPOS:
                        firma = ('(otros)', '', 0, '')
                        entrada = self._pendientes.get(firma)
                if entrada is None:
                    traza = ''
                    if record.exc_info:
                        traza = ''.join(traceback.format_exception(*record.exc_info))[-2500:]
                    entrada = self._pendientes[firma] = {
                        'veces': 0, 'primera': ahora, 'ultima': ahora, 'nivel': record.levelname,
                        'mensaje': _limpiar(mensaje)[:600], 'traza': _limpiar(traza),
                    }
                entrada['veces'] += 1
                entrada['ultima'] = ahora
                if self._primero is None:
                    self._primero = self._reloj()
            self._arrancar_hilo()
            self._despertar.set()
        except Exception:
            pass

    # --- envío (hilo propio) ------------------------------------------------------------
    def _arrancar_hilo(self):
        if self._hilo_envio is None or not self._hilo_envio.is_alive():
            with self._cerrojo:
                if self._hilo_envio is None or not self._hilo_envio.is_alive():
                    self._hilo_envio = threading.Thread(target=self._bucle, name='aviso-errores', daemon=True)
                    self._hilo_envio.start()

    def _bucle(self):
        while True:
            self._despertar.wait()
            self._despertar.clear()
            try:
                while self.enviar_si_toca() is False:
                    time.sleep(30 if self._enviados_dia >= self._max_dia else 5)
            except Exception:
                pass

    def enviar_si_toca(self):
        """Envía el resumen si ya pasó el tiempo de agrupar y el intervalo mínimo.
        Devuelve True si envió o no había nada, False si aún debe esperar."""
        ahora = self._reloj()
        with self._cerrojo:
            if not self._pendientes:
                return True
            if ahora - self._primero < self._agrupar:
                return False
            if self._ultimo_envio is not None and ahora - self._ultimo_envio < self._intervalo:
                return False
            dia = self._hoy()
            if dia != self._dia:
                self._dia, self._enviados_dia = dia, 0
            if self._enviados_dia >= self._max_dia:
                return False  # tope del día: se acumula para el primer email de mañana
            pendientes, self._pendientes, self._primero = self._pendientes, {}, None
            self._ultimo_envio = ahora
            self._enviados_dia += 1
        asunto, html = self._componer(pendientes)
        try:
            self._enviar(asunto, html)
        except Exception:
            pass
        return True

    def _componer(self, pendientes):
        total = sum(e['veces'] for e in pendientes.values())
        etiqueta = str(self._etiqueta() if callable(self._etiqueta) else self._etiqueta).upper()
        asunto = f"[{etiqueta}] Clicandseo: {total} error(es) de {len(pendientes)} tipo(s)"
        filas = []
        for (logger_name, fichero, linea, tipo), e in sorted(pendientes.items(), key=lambda kv: -kv[1]['veces']):
            origen = f"{logger_name} · {fichero}:{linea}" + (f" · {tipo}" if tipo else '')
            traza = f"<pre style='white-space:pre-wrap;font-size:11px;background:#f6f6f6;padding:6px'>{escape(e['traza'])}</pre>" if e['traza'] else ''
            filas.append(
                f"<tr><td style='vertical-align:top;padding:6px'><b>{e['veces']}</b></td>"
                f"<td style='padding:6px'><div style='color:#666;font-size:12px'>{escape(origen)} · "
                f"{e['primera']:%H:%M}–{e['ultima']:%H:%M} UTC</div>"
                f"<div>{escape(e['mensaje'])}</div>{traza}</td></tr>")
        html = (f"<html><body style='font-family:-apple-system,Segoe UI,Roboto,sans-serif'>"
                f"<h2 style='margin-top:0'>{escape(asunto)}</h2>"
                f"<p>Errores registrados por la aplicación desde el último aviso. Detalle completo en los logs de Railway.</p>"
                f"<table style='border-collapse:collapse;font-size:14px'>{''.join(filas)}</table>"
                f"<p style='color:#888;font-size:12px'>Para silenciar: ERROR_ALERTS_ENABLED=false.</p></body></html>")
        return asunto, html


def _registrar_excepciones_de_hilos():
    """Las excepciones sin capturar de un hilo solo iban a stderr: ahora se registran."""
    anterior = threading.excepthook

    def gancho(args):
        if args.exc_type is not SystemExit:
            logging.getLogger('hilos').error(
                f"Excepción sin capturar en el hilo {getattr(args.thread, 'name', '?')}",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        anterior(args)

    threading.excepthook = gancho


def instalar_avisos_de_errores():
    """Instala el handler en el logger raíz si procede. Devuelve el handler o None."""
    import config
    if not config.desplegado() or os.getenv('ERROR_ALERTS_ENABLED', 'true').lower() != 'true':
        return None
    raiz = logging.getLogger()
    for h in raiz.handlers:
        if isinstance(h, AvisoErrores):
            return h

    def enviar(asunto, html):
        from email_service import send_email
        send_email(config.email_alertas(), asunto, html)

    handler = AvisoErrores(enviar, config.etiqueta_entorno)
    raiz.addHandler(handler)
    _registrar_excepciones_de_hilos()
    logging.getLogger(__name__).warning(
        f"✉️ Avisos de errores por email activos ({config.etiqueta_entorno()}): "
        f"máx. 1 cada {INTERVALO_MINIMO_SEGUNDOS // 60} min y {MAX_EMAILS_DIA} al día")
    return handler
