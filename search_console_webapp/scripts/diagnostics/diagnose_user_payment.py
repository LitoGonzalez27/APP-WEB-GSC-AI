#!/usr/bin/env python3
"""
Diagnóstico Usuario Payment - Verificar estado después del pago
===============================================================

Diagnostica por qué un usuario sigue como Free después del pago exitoso
y permite corrección manual del estado.
"""

import os
import sys
import json
import stripe
from datetime import datetime
from database import get_db_connection
from stripe_config import get_stripe_config

class UserPaymentDiagnostic:
    
    def __init__(self):
        """Inicializa diagnóstico con configuración"""
        self.config = get_stripe_config()
        stripe.api_key = self.config.secret_key
        print(f"🔗 Conectado a Stripe - Environment: {self.config.app_env}")
    
    def diagnose_user(self, email: str):
        """Diagnostica estado completo de un usuario"""
        print(f"\n🔍 DIAGNÓSTICO COMPLETO PARA: {email}")
        print("=" * 60)
        
        # 1. Estado en nuestra base de datos
        db_info = self.get_user_database_info(email)
        if not db_info:
            print("❌ Usuario no encontrado en base de datos")
            return False
        
        print(f"\n📊 ESTADO EN BASE DE DATOS:")
        print(f"   ID: {db_info['id']}")
        print(f"   Email: {db_info['email']}")
        print(f"   Plan: {db_info.get('plan', 'N/A')}")
        print(f"   Billing Status: {db_info.get('billing_status', 'N/A')}")
        print(f"   Quota Limit: {db_info.get('quota_limit', 'N/A')}")
        print(f"   Stripe Customer ID: {db_info.get('stripe_customer_id', 'N/A')}")
        print(f"   Subscription ID: {db_info.get('subscription_id', 'N/A')}")
        print(f"   Created: {db_info.get('created_at', 'N/A')}")
        print(f"   Updated: {db_info.get('updated_at', 'N/A')}")
        
        # 2. Estado en Stripe (si existe customer)
        stripe_customer_id = db_info.get('stripe_customer_id')
        if stripe_customer_id:
            stripe_info = self.get_stripe_customer_info(stripe_customer_id)
            print(f"\n💳 ESTADO EN STRIPE:")
            if stripe_info:
                self.print_stripe_info(stripe_info)
            else:
                print("   ❌ Customer no encontrado en Stripe")
        else:
            print(f"\n💳 ESTADO EN STRIPE: No hay customer_id asociado")
        
        # 3. Buscar customer por email en Stripe
        stripe_by_email = self.find_stripe_customer_by_email(email)
        if stripe_by_email and stripe_by_email != stripe_customer_id:
            print(f"\n🔍 CUSTOMER ENCONTRADO POR EMAIL (diferente al guardado):")
            stripe_info = self.get_stripe_customer_info(stripe_by_email)
            if stripe_info:
                self.print_stripe_info(stripe_info)
        
        # 4. Recomendaciones
        self.analyze_and_recommend(db_info, stripe_customer_id)
        
        return db_info
    
    def get_user_database_info(self, email: str):
        """Obtiene información del usuario de la base de datos"""
        try:
            conn = get_db_connection()
            if not conn:
                return None
            
            cur = conn.cursor()
            cur.execute('''
                SELECT * FROM users WHERE email = %s
            ''', (email,))
            
            user = cur.fetchone()
            conn.close()
            
            return dict(user) if user else None
            
        except Exception as e:
            print(f"❌ Error consultando base de datos: {e}")
            return None
    
    def get_stripe_customer_info(self, customer_id: str):
        """Obtiene información del customer de Stripe"""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            
            # Obtener suscripciones
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                limit=10
            )
            
            # Obtener checkout sessions recientes
            checkout_sessions = stripe.checkout.Session.list(
                customer=customer_id,
                limit=10
            )
            
            return {
                'customer': customer,
                'subscriptions': subscriptions.data,
                'checkout_sessions': checkout_sessions.data
            }
            
        except Exception as e:
            print(f"❌ Error consultando Stripe: {e}")
            return None
    
    def find_stripe_customer_by_email(self, email: str):
        """Busca customer en Stripe por email"""
        try:
            customers = stripe.Customer.list(email=email, limit=10)
            return customers.data[0].id if customers.data else None
        except Exception as e:
            print(f"❌ Error buscando customer por email: {e}")
            return None
    
    def print_stripe_info(self, stripe_info):
        """Imprime información de Stripe de forma organizada"""
        customer = stripe_info['customer']
        subscriptions = stripe_info['subscriptions']
        checkout_sessions = stripe_info['checkout_sessions']
        
        print(f"   Customer ID: {customer.id}")
        print(f"   Email: {customer.email}")
        print(f"   Created: {datetime.fromtimestamp(customer.created)}")
        
        print(f"\n   📋 SUSCRIPCIONES ({len(subscriptions)}):")
        for sub in subscriptions:
            print(f"      - ID: {sub.id}")
            print(f"        Status: {sub.status}")
            print(f"        Current Period: {datetime.fromtimestamp(sub.current_period_start)} → {datetime.fromtimestamp(sub.current_period_end)}")
            
            # Items de la suscripción
            for item in sub.items.data:
                price = item.price
                print(f"        Price ID: {price.id}")
                print(f"        Product ID: {price.product}")
                print(f"        Amount: {price.unit_amount/100} {price.currency}")
        
        print(f"\n   🛒 CHECKOUT SESSIONS ({len(checkout_sessions)}):")
        for session in checkout_sessions:
            print(f"      - ID: {session.id}")
            print(f"        Status: {session.payment_status}")
            print(f"        Mode: {session.mode}")
            print(f"        Created: {datetime.fromtimestamp(session.created)}")
            print(f"        Client Reference ID: {session.client_reference_id}")
            print(f"        Subscription: {session.subscription}")
    
    def analyze_and_recommend(self, db_info, stripe_customer_id):
        """Analiza el estado y propone recomendaciones"""
        print(f"\n💡 ANÁLISIS Y RECOMENDACIONES:")
        print("-" * 40)
        
        plan = db_info.get('plan', 'free')
        billing_status = db_info.get('billing_status', 'inactive')
        
        if plan == 'free' and billing_status != 'active':
            print("🚨 PROBLEMA DETECTADO:")
            print("   - Usuario sigue como Free después del pago")
            print("   - Billing status no es 'active'")
            print()
            print("🔧 POSIBLES CAUSAS:")
            print("   1. Webhook no se ejecutó correctamente")
            print("   2. client_reference_id faltante en checkout (CORREGIDO)")
            print("   3. Error en el procesamiento del webhook")
            print("   4. Suscripción creada pero no sincronizada")
            print()
            print("✅ SOLUCIONES DISPONIBLES:")
            print("   - Ejecutar corrección manual del estado")
            print("   - Re-procesar webhook manualmente")
            print("   - Verificar logs de webhook")
            
            return True
        else:
            print("✅ Usuario parece estar en estado correcto")
            return False
    
    def manual_fix_user_state(self, email: str, target_plan: str = 'basic'):
        """Corrección manual del estado del usuario"""
        print(f"\n🔧 CORRECCIÓN MANUAL PARA: {email}")
        print("=" * 50)
        
        # Obtener usuario
        db_info = self.get_user_database_info(email)
        if not db_info:
            print("❌ Usuario no encontrado")
            return False
        
        user_id = db_info['id']
        stripe_customer_id = db_info.get('stripe_customer_id')
        
        if not stripe_customer_id:
            print("❌ No hay stripe_customer_id - no se puede corregir")
            return False
        
        # Obtener suscripción activa de Stripe
        stripe_info = self.get_stripe_customer_info(stripe_customer_id)
        if not stripe_info or not stripe_info['subscriptions']:
            print("❌ No hay suscripciones activas en Stripe")
            return False
        
        # Tomar la primera suscripción activa
        subscription = stripe_info['subscriptions'][0]
        if subscription.status != 'active':
            print(f"❌ Suscripción no está activa: {subscription.status}")
            return False
        
        # Determinar plan y quota
        price_id = subscription.items.data[0].price.id
        plan = self.determine_plan_from_price_id(price_id)
        quota_limit = self.config.get_plan_limits().get(plan, 0)
        
        print(f"🔄 Actualizando usuario:")
        print(f"   Plan: free → {plan}")
        print(f"   Billing Status: → active")
        print(f"   Quota Limit: → {quota_limit}")
        print(f"   Subscription ID: → {subscription.id}")
        
        # Actualizar base de datos
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute('''
                UPDATE users 
                SET 
                    plan = %s,
                    current_plan = %s,
                    billing_status = 'active',
                    quota_limit = %s,
                    quota_used = 0,
                    subscription_id = %s,
                    current_period_start = %s,
                    current_period_end = %s,
                    updated_at = NOW()
                WHERE id = %s
            ''', (
                plan, plan, quota_limit, subscription.id,
                datetime.fromtimestamp(subscription.current_period_start),
                datetime.fromtimestamp(subscription.current_period_end),
                user_id
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Usuario corregido exitosamente")
            print(f"   Plan activado: {plan}")
            print(f"   Quota disponible: {quota_limit} RU")
            
            return True
            
        except Exception as e:
            print(f"❌ Error actualizando usuario: {e}")
            return False
    
    def determine_plan_from_price_id(self, price_id: str):
        """Determina el plan basado en price_id"""
        price_ids = self.config.get_plan_price_ids()
        
        for plan, plan_price_id in price_ids.items():
            if price_id == plan_price_id:
                return plan
        
        # Fallback
        return 'basic'

def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print("Uso: python3 -m scripts.diagnostics.diagnose_user_payment <email> [fix]")
        print("Ejemplos:")
        print("  python3 -m scripts.diagnostics.diagnose_user_payment info@tucreditorapido.com")
        print("  python3 -m scripts.diagnostics.diagnose_user_payment info@tucreditorapido.com fix")
        sys.exit(1)
    
    email = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else 'diagnose'
    
    diagnostic = UserPaymentDiagnostic()
    
    if action == 'fix':
        # Primero diagnosticar
        db_info = diagnostic.diagnose_user(email)
        if db_info:
            print(f"\n" + "="*60)
            print("🔧 EJECUTANDO CORRECCIÓN MANUAL")
            diagnostic.manual_fix_user_state(email)
    else:
        # Solo diagnosticar
        diagnostic.diagnose_user(email)

if __name__ == "__main__":
    main()
