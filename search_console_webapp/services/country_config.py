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

# ===== Europa - países adicionales =====
COUNTRY_MAPPING.update({
    'prt': {
        'name': 'Portugal', 'flag': '🇵🇹', 'gsc_code': 'prt',
        'serp_location': 'Lisbon, Portugal', 'serp_gl': 'pt', 'serp_hl': 'pt', 'google_domain': 'google.pt'
    },
    'irl': {
        'name': 'Irlanda', 'flag': '🇮🇪', 'gsc_code': 'irl',
        'serp_location': 'Dublin, Ireland', 'serp_gl': 'ie', 'serp_hl': 'en', 'google_domain': 'google.ie'
    },
    'nor': {
        'name': 'Noruega', 'flag': '🇳🇴', 'gsc_code': 'nor',
        'serp_location': 'Oslo, Norway', 'serp_gl': 'no', 'serp_hl': 'no', 'google_domain': 'google.no'
    },
    'dnk': {
        'name': 'Dinamarca', 'flag': '🇩🇰', 'gsc_code': 'dnk',
        'serp_location': 'Copenhagen, Denmark', 'serp_gl': 'dk', 'serp_hl': 'da', 'google_domain': 'google.dk'
    },
    'fin': {
        'name': 'Finlandia', 'flag': '🇫🇮', 'gsc_code': 'fin',
        'serp_location': 'Helsinki, Finland', 'serp_gl': 'fi', 'serp_hl': 'fi', 'google_domain': 'google.fi'
    },
    'cyp': {
        'name': 'Chipre', 'flag': '🇨🇾', 'gsc_code': 'cyp',
        'serp_location': 'Nicosia, Cyprus', 'serp_gl': 'cy', 'serp_hl': 'el', 'google_domain': 'google.com.cy'
    },
    'alb': {
        'name': 'Albania', 'flag': '🇦🇱', 'gsc_code': 'alb',
        'serp_location': 'Tirana, Albania', 'serp_gl': 'al', 'serp_hl': 'sq', 'google_domain': 'google.al'
    },
    'and': {
        'name': 'Andorra', 'flag': '🇦🇩', 'gsc_code': 'and',
        'serp_location': 'Andorra la Vella, Andorra', 'serp_gl': 'ad', 'serp_hl': 'ca', 'google_domain': 'google.ad'
    },
    'arm': {
        'name': 'Armenia', 'flag': '🇦🇲', 'gsc_code': 'arm',
        'serp_location': 'Yerevan, Armenia', 'serp_gl': 'am', 'serp_hl': 'hy', 'google_domain': 'google.am'
    },
    'aze': {
        'name': 'Azerbaiyán', 'flag': '🇦🇿', 'gsc_code': 'aze',
        'serp_location': 'Baku, Azerbaijan', 'serp_gl': 'az', 'serp_hl': 'az', 'google_domain': 'google.az'
    },
    'blr': {
        'name': 'Bielorrusia', 'flag': '🇧🇾', 'gsc_code': 'blr',
        'serp_location': 'Minsk, Belarus', 'serp_gl': 'by', 'serp_hl': 'be', 'google_domain': 'google.by'
    },
    'bih': {
        'name': 'Bosnia y Herzegovina', 'flag': '🇧🇦', 'gsc_code': 'bih',
        'serp_location': 'Sarajevo, Bosnia and Herzegovina', 'serp_gl': 'ba', 'serp_hl': 'bs', 'google_domain': 'google.ba'
    },
    'hrv': {
        'name': 'Croacia', 'flag': '🇭🇷', 'gsc_code': 'hrv',
        'serp_location': 'Zagreb, Croatia', 'serp_gl': 'hr', 'serp_hl': 'hr', 'google_domain': 'google.hr'
    },
    'est': {
        'name': 'Estonia', 'flag': '🇪🇪', 'gsc_code': 'est',
        'serp_location': 'Tallinn, Estonia', 'serp_gl': 'ee', 'serp_hl': 'et', 'google_domain': 'google.ee'
    },
    'geo': {
        'name': 'Georgia', 'flag': '🇬🇪', 'gsc_code': 'geo',
        'serp_location': 'Tbilisi, Georgia', 'serp_gl': 'ge', 'serp_hl': 'ka', 'google_domain': 'google.ge'
    },
    'isl': {
        'name': 'Islandia', 'flag': '🇮🇸', 'gsc_code': 'isl',
        'serp_location': 'Reykjavik, Iceland', 'serp_gl': 'is', 'serp_hl': 'is', 'google_domain': 'google.is'
    },
    'kaz': {
        'name': 'Kazajistán', 'flag': '🇰🇿', 'gsc_code': 'kaz',
        'serp_location': 'Astana, Kazakhstan', 'serp_gl': 'kz', 'serp_hl': 'kk', 'google_domain': 'google.kz'
    },
    'xkx': {
        'name': 'Kosovo', 'flag': '🇽🇰', 'gsc_code': 'xkx',
        'serp_location': 'Pristina, Kosovo', 'serp_gl': 'xk', 'serp_hl': 'sq', 'google_domain': 'google.com'
    },
    'lva': {
        'name': 'Letonia', 'flag': '🇱🇻', 'gsc_code': 'lva',
        'serp_location': 'Riga, Latvia', 'serp_gl': 'lv', 'serp_hl': 'lv', 'google_domain': 'google.lv'
    },
    'lie': {
        'name': 'Liechtenstein', 'flag': '🇱🇮', 'gsc_code': 'lie',
        'serp_location': 'Vaduz, Liechtenstein', 'serp_gl': 'li', 'serp_hl': 'de', 'google_domain': 'google.li'
    },
    'ltu': {
        'name': 'Lituania', 'flag': '🇱🇹', 'gsc_code': 'ltu',
        'serp_location': 'Vilnius, Lithuania', 'serp_gl': 'lt', 'serp_hl': 'lt', 'google_domain': 'google.lt'
    },
    'lux': {
        'name': 'Luxemburgo', 'flag': '🇱🇺', 'gsc_code': 'lux',
        'serp_location': 'Luxembourg, Luxembourg', 'serp_gl': 'lu', 'serp_hl': 'fr', 'google_domain': 'google.lu'
    },
    'mkd': {
        'name': 'Macedonia del Norte', 'flag': '🇲🇰', 'gsc_code': 'mkd',
        'serp_location': 'Skopje, North Macedonia', 'serp_gl': 'mk', 'serp_hl': 'mk', 'google_domain': 'google.mk'
    },
    'mlt': {
        'name': 'Malta', 'flag': '🇲🇹', 'gsc_code': 'mlt',
        'serp_location': 'Valletta, Malta', 'serp_gl': 'mt', 'serp_hl': 'mt', 'google_domain': 'google.com.mt'
    },
    'mda': {
        'name': 'Moldavia', 'flag': '🇲🇩', 'gsc_code': 'mda',
        'serp_location': 'Chisinau, Moldova', 'serp_gl': 'md', 'serp_hl': 'ro', 'google_domain': 'google.md'
    },
    'mco': {
        'name': 'Mónaco', 'flag': '🇲🇨', 'gsc_code': 'mco',
        'serp_location': 'Monaco, Monaco', 'serp_gl': 'mc', 'serp_hl': 'fr', 'google_domain': 'google.mc'
    },
    'mne': {
        'name': 'Montenegro', 'flag': '🇲🇪', 'gsc_code': 'mne',
        'serp_location': 'Podgorica, Montenegro', 'serp_gl': 'me', 'serp_hl': 'sr', 'google_domain': 'google.me'
    },
    'rou': {
        'name': 'Rumanía', 'flag': '🇷🇴', 'gsc_code': 'rou',
        'serp_location': 'Bucharest, Romania', 'serp_gl': 'ro', 'serp_hl': 'ro', 'google_domain': 'google.ro'
    },
    'smr': {
        'name': 'San Marino', 'flag': '🇸🇲', 'gsc_code': 'smr',
        'serp_location': 'San Marino, San Marino', 'serp_gl': 'sm', 'serp_hl': 'it', 'google_domain': 'google.sm'
    },
    'srb': {
        'name': 'Serbia', 'flag': '🇷🇸', 'gsc_code': 'srb',
        'serp_location': 'Belgrade, Serbia', 'serp_gl': 'rs', 'serp_hl': 'sr', 'google_domain': 'google.rs'
    },
    'svk': {
        'name': 'Eslovaquia', 'flag': '🇸🇰', 'gsc_code': 'svk',
        'serp_location': 'Bratislava, Slovakia', 'serp_gl': 'sk', 'serp_hl': 'sk', 'google_domain': 'google.sk'
    },
    'svn': {
        'name': 'Eslovenia', 'flag': '🇸🇮', 'gsc_code': 'svn',
        'serp_location': 'Ljubljana, Slovenia', 'serp_gl': 'si', 'serp_hl': 'sl', 'google_domain': 'google.si'
    },
    'ukr': {
        'name': 'Ucrania', 'flag': '🇺🇦', 'gsc_code': 'ukr',
        'serp_location': 'Kyiv, Ukraine', 'serp_gl': 'ua', 'serp_hl': 'uk', 'google_domain': 'google.com.ua'
    },
    'vat': {
        'name': 'Ciudad del Vaticano', 'flag': '🇻🇦', 'gsc_code': 'vat',
        'serp_location': 'Vatican City, Vatican', 'serp_gl': 'va', 'serp_hl': 'it', 'google_domain': 'google.it'
    }
})

# ===== Latinoamérica - países adicionales =====
COUNTRY_MAPPING.update({
    'blz': {
        'name': 'Belice', 'flag': '🇧🇿', 'gsc_code': 'blz',
        'serp_location': 'Belmopan, Belize', 'serp_gl': 'bz', 'serp_hl': 'en', 'google_domain': 'google.com.bz'
    },
    'guy': {
        'name': 'Guyana', 'flag': '🇬🇾', 'gsc_code': 'guy',
        'serp_location': 'Georgetown, Guyana', 'serp_gl': 'gy', 'serp_hl': 'en', 'google_domain': 'google.gy'
    },
    'sur': {
        'name': 'Surinam', 'flag': '🇸🇷', 'gsc_code': 'sur',
        'serp_location': 'Paramaribo, Suriname', 'serp_gl': 'sr', 'serp_hl': 'nl', 'google_domain': 'google.sr'
    },
    'hti': {
        'name': 'Haití', 'flag': '🇭🇹', 'gsc_code': 'hti',
        'serp_location': 'Port-au-Prince, Haiti', 'serp_gl': 'ht', 'serp_hl': 'fr', 'google_domain': 'google.ht'
    }
})

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


# ============================================================
# País (ISO-2) -> idioma de contenido por defecto (ISO 639-1)
# ============================================================
# Se usa para auto-rellenar el idioma de un proyecto cuando el cliente no
# lo especifica (p.ej. creación de proyectos LLM Monitoring), de forma que
# un proyecto de Francia use 'fr' en vez de asumir 'es'. El idioma elegido
# es coherente con el 'serp_hl' que cada país usa en COUNTRY_MAPPING, para
# que LLMs y SERP (AI Overview / AI Mode) hablen el mismo idioma por mercado.
COUNTRY_TO_LANGUAGE = {
    # Español
    'ES': 'es', 'MX': 'es', 'AR': 'es', 'CO': 'es', 'CL': 'es', 'PE': 'es',
    'VE': 'es', 'EC': 'es', 'UY': 'es', 'PY': 'es', 'BO': 'es', 'GT': 'es',
    'CR': 'es', 'CU': 'es', 'HN': 'es', 'SV': 'es', 'PA': 'es', 'NI': 'es',
    'PR': 'es', 'DO': 'es',
    # Portugués
    'PT': 'pt', 'BR': 'pt',
    # Francés (coherente con serp_hl: BE y LU usan 'fr')
    'FR': 'fr', 'BE': 'fr', 'LU': 'fr', 'MC': 'fr',
    # Italiano
    'IT': 'it',
    # Alemán (coherente con serp_hl: CH y LI usan 'de')
    'DE': 'de', 'AT': 'de', 'CH': 'de', 'LI': 'de',
    # Neerlandés
    'NL': 'nl',
    # Nórdicos
    'SE': 'sv', 'DK': 'da', 'NO': 'no', 'FI': 'fi',
    # Otros europeos
    'PL': 'pl', 'RO': 'ro', 'GR': 'el',
    # Inglés
    'US': 'en', 'GB': 'en', 'IE': 'en', 'CA': 'en', 'AU': 'en', 'NZ': 'en',
    'IN': 'en', 'SG': 'en', 'ZA': 'en', 'AE': 'en',
    # Otros mercados
    'TR': 'tr', 'IL': 'he', 'SA': 'ar', 'JP': 'ja', 'CN': 'zh', 'KR': 'ko',
    'ID': 'id', 'TH': 'th', 'RU': 'ru',
}


def get_default_language_for_country(country_code, fallback='es'):
    """Idioma de contenido por defecto (ISO 639-1) para un país ISO-2.

    Devuelve `fallback` ('es' por compatibilidad histórica con el
    comportamiento previo) si el país no está mapeado o no se proporciona.
    """
    if not country_code:
        return fallback
    return COUNTRY_TO_LANGUAGE.get(str(country_code).strip().upper(), fallback)
