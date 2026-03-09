"""
AI Overview Recommendations Service
====================================
Fetches competitor page content via Jina.ai Reader API, builds a structured
prompt, sends it to Gemini 3 Flash, and returns actionable SEO recommendations
for appearing (or improving position) in Google AI Overview.

Dependencies:
- requests (already in requirements.txt)
- google.generativeai via GoogleProvider (existing)
- concurrent.futures (stdlib)
"""

import os
import logging
import time
import json
import hashlib
from typing import Dict, List, Optional, Any
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  In-memory cache (LRU, TTL-based)
# ──────────────────────────────────────────────

_RECOMMENDATIONS_CACHE: OrderedDict = OrderedDict()
_CACHE_MAX = 100
_CACHE_TTL = int(os.getenv("AIO_RECS_CACHE_TTL", "86400"))  # 24h default


def _cache_key(keyword: str, user_domain: str) -> str:
    """Generate deterministic cache key from keyword + domain."""
    raw = f"{keyword.lower().strip()}:{user_domain.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(keyword: str, user_domain: str) -> Optional[Dict]:
    """Return cached recommendations if still fresh, else None."""
    key = _cache_key(keyword, user_domain)
    entry = _RECOMMENDATIONS_CACHE.get(key)
    if entry and (time.time() - entry['timestamp']) < _CACHE_TTL:
        logger.info(f"✅ Cache hit for recommendations: {keyword}")
        _RECOMMENDATIONS_CACHE.move_to_end(key)
        return entry['data']
    elif entry:
        del _RECOMMENDATIONS_CACHE[key]
    return None


def _set_cached(keyword: str, user_domain: str, data: Dict) -> None:
    """Store recommendations in cache with LRU eviction."""
    key = _cache_key(keyword, user_domain)
    _RECOMMENDATIONS_CACHE[key] = {
        'timestamp': time.time(),
        'data': data
    }
    _RECOMMENDATIONS_CACHE.move_to_end(key)
    while len(_RECOMMENDATIONS_CACHE) > _CACHE_MAX:
        _RECOMMENDATIONS_CACHE.popitem(last=False)


# ──────────────────────────────────────────────
#  Jina.ai Reader — content fetching
# ──────────────────────────────────────────────

JINA_READER_BASE = "https://r.jina.ai/"
CONTENT_MAX_CHARS = 3000


def _truncate_at_word(text: str, max_chars: int) -> str:
    """Truncate text at the nearest word boundary."""
    if not text or len(text) <= max_chars:
        return text or ''
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + '...'


def fetch_page_content(url: str, timeout: int = 20) -> Dict[str, Any]:
    """
    Fetch a single page's content via Jina.ai Reader API.

    Returns:
        {success, url, title, content, description, error}
    """
    jina_key = os.getenv('JINA_API_KEY', '')
    if not jina_key:
        logger.warning("⚠️ JINA_API_KEY not configured — cannot fetch page content")
        return {
            'success': False,
            'url': url,
            'title': '',
            'content': '',
            'description': '',
            'error': 'JINA_API_KEY not configured'
        }

    try:
        headers = {
            'Authorization': f'Bearer {jina_key}',
            'Accept': 'application/json',
            'x-remove-selector': 'nav,footer,header,.sidebar,.menu,.cookie,.cookies,.popup,.modal,.banner',
            'x-no-cache': 'true'
        }

        target_url = f"{JINA_READER_BASE}{url}"
        logger.info(f"📄 Fetching via Jina: {url[:80]}...")

        response = requests.get(target_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        data = response.json()

        raw_content = data.get('content', '') or data.get('text', '') or ''
        title = data.get('title', '') or ''
        description = data.get('description', '') or ''

        content = _truncate_at_word(raw_content, CONTENT_MAX_CHARS)

        logger.info(f"✅ Fetched: {title[:60]} ({len(raw_content)} chars → {len(content)} truncated)")

        return {
            'success': True,
            'url': url,
            'title': title,
            'content': content,
            'description': description,
            'error': None
        }

    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Timeout fetching {url}")
        return {'success': False, 'url': url, 'title': '', 'content': '', 'description': '', 'error': f'Timeout after {timeout}s'}

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 'unknown'
        logger.warning(f"❌ HTTP {status} fetching {url}: {e}")
        return {'success': False, 'url': url, 'title': '', 'content': '', 'description': '', 'error': f'HTTP {status}'}

    except Exception as e:
        logger.error(f"❌ Error fetching {url}: {e}", exc_info=True)
        return {'success': False, 'url': url, 'title': '', 'content': '', 'description': '', 'error': str(e)}


def fetch_multiple_pages(urls: List[str], max_pages: int = 4) -> List[Dict]:
    """
    Fetch content for up to max_pages URLs in parallel.
    Each result carries its own success flag.
    """
    urls_to_fetch = urls[:max_pages]

    if not urls_to_fetch:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=min(len(urls_to_fetch), 4)) as executor:
        future_to_url = {
            executor.submit(fetch_page_content, url): url
            for url in urls_to_fetch
        }
        for future in as_completed(future_to_url):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                url = future_to_url[future]
                logger.error(f"❌ Thread error for {url}: {e}")
                results.append({
                    'success': False, 'url': url, 'title': '', 'content': '',
                    'description': '', 'error': str(e)
                })

    # Sort results to maintain original URL order
    url_order = {url: i for i, url in enumerate(urls_to_fetch)}
    results.sort(key=lambda r: url_order.get(r.get('url', ''), 999))

    return results


# ──────────────────────────────────────────────
#  Gemini prompt construction
# ──────────────────────────────────────────────

def build_recommendation_prompt(
    keyword: str,
    aio_content: str,
    cited_pages: List[Dict],
    user_page: Optional[Dict],
    user_domain: str,
    organic_position: Optional[int]
) -> str:
    """
    Build the structured prompt for Gemini to generate SEO recommendations.
    """
    successful_pages = [p for p in cited_pages if p.get('success')]
    failed_pages = [p for p in cited_pages if not p.get('success')]

    parts = []

    # ── System role & context ──
    parts.append(f"""You are an expert SEO analyst specializing in Google AI Overview (AIO) optimization.

TASK: Analyze why certain pages are cited in Google's AI Overview for the keyword "{keyword}" and provide specific, actionable recommendations for the domain "{user_domain}" to appear in (or improve position in) the AI Overview.

CONTEXT:
- Target keyword: "{keyword}"
- User's domain: {user_domain}
- User's organic position: {organic_position if organic_position else 'Unknown'}
- Pages cited in AI Overview: {len(cited_pages)} total ({len(successful_pages)} analyzed, {len(failed_pages)} could not be fetched)
""")

    # ── AI Overview content ──
    if aio_content:
        truncated_aio = aio_content[:2000]
        parts.append(f"""
═══ AI OVERVIEW CONTENT (what Google displays to users) ═══
{truncated_aio}
{'[...truncated]' if len(aio_content) > 2000 else ''}
═══════════════════════════════════════════════════════════
""")

    # ── Cited sources ──
    for i, page in enumerate(cited_pages):
        if page.get('success') and page.get('content'):
            parts.append(f"""
─── CITED SOURCE #{i+1} ───
Title: {page.get('title', 'Unknown')}
URL: {page.get('url', '')}
Description: {page.get('description', '')}
Content:
{page.get('content', '')}
───────────────────────
""")
        else:
            parts.append(f"""
─── CITED SOURCE #{i+1} ───
URL: {page.get('url', '')}
Status: Could not fetch — {page.get('error', 'unknown error')}
───────────────────────
""")

    # ── User's page ──
    if user_page and user_page.get('success') and user_page.get('content'):
        parts.append(f"""
═══ USER'S PAGE ({user_domain}) ═══
Title: {user_page.get('title', 'Unknown')}
URL: {user_page.get('url', '')}
Description: {user_page.get('description', '')}
Content:
{user_page.get('content', '')}
═══════════════════════════════════
""")
    else:
        parts.append(f"""
═══ USER'S PAGE ({user_domain}) ═══
Status: Not available for analysis.
═══════════════════════════════════
""")

    # ── Instructions ──
    parts.append("""
ANALYSIS INSTRUCTIONS:
1. Identify PATTERNS in cited sources — what do they have in common? (content depth, structure, data, authority signals, E-E-A-T)
2. Identify what makes these pages suitable for AI Overview citation (direct answers, structured data, lists, statistics, expert language, freshness)
3. If user's page is available, compare it with cited sources — identify specific gaps.
4. Provide 5-7 specific, actionable recommendations ranked by expected impact.

RESPOND ONLY WITH VALID JSON (no markdown fences, no explanation outside JSON):
{
  "summary": "A 2-3 sentence executive summary explaining why the user doesn't appear in AIO and the single most important action to take.",
  "cited_sources_analysis": "Brief analysis of what the cited sources have in common (2-3 sentences).",
  "recommendations": [
    {
      "title": "Short title (max 10 words)",
      "description": "Detailed, actionable explanation — be specific to this keyword. Reference actual content from cited pages. Explain what to do AND why it helps for AIO.",
      "priority": "high|medium|low",
      "category": "content|structure|authority|technical"
    }
  ]
}

RULES:
- Be EXTREMELY specific to this keyword — no generic SEO advice like "improve page speed".
- Reference actual content/topics from the cited pages when explaining what works.
- Recommendations must be things the user can DO within their content/site.
- "high" = likely to directly affect AIO appearance, "medium" = supportive, "low" = nice-to-have.
- Categories: "content" (topic coverage, depth, answers), "structure" (formatting, headings, lists, tables), "authority" (E-E-A-T, citations, credentials, data sources), "technical" (schema markup, structured data).
- Order recommendations from highest to lowest priority.
""")

    return "\n".join(parts)


# ──────────────────────────────────────────────
#  Main orchestrator
# ──────────────────────────────────────────────

def get_ai_recommendations(
    keyword: str,
    user_domain: str,
    cited_urls: List[str],
    aio_content: str,
    user_url: Optional[str] = None,
    organic_position: Optional[int] = None
) -> Dict[str, Any]:
    """
    Main orchestrator for AI recommendations.

    1. Check cache
    2. Fetch cited pages via Jina (max 4)
    3. Fetch user's page via Jina (if URL provided)
    4. Build prompt
    5. Call Gemini via GoogleProvider
    6. Parse response
    7. Cache and return
    """
    start_time = time.time()

    # ── 1. Cache check ──
    cached = _get_cached(keyword, user_domain)
    if cached:
        cached['cached'] = True
        return cached

    # ── 2. Fetch cited pages ──
    logger.info(f"🔍 Generating AI recommendations for: '{keyword}' ({user_domain})")
    logger.info(f"   Cited URLs to analyze: {len(cited_urls)}")

    cited_pages = []
    if cited_urls:
        cited_pages = fetch_multiple_pages(cited_urls, max_pages=4)
        successful = sum(1 for p in cited_pages if p.get('success'))
        logger.info(f"   Pages fetched successfully: {successful}/{len(cited_pages)}")

    # ── 3. Fetch user's page ──
    user_page = None
    if user_url:
        logger.info(f"   Fetching user's page: {user_url[:80]}")
        user_page = fetch_page_content(user_url)
    else:
        logger.info("   No user URL provided — skipping user page fetch")

    # ── 4. Build prompt ──
    prompt = build_recommendation_prompt(
        keyword=keyword,
        aio_content=aio_content,
        cited_pages=cited_pages,
        user_page=user_page,
        user_domain=user_domain,
        organic_position=organic_position
    )

    prompt_length = len(prompt)
    logger.info(f"   Prompt built: {prompt_length} chars (~{int(prompt_length / 4)} tokens est.)")

    # ── 5. Call Gemini ──
    try:
        google_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
        if not google_key:
            return {
                'success': False,
                'error': 'Google API key not configured',
                'recommendations': [],
                'summary': '',
                'cached': False
            }

        from services.llm_providers.google_provider import GoogleProvider
        provider = GoogleProvider(api_key=google_key, model='gemini-3-flash-preview')

        logger.info(f"   Sending to Gemini 3 Flash...")
        llm_result = provider.execute_query(prompt)

        if not llm_result.get('success'):
            error_msg = llm_result.get('error', 'Unknown Gemini error')
            logger.error(f"❌ Gemini call failed: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'recommendations': [],
                'summary': '',
                'cached': False
            }

        raw_content = llm_result.get('content', '')
        tokens_used = llm_result.get('tokens', 0)
        cost_usd = llm_result.get('cost_usd', 0)

        logger.info(f"   Gemini response: {tokens_used} tokens, ${cost_usd:.6f}")

    except Exception as e:
        logger.error(f"❌ Error calling Gemini: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'LLM error: {str(e)}',
            'recommendations': [],
            'summary': '',
            'cached': False
        }

    # ── 6. Parse response ──
    parsed = _parse_gemini_response(raw_content)

    # ── 7. Build result & cache ──
    elapsed = round(time.time() - start_time, 2)

    result = {
        'success': True,
        'recommendations': parsed.get('recommendations', []),
        'summary': parsed.get('summary', ''),
        'cited_sources_analysis': parsed.get('cited_sources_analysis', ''),
        'cited_pages_analyzed': sum(1 for p in cited_pages if p.get('success')),
        'user_page_analyzed': bool(user_page and user_page.get('success')),
        'tokens_used': tokens_used,
        'cost_usd': cost_usd,
        'elapsed_seconds': elapsed,
        'cached': False,
        'error': None
    }

    _set_cached(keyword, user_domain, result)
    logger.info(f"✅ AI recommendations generated in {elapsed}s for '{keyword}'")

    return result


def _parse_gemini_response(raw_content: str) -> Dict:
    """
    Parse Gemini's JSON response. Falls back gracefully if JSON is malformed.
    """
    if not raw_content:
        return {'summary': 'No response from AI', 'recommendations': []}

    # Strip markdown code fences if present
    cleaned = raw_content.strip()
    if cleaned.startswith('```'):
        # Remove ```json ... ``` wrapper
        lines = cleaned.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines)

    try:
        parsed = json.loads(cleaned)

        # Validate structure
        if not isinstance(parsed, dict):
            raise ValueError("Response is not a JSON object")

        recommendations = parsed.get('recommendations', [])
        if not isinstance(recommendations, list):
            recommendations = []

        # Validate each recommendation
        valid_recs = []
        for rec in recommendations:
            if isinstance(rec, dict) and rec.get('title') and rec.get('description'):
                valid_recs.append({
                    'title': str(rec.get('title', '')),
                    'description': str(rec.get('description', '')),
                    'priority': str(rec.get('priority', 'medium')).lower(),
                    'category': str(rec.get('category', 'content')).lower()
                })

        return {
            'summary': str(parsed.get('summary', '')),
            'cited_sources_analysis': str(parsed.get('cited_sources_analysis', '')),
            'recommendations': valid_recs
        }

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"⚠️ Could not parse Gemini JSON response: {e}")
        logger.debug(f"   Raw content (first 500 chars): {raw_content[:500]}")

        # Fallback: wrap raw text as summary
        return {
            'summary': raw_content[:500],
            'cited_sources_analysis': '',
            'recommendations': []
        }
