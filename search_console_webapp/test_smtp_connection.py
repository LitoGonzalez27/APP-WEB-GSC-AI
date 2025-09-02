#!/usr/bin/env python3
# test_smtp_connection.py - Diagnóstico de conexión SMTP

import smtplib
import ssl
import os
import socket
from dotenv import load_dotenv

load_dotenv()

def test_smtp_connection():
    """Prueba diferentes configuraciones SMTP"""
    
    server = os.getenv('SMTP_SERVER', 'mail.clicandseo.com')
    username = os.getenv('SMTP_USERNAME', 'info@clicandseo.com')
    password = os.getenv('SMTP_PASSWORD', '')
    
    print(f"🧪 Testing SMTP connection to {server}")
    print(f"👤 Username: {username}")
    print(f"🔑 Password: {'✅ Set' if password else '❌ Not set'}")
    print()
    
    # Test 1: Puerto 465 (SSL directo)
    print("🔌 Test 1: Port 465 (SSL Direct)")
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(server, 465, context=context, timeout=10) as smtp:
            smtp.login(username, password)
            print("✅ Port 465 SSL: SUCCESS")
            return True
    except socket.timeout:
        print("❌ Port 465 SSL: Connection timeout")
    except Exception as e:
        print(f"❌ Port 465 SSL: {e}")
    
    # Test 2: Puerto 587 (STARTTLS)
    print("\n🔌 Test 2: Port 587 (STARTTLS)")
    try:
        with smtplib.SMTP(server, 587, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            print("✅ Port 587 STARTTLS: SUCCESS")
            return True
    except socket.timeout:
        print("❌ Port 587 STARTTLS: Connection timeout")
    except Exception as e:
        print(f"❌ Port 587 STARTTLS: {e}")
    
    # Test 3: Puerto 25 (No seguro, solo para test)
    print("\n🔌 Test 3: Port 25 (Insecure - test only)")
    try:
        with smtplib.SMTP(server, 25, timeout=10) as smtp:
            smtp.login(username, password)
            print("✅ Port 25: SUCCESS (but insecure)")
            return True
    except socket.timeout:
        print("❌ Port 25: Connection timeout")
    except Exception as e:
        print(f"❌ Port 25: {e}")
    
    print("\n💡 Railway podría estar bloqueando conexiones SMTP salientes")
    print("🎯 Recomendación: Usar SendGrid, Mailgun o AWS SES")
    
    return False

if __name__ == "__main__":
    test_smtp_connection()
