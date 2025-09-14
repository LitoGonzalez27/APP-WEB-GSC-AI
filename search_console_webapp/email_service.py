# email_service.py - Servicio de envío de emails

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional

load_dotenv()
logger = logging.getLogger(__name__)

# Configuración SMTP - Optimizada para Brevo
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp-relay.brevo.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))  # Puerto STARTTLS
USE_STARTTLS = os.getenv('USE_STARTTLS', 'true').lower() == 'true'
SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'info@clicandseo.com')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'info@clicandseo.com')
FROM_NAME = os.getenv('FROM_NAME', 'ClicandSEO')

# Branding y URLs públicas
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'https://app.clicandseo.com')
LOGO_URL = f"{PUBLIC_BASE_URL}/static/images/logos/logo%20clicandseo.png"

def send_email(to_email: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """
    Envía un email usando SMTP
    
    Args:
        to_email: Email destinatario
        subject: Asunto del email
        html_body: Cuerpo HTML del email
        text_body: Cuerpo de texto plano (opcional)
    
    Returns:
        bool: True si se envió exitosamente, False en caso contrario
    """
    try:
        # Verificar configuración
        if not SMTP_PASSWORD:
            logger.error("SMTP_PASSWORD no configurada")
            return False
        
        # Crear mensaje
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        message["To"] = to_email
        
        # Agregar cuerpo de texto plano si se proporciona
        if text_body:
            text_part = MIMEText(text_body, "plain", "utf-8")
            message.attach(text_part)
        
        # Agregar cuerpo HTML
        html_part = MIMEText(html_body, "html", "utf-8")
        message.attach(html_part)
        
        # Crear contexto SSL seguro
        context = ssl.create_default_context()
        
        # Conectar al servidor SMTP con timeout más largo para Railway/Brevo
        if USE_STARTTLS or SMTP_PORT == 587:
            # Usar STARTTLS (puerto 587)
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                server.starttls(context=context)
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, to_email, message.as_string())
        else:
            # Usar SSL directo (puerto 465)
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=30) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, to_email, message.as_string())
        
        logger.info(f"Email enviado exitosamente a {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error enviando email a {to_email}: {e}")
        return False

def send_password_reset_email(to_email: str, reset_url: str, user_name: str = None) -> bool:
    """
    Envía email de reset de contraseña
    
    Args:
        to_email: Email del usuario
        reset_url: URL con token para resetear contraseña
        user_name: Nombre del usuario (opcional)
    
    Returns:
        bool: True si se envió exitosamente
    """
    
    # Determinar saludo
    greeting = f"Hi {user_name}!" if user_name else "Hi!"
    
    # Asunto del email
    subject = "Reset Your ClicandSEO Password"
    
    # Cuerpo HTML del email
    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reset Your Password</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 20px;
                background-color: #F3F2F1;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .logo {{
                margin-bottom: 20px;
            }}
            .logo img {{
                max-width: 180px;
                height: auto;
                max-height: 50px;
            }}
            h1 {{
                color: #1f2937;
                font-size: 24px;
                margin-bottom: 20px;
            }}
            .content {{
                margin-bottom: 30px;
                font-size: 16px;
                line-height: 1.6;
            }}
            .button {{
                display: inline-block;
                background-color: #D8F9B8;
                color: #161616;
                padding: 14px 28px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                margin: 20px 0;
                transition: all 0.3s ease;
            }}
            .button:hover {{
                background-color: #C5E89A;
                transform: translateY(-1px);
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e5e7eb;
                font-size: 14px;
                color: #6b7280;
                text-align: center;
            }}
            .warning {{
                background-color: #fef3c7;
                color: #92400e;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                font-size: 14px;
            }}
            .url-fallback {{
                background-color: #f3f4f6;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                font-size: 14px;
                word-break: break-all;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">
                    <img src="{LOGO_URL}" alt="ClicandSEO" />
                </div>
            </div>
            
            <h1>Reset Your Password</h1>
            
            <div class="content">
                <p>{greeting}</p>
                
                <p>We received a request to reset your password for your ClicandSEO account. Click the button below to create a new password:</p>
                
                <div style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset My Password</a>
                </div>
                
                <div class="warning">
                    <strong>Important:</strong> This link will expire in 1 hour for security reasons.
                </div>
                
                <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                <div class="url-fallback">
                    {reset_url}
                </div>
                
                <p>If you didn't request this password reset, you can safely ignore this email. Your password will remain unchanged.</p>
            </div>
            
            <div class="footer">
                <p>This email was sent by ClicandSEO</p>
                <p>If you have any questions, please contact our support team.</p>
                <p style="margin-top: 15px; font-size: 12px;">
                    For security reasons, do not forward this email or share the reset link with anyone.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Cuerpo de texto plano (fallback)
    text_body = f"""
    {greeting}
    
    We received a request to reset your password for your ClicandSEO account.
    
    Please click on the following link to reset your password:
    {reset_url}
    
    This link will expire in 1 hour for security reasons.
    
    If you didn't request this password reset, you can safely ignore this email.
    
    For security reasons, do not forward this email or share the reset link with anyone.
    
    --
    ClicandSEO Team
    """
    
    return send_email(to_email, subject, html_body, text_body)

def send_welcome_email(to_email: str, user_name: Optional[str] = None) -> bool:
    """
    Envía el email de bienvenida tras registro. Intenta API de Brevo y hace fallback a SMTP.
    """
    greeting = f"Hi {user_name}!" if user_name else "Hi!"
    subject = "Welcome to ClicandSEO"

    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 20px;
                background-color: #F3F2F1;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 24px;
            }}
            .logo img {{
                max-width: 180px;
                height: auto;
                max-height: 50px;
            }}
            h1 {{
                color: #1f2937;
                font-size: 24px;
                margin-bottom: 12px;
            }}
            .content {{
                margin-bottom: 20px;
                font-size: 16px;
            }}
            .button {{
                display: inline-block;
                background-color: #D8F9B8;
                color: #161616;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                margin: 16px 0;
            }}
            .footer {{
                margin-top: 24px;
                padding-top: 16px;
                border-top: 1px solid #e5e7eb;
                font-size: 14px;
                color: #6b7280;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">
                    <img src="{LOGO_URL}" alt="ClicandSEO" />
                </div>
            </div>
            <h1>Welcome to ClicandSEO</h1>
            <div class="content">
                <p>{greeting}</p>
                <p>Thanks for signing up! Your account has been created successfully.</p>
                <p>You can now sign in and start using the app.</p>
                <div style="text-align:center;">
                    <a href="https://app.clicandseo.com/" class="button">Go to the App</a>
                </div>
                <p>If you need any help, contact us at <a href="mailto:hola@clicandseo.com" style="color:#111; text-decoration:none; font-weight:600;">hola@clicandseo.com</a>.</p>
            </div>
            <div class="footer">
                <p>This email was sent by ClicandSEO</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"""
    {greeting}

    Thanks for signing up! Your account has been created successfully.
    You can now sign in and start using the app: https://app.clicandseo.com/

    Need help? Email us at hola@clicandseo.com

    --
    ClicandSEO Team
    """

    # Intentar API de Brevo primero
    try:
        from brevo_api_service import send_email_via_api as _brevo_send
        sent = _brevo_send(to_email, subject, html_body)
        if sent:
            return True
    except Exception as e:
        logger.warning(f"Fallo envío via API (welcome), usando SMTP fallback: {e}")

    return send_email(to_email, subject, html_body, text_body)

def send_trial_started_email(to_email: str, plan: str, trial_end: Optional[datetime]) -> bool:
    """
    Envía el email de inicio de prueba (7 días). Intenta API de Brevo y hace fallback a SMTP.
    """
    subject = "Your 7-day free trial has started"
    trial_end_str = trial_end.strftime('%Y-%m-%d') if isinstance(trial_end, datetime) else 'in 7 days'

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color:#F3F2F1; padding:20px;">
        <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;">
        <h2 style="margin:0 0 8px 0;">Welcome to your {plan.title()} trial!</h2>
        <p>You have activated a <strong>7-day free trial</strong> of the <strong>{plan.title()}</strong> plan.</p>
        <p>At the end of the trial (on <strong>{trial_end_str}</strong>), your subscription will renew automatically unless you cancel beforehand.</p>
        <p>You can manage your subscription anytime from the billing portal.</p>
        <p><a href="https://app.clicandseo.com/billing/portal" style="display:inline-block;padding:10px 16px;background:#D8F9B8;color:#111;text-decoration:none;border-radius:8px;">Open billing portal</a></p>
        <p style="color:#666;font-size:12px;margin-top:20px;">If you didn't expect this message, please contact support.</p>
        </div>
    </body>
    </html>
    """

    text_body = (
        f"Your 7-day free trial of the {plan.title()} plan has started. "
        f"It will renew automatically on {trial_end_str} unless you cancel earlier. "
        "Manage your subscription at https://app.clicandseo.com/billing/portal"
    )

    # Intentar API de Brevo primero
    try:
        from brevo_api_service import send_email_via_api as _brevo_send
        sent = _brevo_send(to_email, subject, html_body)
        if sent:
            return True
    except Exception as e:
        logger.warning(f"Fallo envío via API (trial), usando SMTP fallback: {e}")

    return send_email(to_email, subject, html_body, text_body)

def send_test_email(to_email: str) -> bool:
    """
    Envía un email de prueba para verificar la configuración SMTP
    """
    subject = "ClicandSEO - Test Email"
    html_body = """
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #D8F9B8;">ClicandSEO Email Configuration Test</h2>
        <p>If you're reading this, the SMTP configuration is working correctly!</p>
        <p>✅ SMTP server connection: Success</p>
        <p>✅ Email sending: Success</p>
        <p>✅ HTML formatting: Success</p>
        <hr>
        <p style="font-size: 12px; color: #666;">
            This is a test email sent from the ClicandSEO password reset system.
        </p>
    </body>
    </html>
    """
    text_body = """
    ClicandSEO Email Configuration Test
    
    If you're reading this, the SMTP configuration is working correctly!
    
    ✅ SMTP server connection: Success
    ✅ Email sending: Success
    
    This is a test email sent from the ClicandSEO password reset system.
    """
    
    return send_email(to_email, subject, html_body, text_body)

if __name__ == "__main__":
    # Script de prueba
    test_email = input("Ingresa email para prueba: ").strip()
    if test_email:
        print("Enviando email de prueba...")
        success = send_test_email(test_email)
        if success:
            print("✅ Email de prueba enviado exitosamente!")
        else:
            print("❌ Error enviando email de prueba")
    else:
        print("Email inválido")
