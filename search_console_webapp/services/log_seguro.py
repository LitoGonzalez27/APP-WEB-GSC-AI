"""Filtro de logs: no escribir los secretos que viajan en la URL (sep-2026).

Werkzeug registra cada petición con la URL completa, y varias URLs llevan un
secreto en la query: el código y el state del retorno de Google
(/auth/callback), el token de restablecer contraseña (/reset-password?token=),
el de aceptar una invitación a un proyecto y el de aprobar o rechazar modelos
de LLM Monitoring. Cualquiera con acceso a los logs de Railway podía usar un
token de contraseña que siguiera vigente. El filtro sustituye el valor de esos
parámetros por una marca y deja el resto de la línea igual. También oculta el
email de /auth/check-email (dato personal) y limpia las trazas de excepción.

Un secreto puede ir codificado dentro de otro parámetro: el login redirige a
/auth/login?next=%2Fproject-invitations%2Faccept%3Ftoken%3D... y Werkzeug solo
decodifica parte (deja %3D). Si al decodificar aparece un secreto, se registra
la versión decodificada y limpia; las líneas sin secretos no se tocan.

Solo cubre los handlers que existen al instalarlo (los de logging.basicConfig)
y el logger de Werkzeug; un handler que se añada después necesita su propio
filtro. Los logs HTTP del borde de Railway quedan fuera de la app.
"""

import logging
import re
from urllib.parse import unquote

PARAMETROS_SECRETOS = (
    'code', 'state', 'token', 'access_token', 'refresh_token', 'id_token',
    'client_secret', 'password', 'secret', 'api_key', 'key', 'email',
)
MARCA = '[oculto]'
_NIVELES_DE_CODIFICACION = 10
# Werkzeug deja %0A, %1B... sin decodificar a propósito: al decodificar hay que
# volver a escaparlos o una URL podría meter líneas falsas (o colores ANSI) en el log.
_CONTROL = re.compile(r'[\x00-\x1f\x7f-\x9f]')

_PATRON = re.compile(
    r'([?&](?:%s)=)[^&\s"\']+' % '|'.join(PARAMETROS_SECRETOS), re.IGNORECASE)


def _ocultar(texto):
    return _PATRON.sub(lambda m: m.group(1) + MARCA, texto)


def _sin_controles(texto):
    return _CONTROL.sub(lambda m: '\\x%02x' % ord(m.group()), texto)


def ocultar_secretos_en_url(texto):
    """Devuelve `texto` con el valor de los parámetros secretos sustituido,
    también cuando van codificados dentro de otro parámetro."""
    resultado = _ocultar(texto)
    actual = resultado
    for _ in range(_NIVELES_DE_CODIFICACION):
        if '%' not in actual:
            break
        decodificado = unquote(actual)
        if decodificado == actual:
            break
        limpio = _ocultar(decodificado)
        if limpio != decodificado:
            resultado = _sin_controles(limpio)
        actual = limpio
    return resultado


class FiltroSecretosEnUrl(logging.Filter):
    """Reescribe el mensaje, la traza y la pila del registro si contienen un
    parámetro secreto. Nunca descarta un registro ni lanza una excepción."""

    def filter(self, record):
        try:
            mensaje = record.getMessage()
            limpio = ocultar_secretos_en_url(mensaje)
            if limpio != mensaje:
                record.msg = limpio
                record.args = ()
            if record.exc_info and not record.exc_text:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            if record.exc_text:
                record.exc_text = ocultar_secretos_en_url(record.exc_text)
            if record.stack_info:
                record.stack_info = ocultar_secretos_en_url(record.stack_info)
        except Exception:
            pass
        return True


def instalar_filtro_secretos(loggers=('werkzeug',)):
    """Instala el filtro en los loggers indicados y en los handlers del logger
    raíz (lo que ya esté configurado con logging.basicConfig). Idempotente."""
    destinos = [logging.getLogger(nombre) for nombre in loggers]
    destinos.extend(logging.getLogger().handlers)
    for destino in destinos:
        if not any(isinstance(f, FiltroSecretosEnUrl) for f in destino.filters):
            destino.addFilter(FiltroSecretosEnUrl())
