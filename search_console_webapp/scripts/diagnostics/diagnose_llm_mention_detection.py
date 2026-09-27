#!/usr/bin/env python3
"""
Script de diagnóstico para verificar detección de menciones en LLM Monitoring

Analiza una respuesta específica de LLM y muestra:
- Qué variaciones de marca se están generando
- Si se detectan menciones de la marca
- Si se detectan menciones de competidores
- Por qué podría no estar detectando correctamente
"""

import sys
from services.ai_analysis import extract_brand_variations, remove_accents
import re

# La respuesta real de ChatGPT que el usuario dice que tiene menciones
RESPONSE_TEXT = """
¿Qué tasas de éxito tiene Ginemed en comparación con IVI?

Aquí tienes lo que he podido averiguar sobre las tasas de éxito de IVI y Ginemed en España — pero ojo: los datos no permiten una comparación directa fiable, porque los criterios, tratamientos y segmentos de pacientes varían bastante. Te lo explico con detalle.

IVI

En su página, IVI afirma que sus "tasas de éxito son hasta un 25 % superiores a la media del sector según datos públicos de la Sociedad Española de Fertilidad (SEF)". 
IVI

En otro apartado, dicen que "en FIV como en ovodonación nuestras tasas de éxito rondan en torno al 70 %-80 % en un solo intento, mientras que la tasa acumulada a tres intentos en ambos casos es muy cercana al 100 %". 
IVI

En un foro, alguien cita datos para IVI Madrid: para mujeres <35 años con óvulos propios, 42.7-52.4 % de embarazo; para 35-39 años, 30.8-44.4 %; para >40 años, 1.5-29.3 %. 
Reproducción Asistida ORG

Según información general del sector (no específica de IVI), la tasa de parto por transferencia para FIV-ICSI con óvulos propios: <35 años → ~34.6 %, 35-39 años → ~25 %, ≥40 años → ~11.6 %. 
Reproducción Asistida ORG

Conclusión para IVI: La clínica afirma tasas elevadas (70-80 % en ciertos tratamientos), pero los datos públicos más detallados muestran rangos mucho más bajos y muy dependientes de la edad y del tipo de tratamiento. En resumen: tienen buenos resultados, pero no hay garantía de 70-80 % para todos los casos.

Ginemed

En su web señalan para "ovodonación" una tasa "en torno al 80 %" en transferencias de dos embriones en día +5 (blastocisto). 
Ginemed

También indican: "un 84 % de embarazos en un ciclo (fresco + vitrificado)" para ovodonación. 
Ginemed

Un site de análisis de clínicas indica para Ginemed Madrid algunos datos poco fiables: por ejemplo, "mujer receptora menor de 35 años: 100 %-100 %" en embarazo por transferencia embrionaria (lo que parece poco creíble). 
asprofa.es

Otro informe muestra una tasa de embarazo por ciclo (FIV-ICSI) según otro site: 73 %. 
Mundo Fertilidad

Conclusión para Ginemed: También declaran tasas muy altas, especialmente en ovodonación. Pero como con IVI, es clave ver a qué tratamiento corresponde exactamente, la edad, si es óvulos propios o donados, etc. Los datos públicos más neutrales muestran rangos menos definitivos.

Comparación crítica

Tratamientos distintos: Cuando una clínica habla de "ovodonación" (óvulos de donante) los porcentajes son sustancialmente mejores que cuando se usan los propios óvulos de la mujer. Por lo tanto, si Ginemed cita ~80 % para ovodonación y IVI habla de 70-80 % para ciertos casos, puede que ambos estén hablando de óvulos de donante o de tratamientos seleccionados, no del promedio global.

Edad de la paciente: Es el factor número uno que afecta éxito. Las cifras globales del sector muestran tasas de parto muy inferiores para >40 años, por ejemplo ~11%. 
Reproducción Asistida ORG

Transparencia de los datos: Muchos datos provienen de soportes de marketing de las clínicas, no de un informe público homogéneo. Esto dificulta la comparación estricta y objetiva.

Promesas vs realidad: Decir "tasa hasta 25 % mejor que la media" es algo vago: no se especifica para qué grupo de pacientes, cuántos ciclos, etc.

Expectativas cautas: Ninguna clínica puede garantizar embarazo o parto. Como dice un artículo: "ninguna clínica… puede asegurarte que tendrás un hijo". 
Newtral

¿Mi veredicto?

Carlos: no estás totalmente equivocado al querer ver cuál de las dos tiene "mejores" resultados — es una pregunta legítima y relevante para tu cliente. Pero sí estaría equivocado si esperas una respuesta clara y "cuál es la mejor con datos inequívocos" porque no existe una comparación perfecta disponible públicamente.

Si tuviera que resumir:

IVI tiene una reputación fuerte, declaran buenos resultados, pero los datos públicos muestran que los resultados dependen mucho del perfil de la paciente.

Ginemed también afirma tasas altas, especialmente en ovodonación, pero hay menos datos independientes de comparación.

Si quieres, puedo revisar los informes más recientes de la SEF o de cada clínica para ver valores actualizados específicos para Madrid en 2023-24, y ver si logro encontrar datos comparativos en contextos similares (por edad, tratamiento). ¿Te parece bien que lo haga?
"""

def diagnose_mention_detection():
    """
    Diagnostica por qué no se están detectando las menciones correctamente
    """
    
    print("="*80)
    print("🔍 DIAGNÓSTICO DE DETECCIÓN DE MENCIONES")
    print("="*80)
    print()
    
    # Probar diferentes brand_names posibles
    test_cases = [
        {
            'brand_name': 'Ginemed',
            'competitors': ['IVI', 'Reproducción Asistida']
        },
        {
            'brand_name': 'ginemed.com',
            'competitors': ['ivi.es', 'reproduccionasistida.org']
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        brand_name = test['brand_name']
        competitors = test['competitors']
        
        print(f"\n{'='*80}")
        print(f"TEST {i}: brand_name = '{brand_name}'")
        print(f"{'='*80}\n")
        
        # 1. Generar variaciones de marca
        print(f"1️⃣ VARIACIONES GENERADAS DE '{brand_name}':")
        brand_variations = extract_brand_variations(brand_name.lower())
        for var in brand_variations:
            print(f"   - '{var}'")
        
        # 2. Buscar menciones
        print(f"\n2️⃣ BÚSQUEDA DE MENCIONES:")
        mentions_found = []
        text_lower = RESPONSE_TEXT.lower()
        
        for variation in brand_variations:
            pattern = r'\b' + re.escape(variation.lower()) + r'\b'
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            
            if matches:
                print(f"   ✅ '{variation}' encontrada: {len(matches)} veces")
                for match in matches:
                    start = max(0, match.start() - 50)
                    end = min(len(RESPONSE_TEXT), match.end() + 50)
                    context = RESPONSE_TEXT[start:end].strip()
                    mentions_found.append((variation, context))
            else:
                print(f"   ❌ '{variation}' NO encontrada")
        
        # 3. Resultados finales
        print(f"\n3️⃣ RESULTADO FINAL:")
        print(f"   Total menciones encontradas: {len(mentions_found)}")
        print(f"   Brand mentioned: {len(mentions_found) > 0}")
        
        if mentions_found:
            print(f"\n   📝 Contextos de menciones:")
            for var, context in mentions_found[:3]:  # Mostrar solo primeras 3
                print(f"\n   Variación: '{var}'")
                print(f"   Contexto: ...{context}...")
        
        # 4. Buscar competidores
        print(f"\n4️⃣ COMPETIDORES DETECTADOS:")
        for competitor in competitors:
            comp_variations = extract_brand_variations(competitor.lower())
            comp_count = 0
            
            for variation in comp_variations:
                pattern = r'\b' + re.escape(variation.lower()) + r'\b'
                comp_count += len(re.findall(pattern, text_lower, re.IGNORECASE))
            
            if comp_count > 0:
                print(f"   ✅ '{competitor}': {comp_count} menciones")
            else:
                print(f"   ❌ '{competitor}': 0 menciones")
        
        print(f"\n{'='*80}\n")
    
    # Análisis manual (búsqueda simple)
    print("\n" + "="*80)
    print("5️⃣ BÚSQUEDA MANUAL SIMPLE (sin regex):")
    print("="*80)
    
    simple_searches = ['ginemed', 'ivi', 'reproducción asistida', 'eevee', 'ginemate']
    text_lower = RESPONSE_TEXT.lower()
    
    for term in simple_searches:
        count = text_lower.count(term)
        if count > 0:
            print(f"   ✅ '{term}': {count} menciones (búsqueda simple)")
        else:
            print(f"   ❌ '{term}': 0 menciones")
    
    print("\n" + "="*80)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("="*80)

if __name__ == '__main__':
    diagnose_mention_detection()


