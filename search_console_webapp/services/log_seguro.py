"""Filtro de logs: no escribir los secretos que viajan en la URL (sep-2026).

Werkzeug registra cada petición con la URL completa, y varias URLs llevan un
secreto en la query: el código y el state del retorno de Google
(/auth/callback), el token de restablecer contraseña (/reset-password?token=),
el de aceptar una invitación a un proyecto y el de aprobar o rechazar modelos
de LLM Monitoring. Cualquiera con acceso a los logs de Railway podía usar un
token de contraseña que siguiera vigente. El filtro sustituye el valor de esos
parámetros por una marca y deja el resto de la línea igual.
"""

import logging
import re

PARAMETROS_SECRETOS = (
    'code', 'state', 'token', 'access_token', 'refresh_token', 'id_token',
    'client_secret', 'password', 'secret', 'api_key', 'key',
)
MARCA = '[oculto]'

_PATRON = re.compile(
    r'([?&](?:%s)=)[^&\s"\']+' % '|'.join(PARAMETROS_SECRETOS), re.IGNORECASE)


def ocultar_secretos_en_url(texto):
    """Devuelve `texto` con el valor de los parámetros secretos sustituido."""
    return _PATRON.sub(lambda m: m.group(1) + MARCA, texto)


class FiltroSecretosEnUrl(logging.Filter):
    """Reescribe el mensaje del registro si contiene un parámetro secreto.
    Nunca descarta un registro ni lanza una excepción."""

    def filter(self, record):
        try:
            mensaje = record.getMessage()
            limpio = ocultar_secretos_en_url(mensaje)
        except Exception:
            return True
        if limpio != mensaje:
            record.msg = limpio
            record.args = ()
        return True


def instalar_filtro_secretos(loggers=('werkzeug',)):
    """Instala el filtro en los loggers indicados y en los handlers del logger
    raíz (lo que ya esté configurado con logging.basicConfig). Idempotente."""
    destinos = [logging.getLogger(nombre) for nombre in loggers]
    destinos.extend(logging.getLogger().handlers)
    for destino in destinos:
        if not any(isinstance(f, FiltroSecretosEnUrl) for f in destino.filters):
            destino.addFilter(FiltroSecretosEnUrl())
