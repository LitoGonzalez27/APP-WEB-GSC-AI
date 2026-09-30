"""Avisos por email de los errores de la aplicación (sep-2026).

Hasta ahora los errores solo quedaban en los logs de Railway: si algo fallaba
de madrugada, nadie se enteraba hasta que un cliente lo notaba. Este handler
recoge los registros de nivel ERROR o superior (también las excepciones sin
capturar de las rutas y de los hilos) y envía un resumen por email:

- agrupa por tipo de error (logger, fichero y línea donde nació, tipo de
  excepción) y cuenta;
- espera AGRUPAR_SEGUNDOS tras el primer error para juntar ráfagas y no manda
  más de un email cada INTERVALO_MINIMO_SEGUNDOS ni más de MAX_EMAILS_DIA al día.
  Los últimos RESERVA_TIPOS_NUEVOS del día quedan para errores de un tipo aún no
  avisado: un fallo que se repite no tapa uno nuevo. Lo que no cabe se cuenta y
  va en el primer email del día siguiente;
- al salir el proceso (p. ej. sys.exit por no poder arrancar) manda lo pendiente
  sin esperar;
- ignora el ruido conocido (IGNORAR) y los errores de su propio envío;
- oculta secretos (URL, Bearer, claves de API, pares clave=valor) y enmascara emails;
- nunca bloquea ni lanza: emit() solo apunta en memoria; el envío va en un hilo.

Solo se instala en Railway (config.desplegado(): producción y staging, con la
etiqueta del entorno en el asunto) y se apaga con ERROR_ALERTS_ENABLED=false.
Destinatario: config.email_alertas(). Los contadores son de cada proceso: se
reinician con cada despliegue.
"""

import atexit
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
RESERVA_TIPOS_NUEVOS = 4
MAX_TIPOS = 50
# Ruido conocido: cualquiera puede provocarlo desde fuera y no indica un fallo.
# Una firma de Stripe inválida por un secreto mal configurado también cae aquí,
# pero Stripe avisa por su cuenta cuando los webhooks reales fallan.
IGNORAR = (
    'Missing Stripe signature',
    'Invalid signature with provided secrets',
    'Invalid payload:',
    'Error processing webhook: Invalid signature',
    'Error processing webhook: Invalid payload',
)
_PREFIJO_HILO = 'aviso-errores'
_DIR_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MARCA = '[oculto]'
# Sin cuantificadores libres delante de la @: sobre textos largos sin @ una
# expresión con [..]* tardaba segundos (coste cuadrático) con el cerrojo cogido.
_EMAIL = re.compile(r'(?<![\w.%+-])([\w.%+-])[\w.%+-]{0,63}@([A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24})')
_SECRETOS = (
    (re.compile(r'(?i)\b(bearer\s+)[\w.~+/=-]{8,}'), r'\1' + _MARCA),
    (re.compile(r'\b(?:sk|pk|rk|whsec)_(?:live|test)_\w{8,}'), _MARCA),
    (re.compile(r'\bsk-[\w-]{16,}'), _MARCA),
    (re.compile(r'\bAIza[\w-]{30,}'), _MARCA),
    (re.compile(r'''(?i)(['"]?\b(?:api_?key|password|passwd|secret|client_secret|access_token|refresh_token|'''
                r'''id_token|token|authorization)['"]?\s*[:=]\s*['"]?)[^'"\s,}&]{4,}'''), r'\1' + _MARCA),
)


def _limpiar(texto):
    from services.log_seguro import ocultar_secretos_en_url
    texto = ocultar_secretos_en_url(str(texto))
    for patron, sustituto in _SECRETOS:
        texto = patron.sub(sustituto, texto)
    return _EMAIL.sub(r'\1***@\2', texto)


def _origen(record):
    """Fichero y línea donde nació el error: el último frame del código de la app.

    Flask registra todas las excepciones de las rutas desde la misma línea (y el
    excepthook de hilos, igual), así que con record.pathname/lineno dos bugs
    distintos saldrían como uno solo."""
    tb = record.exc_info[2] if record.exc_info else None
    if tb is not None:
        frames = traceback.StackSummary.extract(traceback.walk_tb(tb), lookup_lines=False)
        propios = [f for f in frames if f.filename.startswith(_DIR_APP) and 'site-packages' not in f.filename]
        frame = (propios or frames)[-1] if frames else None
        if frame is not None:
            return os.path.basename(frame.filename), frame.lineno
    return os.path.basename(record.pathname or ''), record.lineno


class AvisoErrores(logging.Handler):
    def __init__(self, enviar, etiqueta_entorno, agrupar=AGRUPAR_SEGUNDOS, intervalo=INTERVALO_MINIMO_SEGUNDOS,
                 reloj=time.monotonic, max_dia=MAX_EMAILS_DIA, hoy=lambda: datetime.now(timezone.utc).date(),
                 reserva_tipos_nuevos=RESERVA_TIPOS_NUEVOS):
        super().__init__(level=logging.ERROR)
        self._enviar = enviar
        self._etiqueta = etiqueta_entorno
        self._agrupar = agrupar
        self._intervalo = intervalo
        self._reloj = reloj
        # RLock: si algo registrara un ERROR con el cerrojo cogido, no se bloquea.
        self._cerrojo = threading.RLock()
        self._pendientes = {}          # firma -> dict
        self._primero = None           # instante del primer error pendiente
        self._ultimo_envio = None
        self._hilo_envio = None
        self._despertar = threading.Event()
        self._max_dia = max_dia
        self._reserva = min(reserva_tipos_nuevos, max(max_dia - 1, 0))
        self._hoy = hoy
        self._dia = None
        self._enviados_dia = 0
        self._avisadas_dia = set()     # firmas ya incluidas en un email hoy

    # --- recogida (en el hilo que registra: rápido y sin excepciones) ---------------
    def emit(self, record):
        try:
            if threading.current_thread().name.startswith(_PREFIJO_HILO):
                return  # errores del propio envío: no realimentar
            mensaje = record.getMessage()
            if any(ruido in mensaje for ruido in IGNORAR):
                return
            tipo_exc = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else ''
            fichero, linea = _origen(record)
            firma = (record.name, fichero, linea, tipo_exc)
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
                        # Se limpia antes de recortar: un corte justo detrás de
                        # "?token=" dejaría el valor sin su nombre y sin ocultar.
                        traza = _limpiar(''.join(traceback.format_exception(*record.exc_info))[-8000:])[-2500:]
                    entrada = self._pendientes[firma] = {
                        'veces': 0, 'primera': ahora, 'ultima': ahora, 'nivel': record.levelname,
                        'mensaje': _limpiar(mensaje[:4000])[:600], 'traza': traza,
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
                    self._hilo_envio = threading.Thread(target=self._bucle, name=_PREFIJO_HILO, daemon=True)
                    self._hilo_envio.start()

    def _bucle(self):
        while True:
            self._despertar.wait()
            self._despertar.clear()
            try:
                while self.enviar_si_toca() is False:
                    time.sleep(30 if self._enviados_dia >= self._max_dia - self._reserva else 5)
            except Exception:
                pass

    def _tomar(self, forzar=False):
        """Saca lo pendiente si toca enviarlo. None si no hay nada o aún no toca.
        Con forzar no espera a agrupar ni al intervalo, pero sí respeta el tope."""
        ahora = self._reloj()
        with self._cerrojo:
            if not self._pendientes:
                return None
            if not forzar:
                if ahora - self._primero < self._agrupar:
                    return None
                if self._ultimo_envio is not None and ahora - self._ultimo_envio < self._intervalo:
                    return None
            dia = self._hoy()
            if dia != self._dia:
                self._dia, self._enviados_dia, self._avisadas_dia = dia, 0, set()
            hay_tipo_nuevo = any(firma not in self._avisadas_dia for firma in self._pendientes)
            tope = self._max_dia if hay_tipo_nuevo else self._max_dia - self._reserva
            if self._enviados_dia >= tope:
                return None  # tope del día: se acumula para el siguiente email
            pendientes, self._pendientes, self._primero = self._pendientes, {}, None
            self._ultimo_envio = ahora
            self._enviados_dia += 1
            self._avisadas_dia.update(pendientes)
            return pendientes

    def _enviar_seguro(self, pendientes):
        asunto, html = self._componer(pendientes)
        try:
            self._enviar(asunto, html)
        except Exception:
            pass  # sin reintento: el detalle sigue en los logs de Railway

    def enviar_si_toca(self):
        """Envía el resumen si ya pasó el tiempo de agrupar y el intervalo mínimo.
        Devuelve True si envió o no había nada, False si aún debe esperar."""
        with self._cerrojo:
            if not self._pendientes:
                return True
        pendientes = self._tomar()
        if pendientes is None:
            return False
        self._enviar_seguro(pendientes)
        return True

    def vaciar(self, espera=10):
        """Al salir el proceso: manda lo pendiente ya, sin agrupar ni esperar al
        intervalo. Un error de arranque seguido de sys.exit no llegaba nunca porque
        el hilo de envío es daemon. Espera como mucho `espera` segundos."""
        pendientes = self._tomar(forzar=True)
        if pendientes is None:
            return False
        hilo = threading.Thread(target=self._enviar_seguro, args=(pendientes,),
                                name=f'{_PREFIJO_HILO}-salida', daemon=True)
        hilo.start()
        hilo.join(espera)
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
    atexit.register(handler.vaciar)
    logging.getLogger(__name__).warning(
        f"✉️ Avisos de errores por email activos ({config.etiqueta_entorno()}): "
        f"máx. 1 cada {INTERVALO_MINIMO_SEGUNDOS // 60} min y {MAX_EMAILS_DIA} al día")
    return handler
