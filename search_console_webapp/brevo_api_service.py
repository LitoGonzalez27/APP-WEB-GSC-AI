# brevo_api_service.py - Servicio de email usando API de Brevo (más rápido que SMTP)

import requests
import os
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Configuración API Brevo
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'info@clicandseo.com')
FROM_NAME = os.getenv('FROM_NAME', 'ClicandSEO')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'https://app.clicandseo.com')
LOGO_URL = f"{PUBLIC_BASE_URL}/static/images/logos/logo%20clicandseo.png"

def send_email_via_api(to_email: str, subject: str, html_body: str) -> bool:
    """
    Envía email usando API de Brevo (más rápido que SMTP)
    """
    try:
        if not BREVO_API_KEY:
            logger.error("BREVO_API_KEY no configurada")
            return False
        
        url = "https://api.brevo.com/v3/smtp/email"
        
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        
        payload = {
            "sender": {
                "name": FROM_NAME,
                "email": FROM_EMAIL
            },
            "to": [
                {
                    "email": to_email,
                    "name": to_email.split('@')[0].title()
                }
            ],
            "subject": subject,
            "htmlContent": html_body,
            "headers": {
                "X-Mailer": "ClicandSEO-App",
                "List-Id": "clicandseo.app"
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 201:
            logger.info(f"✅ Email enviado via API a {to_email}")
            return True
        else:
            logger.error(f"❌ Error API Brevo: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error enviando email via API: {e}")
        return False

def send_password_reset_via_api(to_email: str, reset_url: str, user_name: str = None) -> bool:
    """
    Envía email de reset usando API de Brevo
    """
    greeting = f"Hi {user_name}!" if user_name else "Hi!"
    subject = "Reset Your ClicandSEO Password"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }}
            .logo {{ font-size: 28px; font-weight: 700; color: #D8F9B8; margin-bottom: 20px; text-align: center; }}
            h1 {{ color: #1f2937; font-size: 24px; margin-bottom: 20px; }}
            .button {{ display: inline-block; background-color: #D8F9B8; color: #161616; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; margin: 20px 0; }}
            .warning {{ background-color: #fef3c7; color: #92400e; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 14px; }}
            .url-fallback {{ background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 14px; word-break: break-all; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 14px; color: #6b7280; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">ClicandSEO</div>
            <h1>Reset Your Password</h1>
            <p>{greeting}</p>
            <p>We received a request to reset your password for your ClicandSEO account. Click the button below to create a new password:</p>
            <div style="text-align: center;">
                <a href="{reset_url}" class="button">Reset My Password</a>
            </div>
            <div class="warning">
                <strong>Important:</strong> This link will expire in 1 hour for security reasons.
            </div>
            <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
            <div class="url-fallback">{reset_url}</div>
            <p>If you didn't request this password reset, you can safely ignore this email. Your password will remain unchanged.</p>
            <div class="footer">
                <p>This email was sent by ClicandSEO</p>
                <p>If you have any questions, please contact our support team.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_via_api(to_email, subject, html_body)

# =============================
# Gestión de Contactos y Listas
# =============================

def _get_api_headers() -> Dict[str, str]:
    return {
        "accept": "application/json",
        "api-key": os.getenv('BREVO_API_KEY', BREVO_API_KEY or ''),
        "content-type": "application/json",
    }

def _check_api_key_configured() -> bool:
    if not (os.getenv('BREVO_API_KEY') or BREVO_API_KEY):
        logger.error("BREVO_API_KEY no configurada para operaciones de contactos")
        return False
    return True

def _split_name(full_name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not full_name:
        return None, None
    name = ' '.join((full_name or '').strip().split())
    if not name:
        return None, None
    parts = name.split(' ')
    if len(parts) == 1:
        return parts[0], None
    return parts[0], ' '.join(parts[1:])

def _normalize_brevo_attributes(attrs: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for k, v in (attrs or {}).items():
        if v is None:
            continue
        key = str(k)
        val = v
        # Brevo 'date' attributes esperan YYYY-MM-DD
        if key.upper() in {"LAST_LOGIN_AT", "LAST_SEEN_AT"}:
            try:
                import datetime as _dt
                if isinstance(v, _dt.datetime):
                    val = v.date().isoformat()
                elif isinstance(v, _dt.date):
                    val = v.isoformat()
                else:
                    # strings: tomar solo la parte de fecha si viene ISO
                    s = str(v)
                    if 'T' in s:
                        val = s.split('T', 1)[0]
                    elif ' ' in s:
                        val = s.split(' ', 1)[0]
                    else:
                        val = s
            except Exception:
                val = str(v)
        normalized[key] = val
    return normalized

def get_list_id_by_name(list_name: str, limit: int = 50) -> Optional[int]:
    """
    Devuelve el ID de la lista cuyo nombre coincide (case-insensitive). Si no existe, retorna None.
    """
    try:
        if not _check_api_key_configured():
            return None
        url = "https://api.brevo.com/v3/contacts/lists"
        params = {"limit": limit, "offset": 0}
        headers = _get_api_headers()
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Error listando listas de Brevo: {resp.status_code} - {resp.text}")
                return None
            data = resp.json() or {}
            lists = data.get('lists') or data.get('items') or []
            for item in lists:
                name = (item.get('name') or '').strip()
                if name.lower() == list_name.strip().lower():
                    return int(item.get('id'))
            count = len(lists)
            if count < params["limit"]:
                return None
            params["offset"] = params["offset"] + count
    except Exception as e:
        logger.error(f"Error obteniendo lista por nombre en Brevo: {e}")
        return None

def _get_default_folder_id() -> Optional[int]:
    """
    Obtiene un folderId para crear listas. Usa env BREVO_FOLDER_ID si existe; si no, intenta el primero disponible.
    """
    try:
        if not _check_api_key_configured():
            return None
        env_folder = os.getenv('BREVO_FOLDER_ID')
        if env_folder:
            try:
                return int(env_folder)
            except Exception:
                logger.warning("BREVO_FOLDER_ID no es un entero válido; intentando descubrir folder por API")
        url = "https://api.brevo.com/v3/contacts/folders"
        params = {"limit": 50, "offset": 0}
        headers = _get_api_headers()
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            logger.error(f"Error listando folders en Brevo: {resp.status_code} - {resp.text}")
            return None
        data = resp.json() or {}
        folders = data.get('folders') or data.get('items') or []
        if not folders:
            logger.error("No se encontraron folders en Brevo; especifique BREVO_FOLDER_ID")
            return None
        # Preferir 'Your First Folder' si existe
        preferred = next((f for f in folders if (f.get('name') or '').strip().lower() == 'your first folder'), None)
        folder = preferred or folders[0]
        return int(folder.get('id'))
    except Exception as e:
        logger.error(f"Error obteniendo folderId por defecto: {e}")
        return None

def get_or_create_list_id(list_name: str, folder_id: Optional[int] = None) -> Optional[int]:
    """
    Obtiene el ID de la lista por nombre; si no existe, la crea (requiere folderId).
    Respeta la variable de entorno BREVO_CONTACT_LIST_ID si está definida.
    """
    try:
        env_list_id = os.getenv('BREVO_CONTACT_LIST_ID')
        if env_list_id:
            try:
                return int(env_list_id)
            except Exception:
                logger.warning("BREVO_CONTACT_LIST_ID no es un entero válido; ignorando y buscando por nombre")

        existing_id = get_list_id_by_name(list_name)
        if existing_id is not None:
            return existing_id

        if not _check_api_key_configured():
            return None

        target_folder_id = folder_id if folder_id is not None else _get_default_folder_id()
        if target_folder_id is None:
            return None

        url = "https://api.brevo.com/v3/contacts/lists"
        headers = _get_api_headers()
        payload: Dict[str, Any] = {"name": list_name, "folderId": int(target_folder_id)}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            data = resp.json() or {}
            list_id = data.get('id') or data.get('listId')
            return int(list_id) if list_id is not None else None
        else:
            logger.error(f"Error creando lista '{list_name}' en Brevo: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Error en get_or_create_list_id: {e}")
        return None

def upsert_brevo_contact(
    email: str,
    name: Optional[str] = None,
    list_id: Optional[int] = None,
    attributes: Optional[Dict[str, Any]] = None,
    update_enabled: bool = True,
) -> bool:
    """
    Crea o actualiza un contacto en Brevo y lo añade a la lista indicada (si se provee).
    """
    try:
        if not _check_api_key_configured():
            return False

        headers = _get_api_headers()
        url = "https://api.brevo.com/v3/contacts"

        # Preparar atributos
        contact_attributes: Dict[str, Any] = {}
        if attributes:
            contact_attributes.update(attributes)
        # En Brevo se usan atributos FIRSTNAME/LASTNAME por defecto
        first_name, last_name = _split_name(name)
        if first_name:
            contact_attributes['FIRSTNAME'] = first_name
        if last_name:
            contact_attributes['LASTNAME'] = last_name
        # Enviar también FULL_NAME si el esquema de atributos lo usa
        if name:
            contact_attributes['FULL_NAME'] = name

        payload: Dict[str, Any] = {
            "email": email,
            "updateEnabled": bool(update_enabled),
        }
        if contact_attributes:
            payload["attributes"] = _normalize_brevo_attributes(contact_attributes)
        if list_id is not None:
            payload["listIds"] = [int(list_id)]

        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        # Brevo puede devolver 201 (created), 200 (updated) o 204 (sin contenido) en algunos flujos
        if resp.status_code in (200, 201, 204):
            return True
        # Si ya existe y updateEnabled no fue respetado por API, intentar endpoint específico
        if resp.status_code == 400 and 'already exists' in (resp.text or '').lower():
            # Intentar añadir a lista mediante endpoint de add
            if list_id is not None:
                return add_contact_to_list(list_id, email)
        logger.error(f"Error upsert contacto Brevo: {resp.status_code} - {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Error upsert_brevo_contact: {e}")
        return False

def update_brevo_contact(
    email: str,
    attributes: Optional[Dict[str, Any]] = None,
    list_id: Optional[int] = None,
) -> bool:
    """
    Actualiza un contacto existente (PUT /v3/contacts/{identifier}).
    """
    try:
        if not _check_api_key_configured():
            return False
        if not attributes and list_id is None:
            return True
        url = f"https://api.brevo.com/v3/contacts/{quote(email)}"
        headers = _get_api_headers()
        payload: Dict[str, Any] = {}
        if attributes:
            payload["attributes"] = _normalize_brevo_attributes(attributes)
        if list_id is not None:
            payload["listIds"] = [int(list_id)]
        resp = requests.put(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201, 204):
            return True
        logger.error(f"Error actualizando contacto Brevo: {resp.status_code} - {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Error update_brevo_contact: {e}")
        return False

def add_contact_to_list(list_id: int, email: str) -> bool:
    """
    Añade un email a una lista existente usando el endpoint de list-add.
    """
    try:
        if not _check_api_key_configured():
            return False
        url = f"https://api.brevo.com/v3/contacts/lists/{int(list_id)}/contacts/add"
        headers = _get_api_headers()
        payload = {"emails": [email]}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            return True
        logger.error(f"Error añadiendo contacto a lista {list_id}: {resp.status_code} - {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Error add_contact_to_list: {e}")
        return False

def bulk_upsert_contacts(contacts: List[Dict[str, Any]], list_id: Optional[int] = None) -> Dict[str, int]:
    """
    Realiza upsert en bloque de contactos. Retorna conteo {'success': X, 'failed': Y}.
    """
    success = 0
    failed = 0
    for item in contacts:
        email = (item.get('email') or '').strip().lower()
        if not email:
            failed += 1
            continue
        name = item.get('name') or None
        attrs = item.get('attributes') or {}
        if upsert_brevo_contact(email=email, name=name, list_id=list_id, attributes=attrs):
            # Refuerzo: asegurar atributos vía PUT update
            update_brevo_contact(email=email, attributes=attrs, list_id=list_id)
            success += 1
        else:
            failed += 1
    return {"success": success, "failed": failed}
