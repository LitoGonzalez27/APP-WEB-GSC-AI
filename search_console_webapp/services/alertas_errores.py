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

from services.alertas_explicaciones import (GRAVEDADES, ORDEN_GRAVEDAD, ajustar_por_repeticion,
                                            explicar)

try:  # horas del email en hora de España; si faltara la base de zonas, en UTC
    from zoneinfo import ZoneInfo
    _ZONA = ZoneInfo('Europe/Madrid')
    _NOMBRE_ZONA = 'hora de España'
except Exception:
    _ZONA, _NOMBRE_ZONA = timezone.utc, 'UTC'

AGRUPAR_SEGUNDOS = int(os.getenv('ERROR_ALERTS_GROUP_SECONDS', '60'))
INTERVALO_MINIMO_SEGUNDOS = int(os.getenv('ERROR_ALERTS_MIN_INTERVAL_SECONDS', '900'))
# Tope diario: aunque algo provoque errores en bucle, no más de estos emails al día.
MAX_EMAILS_DIA = int(os.getenv('ERROR_ALERTS_MAX_PER_DAY', '12'))
RESERVA_TIPOS_NUEVOS = 4
MAX_TIPOS = 50
# Ruido conocido: cualquiera puede provocarlo desde fuera y no indica un fallo.
# Solo la firma de Stripe AUSENTE: una firma inválida sí avisa, porque también es
# lo que se ve si el secreto del webhook está mal configurado (los pagos no activan
# el plan), y un bot rara vez manda la cabecera. "Invalid payload" solo llega con
# una firma válida, así que tampoco es ruido externo.
IGNORAR = (
    'Missing Stripe signature',
)
_PREFIJO_HILO = 'aviso-errores'
_DIR_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MARCA = '[oculto]'
# Sin cuantificadores libres delante de la @: sobre textos largos sin @ una
# expresión con [..]* tardaba segundos (coste cuadrático) con el cerrojo cogido.
_EMAIL = re.compile(r'(?<![\w.%+-])([\w.%+-])[\w.%+-]{0,63}@([A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24})')
_CLAVES = (r'(?:x-)?api[_-]?key|password|passwd|secret|client_secret|access_token|refresh_token|'
           r'id_token|token|authorization')


def _ocultar_valor(m):
    # No se toca lo que no es un secreto: None/null, o código de una línea de la traza
    # (password = request.form['password']).
    valor = m.group(2)
    # Solo es código si termina en llamada o índice (request.form[, os.getenv():
    # "ya29.a0..." (token de Google) o "Verano2024.segura" sí se ocultan.
    if valor.lower() in ('none', 'null', 'true', 'false') or re.fullmatch(r'[A-Za-z_][\w.]*[(\[]', valor):
        return m.group(0)
    return m.group(1) + _MARCA


_SECRETOS = (
    (re.compile(r'(?i)\b((?:bearer|basic)\s+)[\w.~+/=-]{8,}'), r'\1' + _MARCA),
    (re.compile(r'\b(?:sk|pk|rk)_(?:live|test)_\w{8,}|\bwhsec_\w{8,}'), _MARCA),
    (re.compile(r'\b(?:sk|xkeysib|pplx)-[\w-]{16,}'), _MARCA),
    (re.compile(r'\bAIza[\w-]{30,}'), _MARCA),
    (re.compile(r'\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}'), _MARCA),          # JWT
    # usuario:clave@ hasta la última @ antes de la primera / (host:puerto/…?a=b@c no es una clave)
    (re.compile(r'(\b[a-z][a-z0-9+.-]{1,20}://[^:/\s@]{1,64}:)[^/\s]{1,256}@'), r'\1' + _MARCA + '@'),
    # Diccionarios y JSON: la clave va entre comillas ('api_key': '...', "password": ...).
    (re.compile(r'''(?i)(['"](?:%s)['"]\s*:\s*['"]?)([^'"\s,}&]{4,})''' % _CLAVES), _ocultar_valor),
    # clave=valor fuera de una URL. "token: invalid_grant" (prosa) no se toca.
    (re.compile(r'''(?i)(\b(?:%s)\s*=\s*['"]?)([^'"\s,}&]{4,})''' % _CLAVES), _ocultar_valor),
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
        # Envíos tomados y aún sin terminar (se cuenta al tomar el lote, bajo el cerrojo,
        # para que vaciar() no vea un hueco entre _tomar y el envío).
        self._envios_en_curso = 0
        self._fin_de_envio = threading.Condition(self._cerrojo)

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
            self._envios_en_curso += 1
            return pendientes

    def _enviar_seguro(self, pendientes):
        """Envía un lote sacado con _tomar() (que ya lo contó como en curso).

        Deja una línea WARNING con el resultado: en Railway el logger raíz está en
        WARNING y el INFO de send_email no se ve, así que sin esto un envío correcto
        no dejaba rastro. Estos registros salen del hilo de envío y el propio
        handler los ignora (no se realimenta)."""
        registro = logging.getLogger(__name__)
        try:
            asunto, html = self._componer(pendientes)
            if self._enviar(asunto, html) is True:   # send_email devuelve True/False
                registro.warning(f"✉️ Aviso de errores enviado: «{asunto}»")
            else:
                registro.warning(f"✉️ No se pudo enviar el aviso de errores «{asunto}» (ver el error de envío)")
        except Exception as e:
            # sin reintento: el detalle sigue en los logs de Railway
            registro.warning(f"✉️ Fallo al preparar o enviar el aviso de errores: {type(e).__name__}: "
                             f"{_limpiar(str(e))[:300]}")
        finally:
            with self._fin_de_envio:
                self._envios_en_curso -= 1
                self._fin_de_envio.notify_all()

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
        el hilo de envío es daemon. Espera como mucho `espera` segundos, también a un
        envío que ya estuviera en marcha. SIGTERM (redespliegue) no pasa por aquí."""
        limite = time.monotonic() + espera
        pendientes = self._tomar(forzar=True)
        if pendientes is not None:
            try:
                hilo = threading.Thread(target=self._enviar_seguro, args=(pendientes,),
                                        name=f'{_PREFIJO_HILO}-salida', daemon=True)
                hilo.start()
            except RuntimeError:
                # Desde Python 3.12 no se pueden crear hilos mientras el intérprete
                # se cierra (y atexit ya es el cierre): se envía aquí mismo. Puede
                # pasar de `espera` (timeout de SMTP de 30 s): solo retrasa el cierre.
                self._enviar_seguro(pendientes)
        with self._fin_de_envio:
            self._fin_de_envio.wait_for(lambda: self._envios_en_curso == 0,
                                        timeout=max(0.0, limite - time.monotonic()))
        return pendientes is not None

    @staticmethod
    def _horas(primera, ultima):
        a, b = primera.astimezone(_ZONA), ultima.astimezone(_ZONA)
        formato = '%H:%M' if a.date() == b.date() else '%d/%m %H:%M'
        return f"{a:{formato}}–{b:{formato}} ({_NOMBRE_ZONA})"

    def _componer(self, pendientes):
        """Primero la explicación en lenguaje llano (una tarjeta por causa, lo más grave
        arriba); al final, el detalle técnico de siempre."""
        total = sum(e['veces'] for e in pendientes.values())
        etiqueta = str(self._etiqueta() if callable(self._etiqueta) else self._etiqueta).upper()
        tarjetas = self._tarjetas(pendientes)
        principal = tarjetas[0]['explicacion']
        corta = GRAVEDADES[principal.gravedad][0]
        otras = len(tarjetas) - 1
        asunto = (f"[{etiqueta}] Clicandseo · {corta}: {principal.titulo}"
                  + (f" (y {otras} aviso{'s' if otras > 1 else ''} más)" if otras else ''))
        tecnico = f"{total} error(es) de {len(pendientes)} tipo(s)"

        filas = []
        for (logger_name, fichero, linea, tipo), e in sorted(pendientes.items(), key=lambda kv: -kv[1]['veces']):
            origen = f"{logger_name} · {fichero}:{linea}" + (f" · {tipo}" if tipo else '')
            traza = f"<pre style='white-space:pre-wrap;font-size:11px;background:#f6f6f6;padding:6px'>{escape(e['traza'])}</pre>" if e['traza'] else ''
            filas.append(
                f"<tr><td style='vertical-align:top;padding:6px'><b>{e['veces']}</b></td>"
                f"<td style='padding:6px'><div style='color:#666;font-size:12px'>{escape(origen)} · "
                f"{self._horas(e['primera'], e['ultima'])}</div>"
                f"<div>{escape(e['mensaje'])}</div>{traza}</td></tr>")
        html = (f"<html lang='es'><head><meta charset='utf-8'><meta http-equiv='Content-Language' content='es'></head>"
                f"<body style='font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1d2939;max-width:720px'>"
                f"<h2 style='margin-top:0'>{escape(self._resumen(tarjetas, etiqueta))}</h2>"
                f"{''.join(self._tarjeta_html(t) for t in tarjetas)}"
                f"<hr style='border:none;border-top:1px solid #ddd;margin:28px 0 12px'>"
                f"<h3 style='margin:0 0 4px;color:#555'>Detalle técnico</h3>"
                f"<p style='color:#555;font-size:13px;margin-top:0'>{tecnico} desde el último aviso. "
                f"Para quien lo vaya a investigar; el log completo está en Railway.</p>"
                f"<table style='border-collapse:collapse;font-size:13px'>{''.join(filas)}</table>"
                f"<p style='color:#888;font-size:12px'>Para silenciar: ERROR_ALERTS_ENABLED=false.</p></body></html>")
        return asunto, html

    def _tarjetas(self, pendientes):
        """Agrupa por causa: un mismo fallo suele dejar varias líneas en el log (el
        middleware de SerpAPI y el servicio que lo llamó, p. ej.) y debe leerse como uno."""
        por_causa = {}
        for (logger_name, fichero, linea, tipo), e in pendientes.items():
            base = explicar(logger_name, fichero, tipo, e['mensaje'], e['traza'], linea=linea)
            t = por_causa.setdefault(base.clave, {'explicacion': base, 'veces': 0,
                                                  'primera': e['primera'], 'ultima': e['ultima']})
            # Varias líneas de una misma causa suelen ser el mismo suceso: se cuenta el mayor.
            t['veces'] = max(t['veces'], e['veces'])
            t['primera'], t['ultima'] = min(t['primera'], e['primera']), max(t['ultima'], e['ultima'])
        tarjetas = list(por_causa.values())
        for t in tarjetas:
            t['explicacion'] = ajustar_por_repeticion(t['explicacion'], t['veces'])
        return sorted(tarjetas, key=lambda t: (ORDEN_GRAVEDAD[t['explicacion'].gravedad], -t['veces']))

    @staticmethod
    def _resumen(tarjetas, etiqueta):
        entorno = 'producción' if etiqueta == 'PRODUCTION' else etiqueta.lower()
        n = len(tarjetas)
        cabecera = f"{n} aviso{'s' if n > 1 else ''} de Clicandseo ({entorno})"
        if any(t['explicacion'].gravedad == 'urgente' for t in tarjetas):
            return f"{cabecera}: hay algo urgente"
        if all(t['explicacion'].gravedad == 'sin_accion' for t in tarjetas):
            return f"{cabecera}: no hace falta hacer nada"
        return f"{cabecera}: conviene echar un vistazo"

    def _tarjeta_html(self, t):
        x = t['explicacion']
        _corta, insignia, color = GRAVEDADES[x.gravedad]
        veces = 'una vez' if t['veces'] == 1 else f"{t['veces']} veces"
        apartado = ("<p style='margin:8px 0 2px;font-size:12px;font-weight:600;color:#667085;"
                    "text-transform:uppercase;letter-spacing:.04em'>{}</p><p style='margin:0'>{}</p>")
        return (f"<div style='border-left:4px solid {color};background:#fafafa;padding:12px 16px;margin:14px 0'>"
                f"<span style='display:inline-block;background:{color};color:#fff;font-size:12px;font-weight:600;"
                f"padding:2px 8px;border-radius:10px'>{escape(insignia)}</span>"
                f"<h3 style='margin:8px 0 4px'>{escape(x.titulo)}</h3>"
                f"<div style='color:#667085;font-size:13px'>Ha pasado {veces} · "
                f"{self._horas(t['primera'], t['ultima'])}</div>"
                + apartado.format('Qué ha pasado', escape(x.que_paso))
                + apartado.format('¿Afecta a los clientes?', escape(x.impacto))
                + apartado.format('Qué hacer', escape(x.que_hacer))
                + "</div>")


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
        return send_email(config.email_alertas(), asunto, html)

    handler = AvisoErrores(enviar, config.etiqueta_entorno)
    raiz.addHandler(handler)
    _registrar_excepciones_de_hilos()
    atexit.register(handler.vaciar)
    logging.getLogger(__name__).warning(
        f"✉️ Avisos de errores por email activos ({config.etiqueta_entorno()}): "
        f"máx. 1 cada {INTERVALO_MINIMO_SEGUNDOS // 60} min y {MAX_EMAILS_DIA} al día")
    return handler
