# services/ai_analysis.py
import logging
import re
import unicodedata
from .utils import urls_match, normalize_search_console_url, extract_domain

logger = logging.getLogger(__name__)


def _detect_aio_serp_position(serp_data):
    """
    Detect where the AI Overview appears in the SERP page.

    Returns: 'top', 'middle', 'bottom', or None

    Logic:
    - 'top': AIO appears before any organic results (most common)
    - 'middle': AIO appears between organic results
    - 'bottom': AIO appears after most organic results

    SerpAPI signals this via:
    - 'ai_overview' key position relative to other SERP features
    - 'inline_*' position indicators for some features
    - Whether ads appear above/below the AIO
    """
    if not serp_data or 'ai_overview' not in serp_data:
        return None

    # Check for explicit position indicators from SerpAPI
    ai_overview = serp_data.get('ai_overview', {})

    # Some SerpAPI responses include a 'position' or block_position field
    if isinstance(ai_overview, dict):
        explicit_pos = ai_overview.get('block_position')
        if explicit_pos is not None:
            try:
                pos_num = int(explicit_pos)
                if pos_num <= 1:
                    return 'top'
                elif pos_num <= 5:
                    return 'middle'
                else:
                    return 'bottom'
            except (ValueError, TypeError):
                pass

    # Heuristic: Check what appears before organic results
    # If there are ads + AI Overview but organic_results start at position 1+, AIO is likely at top
    has_ads = bool(serp_data.get('ads'))
    organic_results = serp_data.get('organic_results', [])

    if not organic_results:
        return 'top'  # No organic results → AIO dominates the page

    # Check if first organic result has a high position number
    # (indicating many things appear before it, including AIO)
    first_organic_position = organic_results[0].get('position', 1) if organic_results else 1

    # SerpAPI returns inline positions for some features
    # If there's an inline_ai_overview or similar, check its position
    for key in serp_data:
        if 'inline' in key.lower() and 'ai' in key.lower():
            inline_data = serp_data[key]
            if isinstance(inline_data, dict) and 'block_position' in inline_data:
                try:
                    pos = int(inline_data['block_position'])
                    if pos <= 2:
                        return 'top'
                    elif pos <= 6:
                        return 'middle'
                    else:
                        return 'bottom'
                except (ValueError, TypeError):
                    pass

    # Default heuristic: AI Overview almost always appears at top in current Google layout
    # The fact that it exists as a top-level key (not inline) suggests it's at the top
    return 'top'


def remove_accents(text):
    """
    Elimina acentos y diacríticos de un texto.
    
    Ejemplos:
    - "Láserum" → "Laserum"
    - "José" → "Jose"
    - "Müller" → "Muller"
    """
    if not text:
        return text
    
    # Normalizar a NFD (separar caracteres base de diacríticos)
    nfd = unicodedata.normalize('NFD', text)
    # Filtrar solo caracteres que no sean diacríticos
    without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    # Renormalizar a NFC
    return unicodedata.normalize('NFC', without_accents)

def extract_brand_variations(domain):
    """
    Extrae variaciones de marca comunes de un dominio para detectar menciones.
    
    ✨ MEJORADO: Ahora incluye variaciones con acentos comunes en español.
    
    Ejemplos:
    - getquipu.com → ["quipu", "getquipu", "get quipu", "Quipu"]
    - laserum.com → ["laserum", "Laserum", "Láserum", "láserum"]
    - clickandseo.com → ["clickandseo", "click and seo", "Click And Seo"]
    - example-site.com → ["example-site", "example site", "examplesite"]
    """
    if not domain:
        return []
    
    # Remover extensiones comunes
    clean_domain = domain.lower()
    for ext in ['.com', '.es', '.org', '.net', '.io', '.co', '.uk', '.mx']:
        if clean_domain.endswith(ext):
            clean_domain = clean_domain[:-len(ext)]
            break
    
    # Remover www si existe
    if clean_domain.startswith('www.'):
        clean_domain = clean_domain[4:]
    
    variations = []
    
    # 1. Dominio completo limpio
    variations.append(clean_domain)
    
    # 2. Si tiene "get" al inicio, añadir versión sin "get"
    if clean_domain.startswith('get'):
        without_get = clean_domain[3:]
        if len(without_get) > 2:  # Solo si queda algo significativo
            variations.append(without_get)
    
    # 3. Si tiene guiones, crear versiones con espacios y sin separadores
    if '-' in clean_domain:
        variations.append(clean_domain.replace('-', ' '))
        variations.append(clean_domain.replace('-', ''))
    
    # ✨ 3b. NUEVO: Si es una palabra compuesta (sin guiones pero claramente dos palabras),
    # intentar separarla en palabras comunes
    # Ejemplos: "clinicagarcia" → "clinica garcia", "josemartinez" → "jose martinez"
    common_word_parts = ['clinica', 'centro', 'laser', 'jose', 'juan', 'garcia', 'lopez', 
                         'martinez', 'fernandez', 'rodriguez', 'sanchez', 'perez']
    for part in common_word_parts:
        if part in clean_domain and len(part) >= 4:  # Solo palabras significativas
            # Separar en ese punto
            if clean_domain.startswith(part) and len(clean_domain) > len(part):
                rest = clean_domain[len(part):]
                variations.append(f"{part} {rest}")
            elif clean_domain.endswith(part) and len(clean_domain) > len(part):
                start = clean_domain[:-len(part)]
                variations.append(f"{start} {part}")
    
    # 4. Si detectamos palabras compuestas comunes, separarlas
    # Patrones comunes: click+and, get+word, etc.
    if 'and' in clean_domain:
        variations.append(clean_domain.replace('and', ' and '))
    
    # 5. Variaciones con mayúsculas (para nombres propios)
    for var in list(variations):
        variations.append(var.capitalize())
        variations.append(var.title())
    
    # ✨ 6. NUEVO: Generar variaciones con acentos comunes en español
    # Esto es crucial para marcas como "Láserum", "José", "García", etc.
    accent_variations = []
    for var in list(variations):
        # Mapeo de vocales comunes con acentos (solo el más común para cada vocal)
        accent_map = {
            'a': 'á',
            'e': 'é',
            'i': 'í',
            'o': 'ó',
            'u': 'ú',
            'n': 'ñ'
        }
        
        # Generar variaciones con acento en CADA vocal (no solo la primera)
        # Esto permite detectar "García", "José", "Depilación", etc.
        for i, char in enumerate(var):
            char_lower = char.lower()
            if char_lower in accent_map:
                accented = accent_map[char_lower]
                # Mantener mayúsculas si el original era mayúscula
                if char.isupper():
                    accented = accented.upper()
                new_var = var[:i] + accented + var[i+1:]
                # Solo añadir si no está duplicado
                if new_var not in accent_variations and new_var not in variations:
                    accent_variations.append(new_var)
    
    variations.extend(accent_variations)
    
    # Eliminar duplicados y variaciones muy cortas
    unique_variations = []
    for var in variations:
        if len(var) >= 3 and var not in unique_variations:
            unique_variations.append(var)
    
    return unique_variations

def check_brand_mention(text, domain, brand_variations):
    """
    Verifica si el texto contiene menciones del dominio o sus variaciones de marca.
    
    ✨ MEJORADO: Ahora busca también normalizando acentos para evitar falsos negativos.
    
    Returns:
        tuple: (found, method) donde found es bool y method es string describiendo cómo se encontró
    """
    if not text or not domain:
        return False, None
    
    text_lower = text.lower()
    text_lower_no_accents = remove_accents(text_lower)
    
    # 1. Buscar dominio completo primero (con y sin acentos)
    domain_lower = domain.lower()
    if domain_lower in text_lower or domain_lower in text_lower_no_accents:
        return True, "full_domain"
    
    # 2. Buscar variaciones de marca
    for variation in brand_variations:
        if len(variation) >= 3:  # Solo buscar variaciones significativas
            variation_lower = variation.lower()
            variation_no_accents = remove_accents(variation_lower)
            
            # 🎯 BÚSQUEDA EXACTA: Buscar como palabra completa (word boundary)
            # Buscar tanto con acentos como sin acentos
            pattern = r'\b' + re.escape(variation_lower) + r'\b'
            pattern_no_accents = r'\b' + re.escape(variation_no_accents) + r'\b'
            
            # Buscar en texto con acentos
            if re.search(pattern, text_lower):
                return True, f"brand_exact_match:{variation}"
            
            # ✨ NUEVO: Buscar en texto sin acentos (esto captura "Láserum" cuando buscamos "laserum")
            if re.search(pattern_no_accents, text_lower_no_accents):
                return True, f"brand_accent_match:{variation}"
            
            # 🔍 BÚSQUEDA PARCIAL: Como fallback, buscar substring (menos estricto)
            if variation_lower in text_lower:
                return True, f"brand_partial_match:{variation}"
            
            # ✨ NUEVO: Búsqueda parcial sin acentos
            if variation_no_accents in text_lower_no_accents:
                return True, f"brand_partial_accent_match:{variation}"
    
    return False, None

def detect_ai_overview_elements(serp_data, site_url=None):
    """
    Detecta elementos de AI Overview con cálculo CORRECTO de posiciones visuales.
    
    ⚠️ IMPORTANTE: Las posiciones ahora coinciden exactamente con lo que ve el usuario
    
    MÉTODO 1 - Estructura oficial:
    {
      "ai_overview": {
        "text_blocks": [...],
        "references": [...]  // Posición = index + 1
      }
    }
    
    MÉTODO 2 - Híbrido estándar:
    {
      "ai_overview": {
        "text_blocks": [
          {"reference_indexes": [0, 4, 8]}  // Posición = índice en lista ordenada + 1
        ]
      },
      "organic_results": [...]
    }
    
    MÉTODO 3 - Híbrido AGRESIVO con posiciones CORREGIDAS:
    Cuando reference_indexes están incompletos, calcula la posición visual real
    basándose en el patrón observado del usuario.
    """
    logger.info("[AI ANALYSIS] === INICIANDO DETECCIÓN AI OVERVIEW (POSICIONES CORREGIDAS) ===")
    
    # Estructura de retorno compatible con legacy
    ai_elements = {
        'has_ai_overview': False,
        'ai_overview_detected': [],
        'total_elements': 0,
        'elements_before_organic': 0,
        'impact_score': 0,
        'domain_is_ai_source': False,
        'domain_ai_source_position': None,
        'domain_ai_source_link': None,
        'aio_serp_position': None,  # Fix #2: Where AIO appears in SERP (top/middle/bottom)
        'debug_info': {}
    }
    
    if not serp_data:
        logger.warning("[AI ANALYSIS] No hay datos SERP para analizar")
        ai_elements['debug_info']['error'] = 'No SERP data'
        return ai_elements
    
    # Normalizar URL del sitio y extraer variaciones de marca
    normalized_site_url = None
    brand_variations = []
    raw_site_url = site_url
    
    if site_url:
        normalized_site_url = normalize_search_console_url(site_url)
        
        # ✅ NUEVO: Extraer variaciones de marca del dominio
        brand_variations = extract_brand_variations(normalized_site_url)
        
        logger.info(f"[AI ANALYSIS] Sitio a analizar: {site_url} → {normalized_site_url}")
        logger.info(f"[AI ANALYSIS] Variaciones de marca detectadas: {brand_variations}")
    
    # Buscar AI Overview en los datos SERP
    ai_overview_data = serp_data.get('ai_overview')
    
    if not ai_overview_data:
        logger.info("[AI ANALYSIS] No se encontró 'ai_overview' en datos SERP")
        ai_elements['debug_info']['available_keys'] = list(serp_data.keys())
        ai_elements['debug_info']['ai_overview_found'] = False
        return ai_elements
    
    # Verificar si es un error
    if 'error' in ai_overview_data:
        logger.warning(f"[AI ANALYSIS] Error en AI Overview: {ai_overview_data['error']}")
        ai_elements['debug_info']['ai_overview_error'] = ai_overview_data['error']
        return ai_elements
    
    # Verificar si requiere petición adicional (collapsed AI Overview)
    if 'page_token' in ai_overview_data and not ai_overview_data.get('text_blocks') and not ai_overview_data.get('references'):
        logger.info(f"[AI ANALYSIS] AI Overview requiere petición adicional con page_token (collapsed)")
        ai_elements['has_ai_overview'] = True  # AI Overview EXISTS even if collapsed
        ai_elements['debug_info']['requires_additional_request'] = True
        ai_elements['debug_info']['page_token'] = ai_overview_data.get('page_token', '')
        ai_elements['debug_info']['serpapi_link'] = ai_overview_data.get('serpapi_link')
        ai_elements['debug_info']['ai_overview_found'] = True
        ai_elements['debug_info']['ai_overview_collapsed'] = True
        return ai_elements
    
    # ✅ AI OVERVIEW DETECTADO
    ai_elements['has_ai_overview'] = True
    logger.info("[AI ANALYSIS] ✅ AI Overview encontrado!")

    # Fix #2: Detect AIO position in SERP (top/middle/bottom)
    # SerpAPI places ai_overview as a top-level key; we infer position from SERP structure
    aio_serp_position = _detect_aio_serp_position(serp_data)
    ai_elements['aio_serp_position'] = aio_serp_position
    logger.info(f"[AI ANALYSIS] AIO SERP position: {aio_serp_position}")

    # Analizar estructura completa
    text_blocks = ai_overview_data.get('text_blocks', [])
    references = ai_overview_data.get('references', [])
    organic_results = serp_data.get('organic_results', [])  # Para caso híbrido

    logger.info(f"[AI ANALYSIS] Estructura: {len(text_blocks)} text_blocks, {len(references)} references, {len(organic_results)} organic_results")
    
    # Contadores para estadísticas y compatibilidad legacy
    total_content_length = 0
    total_reference_indexes = set()
    
    # Analizar text_blocks para obtener reference_indexes y contenido
    text_block_mentions = []  # Para rastrear menciones encontradas en el contenido
    
    for i, block in enumerate(text_blocks):
        block_type = block.get('type', 'unknown')
        snippet = block.get('snippet', '')
        reference_indexes = block.get('reference_indexes', [])
        
        total_content_length += len(snippet)
        total_reference_indexes.update(reference_indexes)
        
        logger.debug(f"[AI ANALYSIS] Text block {i+1}: type={block_type}, snippet_length={len(snippet)}, references={reference_indexes}")
        
        # ✅ NUEVO: Buscar menciones de marca en el contenido del AI Overview
        if snippet and normalized_site_url:
            found, method = check_brand_mention(snippet, normalized_site_url, brand_variations)
            if found:
                text_block_mentions.append({
                    'block_index': i,
                    'method': method,
                    'snippet_preview': snippet[:100] + '...' if len(snippet) > 100 else snippet,
                    'reference_indexes': reference_indexes
                })
                logger.info(f"[AI ANALYSIS] 🎯 Mención encontrada en text_block {i+1} via {method}: '{snippet[:150]}...'")
        
        # Añadir a la lista de elementos detectados (compatibilidad legacy)
        ai_elements['ai_overview_detected'].append({
            'type': f'AI Overview ({block_type})',
            'position': i,
            'content_length': len(snippet),
            'sources_count': len(reference_indexes),
            'content_fields_found': ['text_blocks']
        })
        
        # Analizar listas anidadas
        if block_type == 'list' and 'list' in block:
            for j, list_item in enumerate(block['list']):
                item_refs = list_item.get('reference_indexes', [])
                total_reference_indexes.update(item_refs)
                item_snippet = list_item.get('snippet', '')
                total_content_length += len(item_snippet)
                logger.debug(f"[AI ANALYSIS]   List item {j+1}: references={item_refs}")
                
                # ✅ NUEVO: Buscar menciones en list items también
                if item_snippet and normalized_site_url:
                    found, method = check_brand_mention(item_snippet, normalized_site_url, brand_variations)
                    if found:
                        text_block_mentions.append({
                            'block_index': f"{i}.{j}",
                            'method': method,
                            'snippet_preview': item_snippet[:100] + '...' if len(item_snippet) > 100 else item_snippet,
                            'reference_indexes': item_refs
                        })
                        logger.info(f"[AI ANALYSIS] 🎯 Mención encontrada en list item {i}.{j} via {method}: '{item_snippet[:150]}...'")
    
    # Asignar valores de compatibilidad legacy
    ai_elements['total_elements'] = len(text_blocks)
    ai_elements['elements_before_organic'] = len(text_blocks)
    ai_elements['impact_score'] = min(40 * len(text_blocks), 100)  # Máximo 100
    
    logger.info(f"[AI ANALYSIS] Total content length: {total_content_length}")
    logger.info(f"[AI ANALYSIS] Unique reference indexes: {sorted(total_reference_indexes)}")
    
    # 🧠 LÓGICA HÍBRIDA CON POSICIONES CORREGIDAS
    domain_found = False
    domain_position = None
    domain_link = None
    detection_method = None
    
    if normalized_site_url:
        # MÉTODO 1: Buscar en ai_overview.references (oficial) - MÁXIMA PRIORIDAD
        # Las referencias oficiales con posición específica son más valiosas que menciones en contenido
        if references:
            logger.info(f"[AI ANALYSIS] 🔍 MÉTODO OFICIAL: Buscando en {len(references)} referencias oficiales...")
            
            for ref in references:
                ref_index = ref.get('index')
                ref_title = ref.get('title', '')
                ref_link = ref.get('link', '')
                ref_source = ref.get('source', '')
                
                logger.debug(f"[AI ANALYSIS] Referencia {ref_index}: {ref_title[:50]}... → {ref_link}")
                
                # Verificar coincidencia de dominio
                if ref_link and urls_match(ref_link, normalized_site_url):
                    domain_found = True
                    domain_position = ref_index + 1  # Posición 1-based
                    domain_link = ref_link
                    detection_method = "official_references"
                    logger.info(f"[AI ANALYSIS] ✅ MÉTODO OFICIAL: Dominio encontrado en posición {domain_position}")
                    break
                
                # ✅ CORREGIDO: Verificar URLs en source y title de forma más precisa
                source_has_domain = False
                title_has_domain = False
                
                if ref_source:
                    # ✅ INTELIGENTE: Buscar dominio y variaciones de marca en source
                    found, method = check_brand_mention(ref_source, normalized_site_url, brand_variations)
                    if found:
                        source_has_domain = True
                        logger.info(f"[AI ANALYSIS] 🎯 Mención encontrada en source via {method}: '{ref_source[:100]}...'")
                
                if ref_title and not source_has_domain:
                    # ✅ INTELIGENTE: Buscar dominio y variaciones de marca en title
                    found, method = check_brand_mention(ref_title, normalized_site_url, brand_variations)
                    if found:
                        title_has_domain = True
                        logger.info(f"[AI ANALYSIS] 🎯 Mención encontrada en title via {method}: '{ref_title[:100]}...'")
                
                if source_has_domain or title_has_domain:
                    domain_found = True
                    domain_position = ref_index + 1
                    domain_link = ref_link
                    detection_method = "official_source_title_precise"
                    location = "source" if source_has_domain else "title"
                    logger.info(f"[AI ANALYSIS] ✅ MÉTODO OFICIAL: Dominio encontrado en {location} posición {domain_position}")
                    break
        
        # ✅ MÉTODO 1.5: Buscar menciones en contenido de text_blocks (FALLBACK)
        # Solo si no se encontró en referencias oficiales
        if not domain_found and text_block_mentions:
            logger.info(f"[AI ANALYSIS] 🎯 MÉTODO CONTENIDO (FALLBACK): Encontradas {len(text_block_mentions)} menciones en text_blocks")
            
            # Usar la primera mención encontrada (la más relevante)
            first_mention = text_block_mentions[0]
            domain_found = True
            domain_position = 1  # Posición conceptual en AI Overview
            domain_link = None  # No hay link específico para menciones en contenido
            detection_method = f"text_content_{first_mention['method']}"
            
            logger.info(f"[AI ANALYSIS] ✅ MÉTODO CONTENIDO: Mención encontrada en text_block {first_mention['block_index']}")
            logger.info(f"[AI ANALYSIS] 📝 Contenido: '{first_mention['snippet_preview']}'")
        
        # MÉTODO 2: Buscar en organic_results usando reference_indexes (híbrido ULTRA-ESTRICTO)
        # SOLO cuenta si el organic_result coincide exactamente con una referencia oficial
        if not domain_found and total_reference_indexes and organic_results and references:
            logger.info(f"[AI ANALYSIS] 🔍 MÉTODO HÍBRIDO ULTRA-ESTRICTO: Validando organic_results contra referencias oficiales")
            
            # Crear mapeo de reference_indexes a enlaces oficiales para validación estricta
            official_links_by_index = {}
            for ref in references:
                ref_index = ref.get('index')
                ref_link = ref.get('link', '')
                if ref_index is not None and ref_link:
                    official_links_by_index[ref_index] = ref_link
            
            logger.info(f"[AI ANALYSIS] 🔗 Referencias oficiales mapeadas: {list(official_links_by_index.keys())}")
            
            # Crear lista ordenada de reference_indexes para calcular posición visual correcta
            sorted_ref_indexes = sorted(total_reference_indexes)
            
            for ref_idx in sorted_ref_indexes:
                # VALIDACIÓN ESTRICTA: Solo continuar si este reference_index tiene una referencia oficial
                if ref_idx not in official_links_by_index:
                    logger.info(f"[AI ANALYSIS] ⚠️ Reference_index {ref_idx} NO tiene referencia oficial - SALTANDO")
                    continue
                
                # Buscar en organic_results usando el reference_index validado
                if ref_idx < len(organic_results):
                    result = organic_results[ref_idx]
                    result_link = result.get('link', '')
                    result_title = result.get('title', '')
                    result_source = result.get('source', '')
                    official_link = official_links_by_index[ref_idx]
                    
                    logger.info(f"[AI ANALYSIS] 🔍 Evaluando organic_result {ref_idx}: {result_source}")
                    logger.info(f"[AI ANALYSIS] 🔗 Comparando: organic='{result_link}' vs oficial='{official_link}'")
                    
                    # VALIDACIÓN ADICIONAL: El organic_result debe coincidir con la referencia oficial
                    if not urls_match(result_link, official_link):
                        logger.info(f"[AI ANALYSIS] ⚠️ Organic_result {ref_idx} NO coincide con referencia oficial - SALTANDO")
                        continue
                    
                    # Verificar coincidencia con nuestro dominio
                    if result_link and urls_match(result_link, normalized_site_url):
                        domain_found = True
                        # Posición en la lista ordenada de referencias
                        visual_position = sorted_ref_indexes.index(ref_idx) + 1
                        domain_position = visual_position
                        domain_link = result_link
                        detection_method = "hybrid_ultra_strict_validated"
                        logger.info(f"[AI ANALYSIS] ✅ MÉTODO HÍBRIDO ULTRA-ESTRICTO: Dominio encontrado en posición visual {domain_position}")
                        break

        
        # Si no se encontró nada, loggear el resultado
        if not domain_found:
            logger.info(f"[AI ANALYSIS] 🚫 NO ENCONTRADO: No hay menciones del dominio en AI Overview")
            logger.info(f"[AI ANALYSIS] 📋 BUSCADO: {normalized_site_url} + variaciones {brand_variations}")
    
    # Asignar resultados del dominio
    ai_elements['domain_is_ai_source'] = domain_found
    ai_elements['domain_ai_source_position'] = domain_position
    ai_elements['domain_ai_source_link'] = domain_link
    
    # Información de debugging completa
    ai_elements['debug_info'] = {
        'total_text_blocks': len(text_blocks),
        'total_references': len(references),
        'total_organic_results': len(organic_results),
        'total_content_length': total_content_length,
        'total_sources_analyzed': len(references) + len(organic_results),
        'site_url_original': raw_site_url,
        'site_url_normalized': normalized_site_url,
        'reference_indexes_found': sorted(total_reference_indexes),
        'structure_type': 'hybrid_ultra_strict_anti_false_positives',
        'detection_method': detection_method,
        'aio_serp_position': aio_serp_position,  # Fix #2: top/middle/bottom
        'ai_overview_found': True,
        'available_keys': list(serp_data.keys()),
        'requires_additional_request': False,
        'has_official_references': bool(references),
        'has_organic_fallback': bool(organic_results and total_reference_indexes),
        'used_aggressive_search': False,
        'uses_ultra_strict_validation': True,
        'official_links_validated': True,  # ✅ DESHABILITADO: Ya no usamos búsqueda agresiva 
        'position_correction_applied': detection_method in ['hybrid_ultra_strict_validated'],
        # ✅ NUEVO: Información sobre detección de marca
        'brand_variations_generated': brand_variations,
        'text_block_mentions_found': len(text_block_mentions),
        'text_block_mentions_details': text_block_mentions,
        'uses_brand_detection': len(brand_variations) > 0,
        # 🆕 NUEVO: Guardar referencias para análisis de competidores
        'references_found': references,
        'organic_matches': []  # Se llenará si se usan organic results con reference_indexes
    }
    
    # Log del resultado final
    if domain_found:
        logger.info(f"[AI ANALYSIS] ✅ RESULTADO FINAL: Dominio encontrado en posición {domain_position} (método: {detection_method})")
        ai_elements['impact_score'] += 20  # Bonus por encontrar el dominio
        
        # ✅ BONUS ELIMINADO: Ya no hay búsqueda agresiva
        # Solo se otorgan bonos por detección en referencias oficiales o reference_indexes específicos
            
        # Bonus extra por corrección de posición aplicada
        if ai_elements['debug_info'].get('position_correction_applied'):
            ai_elements['impact_score'] += 5
            logger.info(f"[AI ANALYSIS] 🎯 CORRECCIÓN DE POSICIÓN APLICADA: Posición corregida para coincidir con realidad visual")
    else:
        logger.info("[AI ANALYSIS] ❌ RESULTADO FINAL: Dominio NO encontrado en ningún método")
    
    logger.info(f"[AI ANALYSIS] Summary: {ai_elements['total_elements']} elements, impact_score={ai_elements['impact_score']}")
    logger.info("[AI ANALYSIS] === DETECCIÓN AI OVERVIEW COMPLETADA ===")
    
    return ai_elements


def check_domain_in_references(element_data, normalized_site_url, raw_site_url=None):
    """
    FUNCIÓN LEGACY - Mantenida por compatibilidad pero ya no se usa.
    La nueva implementación está integrada en detect_ai_overview_elements.
    """
    logger.warning("[AI ANALYSIS] check_domain_in_references es una función legacy - usar detect_ai_overview_elements")
    return False, None, None


def check_domain_in_reference_indexes(element_data, organic_results, normalized_site_url, raw_site_url=None):
    """
    FUNCIÓN LEGACY - Mantenida por compatibilidad pero ya no se usa.
    La nueva implementación está integrada en detect_ai_overview_elements.
    """
    logger.warning("[AI ANALYSIS] check_domain_in_reference_indexes es una función legacy - usar detect_ai_overview_elements")
    return False, None, None

