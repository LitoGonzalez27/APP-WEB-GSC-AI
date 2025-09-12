# brevo_api_service.py - Servicio de email usando API de Brevo (más rápido que SMTP)

import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Configuración API Brevo
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'info@clicandseo.com')
FROM_NAME = os.getenv('FROM_NAME', 'ClicandSEO')

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
            "htmlContent": html_body
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
