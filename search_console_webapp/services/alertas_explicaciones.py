"""Explicación en lenguaje llano de los errores del aviso por email (oct-2026).

El email de `alertas_errores` solo traía el logger, el fichero, la línea y el
mensaje técnico: para saber si había que hacer algo había que leer código. Este
módulo traduce cada tipo de error a cuatro cosas que se entienden sin saber
programar: qué ha pasado, si afecta a los clientes, qué hay que hacer y cómo de
urgente es. El detalle técnico sigue en el email, pero al final.

- `REGLAS`: errores conocidos, de lo más concreto a lo más general. Se buscan en
  el mensaje y la traza (ya limpios de secretos), en minúsculas.
- Si ninguna regla encaja, se explica por la zona de la app donde nació el error
  (`AREAS`) y se dice con claridad que no está catalogado: nunca se inventa una causa.
- Algo sin importancia que se repite mucho sube a «Revisar».

Para catalogar un error nuevo: añadir una regla a `REGLAS` y un caso al test.
"""

import re
from dataclasses import dataclass, replace

# Gravedad: (etiqueta corta para el asunto, texto de la insignia, color)
GRAVEDADES = {
    'urgente': ('Urgente', 'Urgente: hay que actuar', '#b42318'),
    'revisar': ('Revisar', 'Conviene revisarlo', '#b54708'),
    'sin_accion': ('Sin acción', 'No hace falta hacer nada', '#067647'),
}
ORDEN_GRAVEDAD = {'urgente': 0, 'revisar': 1, 'sin_accion': 2}
# A partir de estas veces, algo «sin importancia» deja de serlo.
REPETICIONES_PARA_REVISAR = 10


@dataclass(frozen=True)
class Explicacion:
    clave: str        # agrupa en una sola tarjeta varias líneas del log con la misma causa
    titulo: str       # frase corta: va en el asunto
    que_paso: str
    impacto: str
    que_hacer: str
    gravedad: str     # clave de GRAVEDADES


# Zonas de la app, por el logger o el fichero donde nace el error (en minúsculas).
AREAS = (
    (('manual_ai', 'daily_analysis_cron'), 'Manual AI',
     'Manual AI (el seguimiento diario de AI Overviews en Google)'),
    (('ai_mode',), 'AI Mode', 'AI Mode (el seguimiento del modo IA de Google)'),
    (('llm_monitoring', 'llm_providers', 'llm_model'), 'LLM Monitoring',
     'LLM Monitoring (las preguntas diarias a ChatGPT, Claude, Gemini y Perplexity)'),
    (('ai_summary',), 'AI Visibility Summary', 'el panel AI Visibility Summary'),
    (('agent',), 'Agent-Ready Scanner', 'el Agent-Ready Scanner'),
    (('stripe', 'billing'), 'pagos', 'los pagos y suscripciones (Stripe)'),
    (('quota_middleware', 'serp_service'), 'búsquedas en Google',
     'las búsquedas en Google que hacemos a través de SerpAPI'),
    (('search_console', 'gsc'), 'Search Console', 'los datos de Google Search Console de los clientes'),
    (('quota',), 'cuotas', 'el control de cuotas de los planes'),
    (('email_service', 'brevo'), 'emails', 'el envío de emails'),
    (('auth',), 'inicio de sesión', 'el inicio de sesión y las cuentas de usuario'),
    (('cron',), 'tareas automáticas', 'las tareas automáticas programadas'),
    (('database', 'init_database'), 'base de datos', 'la base de datos'),
)
AREA_GENERICA = ('la web', 'la aplicación web')


def area(logger_name, fichero):
    donde = f"{logger_name} {fichero}".lower()
    for marcas, corta, larga in AREAS:
        if any(m in donde for m in marcas):
            return corta, larga
    return AREA_GENERICA


def _contiene(*marcas):
    return lambda texto, donde: any(m in texto for m in marcas)


def _serpapi(*marcas):
    """Solo si el error viene de SerpAPI: «account has been suspended» u otros
    textos podrían venir de otro proveedor."""
    return lambda texto, donde: (any(m in texto for m in marcas)
                                 and ('serpapi' in texto or 'serp' in donde or 'quota_middleware' in donde))


_LIMITE_PETICIONES = re.compile(r'(?:code|status|http|error)\W{0,12}(?:429|529)\b')

_PROVEEDORES_IA = (('openai', 'OpenAI (ChatGPT)'), ('anthropic', 'Anthropic (Claude)'),
                   ('perplexity', 'Perplexity'), ('gemini', 'Google (Gemini)'), ('google', 'Google (Gemini)'))


def _proveedor_ia(texto):
    for marca, nombre in _PROVEEDORES_IA:
        if marca in texto:
            return nombre
    return 'uno de los proveedores de IA'


# (prueba(texto, donde), explicación o función(texto) -> explicación). De lo concreto a lo general.
REGLAS = (
    (_serpapi('run out of searches', 'searches for the month are exhausted', 'has been suspended'),
     Explicacion(
         'serpapi_sin_saldo', 'SerpAPI se ha quedado sin búsquedas',
         'SerpAPI, el servicio que usamos para consultar Google, ha rechazado las búsquedas porque la '
         'cuenta se ha quedado sin saldo o está suspendida.',
         'Mientras no se arregle, Manual AI, AI Mode y la vista de resultados de Google no reciben datos '
         'nuevos. Los clientes verán huecos en sus gráficas.',
         'Entra en serpapi.com, revisa el plan y el saldo de la cuenta y amplíalo si hace falta.',
         'urgente')),
    (_serpapi('invalid api key', 'invalid api_key'),
     Explicacion(
         'serpapi_clave', 'La clave de SerpAPI no es válida',
         'SerpAPI ha rechazado nuestra clave de acceso, así que no acepta ninguna búsqueda.',
         'No funciona nada que consulte Google: Manual AI, AI Mode y la vista de resultados de Google.',
         'Comprueba en Railway que la variable SERPAPI_KEY tiene la clave correcta de serpapi.com.',
         'urgente')),
    (_contiene('respuesta vacía o que no es json', 'expecting value: line 1 column 1'),
     Explicacion(
         'serpapi_no_json', 'SerpAPI respondió mal a una búsqueda',
         'SerpAPI, el servicio que usamos para consultar Google, devolvió una respuesta vacía o rota. '
         'Suele pasar cuando sus servidores tienen un problema momentáneo. La app reintenta la búsqueda '
         'y, aun así, no consiguió respuesta.',
         'Esa búsqueda concreta se quedó sin datos. Si era el seguimiento diario de un proyecto, puede '
         'faltar el resultado de hoy de alguna keyword; mañana se consulta de nuevo sola. No afecta a nada más.',
         'Nada. Solo si llegan muchos avisos así el mismo día puede ser una caída de SerpAPI.',
         'sin_accion')),
    (_serpapi('hourly searches limit'),
     Explicacion(
         'serpapi_limite_hora', 'SerpAPI: límite de búsquedas por hora',
         'Hemos hecho más búsquedas en una hora de las que permite nuestro plan de SerpAPI.',
         'Las búsquedas fallan hasta que empieza la hora siguiente. Puede faltar algún dato de hoy.',
         'Si pasa a menudo, hay que repartir mejor las tareas automáticas o subir de plan en SerpAPI.',
         'revisar')),
    (_contiene('insufficient_quota', 'credit_balance_exhausted', 'no credits remaining',
               'credit balance is too low', 'insufficient credits', 'provider_billing_exhausted'),
     lambda texto: Explicacion(
         'ia_sin_credito', f'{_proveedor_ia(texto)} se ha quedado sin crédito',
         f'La cuenta de {_proveedor_ia(texto)} que usa LLM Monitoring se ha quedado sin saldo y rechaza '
         'las preguntas.',
         'LLM Monitoring deja de recibir respuestas de ese modelo: los informes de los clientes saldrán '
         'incompletos hasta que se recargue.',
         'Recarga el crédito en el panel de ese proveedor. Para que no vuelva a pasar, activa la recarga automática.',
         'urgente')),
    (_contiene('invalid signature with provided secrets', 'signatureverificationerror'),
     Explicacion(
         'stripe_firma', 'No se pudo verificar un aviso de pago de Stripe',
         'Stripe nos envió un aviso (un pago, una renovación, una cancelación…) y la app no pudo comprobar '
         'que era auténtico, así que lo descartó.',
         'Si se repite, los pagos no activan ni renuevan los planes: un cliente puede pagar y seguir sin acceso.',
         'Comprueba en Railway que STRIPE_WEBHOOK_SECRET coincide con el secreto del webhook en el panel de Stripe.',
         'urgente')),
    (_contiene('statement timeout', 'querycanceled'),
     Explicacion(
         'bd_lenta', 'Una consulta a la base de datos tardó demasiado',
         'Una operación en la base de datos tardó más de lo permitido y se canceló.',
         'La página o tarea que la pidió falló esa vez. Si alguien estaba usando la web, vio un error.',
         'Si es un caso aislado, nada. Si se repite en la misma parte de la app, conviene revisarlo.',
         'revisar')),
    (_contiene('memoryerror', 'out of memory', 'worker timeout', 'sigkill'),
     Explicacion(
         'servidor_memoria', 'El servidor se quedó sin memoria o se colgó',
         'Un proceso del servidor se quedó sin memoria o tardó tanto que se reinició.',
         'Mientras pasaba, la web pudo ir lenta o dar errores, y una tarea en marcha pudo cortarse.',
         'Si es un caso aislado, nada. Si se repite, mira en Railway el uso de memoria del servicio.',
         'revisar')),
    (_contiene('no se pudo conectar a la base de datos', 'no se pudo conectar a la bd', 'no db connection',
               'failed to get database connection', 'could not connect to server', 'connection refused',
               'server closed the connection unexpectedly', 'too many connections', 'pool exhausted',
               'connection already closed'),
     Explicacion(
         'bd_conexion', 'Fallo de conexión con la base de datos',
         'La app no pudo conectar con la base de datos (o la conexión se cortó a mitad).',
         'Mientras dure, los usuarios pueden ver errores y las tareas automáticas pueden fallar. Si fue un '
         'instante (por ejemplo, durante un despliegue), se recupera sola.',
         'Si es un caso aislado, nada. Si se repite, mira en Railway que la base de datos esté en marcha.',
         'revisar')),
    (_contiene('invalid_grant', 'token has been expired or revoked'),
     Explicacion(
         'google_acceso', 'Google rechazó el acceso de un usuario',
         'El permiso que un usuario nos dio para leer sus datos de Google ha caducado o lo ha retirado.',
         'Ese usuario tendrá que volver a conectar su cuenta de Google. A los demás no les afecta.',
         'Nada, salvo que pase con muchos usuarios a la vez.',
         'sin_accion')),
    (lambda texto, donde: 'email_service' in donde or 'smtp' in texto,
     Explicacion(
         'email_envio', 'No se pudo enviar un email',
         'La app intentó enviar un email y el servicio de envío (Brevo) no lo aceptó.',
         'Algún email (aviso, invitación, recuperación de contraseña…) no llegó a su destinatario.',
         'Si se repite, revisa la cuenta de Brevo: saldo de envíos y credenciales SMTP.',
         'revisar')),
    (lambda texto, donde: (any(m in texto for m in ('too many requests', 'rate limit', 'overloaded',
                                                    'resource_exhausted'))
                           or bool(_LIMITE_PETICIONES.search(texto))),
     Explicacion(
         'servicio_saturado', 'Un servicio externo estaba saturado',
         'Un servicio externo (una IA, Google o SerpAPI) estaba saturado y nos pidió que fuéramos más '
         'despacio. La app reintenta, pero esta vez no lo consiguió.',
         'Puede faltar alguna respuesta o dato de hoy. Normalmente se completa en la siguiente pasada.',
         'Nada, salvo que se repita mucho.',
         'sin_accion')),
    (_contiene('timed out', 'timeout'),
     Explicacion(
         'servicio_lento', 'Un servicio externo tardó demasiado',
         'Un servicio externo (una IA, Google o SerpAPI) tardó demasiado en responder y la app dejó de esperar.',
         'Puede faltar alguna respuesta o dato de hoy. Normalmente se completa en la siguiente pasada.',
         'Nada, salvo que se repita mucho.',
         'sin_accion')),
)


def explicar(logger_name, fichero, tipo_exc, mensaje, traza='', veces=1, linea=0):
    """Explicación llana de un tipo de error. Siempre devuelve una (nunca lanza)."""
    try:
        texto = f"{mensaje}\n{traza}".lower()
        donde = f"{logger_name} {fichero}".lower()
        explicacion = None
        for prueba, resultado in REGLAS:
            if prueba(texto, donde):
                explicacion = resultado(texto) if callable(resultado) else resultado
                break
        if explicacion is None:
            explicacion = _sin_catalogar(logger_name, fichero, linea, tipo_exc, mensaje)
        return ajustar_por_repeticion(explicacion, veces)
    except Exception:
        return _sin_catalogar('', '', 0, '', '')


def _sin_catalogar(logger_name, fichero, linea, tipo_exc, mensaje):
    corta, larga = area(logger_name, fichero)
    que_paso = (f'Algo ha fallado en {larga}. Es un error que todavía no está catalogado, así que este '
                'email no puede decirte la causa con seguridad.')
    if str(mensaje).startswith('Exception on '):
        que_paso += ' Pasó mientras alguien usaba la web.'
        impacto = 'Al menos un usuario vio una página de error en ese momento.'
    elif logger_name == 'hilos':
        que_paso += ' Pasó en un proceso que trabaja en segundo plano, que se cortó.'
        impacto = 'La tarea que estaba haciendo ese proceso pudo quedarse a medias.'
    else:
        impacto = ('Depende de la causa. Si fue en una tarea automática, puede faltar algún dato de hoy; '
                   'si fue en la web, algún usuario pudo ver un error.')
    return Explicacion(
        # Cada error desconocido en su tarjeta: no sabemos si dos comparten causa.
        f'sin_catalogar:{logger_name}:{fichero}:{linea}:{tipo_exc}', f'Fallo no catalogado en {corta}',
        que_paso, impacto,
        'Si es un caso aislado, suele ser un fallo puntual y no hace falta hacer nada. Si vuelve a aparecer '
        'en los próximos avisos, pásale este email a Claude para que lo investigue.',
        'revisar')


def ajustar_por_repeticion(explicacion, veces):
    if explicacion.gravedad == 'sin_accion' and veces >= REPETICIONES_PARA_REVISAR:
        return replace(explicacion, gravedad='revisar',
                       que_hacer=f'Normalmente no haría falta, pero se ha repetido {veces} veces: si sigue '
                                 'pasando en los próximos avisos, conviene mirarlo.')
    return explicacion
