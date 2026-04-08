"""
Locale helpers for LLM Monitoring.

Central module that encapsulates how a project's (language, country) pair is
translated into provider-specific locale instructions and geo parameters.

This module is the single source of truth for:
- LANGUAGE_NAMES / COUNTRY_NAMES (moved here from llm_monitoring_service.py)
- LocaleContext: immutable dataclass passed from the service to each provider
- Per-language system-prompt templates, written in the target language
- Factory function with safe fallbacks

Providers use this to build native locale mechanisms:
- OpenAI / Anthropic / Perplexity: system message in target language
- Perplexity additionally: web_search_options.user_location={country}
- Google Gemini: prepended [SYSTEM INSTRUCTION] block

The goal is to make LLM responses as faithful as possible to what a user
physically located in the target country would receive when asking the same
question in the native language.

Multi-language by design: works for ANY (language, country) combination in
LANGUAGE_NAMES / COUNTRY_NAMES. Languages without a dedicated template fall
back to a generic English template with {language_name} injected — still
correct, never fails.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================
# LANGUAGE AND COUNTRY REGISTRIES
# (moved from llm_monitoring_service.py for reuse; still re-exported
#  from there for backward compatibility with any importer.)
# ============================================================

LANGUAGE_NAMES: Dict[str, str] = {
    'es': 'Spanish',
    'en': 'English',
    'it': 'Italian',
    'fr': 'French',
    'de': 'German',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'sv': 'Swedish',
    'no': 'Norwegian',
    'da': 'Danish',
    'fi': 'Finnish',
    'pl': 'Polish',
    'cs': 'Czech',
    'el': 'Greek',
    'ro': 'Romanian',
    'hu': 'Hungarian',
    'tr': 'Turkish',
    'he': 'Hebrew',
    'ar': 'Arabic',
    'af': 'Afrikaans',
    'hi': 'Hindi',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'ko': 'Korean',
    'id': 'Indonesian',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'tl': 'Filipino',
    'ms': 'Malay',
}

COUNTRY_NAMES: Dict[str, str] = {
    'ES': 'Spain',
    'US': 'United States',
    'GB': 'United Kingdom',
    'FR': 'France',
    'DE': 'Germany',
    'IT': 'Italy',
    'PT': 'Portugal',
    'MX': 'Mexico',
    'AR': 'Argentina',
    'CO': 'Colombia',
    'CL': 'Chile',
    'PE': 'Peru',
    'BR': 'Brazil',
    'CA': 'Canada',
    'AU': 'Australia',
    'NZ': 'New Zealand',
    'IN': 'India',
    'JP': 'Japan',
    'CN': 'China',
    'KR': 'South Korea',
    'NL': 'Netherlands',
    'BE': 'Belgium',
    'CH': 'Switzerland',
    'AT': 'Austria',
    'SE': 'Sweden',
    'NO': 'Norway',
    'DK': 'Denmark',
    'FI': 'Finland',
    'PL': 'Poland',
    'CZ': 'Czech Republic',
    'IE': 'Ireland',
    'GR': 'Greece',
    'RO': 'Romania',
    'HU': 'Hungary',
    'TR': 'Turkey',
    'IL': 'Israel',
    'AE': 'United Arab Emirates',
    'SA': 'Saudi Arabia',
    'ZA': 'South Africa',
    'SG': 'Singapore',
    'ID': 'Indonesia',
    'TH': 'Thailand',
    'VN': 'Vietnam',
    'PH': 'Philippines',
}


# Country names localized per target language. Used when building the
# system instruction so the country name appears in the same language as
# the rest of the prompt (es: "España", not "Spain"; de: "Deutschland",
# not "Germany"). Falls back to COUNTRY_NAMES (English) if not set.
COUNTRY_NAMES_LOCALIZED: Dict[str, Dict[str, str]] = {
    'es': {
        'ES': 'España', 'US': 'Estados Unidos', 'GB': 'Reino Unido',
        'FR': 'Francia', 'DE': 'Alemania', 'IT': 'Italia', 'PT': 'Portugal',
        'MX': 'México', 'AR': 'Argentina', 'CO': 'Colombia', 'CL': 'Chile',
        'PE': 'Perú', 'BR': 'Brasil', 'CA': 'Canadá', 'NL': 'Países Bajos',
        'BE': 'Bélgica', 'CH': 'Suiza', 'AT': 'Austria', 'SE': 'Suecia',
        'NO': 'Noruega', 'DK': 'Dinamarca', 'FI': 'Finlandia', 'PL': 'Polonia',
        'IE': 'Irlanda', 'GR': 'Grecia', 'JP': 'Japón', 'CN': 'China',
        'KR': 'Corea del Sur',
    },
    'pt': {
        'PT': 'Portugal', 'BR': 'Brasil', 'ES': 'Espanha',
        'US': 'Estados Unidos', 'GB': 'Reino Unido', 'FR': 'França',
        'DE': 'Alemanha', 'IT': 'Itália', 'MX': 'México', 'CA': 'Canadá',
        'NL': 'Países Baixos', 'BE': 'Bélgica', 'CH': 'Suíça', 'AT': 'Áustria',
        'SE': 'Suécia', 'NO': 'Noruega', 'DK': 'Dinamarca', 'FI': 'Finlândia',
        'PL': 'Polónia', 'IE': 'Irlanda', 'GR': 'Grécia', 'JP': 'Japão',
        'CN': 'China', 'KR': 'Coreia do Sul',
    },
    'fr': {
        'FR': 'France', 'CA': 'Canada', 'BE': 'Belgique', 'CH': 'Suisse',
        'ES': 'Espagne', 'PT': 'Portugal', 'DE': 'Allemagne', 'IT': 'Italie',
        'US': 'États-Unis', 'GB': 'Royaume-Uni', 'NL': 'Pays-Bas',
        'AT': 'Autriche', 'SE': 'Suède', 'NO': 'Norvège', 'DK': 'Danemark',
        'FI': 'Finlande', 'PL': 'Pologne', 'IE': 'Irlande', 'GR': 'Grèce',
        'BR': 'Brésil', 'MX': 'Mexique', 'JP': 'Japon', 'KR': 'Corée du Sud',
    },
    'de': {
        'DE': 'Deutschland', 'AT': 'Österreich', 'CH': 'Schweiz',
        'ES': 'Spanien', 'PT': 'Portugal', 'FR': 'Frankreich', 'IT': 'Italien',
        'US': 'USA', 'GB': 'Vereinigtes Königreich', 'NL': 'Niederlande',
        'BE': 'Belgien', 'SE': 'Schweden', 'NO': 'Norwegen', 'DK': 'Dänemark',
        'FI': 'Finnland', 'PL': 'Polen', 'IE': 'Irland', 'GR': 'Griechenland',
        'BR': 'Brasilien', 'MX': 'Mexiko', 'JP': 'Japan', 'CN': 'China',
        'KR': 'Südkorea',
    },
    'it': {
        'IT': 'Italia', 'CH': 'Svizzera', 'ES': 'Spagna', 'PT': 'Portogallo',
        'FR': 'Francia', 'DE': 'Germania', 'US': 'Stati Uniti',
        'GB': 'Regno Unito', 'NL': 'Paesi Bassi', 'BE': 'Belgio',
        'AT': 'Austria', 'SE': 'Svezia', 'NO': 'Norvegia', 'DK': 'Danimarca',
        'FI': 'Finlandia', 'PL': 'Polonia', 'IE': 'Irlanda', 'GR': 'Grecia',
        'BR': 'Brasile', 'MX': 'Messico', 'JP': 'Giappone',
    },
    'nl': {
        'NL': 'Nederland', 'BE': 'België', 'ES': 'Spanje', 'PT': 'Portugal',
        'FR': 'Frankrijk', 'DE': 'Duitsland', 'IT': 'Italië',
        'US': 'Verenigde Staten', 'GB': 'Verenigd Koninkrijk',
    },
    'pl': {
        'PL': 'Polska', 'DE': 'Niemcy', 'FR': 'Francja', 'ES': 'Hiszpania',
        'PT': 'Portugalia', 'IT': 'Włochy', 'US': 'Stany Zjednoczone',
        'GB': 'Wielka Brytania',
    },
    'sv': {
        'SE': 'Sverige', 'NO': 'Norge', 'DK': 'Danmark', 'FI': 'Finland',
        'DE': 'Tyskland', 'FR': 'Frankrike', 'ES': 'Spanien', 'PT': 'Portugal',
        'IT': 'Italien', 'US': 'USA', 'GB': 'Storbritannien',
    },
    'da': {
        'DK': 'Danmark', 'SE': 'Sverige', 'NO': 'Norge', 'FI': 'Finland',
        'DE': 'Tyskland', 'FR': 'Frankrig', 'ES': 'Spanien', 'PT': 'Portugal',
        'IT': 'Italien', 'US': 'USA', 'GB': 'Storbritannien',
    },
    'no': {
        'NO': 'Norge', 'SE': 'Sverige', 'DK': 'Danmark', 'FI': 'Finland',
        'DE': 'Tyskland', 'FR': 'Frankrike', 'ES': 'Spania', 'PT': 'Portugal',
        'IT': 'Italia', 'US': 'USA', 'GB': 'Storbritannia',
    },
    'fi': {
        'FI': 'Suomi', 'SE': 'Ruotsi', 'NO': 'Norja', 'DK': 'Tanska',
        'DE': 'Saksa', 'FR': 'Ranska', 'ES': 'Espanja', 'PT': 'Portugali',
        'IT': 'Italia', 'US': 'Yhdysvallat', 'GB': 'Yhdistynyt kuningaskunta',
    },
}


def get_country_name_in_language(country_code: str, language_code: str) -> str:
    """
    Return the localized country name for the given (country, language).

    Falls back to the English name from COUNTRY_NAMES if the language
    does not have a localized entry, then to the country code itself.

    Example:
        >>> get_country_name_in_language('ES', 'es')
        'España'
        >>> get_country_name_in_language('DE', 'de')
        'Deutschland'
        >>> get_country_name_in_language('PT', 'pt')
        'Portugal'
        >>> get_country_name_in_language('JP', 'ja')  # no ja entries
        'Japan'  # fallback to COUNTRY_NAMES
    """
    country = (country_code or '').strip().upper()
    lang = (language_code or '').strip().lower()
    lang_dict = COUNTRY_NAMES_LOCALIZED.get(lang, {})
    return lang_dict.get(country) or COUNTRY_NAMES.get(country) or country


# ============================================================
# LocaleContext dataclass
# ============================================================

@dataclass(frozen=True)
class LocaleContext:
    """
    Immutable locale hint passed from the service layer to providers.

    Frozen (hashable, thread-safe across the ThreadPoolExecutor that runs
    up to 8 concurrent provider calls). Providers SHOULD use this to build
    their most-effective native locale mechanism.

    Fields:
        language_code: ISO 639-1 lowercase, e.g. 'pt', 'es', 'en'
        country_code:  ISO 3166-1 alpha-2 uppercase, e.g. 'PT', 'US'
        language_name: Human name in English, e.g. 'Portuguese'
        country_name:  Human name in English, e.g. 'Portugal'
        country_name_localized: Country name written in language_code when
                                possible (e.g. 'España' for es/ES,
                                'Deutschland' for de/DE). Falls back to
                                country_name. Used inside the system
                                instruction so the prompt reads naturally.
    """
    language_code: str
    country_code: str
    language_name: str
    country_name: str
    country_name_localized: str

    def fingerprint(self) -> str:
        """Short stable identifier used for logging and metadata."""
        return f"{self.language_code}-{self.country_code}"


# ============================================================
# Factory
# ============================================================

def create_locale_context(language: Optional[str],
                          country_code: Optional[str]) -> LocaleContext:
    """
    Build a normalized LocaleContext with safe fallbacks.

    Never raises. Unknown language/country codes pass through with a
    humanized name fallback (uppercased code).

    Fallback rules:
      - None / empty language -> 'en'
      - None / empty country_code -> 'US'

    Args:
        language: Free-form language code or None.
        country_code: Free-form country code or None.

    Returns:
        LocaleContext with normalized fields.

    Examples:
        >>> create_locale_context('pt', 'PT')
        LocaleContext('pt', 'PT', 'Portuguese', 'Portugal')
        >>> create_locale_context(None, None)
        LocaleContext('en', 'US', 'English', 'United States')
        >>> create_locale_context('xx', 'YY')  # unknown codes
        LocaleContext('xx', 'YY', 'XX', 'YY')
    """
    lang = (language or 'en').strip().lower() or 'en'
    country = (country_code or 'US').strip().upper() or 'US'

    language_name = LANGUAGE_NAMES.get(lang, lang.upper())
    country_name = COUNTRY_NAMES.get(country, country)
    country_name_localized = get_country_name_in_language(country, lang)

    return LocaleContext(
        language_code=lang,
        country_code=country,
        language_name=language_name,
        country_name=country_name,
        country_name_localized=country_name_localized,
    )


# ============================================================
# System-prompt instruction templates
# Each template is written IN THE TARGET LANGUAGE so the LLM
# gives it maximum weight. Untemplated languages fall back to
# the English template with {language_name} injected.
#
# _COUNTRY_SPECIFIC_TEMPLATES takes priority: if a (lang, country)
# key exists, it's used; otherwise _INSTRUCTION_TEMPLATES[lang] is used.
# This allows (pt, PT) vs (pt, BR) to have different templates with
# accurate anti-variant instructions ("não brasileiro" for PT, or
# "não de Portugal" for BR).
# ============================================================

# Country-specific overrides. Use for locale pairs where the generic
# language template would produce incorrect variant instructions.
_COUNTRY_SPECIFIC_TEMPLATES: Dict[str, str] = {
    'pt_PT': (
        "Responda em Português de Portugal (português europeu, não "
        "brasileiro). O utilizador está localizado em {country_name}. "
        "Dê prioridade a fornecedores, preços, regulamentos, exemplos e "
        "fontes de {country_name}. Evite referências específicas ao Brasil "
        "a menos que sejam diretamente solicitadas. Cite fontes locais "
        "sempre que possível (domínios .pt, imprensa portuguesa, entidades "
        "oficiais portuguesas)."
    ),
    'pt_BR': (
        "Responda em Português do Brasil (não em português europeu de "
        "Portugal). O usuário está localizado em {country_name}. Dê "
        "prioridade a fornecedores, preços, regulamentos, exemplos e "
        "fontes do Brasil. Evite referências específicas a Portugal a "
        "menos que sejam diretamente solicitadas. Cite fontes locais "
        "sempre que possível (domínios .com.br, imprensa brasileira, "
        "entidades oficiais brasileiras)."
    ),
    'en_US': (
        "Respond in American English as appropriate for a user located "
        "in the United States. Prioritize US providers, pricing (in USD), "
        "regulations, examples, and sources. Avoid references to the UK "
        "or other English-speaking countries unless explicitly requested. "
        "Cite local US sources (.com, .us, .gov) when possible."
    ),
    'en_GB': (
        "Respond in British English as appropriate for a user located "
        "in the United Kingdom. Prioritize UK providers, pricing (in "
        "GBP), regulations, examples, and sources. Avoid references to "
        "the US or other English-speaking countries unless explicitly "
        "requested. Cite local UK sources (.co.uk, .uk, .gov.uk) when "
        "possible."
    ),
    'es_ES': (
        "Responde en español de España (castellano europeo). El usuario "
        "se encuentra en España. Prioriza proveedores, precios (en €), "
        "regulaciones, ejemplos y fuentes de España. Evita referencias "
        "a países hispanoamericanos salvo que se soliciten "
        "explícitamente. Cita fuentes locales (dominios .es, prensa "
        "española, entidades oficiales españolas) siempre que sea "
        "posible."
    ),
    'es_MX': (
        "Responde en español de México. El usuario se encuentra en "
        "México. Prioriza proveedores, precios (en pesos mexicanos MXN), "
        "regulaciones, ejemplos y fuentes de México. Evita referencias a "
        "España u otros países hispanohablantes salvo que se soliciten "
        "explícitamente. Cita fuentes locales (.mx, prensa mexicana) "
        "siempre que sea posible."
    ),
    'fr_FR': (
        "Répondez en français de France. L'utilisateur se trouve en "
        "France. Privilégiez les fournisseurs, prix (en €), "
        "réglementation, exemples et sources de France. Évitez les "
        "références au Québec ou à d'autres régions francophones sauf "
        "demande explicite. Citez des sources locales (.fr, presse "
        "française) lorsque c'est possible."
    ),
    'fr_CA': (
        "Répondez en français du Québec / Canada. L'utilisateur se "
        "trouve au Canada. Privilégiez les fournisseurs, prix (en CAD), "
        "réglementation, exemples et sources du Canada. Évitez les "
        "références à la France sauf demande explicite. Citez des "
        "sources locales (.ca, presse canadienne) lorsque c'est "
        "possible."
    ),
}


_INSTRUCTION_TEMPLATES: Dict[str, str] = {
    'pt': (
        # Generic PT template: used as fallback if there's no
        # country-specific override. Does NOT assume variant
        # (PT-PT or PT-BR).
        "Responda em Português tal como é falado em {country_name}. "
        "O utilizador está localizado em {country_name}. Dê prioridade "
        "a fornecedores, preços, regulamentos, exemplos e fontes de "
        "{country_name}. Cite fontes locais sempre que possível."
    ),
    'es': (
        "Responde en español tal como se usa en {country_name}. "
        "El usuario se encuentra en {country_name}. Prioriza proveedores, "
        "precios, regulaciones, ejemplos y fuentes de {country_name}. "
        "Evita referencias específicas a otros países hispanohablantes "
        "salvo que se soliciten explícitamente. Cita fuentes locales "
        "siempre que sea posible."
    ),
    'en': (
        "Respond in English as appropriate for a user located in "
        "{country_name}. Prioritize providers, pricing, regulations, "
        "examples, and sources from {country_name}. Cite local sources "
        "when possible."
    ),
    'fr': (
        "Répondez en français tel qu'il est utilisé en {country_name}. "
        "L'utilisateur se trouve en {country_name}. Privilégiez les "
        "fournisseurs, les prix, la réglementation, les exemples et les "
        "sources de {country_name}. Citez des sources locales lorsque "
        "c'est possible."
    ),
    'de': (
        "Antworten Sie auf Deutsch, wie es in {country_name} gesprochen "
        "wird. Der Nutzer befindet sich in {country_name}. Bevorzugen Sie "
        "Anbieter, Preise, Vorschriften, Beispiele und Quellen aus "
        "{country_name}. Zitieren Sie lokale Quellen, wann immer möglich."
    ),
    'it': (
        "Rispondi in italiano come parlato in {country_name}. L'utente si "
        "trova in {country_name}. Dai priorità a fornitori, prezzi, "
        "normative, esempi e fonti da {country_name}. Cita fonti locali "
        "quando possibile."
    ),
    'nl': (
        "Antwoord in het Nederlands zoals gesproken in {country_name}. "
        "De gebruiker bevindt zich in {country_name}. Geef prioriteit aan "
        "leveranciers, prijzen, regelgeving, voorbeelden en bronnen uit "
        "{country_name}. Citeer lokale bronnen wanneer mogelijk."
    ),
    'pl': (
        "Odpowiadaj po polsku, jak używany jest w {country_name}. "
        "Użytkownik znajduje się w {country_name}. Priorytet nadaj "
        "dostawcom, cenom, przepisom, przykładom i źródłom z "
        "{country_name}. W miarę możliwości cytuj lokalne źródła."
    ),
    'sv': (
        "Svara på svenska som det används i {country_name}. Användaren "
        "befinner sig i {country_name}. Prioritera leverantörer, priser, "
        "regler, exempel och källor från {country_name}. Citera lokala "
        "källor när det är möjligt."
    ),
    'da': (
        "Svar på dansk, som det bruges i {country_name}. Brugeren "
        "befinder sig i {country_name}. Prioritér udbydere, priser, "
        "regler, eksempler og kilder fra {country_name}. Citér lokale "
        "kilder, når det er muligt."
    ),
    'no': (
        "Svar på norsk slik det brukes i {country_name}. Brukeren "
        "befinner seg i {country_name}. Prioriter leverandører, priser, "
        "regler, eksempler og kilder fra {country_name}. Siter lokale "
        "kilder når det er mulig."
    ),
    'fi': (
        "Vastaa suomeksi niin kuin sitä käytetään maassa {country_name}. "
        "Käyttäjä sijaitsee maassa {country_name}. Aseta etusijalle "
        "palveluntarjoajat, hinnat, säädökset, esimerkit ja lähteet "
        "maasta {country_name}. Viittaa paikallisiin lähteisiin aina, "
        "kun se on mahdollista."
    ),
}


# Generic English fallback for any language not explicitly covered above.
# {language_name} and {country_name} are both interpolated so the LLM
# knows what language to respond in and where to focus.
_FALLBACK_TEMPLATE: str = (
    "Respond in {language_name} as appropriate for a user located in "
    "{country_name}. Prioritize providers, pricing, regulations, examples, "
    "and sources from {country_name}. Cite local sources when possible. "
    "Avoid references to other countries unless explicitly requested."
)


def build_system_instruction(locale: LocaleContext) -> str:
    """
    Build the system-prompt instruction for the given locale.

    Selection priority:
        1. Country-specific template for (language, country) — e.g.
           'pt_PT' vs 'pt_BR', 'en_US' vs 'en_GB'. These have accurate
           anti-variant instructions.
        2. Generic language template — e.g. 'pt' (works for any
           Portuguese-speaking country without assuming variant).
        3. English fallback with language_name injected — e.g. for ja,
           zh, ko, ar, etc.

    The instruction is written in the TARGET language so LLMs give it
    maximum weight. The country name is injected in the target language
    (e.g. "España" not "Spain", "Deutschland" not "Germany") so the
    prompt reads naturally.

    Args:
        locale: LocaleContext to build instruction for.

    Returns:
        A ready-to-use system-prompt string.

    Examples:
        >>> loc = create_locale_context('pt', 'PT')
        >>> build_system_instruction(loc)
        'Responda em Português de Portugal (português europeu, não ...'

        >>> loc = create_locale_context('pt', 'BR')
        >>> build_system_instruction(loc)
        'Responda em Português do Brasil (não em português europeu ...'

        >>> loc = create_locale_context('es', 'ES')
        >>> build_system_instruction(loc)
        'Responde en español de España (castellano europeo). ...'

        >>> loc = create_locale_context('ja', 'JP')  # no template
        >>> build_system_instruction(loc)
        'Respond in Japanese as appropriate for a user located in Japan...'
    """
    # Priority 1: country-specific template for (lang, country)
    specific_key = f"{locale.language_code}_{locale.country_code}"
    template = _COUNTRY_SPECIFIC_TEMPLATES.get(specific_key)

    # Priority 2: generic language template
    if template is None:
        template = _INSTRUCTION_TEMPLATES.get(locale.language_code)

    # Priority 3: English fallback with language_name injected
    if template is None:
        return _FALLBACK_TEMPLATE.format(
            language_name=locale.language_name,
            country_name=locale.country_name,
        )

    # Dedicated template: use the localized country name so the sentence
    # reads naturally in the target language.
    return template.format(
        language_name=locale.language_name,
        country_name=locale.country_name_localized,
    )


def build_legacy_inline_context(locale: LocaleContext) -> str:
    """
    Build the legacy English inline locale context prefix.

    Matches bit-for-bit the output of
    MultiLLMMonitoringService._build_localized_query() in
    services/llm_monitoring_service.py. Kept available as a safety-net
    fallback for any caller that hasn't migrated to the system-prompt
    approach.

    Args:
        locale: LocaleContext to build context for.

    Returns:
        A prefix string meant to be prepended to the user query.
    """
    return (
        f"[Locale context]\n"
        f"- Answer language: {locale.language_name}\n"
        f"- Target market/country: {locale.country_name} "
        f"({locale.country_code})\n"
        f"- Prioritize local providers, pricing, regulations, "
        f"and examples from that country.\n\n"
    )
