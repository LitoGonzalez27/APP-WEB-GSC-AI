#!/usr/bin/env python3
"""
Manual locale-fidelity runner for LLM Monitoring.

⚠️ WARNING: This script makes REAL API calls to all configured LLM
            providers. It costs real money per run. DO NOT run in CI.
            NOT placed under tests/ on purpose — avoid auto-discovery.

Purpose:
    Measure whether the LLM Monitoring system returns responses that
    are fitting for the target country. For each (language, country)
    pair, sends a small representative set of queries to all active
    providers, then scores the responses for locale fidelity:

      score = 100
            - 20 * (number of contamination markers found)
            + 10 * (number of local-TLD citations/URLs found)

    Contamination markers are things that should NOT appear for a
    given locale, e.g. "São Paulo" in a PT-PT response, "Ciudad de
    México" in an ES-ES response.

Usage:
    # All default locales, 3 queries each, all providers:
    python test_locale_fidelity.py

    # Single locale:
    python test_locale_fidelity.py --locale pt_PT

    # Single provider:
    python test_locale_fidelity.py --provider perplexity

    # Save raw JSON for later inspection:
    python test_locale_fidelity.py --output-json baseline.json

    # More queries per locale (slower, more accurate):
    python test_locale_fidelity.py --queries-per-locale 5

Environment:
    Requires the same env vars as the app (OPENAI_API_KEY,
    ANTHROPIC_API_KEY, GOOGLE_API_KEY, PERPLEXITY_API_KEY, and
    DATABASE_URL for pricing lookups).

Exit codes:
    0 — all tested locales scored ≥ 70 (passed)
    1 — some locale scored < 70 (human review required)
    2 — a provider crashed unexpectedly
"""

import argparse
import json
import logging
import os
import re
import sys
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# ── Representative queries per language ──────────────────────
# Each language has a handful of queries that explicitly or
# implicitly touch local market aspects (banks, telcos, energy,
# insurance, utilities).
TEST_QUERIES_BY_LANG: Dict[str, List[str]] = {
    'pt': [
        "Quais são os melhores bancos online para abrir conta?",
        "Compara as melhores operadoras de telemóvel.",
        "Quais são as melhores empresas de eletricidade verde?",
        "Onde posso comprar um carro elétrico ao melhor preço?",
        "Quais são os melhores seguros de saúde privados?",
    ],
    'es': [
        "¿Cuáles son los mejores bancos online para abrir cuenta?",
        "Compara las mejores compañías telefónicas.",
        "¿Cuáles son las mejores compañías de luz verde?",
        "¿Dónde puedo comprar un coche eléctrico al mejor precio?",
        "¿Cuáles son los mejores seguros de salud privados?",
    ],
    'en': [
        "What are the best online banks to open an account?",
        "Compare the best mobile phone carriers.",
        "Who are the best green energy providers?",
        "Where can I buy an electric car at the best price?",
        "What are the best private health insurance options?",
    ],
    'fr': [
        "Quelles sont les meilleures banques en ligne pour ouvrir un compte ?",
        "Compare les meilleurs opérateurs de téléphonie mobile.",
        "Quelles sont les meilleures offres d'électricité verte ?",
        "Où acheter une voiture électrique au meilleur prix ?",
        "Quelles sont les meilleures assurances santé privées ?",
    ],
    'de': [
        "Welche sind die besten Online-Banken zur Kontoeröffnung?",
        "Vergleiche die besten Mobilfunkanbieter.",
        "Welche sind die besten Ökostrom-Anbieter?",
        "Wo kann ich ein Elektroauto zum besten Preis kaufen?",
        "Welche sind die besten privaten Krankenversicherungen?",
    ],
    'it': [
        "Quali sono le migliori banche online per aprire un conto?",
        "Confronta i migliori operatori di telefonia mobile.",
        "Quali sono i migliori fornitori di energia verde?",
        "Dove posso comprare un'auto elettrica al miglior prezzo?",
        "Quali sono le migliori assicurazioni sanitarie private?",
    ],
}


# ── Default test matrix (locale pairs) ─────────────────────────
# Includes the most common pairs. Override with --locale flag.
DEFAULT_LOCALES: List[Tuple[str, str]] = [
    ('pt', 'PT'),  # European Portuguese — must NOT sound Brazilian
    ('es', 'ES'),  # European Spanish — must NOT sound Mexican/Argentinian
    ('en', 'US'),  # American English
    ('en', 'GB'),  # British English
    ('fr', 'FR'),
    ('de', 'DE'),
    ('it', 'IT'),
]


# ── Cross-contamination markers per (lang, country) ────────────
# Strings that should NOT appear in responses for that locale.
CONTAMINATION_MARKERS: Dict[Tuple[str, str], List[str]] = {
    ('pt', 'PT'): [
        'São Paulo', 'Rio de Janeiro', 'Brasília', 'R$',
        'brasileiro', 'brasileira', 'Bradesco', 'Itaú',
        'TIM Brasil', 'Caixa Econômica Federal',
        'Mercado Livre',  # BR version
    ],
    ('es', 'ES'): [
        'Ciudad de México', 'CDMX', 'Buenos Aires', 'Santiago de Chile',
        'peso mexicano', 'peso argentino', 'Banorte',
        'MercadoLibre', 'Bancolombia',
    ],
    ('en', 'US'): [
        '£', 'pound sterling', 'Tesco', 'Sainsbury',
        'BT Group', 'HSBC UK',
    ],
    ('en', 'GB'): [
        '$', 'dollar', 'Walmart', 'Target Corporation',
        'Chase Bank', 'Verizon',
    ],
    ('fr', 'FR'): [
        'Québec', 'Montréal', 'dollar canadien', 'Ontario',
    ],
    ('de', 'DE'): [
        'Österreich', 'Schweizer Franken', 'Zürich',
    ],
    ('it', 'IT'): [
        'Svizzera italiana', 'Ticino', 'Canton',
    ],
}


# ── Local TLD scoring ──────────────────────────────────────────
# Maps (lang, country) → regex pattern for local TLD URL citations.
LOCAL_TLD_PATTERNS: Dict[Tuple[str, str], str] = {
    ('pt', 'PT'): r'\.pt\b',
    ('es', 'ES'): r'\.es\b',
    ('en', 'US'): r'\.(com|us|gov)\b',
    ('en', 'GB'): r'\.(co\.uk|gov\.uk|uk)\b',
    ('fr', 'FR'): r'\.fr\b',
    ('de', 'DE'): r'\.de\b',
    ('it', 'IT'): r'\.it\b',
}


# ═══════════════════════════════════════════════════════════════


def score_response(content: str, locale_key: Tuple[str, str]) -> Dict:
    """
    Compute a fidelity score for one response.

    Returns a dict with:
        score: int in [0, 100]
        contamination_hits: list of markers found
        local_tld_hits: int count of local TLD citations
    """
    if not content:
        return {'score': 0, 'contamination_hits': [], 'local_tld_hits': 0}

    markers = CONTAMINATION_MARKERS.get(locale_key, [])
    contamination_hits: List[str] = []
    lower = content.lower()
    for marker in markers:
        if marker.lower() in lower:
            contamination_hits.append(marker)

    tld_pattern = LOCAL_TLD_PATTERNS.get(locale_key)
    local_tld_hits = 0
    if tld_pattern:
        local_tld_hits = len(re.findall(tld_pattern, content, re.IGNORECASE))

    score = 100 - (20 * len(contamination_hits)) + (10 * local_tld_hits)
    score = max(0, min(100, score))

    return {
        'score': score,
        'contamination_hits': contamination_hits,
        'local_tld_hits': local_tld_hits,
    }


def run_fidelity_test(
    providers: Dict,
    locales: List[Tuple[str, str]],
    queries_per_locale: int = 3,
) -> Dict:
    """
    Run the fidelity test across all providers × locales × queries.

    Returns a nested dict:
        {
          'provider_name': {
            'pt-PT': {
              'avg_score': 87,
              'per_query': [
                {'query': ..., 'score': ..., 'contamination_hits': [...],
                 'local_tld_hits': N, 'prompt_strategy': 'system_user_geo'},
                ...
              ]
            },
            ...
          },
          ...
        }
    """
    from services.llm_providers.locale_helpers import create_locale_context

    results: Dict = {}
    for provider_name, provider in providers.items():
        results[provider_name] = {}
        for lang, country in locales:
            locale_ctx = create_locale_context(lang, country)
            key = f"{lang}-{country}"
            queries = TEST_QUERIES_BY_LANG.get(lang, [])[:queries_per_locale]

            if not queries:
                print(f"[{provider_name}][{key}] No test queries for language '{lang}', skipping.")
                results[provider_name][key] = {
                    'avg_score': None,
                    'per_query': [],
                    'note': f'no queries for lang={lang}',
                }
                continue

            per_query: List[Dict] = []
            for q in queries:
                print(f"[{provider_name}][{key}] {q[:60]}...")
                try:
                    r = provider.execute_query(q, locale=locale_ctx)
                except Exception as e:
                    print(f"   ❌ EXCEPTION: {e}")
                    per_query.append({'query': q, 'error': str(e)})
                    continue

                if not r.get('success'):
                    err = r.get('error', 'Unknown error')
                    print(f"   ⚠️ FAILED: {err}")
                    per_query.append({'query': q, 'error': err})
                    continue

                content = r.get('content', '')
                score_info = score_response(content, (lang, country))
                strategy = r.get('prompt_strategy', 'n/a')
                per_query.append({
                    'query': q,
                    'score': score_info['score'],
                    'contamination_hits': score_info['contamination_hits'],
                    'local_tld_hits': score_info['local_tld_hits'],
                    'prompt_strategy': strategy,
                    'first_200_chars': content[:200].replace('\n', ' '),
                })
                status = "✅" if not score_info['contamination_hits'] else "⚠️"
                print(
                    f"   {status} score={score_info['score']} "
                    f"contam={len(score_info['contamination_hits'])} "
                    f"tld={score_info['local_tld_hits']} "
                    f"strategy={strategy}"
                )

            valid_scores = [s['score'] for s in per_query if 'score' in s]
            avg = (
                round(sum(valid_scores) / len(valid_scores), 1)
                if valid_scores else None
            )
            results[provider_name][key] = {
                'avg_score': avg,
                'per_query': per_query,
            }
    return results


def print_summary(results: Dict) -> int:
    """
    Print a compact summary table and return an exit code.

    Returns:
        0 if all locales scored ≥ 70
        1 if some locale scored < 70
    """
    print("\n" + "=" * 70)
    print("FIDELITY SUMMARY")
    print("=" * 70)
    worst = 100
    some_data = False
    for provider_name, per_locale in results.items():
        print(f"\n{provider_name}:")
        for key, data in per_locale.items():
            avg = data.get('avg_score')
            if avg is None:
                note = data.get('note', 'no data')
                print(f"  {key}: — ({note})")
                continue
            some_data = True
            flag = "✅" if avg >= 70 else "⚠️"
            print(f"  {key}: avg_score={avg}/100 {flag}")
            if avg < worst:
                worst = avg

    print("\n" + "=" * 70)
    if not some_data:
        print("⚠️ No fidelity data collected.")
        return 1
    if worst >= 70:
        print(f"✅ PASSED — worst locale scored {worst}/100 (≥70)")
        return 0
    else:
        print(f"⚠️ REVIEW — worst locale scored {worst}/100 (<70)")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--locale', help='e.g. pt_PT, es_ES, en_US')
    ap.add_argument(
        '--provider',
        choices=['openai', 'anthropic', 'google', 'perplexity'],
        help='Limit to a single provider',
    )
    ap.add_argument(
        '--queries-per-locale', type=int, default=3,
        help='Number of queries to test per locale (default 3)',
    )
    ap.add_argument(
        '--output-json',
        help='Write full results as JSON to this path',
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s - %(message)s',
    )

    # Ensure DATABASE_URL is set (needed by pricing lookups in providers)
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL env var is required (providers look up pricing in DB)")
        return 2

    # Build providers. validate_connections=True is intentional: we want
    # to fail fast if an API key is missing/invalid rather than producing
    # misleading fidelity data.
    try:
        from services.llm_providers import LLMProviderFactory
        all_providers = LLMProviderFactory.create_all_providers(
            validate_connections=True
        )
    except Exception as e:
        print(f"❌ Failed to build providers: {e}")
        return 2

    if not all_providers:
        print("❌ No providers available (check API keys)")
        return 2

    # Filter providers if requested
    if args.provider:
        if args.provider not in all_providers:
            print(f"❌ Provider '{args.provider}' not available. "
                  f"Available: {list(all_providers.keys())}")
            return 2
        all_providers = {args.provider: all_providers[args.provider]}

    # Filter locales if requested
    test_locales = DEFAULT_LOCALES
    if args.locale:
        try:
            lang, country = args.locale.split('_')
            test_locales = [(lang.lower(), country.upper())]
        except ValueError:
            print(f"❌ --locale must be in the format LANG_COUNTRY, e.g. pt_PT")
            return 2

    print(f"🔍 Running fidelity test:")
    print(f"   providers: {list(all_providers.keys())}")
    print(f"   locales: {test_locales}")
    print(f"   queries per locale: {args.queries_per_locale}")
    print()

    try:
        results = run_fidelity_test(
            all_providers, test_locales,
            queries_per_locale=args.queries_per_locale,
        )
    except Exception as e:
        logger.error(f"❌ Unexpected failure running fidelity test: {e}", exc_info=True)
        return 2

    exit_code = print_summary(results)

    if args.output_json:
        try:
            with open(args.output_json, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n📁 Full results written to {args.output_json}")
        except Exception as e:
            print(f"⚠️ Could not write JSON output: {e}")

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
