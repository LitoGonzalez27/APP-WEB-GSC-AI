# En services/country_config.py, añadir el campo 'flag' a cada país:

COUNTRY_MAPPING = {
    'esp': {
        'name': 'España',
        'flag': '🇪🇸',
        'gsc_code': 'esp',
        'serp_location': 'Madrid, Spain',
        'serp_gl': 'es',
        'serp_hl': 'es',
        'google_domain': 'google.es'
    },
    'usa': {
        'name': 'Estados Unidos',
        'flag': '🇺🇸',
        'gsc_code': 'usa', 
        'serp_location': 'New York, United States',
        'serp_gl': 'us',
        'serp_hl': 'en',
        'google_domain': 'google.com'
    },
    'mex': {
        'name': 'México',
        'flag': '🇲🇽',
        'gsc_code': 'mex',
        'serp_location': 'Mexico City, Mexico', 
        'serp_gl': 'mx',
        'serp_hl': 'es',
        'google_domain': 'google.com.mx'
    },
    # NUEVOS países latinoamericanos que faltaban:
    'col': {
        'name': 'Colombia',
        'flag': '🇨🇴',
        'gsc_code': 'col',
        'serp_location': 'Bogotá, Colombia',
        'serp_gl': 'co',
        'serp_hl': 'es',
        'google_domain': 'google.com.co'
    },
    'per': {
        'name': 'Perú',
        'flag': '🇵🇪',
        'gsc_code': 'per',
        'serp_location': 'Lima, Peru',
        'serp_gl': 'pe',
        'serp_hl': 'es',
        'google_domain': 'google.com.pe'
    },
    'chl': {
        'name': 'Chile',
        'flag': '🇨🇱',
        'gsc_code': 'chl',
        'serp_location': 'Santiago, Chile',
        'serp_gl': 'cl',
        'serp_hl': 'es',
        'google_domain': 'google.cl'
    },
    'ven': {
        'name': 'Venezuela',
        'flag': '🇻🇪',
        'gsc_code': 'ven',
        'serp_location': 'Caracas, Venezuela',
        'serp_gl': 've',
        'serp_hl': 'es',
        'google_domain': 'google.co.ve'
    },
    'ecu': {
        'name': 'Ecuador',
        'flag': '🇪🇨',
        'gsc_code': 'ecu',
        'serp_location': 'Quito, Ecuador',
        'serp_gl': 'ec',
        'serp_hl': 'es',
        'google_domain': 'google.com.ec'
    },
    'dom': {
        'name': 'República Dominicana',
        'flag': '🇩🇴',
        'gsc_code': 'dom',
        'serp_location': 'Santo Domingo, Dominican Republic',
        'serp_gl': 'do',
        'serp_hl': 'es',
        'google_domain': 'google.com.do'
    },
    'bol': {
        'name': 'Bolivia',
        'flag': '🇧🇴',
        'gsc_code': 'bol',
        'serp_location': 'La Paz, Bolivia',
        'serp_gl': 'bo',
        'serp_hl': 'es',
        'google_domain': 'google.com.bo'
    },
    'gtm': {
        'name': 'Guatemala',
        'flag': '🇬🇹',
        'gsc_code': 'gtm',
        'serp_location': 'Guatemala City, Guatemala',
        'serp_gl': 'gt',
        'serp_hl': 'es',
        'google_domain': 'google.com.gt'
    },
    'cri': {
        'name': 'Costa Rica',
        'flag': '🇨🇷',
        'gsc_code': 'cri',
        'serp_location': 'San José, Costa Rica',
        'serp_gl': 'cr',
        'serp_hl': 'es',
        'google_domain': 'google.co.cr'
    },
    'cub': {
        'name': 'Cuba',
        'flag': '🇨🇺',
        'gsc_code': 'cub',
        'serp_location': 'Havana, Cuba',
        'serp_gl': 'cu',
        'serp_hl': 'es',
        'google_domain': 'google.com.cu'
    },
    'hnd': {
        'name': 'Honduras',
        'flag': '🇭🇳',
        'gsc_code': 'hnd',
        'serp_location': 'Tegucigalpa, Honduras',
        'serp_gl': 'hn',
        'serp_hl': 'es',
        'google_domain': 'google.hn'
    },
    'ury': {
        'name': 'Uruguay',
        'flag': '🇺🇾',
        'gsc_code': 'ury',
        'serp_location': 'Montevideo, Uruguay',
        'serp_gl': 'uy',
        'serp_hl': 'es',
        'google_domain': 'google.com.uy'
    },
    'pry': {
        'name': 'Paraguay',
        'flag': '🇵🇾',
        'gsc_code': 'pry',
        'serp_location': 'Asunción, Paraguay',
        'serp_gl': 'py',
        'serp_hl': 'es',
        'google_domain': 'google.com.py'
    },
    'slv': {
        'name': 'El Salvador',
        'flag': '🇸🇻',
        'gsc_code': 'slv',
        'serp_location': 'San Salvador, El Salvador',
        'serp_gl': 'sv',
        'serp_hl': 'es',
        'google_domain': 'google.com.sv'
    },
    'pan': {
        'name': 'Panamá',
        'flag': '🇵🇦',
        'gsc_code': 'pan',
        'serp_location': 'Panama City, Panama',
        'serp_gl': 'pa',
        'serp_hl': 'es',
        'google_domain': 'google.com.pa'
    },
    'nic': {
        'name': 'Nicaragua',
        'flag': '🇳🇮',
        'gsc_code': 'nic',
        'serp_location': 'Managua, Nicaragua',
        'serp_gl': 'ni',
        'serp_hl': 'es',
        'google_domain': 'google.com.ni'
    },
    'pri': {
        'name': 'Puerto Rico',
        'flag': '🇵🇷',
        'gsc_code': 'pri',
        'serp_location': 'San Juan, Puerto Rico',
        'serp_gl': 'pr',
        'serp_hl': 'es',
        'google_domain': 'google.com.pr'
    },
    'fra': {
        'name': 'Francia',
        'flag': '🇫🇷',
        'gsc_code': 'fra',
        'serp_location': 'Paris, France',
        'serp_gl': 'fr', 
        'serp_hl': 'fr',
        'google_domain': 'google.fr'
    },
    'deu': {
        'name': 'Alemania',
        'flag': '🇩🇪',
        'gsc_code': 'deu',
        'serp_location': 'Berlin, Germany',
        'serp_gl': 'de',
        'serp_hl': 'de', 
        'google_domain': 'google.de'
    },
    'gbr': {
        'name': 'Reino Unido',
        'flag': '🇬🇧',
        'gsc_code': 'gbr',
        'serp_location': 'London, United Kingdom',
        'serp_gl': 'uk',
        'serp_hl': 'en',
        'google_domain': 'google.co.uk'
    },
    'ita': {
        'name': 'Italia',
        'flag': '🇮🇹',
        'gsc_code': 'ita',
        'serp_location': 'Rome, Italy',
        'serp_gl': 'it',
        'serp_hl': 'it',
        'google_domain': 'google.it'
    },
    'can': {
        'name': 'Canadá',
        'flag': '🇨🇦',
        'gsc_code': 'can',
        'serp_location': 'Toronto, Canada',
        'serp_gl': 'ca',
        'serp_hl': 'en',
        'google_domain': 'google.ca'
    },
    'bra': {
        'name': 'Brasil',
        'flag': '🇧🇷',
        'gsc_code': 'bra',
        'serp_location': 'São Paulo, Brazil',
        'serp_gl': 'br',
        'serp_hl': 'pt',
        'google_domain': 'google.com.br'
    },
    'chn': {
        'name': 'China',
        'flag': '🇨🇳',
        'gsc_code': 'chn',
        'serp_location': 'Beijing, China',
        'serp_gl': 'cn',
        'serp_hl': 'zh-CN',
        'google_domain': 'google.com.hk'
    },
    'ind': {
        'name': 'India',
        'flag': '🇮🇳',
        'gsc_code': 'ind',
        'serp_location': 'New Delhi, India',
        'serp_gl': 'in',
        'serp_hl': 'en',
        'google_domain': 'google.co.in'
    },
    'jpn': {
        'name': 'Japón',
        'flag': '🇯🇵',
        'gsc_code': 'jpn',
        'serp_location': 'Tokyo, Japan',
        'serp_gl': 'jp',
        'serp_hl': 'ja',
        'google_domain': 'google.co.jp'
    },
    'rus': {
        'name': 'Rusia',
        'flag': '🇷🇺',
        'gsc_code': 'rus',
        'serp_location': 'Moscow, Russia',
        'serp_gl': 'ru',
        'serp_hl': 'ru',
        'google_domain': 'google.ru'
    },
    'aus': {
        'name': 'Australia',
        'flag': '🇦🇺',
        'gsc_code': 'aus',
        'serp_location': 'Sydney, Australia',
        'serp_gl': 'au',
        'serp_hl': 'en',
        'google_domain': 'google.com.au'
    },
    'idn': {
        'name': 'Indonesia',
        'flag': '🇮🇩',
        'gsc_code': 'idn',
        'serp_location': 'Jakarta, Indonesia',
        'serp_gl': 'id',
        'serp_hl': 'id',
        'google_domain': 'google.co.id'
    },
    'kor': {
        'name': 'Corea del Sur',
        'flag': '🇰🇷',
        'gsc_code': 'kor',
        'serp_location': 'Seoul, South Korea',
        'serp_gl': 'kr',
        'serp_hl': 'ko',
        'google_domain': 'google.co.kr'
    },
    'tur': {
        'name': 'Turquía',
        'flag': '🇹🇷',
        'gsc_code': 'tur',
        'serp_location': 'Istanbul, Turkey',
        'serp_gl': 'tr',
        'serp_hl': 'tr',
        'google_domain': 'google.com.tr'
    },
    'sau': {
        'name': 'Arabia Saudita',
        'flag': '🇸🇦',
        'gsc_code': 'sau',
        'serp_location': 'Riyadh, Saudi Arabia',
        'serp_gl': 'sa',
        'serp_hl': 'ar',
        'google_domain': 'google.com.sa'
    },
    'arg': {
        'name': 'Argentina',
        'flag': '🇦🇷',
        'gsc_code': 'arg',
        'serp_location': 'Buenos Aires, Argentina',
        'serp_gl': 'ar',
        'serp_hl': 'es',
        'google_domain': 'google.com.ar'
    },
    'nld': {
        'name': 'Países Bajos',
        'flag': '🇳🇱',
        'gsc_code': 'nld',
        'serp_location': 'Amsterdam, Netherlands',
        'serp_gl': 'nl',
        'serp_hl': 'nl',
        'google_domain': 'google.nl'
    },
    'che': {
        'name': 'Suiza',
        'flag': '🇨🇭',
        'gsc_code': 'che',
        'serp_location': 'Bern, Switzerland',
        'serp_gl': 'ch',
        'serp_hl': 'de',
        'google_domain': 'google.ch'
    },
    'pol': {
        'name': 'Polonia',
        'flag': '🇵🇱',
        'gsc_code': 'pol',
        'serp_location': 'Warsaw, Poland',
        'serp_gl': 'pl',
        'serp_hl': 'pl',
        'google_domain': 'google.pl'
    },
    'bel': {
        'name': 'Bélgica',
        'flag': '🇧🇪',
        'gsc_code': 'bel',
        'serp_location': 'Brussels, Belgium',
        'serp_gl': 'be',
        'serp_hl': 'fr',
        'google_domain': 'google.be'
    },
    'swe': {
        'name': 'Suecia',
        'flag': '🇸🇪',
        'gsc_code': 'swe',
        'serp_location': 'Stockholm, Sweden',
        'serp_gl': 'se',
        'serp_hl': 'sv',
        'google_domain': 'google.se'
    },
    'aut': {
        'name': 'Austria',
        'flag': '🇦🇹',
        'gsc_code': 'aut',
        'serp_location': 'Vienna, Austria',
        'serp_gl': 'at',
        'serp_hl': 'de',
        'google_domain': 'google.at'
    },
    'tha': {
        'name': 'Tailandia',
        'flag': '🇹🇭',
        'gsc_code': 'tha',
        'serp_location': 'Bangkok, Thailand',
        'serp_gl': 'th',
        'serp_hl': 'th',
        'google_domain': 'google.co.th'
    },
    'isr': {
        'name': 'Israel',
        'flag': '🇮🇱',
        'gsc_code': 'isr',
        'serp_location': 'Jerusalem, Israel',
        'serp_gl': 'il',
        'serp_hl': 'he',
        'google_domain': 'google.co.il'
    },
    'are': {
        'name': 'Emiratos Árabes Unidos',
        'flag': '🇦🇪',
        'gsc_code': 'are',
        'serp_location': 'Dubai, United Arab Emirates',
        'serp_gl': 'ae',
        'serp_hl': 'en',
        'google_domain': 'google.ae'
    },
    'sgp': {
        'name': 'Singapur',
        'flag': '🇸🇬',
        'gsc_code': 'sgp',
        'serp_location': 'Singapore, Singapore',
        'serp_gl': 'sg',
        'serp_hl': 'en',
        'google_domain': 'google.com.sg'
    },
    'zaf': {
        'name': 'Sudáfrica',
        'flag': '🇿🇦',
        'gsc_code': 'zaf',
        'serp_location': 'Cape Town, South Africa',
        'serp_gl': 'za',
        'serp_hl': 'en',
        'google_domain': 'google.co.za'
    }
}

def get_country_config(gsc_country_code):
    """Obtiene configuración de país para SERP API basado en código GSC"""
    return COUNTRY_MAPPING.get(gsc_country_code.lower())

def get_country_name(gsc_country_code):
    """Obtiene nombre legible del país"""
    config = get_country_config(gsc_country_code)
    return config['name'] if config else gsc_country_code.upper()

def get_country_flag(gsc_country_code):
    """Obtiene bandera del país"""
    config = get_country_config(gsc_country_code)
    return config['flag'] if config else '🌍'  # Bandera mundial por defecto