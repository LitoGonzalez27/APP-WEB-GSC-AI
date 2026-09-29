"""Configuración del entorno en un solo sitio (estructura, sep-2026).

Antes cada módulo decidía por su cuenta en qué entorno estaba y leía las mismas
variables con valores por defecto distintos. Lo grave: stripe_config y
billing_routes tomaban APP_ENV con 'staging' por defecto, así que si faltaba en
producción la app se creía staging (y enseñaba detalles de depuración en los
errores de checkout). Ahora las variables de entorno y los secretos de cron se
leen aquí; tests/test_config.py impide leerlas en otro sitio.

Dos nociones de entorno, a propósito:

- entorno_railway() / desplegado(): RAILWAY_ENVIRONMENT, que pone Railway y no
  se puede olvidar. Decide las barreras de seguridad (clave de sesión
  obligatoria, cookies seguras, modo depuración, cifrado de tokens, HTTP en
  OAuth, llamadas a SerpAPI sin usuario).
- entorno_app() / es_produccion(): APP_ENV si está definida; si no, el entorno
  de Railway; si no, 'development'. Decide detalles en los errores de checkout
  y los avisos de claves de Stripe en el log (el modo lo marcan las claves).

Las funciones leen el entorno cada vez que se llaman. Algunos módulos guardan
el valor al importarse, igual que antes (quota_middleware._IS_DEPLOYED, la URL
pública de los emails, la instancia de StripeConfig, railway_env en app.py y
database.py): cambiar la variable después no les afecta.
"""

import os
import secrets

URL_PUBLICA_POR_DEFECTO = 'https://app.clicandseo.com'
EMAIL_ALERTAS_POR_DEFECTO = 'info@soycarlosgonzalez.com'


# --- Entorno -----------------------------------------------------------------

def entorno_railway():
    """RAILWAY_ENVIRONMENT tal cual ('production', 'staging') o '' fuera de Railway."""
    return os.getenv('RAILWAY_ENVIRONMENT', '')


def desplegado():
    """True en cualquier entorno de Railway salvo uno llamado 'development'
    (barreras de seguridad). Antes solo production y staging: un entorno con
    otro nombre (una preview) quedaba con la clave de sesión de desarrollo."""
    return entorno_railway() not in ('', 'development')


def entorno_app():
    """APP_ENV; si no está, el entorno de Railway; si no, 'development'."""
    return (os.getenv('APP_ENV') or os.getenv('RAILWAY_ENVIRONMENT_NAME')
            or entorno_railway() or 'development')


def es_produccion():
    return entorno_app() == 'production'


def etiqueta_entorno():
    """Etiqueta para el asunto de las alertas ("[PRODUCTION] ..."): APP_ENV, el
    nombre del entorno de Railway o 'unknown'. Igual que antes."""
    return os.getenv('APP_ENV', os.getenv('RAILWAY_ENVIRONMENT_NAME', 'unknown'))


def aviso_de_entorno():
    """Texto de aviso si APP_ENV contradice al entorno de Railway, o None."""
    app_env = os.getenv('APP_ENV')
    railway = os.getenv('RAILWAY_ENVIRONMENT_NAME') or entorno_railway()
    if app_env and railway and app_env != railway:
        return (f"APP_ENV={app_env!r} no coincide con el entorno de Railway {railway!r}: "
                f"el comportamiento de negocio seguirá APP_ENV y la seguridad, Railway")
    return None


# --- Crons ---------------------------------------------------------------------

def token_cron():
    """Secreto de los crons: CRON_TOKEN (o CRON_SECRET, nombre antiguo)."""
    return os.environ.get('CRON_TOKEN') or os.environ.get('CRON_SECRET')


def cabecera_cron_valida(cabecera):
    """True si `cabecera` es 'Bearer <token de cron>' (comparación en tiempo
    constante). Nunca lanza: un token con caracteres no ASCII es simplemente
    inválido (antes daba 500 en cron_routes)."""
    esperado = token_cron()
    cabecera = cabecera or ''
    token = cabecera[7:].strip() if cabecera.lower().startswith('bearer ') else ''
    if not esperado or not token:
        return False
    try:
        return secrets.compare_digest(token, esperado)
    except TypeError:
        return False


def alertas_cron_activas():
    """Interruptor general de alertas por email (CRON_ALERTS_ENABLED, por defecto activas)."""
    return os.getenv('CRON_ALERTS_ENABLED', 'true').lower() == 'true'


def email_alertas():
    return os.getenv('CRON_ALERTS_EMAIL', EMAIL_ALERTAS_POR_DEFECTO)


def email_alertas_llm():
    """Destinatario por defecto de los avisos de LLM Monitoring (watchdog y
    modelos): CRON_ALERTS_EMAIL, CRON_ALERT_EMAIL, MODEL_DISCOVERY_EMAIL o el
    de siempre. Igual que antes; hoy CRON_ALERTS_EMAIL está definida en los dos
    entornos, así que coincide con email_alertas()."""
    return (os.getenv('CRON_ALERTS_EMAIL') or os.getenv('CRON_ALERT_EMAIL')
            or os.getenv('MODEL_DISCOVERY_EMAIL') or EMAIL_ALERTAS_POR_DEFECTO)


# --- Otros ---------------------------------------------------------------------

def url_publica():
    """URL pública de la app para enlaces en emails (sin barra final)."""
    return (os.getenv('PUBLIC_BASE_URL') or URL_PUBLICA_POR_DEFECTO).rstrip('/')


def cuotas_forzadas():
    """ENFORCE_QUOTAS: control de cuota en el middleware de SerpAPI (por defecto no)."""
    return os.getenv('ENFORCE_QUOTAS', 'false').lower() == 'true'
