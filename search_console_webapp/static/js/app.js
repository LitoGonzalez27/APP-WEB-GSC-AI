// static/js/app.js - INICIALIZACIÓN CENTRALIZADA

// 1. Importaciones al inicio
import { elems, storage, initTheme, toggleTheme, setTheme, getCurrentTheme, isMobileDevice, getDeviceType, optimizeForMobile, showMobileOptimizationNotice } from './utils.js';
import { initMonthChips as initializeMonthChipsUI, handleFormSubmit as handleFormSubmitUI, initDownloadExcel } from './ui-core.js'; // Renombradas para evitar conflictos
import { initAIOverviewAnalysis } from './ui-ai-overview.js';
import { initStickyActions } from './ui-sticky-actions.js';
import { initAIOverlay, updateAIOverlayData, resetAIOverlay, updateRealProgress } from './ui-ai-overlay.js';

// Variables para almacenar el país principal del negocio
let primaryBusinessCountry = null;
let primaryBusinessCountryName = '';
let primaryBusinessCountryClicks = 0;

// Variables para controlar llamadas duplicadas
let propertiesLoaded = false;
let isLoadingProperties = false;
let isLoadingCountries = false;
let navbarIntegrationSetup = false;

// Debouncing para evitar llamadas múltiples
let reloadPropertiesTimeout = null;
let countryUpdateTimeout = null;

// ✅ NUEVO: Funcionalidad de placeholder dinámico y análisis de propiedad completa
function updateUrlPlaceholder() {
    if (!elems.urlsInput || !elems.siteUrlSelect) return;
    
    const selectedDomain = elems.siteUrlSelect.value;
    const urlsValue = elems.urlsInput.value.trim();
    
    if (selectedDomain) {
        if (!urlsValue) {
            // Campo vacío - mostrar placeholder de propiedad completa
            const domainDisplay = selectedDomain.replace('sc-domain:', '').replace('https://', '').replace('http://', '');
            elems.urlsInput.placeholder = `Analizando: ${domainDisplay} (todas las páginas)`;
            elems.urlsInput.classList.add('property-analysis-mode');
        } else {
            // Campo con contenido - mostrar placeholder normal
            elems.urlsInput.placeholder = "URLs específicas seleccionadas";
            elems.urlsInput.classList.remove('property-analysis-mode');
        }
    } else {
        // Sin dominio seleccionado
        elems.urlsInput.placeholder = "Selecciona un dominio primero";
        elems.urlsInput.classList.remove('property-analysis-mode');
    }
}

// ✅ NUEVO: Inicializar funcionalidad de placeholder dinámico
function initUrlPlaceholderFunctionality() {
    if (!elems.urlsInput || !elems.siteUrlSelect) return;
    
    // Actualizar placeholder cuando cambie el dominio
    elems.siteUrlSelect.addEventListener('change', updateUrlPlaceholder);
    
    // Actualizar placeholder cuando cambie el contenido del campo URLs
    elems.urlsInput.addEventListener('input', updateUrlPlaceholder);
    elems.urlsInput.addEventListener('paste', () => {
        // Delay para que se procese el paste
        setTimeout(updateUrlPlaceholder, 50);
    });
    
    // Actualizar placeholder inicial
    updateUrlPlaceholder();
}

// ✅ NUEVO: Inicialización automática de optimizaciones móviles
function initMobileOptimizations() {
    const isMobile = isMobileDevice();
    const deviceType = getDeviceType();
    
    console.log(`📱 Iniciando optimizaciones para dispositivo: ${deviceType} (móvil: ${isMobile})`);
    
    if (isMobile) {
        // Aplicar optimizaciones inmediatas
        optimizeForMobile();
        
        // Mostrar notificación de optimizaciones (con delay para no interferir con la carga)
        setTimeout(() => {
            showMobileOptimizationNotice();
        }, 2000);
        
        // Configurar listeners de eventos específicos para móviles
        setupMobileEventListeners();
        
        // Mejorar touch scrolling
        document.documentElement.style.webkitOverflowScrolling = 'touch';
        
        // Prevenir zoom accidental en inputs
        const metaViewport = document.querySelector('meta[name="viewport"]');
        if (metaViewport) {
            metaViewport.setAttribute('content', 
                'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'
            );
        }
        
        console.log('✅ Optimizaciones móviles aplicadas');
    }
    
    // Listeners para cambios de orientación y redimensión
    window.addEventListener('orientationchange', () => {
        setTimeout(() => {
            if (isMobileDevice()) {
                optimizeForMobile();
            }
        }, 300);
    });
    
    window.addEventListener('resize', () => {
        if (isMobileDevice()) {
            optimizeForMobile();
        }
    });
}

// ✅ NUEVO: Event listeners específicos para móviles
function setupMobileEventListeners() {
    // Listener para el evento personalizado de cierre de modal
    document.addEventListener('progressModalClosed', (e) => {
        const { device, attempts, success } = e.detail;
        console.log(`📱 Modal de progreso cerrado en ${device}: ${attempts} intentos, éxito: ${success}`);
        
        if (!success) {
            console.warn('⚠️ Modal no se cerró correctamente, aplicando cleanup adicional');
            
            // Cleanup adicional si el modal no se cerró bien
            setTimeout(() => {
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                
                const modal = document.getElementById('progressModal');
                if (modal) {
                    modal.style.display = 'none';
                    modal.style.opacity = '0';
                    modal.style.visibility = 'hidden';
                }
            }, 500);
        }
    });
    
    // Listener para cierres de modal SERP
    document.addEventListener('modalClosed', (e) => {
        const { modalId, device, attempts, success } = e.detail;
        console.log(`📱 Modal ${modalId} cerrado en ${device}: ${attempts} intentos, éxito: ${success}`);
    });
    
    // Mejorar comportamiento táctil
    document.addEventListener('touchstart', () => {}, { passive: true });
    document.addEventListener('touchmove', () => {}, { passive: true });
    
    console.log('✅ Event listeners móviles configurados');
}

// ✅ ACTUALIZADO: Solo actualizar placeholder, sin mostrar banner
function displayAnalysisMode(analysisInfo) {
    if (!analysisInfo) return;
    
    // Eliminar cualquier banner existente
    const existingIndicator = document.getElementById('analysisModeIndicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    // Solo actualizar el placeholder y el tooltip
    updateUrlPlaceholder();
    
    // Logging para debug
    console.log('🎯 Modo de análisis actualizado:', {
        mode: analysisInfo.is_property_analysis ? 'property' : 'page',
        domain: analysisInfo.domain,
        urlCount: analysisInfo.url_count
    });
}

// 2. Funciones auxiliares y de utilidad (como getCountryName)
// ✅ MAPEO COMPLETO DE PAÍSES - Función para app.js
function getCountryName(code) {
    const countries = {
        // Países principales ya existentes
        'esp': { name: 'Spain', flag: '🇪🇸' },
        'usa': { name: 'United States', flag: '🇺🇸' },
        'mex': { name: 'Mexico', flag: '🇲🇽' },
        'fra': { name: 'France', flag: '🇫🇷' },
        'deu': { name: 'Germany', flag: '🇩🇪' },
        'gbr': { name: 'United Kingdom', flag: '🇬🇧' },
        'ita': { name: 'Italy', flag: '🇮🇹' },
        'can': { name: 'Canada', flag: '🇨🇦' },
        'bra': { name: 'Brazil', flag: '🇧🇷' },
        'chn': { name: 'China', flag: '🇨🇳' },
        'ind': { name: 'India', flag: '🇮🇳' },
        'jpn': { name: 'Japan', flag: '🇯🇵' },
        'rus': { name: 'Russia', flag: '🇷🇺' },
        'aus': { name: 'Australia', flag: '🇦🇺' },

        // Países latinoamericanos
        'arg': { name: 'Argentina', flag: '🇦🇷' },
        'bol': { name: 'Bolivia', flag: '🇧🇴' },
        'chl': { name: 'Chile', flag: '🇨🇱' },
        'col': { name: 'Colombia', flag: '🇨🇴' },
        'cri': { name: 'Costa Rica', flag: '🇨🇷' },
        'cub': { name: 'Cuba', flag: '🇨🇺' },
        'dom': { name: 'Dominican Republic', flag: '🇩🇴' },
        'ecu': { name: 'Ecuador', flag: '🇪🇨' },
        'slv': { name: 'El Salvador', flag: '🇸🇻' },
        'gtm': { name: 'Guatemala', flag: '🇬🇹' },
        'guy': { name: 'Guyana', flag: '🇬🇾' },
        'hti': { name: 'Haiti', flag: '🇭🇹' },
        'hnd': { name: 'Honduras', flag: '🇭🇳' },
        'nic': { name: 'Nicaragua', flag: '🇳🇮' },
        'pan': { name: 'Panama', flag: '🇵🇦' },
        'pry': { name: 'Paraguay', flag: '🇵🇾' },
        'per': { name: 'Peru', flag: '🇵🇪' },
        'pri': { name: 'Puerto Rico', flag: '🇵🇷' },
        'sur': { name: 'Suriname', flag: '🇸🇷' },
        'ury': { name: 'Uruguay', flag: '🇺🇾' },
        'ven': { name: 'Venezuela', flag: '🇻🇪' },

        // Europa (selección)
        'alb': { name: 'Albania', flag: '🇦🇱' },
        'and': { name: 'Andorra', flag: '🇦🇩' },
        'arm': { name: 'Armenia', flag: '🇦🇲' },
        'aut': { name: 'Austria', flag: '🇦🇹' },
        'aze': { name: 'Azerbaijan', flag: '🇦🇿' },
        'blr': { name: 'Belarus', flag: '🇧🇾' },
        'bel': { name: 'Belgium', flag: '🇧🇪' },
        'bih': { name: 'Bosnia and Herzegovina', flag: '🇧🇦' },
        'bgr': { name: 'Bulgaria', flag: '🇧🇬' },
        'hrv': { name: 'Croatia', flag: '🇭🇷' },
        'cyp': { name: 'Cyprus', flag: '🇨🇾' },
        'cze': { name: 'Czech Republic', flag: '🇨🇿' },
        'dnk': { name: 'Denmark', flag: '🇩🇰' },
        'est': { name: 'Estonia', flag: '🇪🇪' },
        'fin': { name: 'Finland', flag: '🇫🇮' },
        'geo': { name: 'Georgia', flag: '🇬🇪' },
        'grc': { name: 'Greece', flag: '🇬🇷' },
        'hun': { name: 'Hungary', flag: '🇭🇺' },
        'isl': { name: 'Iceland', flag: '🇮🇸' },
        'irl': { name: 'Ireland', flag: '🇮🇪' },
        'kaz': { name: 'Kazakhstan', flag: '🇰🇿' },
        'xkx': { name: 'Kosovo', flag: '🇽🇰' },
        'lva': { name: 'Latvia', flag: '🇱🇻' },
        'lie': { name: 'Liechtenstein', flag: '🇱🇮' },
        'ltu': { name: 'Lithuania', flag: '🇱🇹' },
        'lux': { name: 'Luxembourg', flag: '🇱🇺' },
        'mkd': { name: 'North Macedonia', flag: '🇲🇰' },
        'mlt': { name: 'Malta', flag: '🇲🇹' },
        'mda': { name: 'Moldova', flag: '🇲🇩' },
        'mco': { name: 'Monaco', flag: '🇲🇨' },
        'mne': { name: 'Montenegro', flag: '🇲🇪' },
        'nld': { name: 'Netherlands', flag: '🇳🇱' },
        'nor': { name: 'Norway', flag: '🇳🇴' },
        'pol': { name: 'Poland', flag: '🇵🇱' },
        'prt': { name: 'Portugal', flag: '🇵🇹' },
        'rou': { name: 'Romania', flag: '🇷🇴' },
        'smr': { name: 'San Marino', flag: '🇸🇲' },
        'srb': { name: 'Serbia', flag: '🇷🇸' },
        'svk': { name: 'Slovakia', flag: '🇸🇰' },
        'svn': { name: 'Slovenia', flag: '🇸🇮' },
        'swe': { name: 'Sweden', flag: '🇸🇪' },
        'che': { name: 'Switzerland', flag: '🇨🇭' },
        'tur': { name: 'Turkey', flag: '🇹🇷' },
        'ukr': { name: 'Ukraine', flag: '🇺🇦' },
        'vat': { name: 'Vatican City', flag: '🇻🇦' },

        // Asia (selección importante)
        'afg': { name: 'Afghanistan', flag: '🇦🇫' },
        'bhr': { name: 'Bahrain', flag: '🇧🇭' },
        'bgd': { name: 'Bangladesh', flag: '🇧🇩' },
        'btn': { name: 'Bhutan', flag: '🇧🇹' },
        'brn': { name: 'Brunei', flag: '��🇳' },
        'khm': { name: 'Cambodia', flag: '🇰🇭' },
        'idn': { name: 'Indonesia', flag: '🇮🇩' },
        'irn': { name: 'Iran', flag: '🇮🇷' },
        'irq': { name: 'Iraq', flag: '🇮🇶' },
        'isr': { name: 'Israel', flag: '🇮��' },
        'jor': { name: 'Jordan', flag: '🇯🇴' },
        'kwt': { name: 'Kuwait', flag: '🇰🇼' },
        'kgz': { name: 'Kyrgyzstan', flag: '🇰🇬' },
        'lao': { name: 'Laos', flag: '🇱🇦' },
        'lbn': { name: 'Lebanon', flag: '🇱🇧' },
        'mys': { name: 'Malaysia', flag: '🇲🇾' },
        'mdv': { name: 'Maldives', flag: '🇲🇻' },
        'mng': { name: 'Mongolia', flag: '🇲🇳' },
        'mmr': { name: 'Myanmar', flag: '🇲🇲' },
        'npl': { name: 'Nepal', flag: '🇳🇵' },
        'prk': { name: 'North Korea', flag: '🇰🇵' },
        'omn': { name: 'Oman', flag: '🇴🇲' },
        'pak': { name: 'Pakistan', flag: '🇵🇰' },
        'pse': { name: 'Palestine', flag: '🇵🇸' },
        'phl': { name: 'Philippines', flag: '🇵🇭' },
        'qat': { name: 'Qatar', flag: '🇶🇦' },
        'sau': { name: 'Saudi Arabia', flag: '🇸🇦' },
        'sgp': { name: 'Singapore', flag: '🇸🇬' },
        'kor': { name: 'South Korea', flag: '🇰🇷' },
        'lka': { name: 'Sri Lanka', flag: '🇱🇰' },
        'syr': { name: 'Syria', flag: '🇸🇾' },
        'twn': { name: 'Taiwan', flag: '🇹🇼' },
        'tjk': { name: 'Tajikistan', flag: '🇹🇯' },
        'tha': { name: 'Thailand', flag: '🇹🇭' },
        'tkm': { name: 'Turkmenistan', flag: '🇹🇲' },
        'are': { name: 'United Arab Emirates', flag: '🇦🇪' },
        'uzb': { name: 'Uzbekistan', flag: '🇺🇿' },
        'vnm': { name: 'Vietnam', flag: '🇻🇳' },
        'yem': { name: 'Yemen', flag: '🇾🇪' },

        // África (selección importante)
        'dza': { name: 'Algeria', flag: '🇩🇿' },
        'ago': { name: 'Angola', flag: '🇦🇴' },
        'ben': { name: 'Benin', flag: '🇧🇯' },
        'bwa': { name: 'Botswana', flag: '🇧🇼' },
        'bfa': { name: 'Burkina Faso', flag: '🇧🇫' },
        'bdi': { name: 'Burundi', flag: '🇧🇮' },
        'cmr': { name: 'Cameroon', flag: '🇨🇲' },
        'cpv': { name: 'Cape Verde', flag: '🇨🇻' },
        'caf': { name: 'Central African Republic', flag: '🇨🇫' },
        'tcd': { name: 'Chad', flag: '🇹🇩' },
        'com': { name: 'Comoros', flag: '🇰🇲' },
        'cod': { name: 'Democratic Republic of the Congo', flag: '🇨🇩' },
        'cog': { name: 'Republic of the Congo', flag: '🇨🇬' },
        'civ': { name: 'Côte d\'Ivoire', flag: '🇨🇮' },
        'dji': { name: 'Djibouti', flag: '🇩🇯' },
        'egy': { name: 'Egypt', flag: '🇪🇬' },
        'gnq': { name: 'Equatorial Guinea', flag: '🇬🇶' },
        'eri': { name: 'Eritrea', flag: '🇪🇷' },
        'swz': { name: 'Eswatini', flag: '🇸🇿' },
        'eth': { name: 'Ethiopia', flag: '🇪🇹' },
        'gab': { name: 'Gabon', flag: '🇬🇦' },
        'gmb': { name: 'Gambia', flag: '🇬🇲' },
        'gha': { name: 'Ghana', flag: '🇬🇭' },
        'gin': { name: 'Guinea', flag: '🇬🇳' },
        'gnb': { name: 'Guinea-Bissau', flag: '🇬🇼' },
        'ken': { name: 'Kenya', flag: '🇰🇪' },
        'lso': { name: 'Lesotho', flag: '🇱🇸' },
        'lbr': { name: 'Liberia', flag: '🇱🇷' },
        'lby': { name: 'Libya', flag: '🇱🇾' },
        'mdg': { name: 'Madagascar', flag: '🇲🇬' },
        'mwi': { name: 'Malawi', flag: '🇲🇼' },
        'mli': { name: 'Mali', flag: '🇲🇱' },
        'mrt': { name: 'Mauritania', flag: '🇲🇷' },
        'mus': { name: 'Mauritius', flag: '🇲🇺' },
        'mar': { name: 'Morocco', flag: '🇲🇦' },
        'moz': { name: 'Mozambique', flag: '🇲🇿' },
        'nam': { name: 'Namibia', flag: '🇳🇦' },
        'ner': { name: 'Niger', flag: '🇳🇪' },
        'nga': { name: 'Nigeria', flag: '🇳🇬' },
        'rwa': { name: 'Rwanda', flag: '🇷🇼' },
        'stp': { name: 'São Tomé and Príncipe', flag: '🇸🇹' },
        'sen': { name: 'Senegal', flag: '🇸🇳' },
        'syc': { name: 'Seychelles', flag: '🇸🇨' },
        'sle': { name: 'Sierra Leone', flag: '🇸🇱' },
        'som': { name: 'Somalia', flag: '🇸🇴' },
        'zaf': { name: 'South Africa', flag: '🇿🇦' },
        'ssd': { name: 'South Sudan', flag: '🇸🇸' },
        'sdn': { name: 'Sudan', flag: '🇸🇩' },
        'tza': { name: 'Tanzania', flag: '🇹🇿' },
        'tgo': { name: 'Togo', flag: '🇹🇬' },
        'tun': { name: 'Tunisia', flag: '🇹🇳' },
        'uga': { name: 'Uganda', flag: '🇺🇬' },
        'esh': { name: 'Western Sahara', flag: '🇪🇭' },
        'zmb': { name: 'Zambia', flag: '🇿🇲' },
        'zwe': { name: 'Zimbabwe', flag: '🇿🇼' },

        // Oceanía
        'fji': { name: 'Fiji', flag: '🇫🇯' },
        'kir': { name: 'Kiribati', flag: '🇰🇮' },
        'mhl': { name: 'Marshall Islands', flag: '🇲🇭' },
        'fsm': { name: 'Micronesia', flag: '🇫🇲' },
        'nru': { name: 'Nauru', flag: '🇳🇷' },
        'nzl': { name: 'New Zealand', flag: '🇳🇿' },
        'plw': { name: 'Palau', flag: '🇵🇼' },
        'png': { name: 'Papua New Guinea', flag: '🇵🇬' },
        'wsm': { name: 'Samoa', flag: '🇼🇸' },
        'slb': { name: 'Solomon Islands', flag: '🇸🇧' },
        'ton': { name: 'Tonga', flag: '🇹🇴' },
        'tuv': { name: 'Tuvalu', flag: '🇹🇻' },
        'vuv': { name: 'Vanuatu', flag: '🇻🇺' },
        'vut': { name: 'Vanuatu', flag: '🇻🇺' },

        // Territorios y dependencias
        'abw': { name: 'Aruba', flag: '🇦🇼' },
        'asm': { name: 'American Samoa', flag: '🇦🇸' },
        'bvt': { name: 'Bouvet Island', flag: '🇧🇻' },
        'iot': { name: 'British Indian Ocean Territory', flag: '🇮🇴' },
        'vgb': { name: 'British Virgin Islands', flag: '🇻🇬' },
        'cuw': { name: 'Curaçao', flag: '🇨🇼' },
        'cxr': { name: 'Christmas Island', flag: '🇨🇽' },
        'cck': { name: 'Cocos (Keeling) Islands', flag: '🇨🇨' },
        'cok': { name: 'Cook Islands', flag: '🇨🇰' },
        'flk': { name: 'Falkland Islands', flag: '🇫🇰' },
        'fro': { name: 'Faroe Islands', flag: '🇫🇴' },
        'guf': { name: 'French Guiana', flag: '🇬🇫' },
        'pyf': { name: 'French Polynesia', flag: '🇵🇫' },
        'atf': { name: 'French Southern Territories', flag: '🇹🇫' },
        'gib': { name: 'Gibraltar', flag: '🇬🇮' },
        'grl': { name: 'Greenland', flag: '🇬🇱' },
        'glp': { name: 'Guadeloupe', flag: '🇬🇵' },
        'gum': { name: 'Guam', flag: '🇬🇺' },
        'ggy': { name: 'Guernsey', flag: '🇬🇬' },
        'hmd': { name: 'Heard Island and McDonald Islands', flag: '🇭🇲' },
        'hkg': { name: 'Hong Kong', flag: '🇭🇰' },
        'imn': { name: 'Isle of Man', flag: '🇮🇲' },
        'jey': { name: 'Jersey', flag: '🇯🇪' },
        'cym': { name: 'Cayman Islands', flag: '🇰🇾' },
        'mac': { name: 'Macao', flag: '🇲🇴' },
        'mtq': { name: 'Martinique', flag: '🇲🇶' },
        'myt': { name: 'Mayotte', flag: '🇾🇹' },
        'msr': { name: 'Montserrat', flag: '🇲🇸' },
        'ncl': { name: 'New Caledonia', flag: '🇳🇨' },
        'niu': { name: 'Niue', flag: '🇳🇺' },
        'nfk': { name: 'Norfolk Island', flag: '🇳🇫' },
        'mnp': { name: 'Northern Mariana Islands', flag: '🇲🇵' },
        'pcn': { name: 'Pitcairn Islands', flag: '🇵🇳' },
        'reu': { name: 'Reunion', flag: '🇷🇪' },
        'shn': { name: 'Saint Helena', flag: '🇸🇭' },
        'spm': { name: 'Saint Pierre and Miquelon', flag: '🇵🇲' },
        'sjm': { name: 'Svalbard and Jan Mayen', flag: '🇸🇯' },
        'tca': { name: 'Turks and Caicos Islands', flag: '🇹🇨' },
        'umi': { name: 'U.S. Minor Outlying Islands', flag: '🇺🇲' },
        'vir': { name: 'U.S. Virgin Islands', flag: '🇻🇮' },
        'wlf': { name: 'Wallis and Futuna', flag: '🇼🇫' },

        // Otros territorios específicos que aparecen en las imágenes
        'blz': { name: 'Belize', flag: '🇧🇿' },
        'brb': { name: 'Barbados', flag: '🇧🇧' },
        'bes': { name: 'Bonaire', flag: '🇧🇶' },
        'kna': { name: 'Saint Kitts and Nevis', flag: '🇰🇳' },
        'lca': { name: 'Saint Lucia', flag: '🇱🇨' },
        'maf': { name: 'Saint Martin', flag: '🇲🇫' },
        'tto': { name: 'Trinidad and Tobago', flag: '🇹🇹' },
        'vct': { name: 'Saint Vincent and the Grenadines', flag: '🇻🇨' },
        'ant': { name: 'Netherlands Antilles', flag: '🇳🇱' }, // Ya no existe pero aparece en datos
        'zzz': { name: 'Unknown', flag: '🌍' } // Para códigos no identificados
    };

    const country = countries[code.toLowerCase()];
    return country ? `${country.flag} ${country.name}` : code.toUpperCase();
}

// ✅ Función auxiliar para nombres limpios (sin bandera) - TAMBIÉN COMPLETA
function getCleanCountryName(code) {
    const countries = {
        'esp': 'Spain', 'usa': 'United States', 'mex': 'Mexico', 'fra': 'France',
        'deu': 'Germany', 'gbr': 'United Kingdom', 'ita': 'Italy', 'can': 'Canada',
        'bra': 'Brazil', 'chn': 'China', 'ind': 'India', 'jpn': 'Japan',
        'rus': 'Russia', 'aus': 'Australia', 'arg': 'Argentina', 'bol': 'Bolivia',
        'chl': 'Chile', 'col': 'Colombia', 'cri': 'Costa Rica', 'cub': 'Cuba',
        'dom': 'Dominican Republic', 'ecu': 'Ecuador', 'slv': 'El Salvador',
        'gtm': 'Guatemala', 'guy': 'Guyana', 'hti': 'Haiti', 'hnd': 'Honduras',
        'nic': 'Nicaragua', 'pan': 'Panama', 'pry': 'Paraguay', 'per': 'Peru',
        'pri': 'Puerto Rico', 'sur': 'Suriname', 'ury': 'Uruguay', 'ven': 'Venezuela',
        'alb': 'Albania', 'and': 'Andorra', 'arm': 'Armenia', 'aut': 'Austria', 'aze': 'Azerbaijan',
        'blr': 'Belarus', 'bel': 'Belgium', 'bih': 'Bosnia and Herzegovina', 'bgr': 'Bulgaria',
        'hrv': 'Croatia', 'cyp': 'Cyprus', 'cze': 'Czech Republic', 'dnk': 'Denmark',
        'est': 'Estonia', 'fin': 'Finland', 'geo': 'Georgia', 'grc': 'Greece',
        'hun': 'Hungary', 'isl': 'Iceland', 'irl': 'Ireland', 'kaz': 'Kazakhstan',
        'xkx': 'Kosovo', 'lva': 'Latvia', 'lie': 'Liechtenstein', 'ltu': 'Lithuania',
        'lux': 'Luxembourg', 'mkd': 'North Macedonia', 'mlt': 'Malta', 'mda': 'Moldova',
        'mco': 'Monaco', 'mne': 'Montenegro', 'nld': 'Netherlands', 'nor': 'Norway',
        'pol': 'Poland', 'prt': 'Portugal', 'rou': 'Romania', 'smr': 'San Marino',
        'srb': 'Serbia', 'svk': 'Slovakia', 'svn': 'Slovenia', 'swe': 'Sweden',
        'che': 'Switzerland', 'tur': 'Turkey', 'ukr': 'Ukraine', 'vat': 'Vatican City',
        'afg': 'Afghanistan', 'bhr': 'Bahrain', 'bgd': 'Bangladesh', 'btn': 'Bhutan', 'brn': 'Brunei',
        'khm': 'Cambodia', 'idn': 'Indonesia', 'irn': 'Iran', 'irq': 'Iraq', 'isr': 'Israel',
        'jor': 'Jordan', 'kwt': 'Kuwait', 'kgz': 'Kyrgyzstan', 'lao': 'Laos', 'lbn': 'Lebanon',
        'mys': 'Malaysia', 'mdv': 'Maldives', 'mng': 'Mongolia', 'mmr': 'Myanmar', 'npl': 'Nepal',
        'prk': 'North Korea', 'omn': 'Oman', 'pak': 'Pakistan', 'pse': 'Palestine',
        'phl': 'Philippines', 'qat': 'Qatar', 'sau': 'Saudi Arabia', 'sgp': 'Singapore',
        'kor': 'South Korea', 'lka': 'Sri Lanka', 'syr': 'Syria', 'twn': 'Taiwan',
        'tjk': 'Tajikistan', 'tha': 'Thailand', 'tkm': 'Turkmenistan', 'are': 'United Arab Emirates',
        'uzb': 'Uzbekistan', 'vnm': 'Vietnam', 'yem': 'Yemen',
        'dza': 'Algeria', 'ago': 'Angola', 'ben': 'Benin', 'bwa': 'Botswana', 'bfa': 'Burkina Faso',
        'bdi': 'Burundi', 'cmr': 'Cameroon', 'cpv': 'Cape Verde', 'caf': 'Central African Republic',
        'tcd': 'Chad', 'com': 'Comoros', 'cod': 'Democratic Republic of the Congo', 'cog': 'Republic of the Congo',
        'civ': 'Côte d\'Ivoire', 'dji': 'Djibouti', 'egy': 'Egypt', 'gnq': 'Equatorial Guinea',
        'eri': 'Eritrea', 'swz': 'Eswatini', 'eth': 'Ethiopia', 'gab': 'Gabon', 'gmb': 'Gambia',
        'gha': 'Ghana', 'gin': 'Guinea', 'gnb': 'Guinea-Bissau', 'ken': 'Kenya', 'lso': 'Lesotho',
        'lbr': 'Liberia', 'lby': 'Libya', 'mdg': 'Madagascar', 'mwi': 'Malawi', 'mli': 'Mali',
        'mrt': 'Mauritania', 'mus': 'Mauritius', 'mar': 'Morocco', 'moz': 'Mozambique', 'nam': 'Namibia',
        'ner': 'Niger', 'nga': 'Nigeria', 'rwa': 'Rwanda', 'stp': 'São Tomé and Príncipe',
        'sen': 'Senegal', 'syc': 'Seychelles', 'sle': 'Sierra Leone', 'som': 'Somalia',
        'zaf': 'South Africa', 'ssd': 'South Sudan', 'sdn': 'Sudan', 'tza': 'Tanzania',
        'tgo': 'Togo', 'tun': 'Tunisia', 'uga': 'Uganda', 'esh': 'Western Sahara',
        'zmb': 'Zambia', 'zwe': 'Zimbabwe',
        'fji': 'Fiji', 'kir': 'Kiribati', 'mhl': 'Marshall Islands', 'fsm': 'Micronesia',
        'nru': 'Nauru', 'nzl': 'New Zealand', 'plw': 'Palau', 'png': 'Papua New Guinea',
        'wsm': 'Samoa', 'slb': 'Solomon Islands', 'ton': 'Tonga', 'tuv': 'Tuvalu',
        'vuv': 'Vanuatu', 'vut': 'Vanuatu',
        'abw': 'Aruba', 'asm': 'American Samoa', 'bvt': 'Bouvet Island', 'iot': 'British Indian Ocean Territory',
        'vgb': 'British Virgin Islands', 'cuw': 'Curaçao', 'cxr': 'Christmas Island', 'cck': 'Cocos (Keeling) Islands',
        'cok': 'Cook Islands', 'flk': 'Falkland Islands', 'fro': 'Faroe Islands', 'guf': 'French Guiana',
        'pyf': 'French Polynesia', 'atf': 'French Southern Territories', 'gib': 'Gibraltar',
        'grl': 'Greenland', 'glp': 'Guadeloupe', 'gum': 'Guam', 'ggy': 'Guernsey',
        'hmd': 'Heard Island and McDonald Islands', 'hkg': 'Hong Kong', 'imn': 'Isle of Man', 'jey': 'Jersey',
        'cym': 'Cayman Islands', 'mac': 'Macao', 'mtq': 'Martinique', 'myt': 'Mayotte', 'msr': 'Montserrat',
        'ncl': 'New Caledonia', 'niu': 'Niue', 'nfk': 'Norfolk Island', 'mnp': 'Northern Mariana Islands',
        'pcn': 'Pitcairn Islands', 'reu': 'Reunion', 'shn': 'Saint Helena', 'spm': 'Saint Pierre and Miquelon',
        'sjm': 'Svalbard and Jan Mayen', 'tca': 'Turks and Caicos Islands', 'umi': 'U.S. Minor Outlying Islands',
        'vir': 'U.S. Virgin Islands', 'wlf': 'Wallis and Futuna',
        'blz': 'Belize', 'brb': 'Barbados', 'bes': 'Bonaire', 'kna': 'Saint Kitts and Nevis',
        'lca': 'Saint Lucia', 'maf': 'Saint Martin', 'tto': 'Trinidad and Tobago', 'vct': 'Saint Vincent and the Grenadines',
        'ant': 'Netherlands Antilles',
        'zzz': 'Unknown'
    };

    return countries[code.toLowerCase()] || code.toUpperCase();
}

// ✅ FUNCIÓN CORREGIDA: getCountryToUse() 
// Ahora respeta la selección "Todos los países" (value="")
function getCountryToUse() {
    const countrySelect = document.getElementById('countrySelect');
    const selectedCountry = countrySelect ? countrySelect.value : '';

    // ✅ NUEVO: Si el usuario seleccionó "Todos los países" (value=""), respetarlo
    if (countrySelect && countrySelect.value === '') {
        console.log('🌍 Usuario seleccionó "Todos los países" - sin filtro de país');
        return null; // o return '' - ambos significan "sin filtrar por país"
    }

    // Si hay selección manual específica, usarla
    if (selectedCountry) {
        console.log(`🎯 Usuario seleccionó país específico: ${selectedCountry}`);
        return selectedCountry;
    }

    // ✅ CAMBIADO: Solo usar país principal del negocio si NO hay select de país
    // Esto evita que se aplique automáticamente cuando el usuario eligió "Todos"
    if (!countrySelect && primaryBusinessCountry && primaryBusinessCountry !== 'esp') {
        console.log(`👑 Usando país principal del negocio: ${primaryBusinessCountry}`);
        return primaryBusinessCountry;
    }

    // ✅ CAMBIADO: Fallback a null/vacío en lugar de 'esp'
    console.log('🌍 Sin selección de país - mostrando todos los países');
    return null; // Sin filtro de país = todos los países
}

// ✅ NUEVA función para crear el tooltip con icono (estructura actualizada)
function initializeTooltip() {
    // Remover tooltip anterior si existe
    const existingTooltip = document.querySelector('.country-info-tooltip');
    if (existingTooltip) {
        existingTooltip.remove();
    }

    const countryInfoIcon = document.getElementById('countryInfoIcon');
    if (!countryInfoIcon) {
        console.warn('Icono de información de país no encontrado');
        return;
    }

    // Crear el tooltip y añadirlo al icono
    const tooltip = document.createElement('div');
    tooltip.className = 'country-info-tooltip';
    tooltip.innerHTML = `
        <div class="tooltip-content">
            <div class="tooltip-title">📊 Analyzing ALL countries</div>
            <div class="tooltip-description">
                Metrics from all countries where your site has traffic are included.<br>
                For SERPs, we will use <strong>${getCleanCountryName(primaryBusinessCountry || 'esp')}</strong> as a reference.
            </div>
        </div>
        <div class="tooltip-arrow"></div>
    `;

    // Añadir el tooltip al icono
    countryInfoIcon.appendChild(tooltip);

    // Event listeners para mostrar/ocultar tooltip

    // Para desktop: hover
    countryInfoIcon.addEventListener('mouseenter', () => {
        tooltip.classList.add('visible');
    });

    countryInfoIcon.addEventListener('mouseleave', () => {
        tooltip.classList.remove('visible');
    });

    // Para mobile: tap/click
    countryInfoIcon.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        tooltip.classList.toggle('visible');
    });

    // Cerrar tooltip si se hace click fuera
    document.addEventListener('click', (e) => {
        if (!countryInfoIcon.contains(e.target)) {
            tooltip.classList.remove('visible');
        }
    });

    // Actualizar contenido inicial
    updateTooltipContent();
}

// ✅ FUNCIÓN CORREGIDA: updateTooltipContent
function updateTooltipContent() {
    const tooltip = document.querySelector('.country-info-tooltip .tooltip-content');
    if (!tooltip) return;

    const countrySelect = document.getElementById('countrySelect');
    const selectedCountry = countrySelect ? countrySelect.value : '';

    // ✅ NUEVO: Manejar caso "Todos los países"
    if (countrySelect && selectedCountry === '') {
        // Usuario seleccionó explícitamente "Todos los países"
        tooltip.innerHTML = `
            <div class="tooltip-title">📊 Analyzing ALL countries</div>
            <div class="tooltip-description">
                Metrics from all countries where your site has traffic are included.<br>
                For SERPs, we will use <strong>${getCleanCountryName(primaryBusinessCountry || 'esp')}</strong> as a reference.
            </div>
        `;
    } else if (selectedCountry) {
        // Usuario seleccionó un país específico
        const countryNameClean = getCleanCountryName(selectedCountry);
        tooltip.innerHTML = `
            <div class="tooltip-title">🎯 Analyzing ${countryNameClean}</div>
            <div class="tooltip-description">
                Metrics and SERPs filtered only for this country.<br>
                You can switch to "All countries" to see global metrics.
            </div>
        `;
    } else {
        // No hay countrySelect disponible (estado inicial)
        tooltip.innerHTML = `
            <div class="tooltip-title">🌍 Configuring country analysis</div>
            <div class="tooltip-description">
                Select a domain first to see country options.
            </div>
        `;
    }
}

// ✅ OPTIMIZADA: función para determinar país basado en datos de negocio (con protección anti-duplicados)
async function loadAvailableCountries(siteUrl) {
    if (!siteUrl) {
        document.getElementById('countrySelect').innerHTML =
            '<option value="" disabled selected>Selecciona primero un dominio</option>';
        resetPrimaryBusinessCountry();
        return;
    }

    // ✅ NUEVO: Evitar llamadas duplicadas
    if (isLoadingCountries) {
        console.log('⏳ Ya cargando países, evitando llamada duplicada');
        return;
    }

    isLoadingCountries = true;

    try {
        const response = await fetch('/get-available-countries', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ site_url: siteUrl })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Error desconocido' }));
            
            // NUEVO: Manejar errores de autenticación
            if (errorData.auth_required || response.status === 401) {
                handleAuthError(errorData, 'al cargar países');
                document.getElementById('countrySelect').innerHTML =
                    '<option value="" disabled selected>Necesitas iniciar sesión</option>';
                resetPrimaryBusinessCountry();
                return;
            }
            
            console.error('Error cargando países:', errorData.error);
            document.getElementById('countrySelect').innerHTML =
                `<option value="" disabled selected>Error cargando países: ${errorData.error}</option>`;
            resetPrimaryBusinessCountry();
            return;
        }

        const data = await response.json();
        if (data.error) {
            console.error('Error cargando países:', data.error);
            document.getElementById('countrySelect').innerHTML =
                `<option value="" disabled selected>Error cargando países: ${data.error}</option>`;
            resetPrimaryBusinessCountry();
            return;
        }

        const countrySelect = document.getElementById('countrySelect');
        countrySelect.innerHTML = '<option value="">🌍 All countries</option>';

        // ✅ OPTIMIZADA: Lógica de país principal (sin logs excesivos)
        if (data.countries && data.countries.length > 0) {
            const topCountry = data.countries[0];

            // Solo establecer si cambió o es la primera vez
            if (primaryBusinessCountry !== topCountry.code) {
                primaryBusinessCountry = topCountry.code;
                primaryBusinessCountryName = getCountryName(topCountry.code);
                primaryBusinessCountryClicks = topCountry.clicks;

                console.log(`🎯 País principal del negocio detectado: ${primaryBusinessCountryName} (${topCountry.clicks.toLocaleString()} clics)`);
            }
        } else {
            resetPrimaryBusinessCountry();
        }

        // ✅ MODIFICADO: Llenar el dropdown SIN corona
        data.countries.forEach((country) => {
            const option = document.createElement('option');
            option.value = country.code;
            option.textContent = `${getCountryName(country.code)} (${country.clicks.toLocaleString()} clics)`;
            countrySelect.appendChild(option);
        });

        // Restaurar la selección guardada o establecer "Todos los países"
        const savedCountry = storage.country;
        if (savedCountry !== undefined && countrySelect.querySelector(`option[value="${savedCountry}"]`)) {
            countrySelect.value = savedCountry;
        } else {
            countrySelect.value = ''; // Por defecto, seleccionar "Todos los países"
        }

        // Event listener para actualizar tooltip
        countrySelect.addEventListener('change', function() {
            clearTimeout(countryUpdateTimeout);
            countryUpdateTimeout = setTimeout(() => {
                storage.country = this.value; // Guardar la selección
                updateTooltipContent();
                // ✅ ELIMINADO: updatePageTitlesWithCountry(); 
            }, 100);
        });

        // Inicializar el tooltip
        initializeTooltip();
        // ✅ ELIMINADO: updatePageTitlesWithCountry(); 

    } catch (error) {
        console.error('Error cargando países:', error);
        document.getElementById('countrySelect').innerHTML =
            '<option value="" disabled selected>Error de red al cargar países</option>';
        resetPrimaryBusinessCountry();
        handleAuthError(error, 'en loadAvailableCountries');
    } finally {
        isLoadingCountries = false;
    }
}

// ✅ ACTUALIZAR resetPrimaryBusinessCountry para limpiar tooltips
function resetPrimaryBusinessCountry() {
    primaryBusinessCountry = 'esp';
    primaryBusinessCountryName = '🇪🇸 España';
    primaryBusinessCountryClicks = 0;
    storage.country = ''; // Limpiar la selección de país guardada

    // Limpiar cualquier tooltip que pueda quedar
    const existingTooltips = document.querySelectorAll(
        '.country-info-tooltip, .country-how-it-works, .primary-business-country-info, .active-country-indicator, .detected-country-info'
    );
    existingTooltips.forEach(tooltip => tooltip.remove());
}

// ✅ NUEVA función para verificar si el usuario está autenticado
async function checkUserAuthentication() {
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        return data.authenticated || false;
    } catch (error) {
        console.error('Error verificando autenticación:', error);
        return false;
    }
}

// ✅ NUEVA función para mostrar estado de no autenticación
function showUnauthenticatedState() {
    if (elems.siteUrlSelect) {
        elems.siteUrlSelect.innerHTML = '<option value="" disabled selected>Inicia sesión para cargar propiedades</option>';
        elems.siteUrlSelect.disabled = true;
    }
    
    const countrySelect = document.getElementById('countrySelect');
    if (countrySelect) {
        countrySelect.innerHTML = '<option value="" disabled selected>Autenticación requerida</option>';
    }
    
    resetPrimaryBusinessCountry();
    propertiesLoaded = false;
}

// Hacer funciones disponibles globalmente
window.getCountryToUse = getCountryToUse;
window.getCountryName = getCountryName;
window.primaryBusinessCountry = () => primaryBusinessCountry;
window.primaryBusinessCountryName = () => primaryBusinessCountryName;
window.handleAuthError = handleAuthError; // NUEVO: Hacer disponible globalmente

// ✅ OPTIMIZADA: función principal (con protección anti-duplicados)
async function loadSearchConsoleProperties() {
    if (!elems.siteUrlSelect) {
        console.warn("Elemento siteUrlSelect no encontrado. No se cargarán propiedades.");
        return;
    }

    // ✅ NUEVO: Evitar llamadas duplicadas
    if (isLoadingProperties) {
        console.log('⏳ Ya cargando propiedades, evitando llamada duplicada');
        return;
    }

    isLoadingProperties = true;

    // ✅ NUEVO: Verificar autenticación antes de cargar propiedades
    const isAuthenticated = await checkUserAuthentication();
    if (!isAuthenticated) {
        console.log('Usuario no autenticado, mostrando estado sin autenticación');
        showUnauthenticatedState();
        isLoadingProperties = false;
        return;
    }

    elems.siteUrlSelect.innerHTML = `<option value="" disabled selected>Cargando propiedades...</option>`;
    elems.siteUrlSelect.disabled = true;

    try {
        const response = await fetch('/get-properties');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Error desconocido al parsear respuesta del servidor.' }));
            let errorMsg = `Error al cargar propiedades: ${response.statusText}`;
            if (errorData.error) {
                errorMsg = errorData.error;
            }
            console.error('Error fetching properties:', errorData);
            elems.siteUrlSelect.innerHTML = `<option value="" disabled selected>${errorMsg}</option`;

            // NUEVO: Manejar errores de autenticación
            if (errorData.auth_required || response.status === 401) {
                handleAuthError(errorData, 'al cargar propiedades');
                showUnauthenticatedState();
                return;
            }

            if (errorData.reauth_required) {
                alert("La autenticación con Google ha fallado o expirado. Se intentará re-autenticar al recargar. Si el problema persiste, borra el archivo 'token.json' en el servidor y recarga la página.");
            }
            return;
        }

        const data = await response.json();
        if (data.properties && data.properties.length > 0) {
            elems.siteUrlSelect.innerHTML = '';
            data.properties.forEach(prop => {
                const option = document.createElement('option');
                option.value = prop.siteUrl;
                option.textContent = prop.siteUrl;
                elems.siteUrlSelect.appendChild(option);
            });

            const savedSiteUrl = storage.siteUrl;
            if (savedSiteUrl && elems.siteUrlSelect.querySelector(`option[value="${savedSiteUrl}"]`)) {
                elems.siteUrlSelect.value = savedSiteUrl;
            } else if (data.properties.length > 0) {
                elems.siteUrlSelect.value = data.properties[0].siteUrl;
                storage.siteUrl = elems.siteUrlSelect.value;
            }
            elems.siteUrlSelect.disabled = false;

            await loadAvailableCountries(elems.siteUrlSelect.value);
            propertiesLoaded = true; // ✅ NUEVO: Marcar como cargado

        } else {
            elems.siteUrlSelect.innerHTML = `<option value="" disabled selected>No hay propiedades disponibles</option>`;
        }
    } catch (error) {
        console.error('Excepción en loadSearchConsoleProperties:', error);
        elems.siteUrlSelect.innerHTML = `<option value="" disabled selected>Error de red al cargar propiedades</option>`;
        handleAuthError(error, 'en loadSearchConsoleProperties');
    } finally {
        isLoadingProperties = false;
    }
}

// ✅ OPTIMIZADA: función para recargar propiedades (con debouncing)
async function reloadPropertiesAfterLogin() {
    if (propertiesLoaded) {
        console.log('✅ Propiedades ya cargadas, no es necesario recargar');
        return;
    }

    // ✅ Debouncing para evitar múltiples llamadas rápidas
    clearTimeout(reloadPropertiesTimeout);
    reloadPropertiesTimeout = setTimeout(async () => {
        console.log('🔄 Recargando propiedades después del login...');
        await loadSearchConsoleProperties();
        // ✅ ELIMINADO: updatePageTitlesWithCountry();
    }, 500);
}

// ✅ FUNCIÓN DE DEBUG ACTUALIZADA
window.debugCountryLogic = function() {
    console.log('=== DEBUG COUNTRY LOGIC ===');
    console.log('País principal del negocio:', primaryBusinessCountry, primaryBusinessCountryName);
    console.log('Clics del país principal:', primaryBusinessCountryClicks);

    const countrySelect = document.getElementById('countrySelect');
    console.log('Country Select existe:', !!countrySelect);
    console.log('Country Select value:', countrySelect?.value);
    console.log('¿Es "Todos los países"?:', countrySelect?.value === '');

    const finalCountry = getCountryToUse();
    console.log('País final para GSC:', finalCountry);
    
    const serpCountry = window.getSelectedCountry ? window.getSelectedCountry() : 'N/A';
    console.log('País final para SERP:', serpCountry);

    console.log('Lógica aplicada:');
    if (countrySelect?.value === '') {
        console.log('→ Usuario seleccionó "Todos los países"');
        console.log('  - GSC: SIN filtro de país (métricas globales)');
        console.log('  - SERP: Usa país principal o España como geolocalización');
    } else if (finalCountry) {
        console.log('→ Usuario seleccionó país específico:', finalCountry);
        console.log('  - GSC: CON filtro de país');
        console.log('  - SERP: Usa mismo país');
    } else {
        console.log('→ Estado inicial o error');
    }
    console.log('=========================');
};

// ✅ OPTIMIZADA: función para sincronizar con el navbar (solo una vez)
function setupNavbarIntegration() {
    if (navbarIntegrationSetup) {
        console.log('✅ Integración con navbar ya configurada');
        return;
    }

    // Esperar a que el navbar esté disponible
    const checkNavbar = () => {
        if (window.navbar) {
            console.log('✅ Navbar disponible, configurando integración');
            
            // ✅ NUEVO: Escuchar cambios en el estado de autenticación
            const originalSetLoginStatus = window.navbar.setLoginStatus;
            window.navbar.setLoginStatus = function(isLoggedIn, user) {
                originalSetLoginStatus.call(this, isLoggedIn, user);
                
                // Si el usuario se autentica y las propiedades no están cargadas
                if (isLoggedIn && !propertiesLoaded) {
                    reloadPropertiesAfterLogin();
                }
                
                // Si el usuario se desautentica, limpiar estado
                if (!isLoggedIn && propertiesLoaded) {
                    showUnauthenticatedState();
                }
            };
            
            // Verificar estado de autenticación al cargar
            if (typeof window.navbar.checkAuthStatus === 'function') {
                window.navbar.checkAuthStatus();
            }
            
            navbarIntegrationSetup = true;
            return true;
        }
        return false;
    };

    if (!checkNavbar()) {
        // Si el navbar no está listo, intentar cada 100ms hasta 3 segundos
        let attempts = 0;
        const maxAttempts = 30;
        
        const interval = setInterval(() => {
            attempts++;
            if (checkNavbar() || attempts >= maxAttempts) {
                clearInterval(interval);
                if (attempts >= maxAttempts) {
                    console.warn('⚠️ Navbar no se inicializó en el tiempo esperado');
                }
            }
        }, 100);
    }
}

// ✅ NUEVA función para manejar errores de autenticación
function handleAuthError(error, context = '') {
    console.error(`Error de autenticación ${context}:`, error);
    
    if (window.navbar && typeof window.navbar.showToast === 'function') {
        if (error.auth_required || error.reauth_required) {
            window.navbar.showToast('Tu sesión ha expirado. Redirigiendo al login...', 'warning');
        } else {
            window.navbar.showToast('Error de autenticación. Redirigiendo al login...', 'error');
        }
    }
    
    // Actualizar estado del navbar
    if (window.navbar) {
        window.navbar.setLoginStatus(false, null);
    }
    
    // Redirigir a login después de un breve delay
    setTimeout(() => {
        window.location.href = '/login?session_expired=true';
    }, 2000);
}

// ✅ NUEVO: Inicializar tooltip del campo URLs
function initUrlsInfoTooltip() {
    console.log('🔍 Iniciando initUrlsInfoTooltip...');
    
    const urlsLabel = document.querySelector('label[for="urlsInput"]');
    const urlsIcon = document.getElementById('urlsInfoIcon');
    
    console.log('🔍 Elementos encontrados:', {
        urlsLabel: !!urlsLabel,
        urlsIcon: !!urlsIcon,
        labelElement: urlsLabel,
        iconElement: urlsIcon
    });
    
    if (!urlsLabel || !urlsIcon) {
        console.error('❌ No se encontraron los elementos necesarios para el tooltip');
        return;
    }
    
    // Verificar si ya existe el tooltip
    const existingTooltip = document.getElementById('urlsInfoTooltip');
    if (existingTooltip) {
        console.log('⚠️ Tooltip ya existe, eliminando...');
        existingTooltip.remove();
    }
    
    // Crear el tooltip HTML
    const tooltipHTML = `
        <div class="urls-info-tooltip" id="urlsInfoTooltip">
            <strong>ℹ️ How URL Analysis Works</strong>
            <p>When you leave the URL field empty, the analysis covers your entire Search Console property with all pages included. If you specify URLs, the system will filter data to show only pages that match your criteria. Use <em>Contains</em> to find pages that include your specified text anywhere in the URL, <em>Equals</em> for exact URL matches, or <em>Not Contains</em> to exclude pages that contain your specified text. Enter one URL per line for multiple URL analysis.</p>
        </div>
    `;
    
    // Agregar el tooltip al label
    urlsLabel.insertAdjacentHTML('beforeend', tooltipHTML);
    
    const tooltip = document.getElementById('urlsInfoTooltip');
    console.log('🔍 Tooltip creado:', !!tooltip);
    
    // Funcionalidad de click
    urlsIcon.addEventListener('click', (e) => {
        console.log('🔍 Click en icono detectado');
        e.preventDefault();
        e.stopPropagation();
        tooltip.classList.toggle('active');
        console.log('🔍 Tooltip activo:', tooltip.classList.contains('active'));
    });
    
    // Agregar hover también
    urlsIcon.addEventListener('mouseenter', () => {
        console.log('🔍 Hover en icono detectado');
        tooltip.classList.add('active');
    });
    
    urlsIcon.addEventListener('mouseleave', () => {
        // Delay para permitir hover en el tooltip
        setTimeout(() => {
            if (!tooltip.matches(':hover')) {
                tooltip.classList.remove('active');
            }
        }, 100);
    });
    
    // Mantener abierto cuando se hace hover en el tooltip
    tooltip.addEventListener('mouseenter', () => {
        tooltip.classList.add('active');
    });
    
    tooltip.addEventListener('mouseleave', () => {
        tooltip.classList.remove('active');
    });
    
    // Cerrar al hacer click fuera
    document.addEventListener('click', (e) => {
        if (!urlsLabel.contains(e.target)) {
            tooltip.classList.remove('active');
        }
    });
    
    // Cerrar con ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            tooltip.classList.remove('active');
        }
    });
    
    console.log('✅ Tooltip del campo URLs inicializado correctamente');
}

// ✅ NUEVO: Configurar interacciones del tooltip (SIMPLIFICADO)
function setupTooltipInteraction() {
    const tooltipElement = document.querySelector('[data-tooltip-id="analysis-mode-tooltip"]');
    if (!tooltipElement) return;
    
    // Solo para móviles: agregar funcionalidad de click
    if (window.matchMedia('(hover: none)').matches) {
        tooltipElement.addEventListener('click', (e) => {
            e.stopPropagation();
            tooltipElement.classList.toggle('active');
        });
        
        // Cerrar al hacer click fuera
        document.addEventListener('click', (e) => {
            if (!tooltipElement.contains(e.target)) {
                tooltipElement.classList.remove('active');
            }
        });
    }
    
    console.log('📱 Tooltip interaction configurado (simple)');
}

// ✅ FUNCIÓN PRINCIPAL DE INICIALIZACIÓN DE LA APLICACIÓN
function initializeApp() {
    // 2) Carga los ajustes guardados en los inputs
    const urlTextarea = document.querySelector('textarea[name="urls"]');
    if (urlTextarea) {
        urlTextarea.value = storage.urls;
        urlTextarea.addEventListener('input', e => storage.urls = e.target.value);
    }

    // ✅ ACTUALIZAR: Manejar radio buttons para match_type
    const savedMatchType = storage.matchType;
    const matchTypeRadios = document.querySelectorAll('input[name="match_type"]');
    
    if (matchTypeRadios.length > 0) {
        // Establecer el valor guardado
        const radioToCheck = document.querySelector(`input[name="match_type"][value="${savedMatchType}"]`);
        if (radioToCheck) {
            radioToCheck.checked = true;
        } else {
            // Si no hay valor guardado, asegurar que "contains" esté seleccionado
            const defaultRadio = document.querySelector('input[name="match_type"][value="contains"]');
            if (defaultRadio) defaultRadio.checked = true;
        }
        
        // Añadir event listeners para guardar cambios
        matchTypeRadios.forEach(radio => {
            radio.addEventListener('change', e => {
                if (e.target.checked) {
                    storage.matchType = e.target.value;
                }
            });
        });
    }

    // ✅ OPTIMIZADO: Solo cargar propiedades si no está en estado inicial
    console.log('Verificando estado de autenticación...');
    
    // ✅ NUEVO: Esperar un poco a que el navbar se inicialice
    setTimeout(async () => {
        const isAuthenticated = await checkUserAuthentication();
        if (isAuthenticated) {
            console.log('Usuario autenticado, cargando propiedades...');
            await loadSearchConsoleProperties();
        } else {
            console.log('Usuario no autenticado, mostrando estado inicial...');
            showUnauthenticatedState();
        }
        // ✅ ELIMINADO: updatePageTitlesWithCountry();
    }, 500);

    // 4) Event listener para el selector de dominio
    if (elems.siteUrlSelect) {
        elems.siteUrlSelect.addEventListener('change', async e => {
            storage.siteUrl = e.target.value;
            await loadAvailableCountries(e.target.value);
            // ✅ ELIMINADO: updatePageTitlesWithCountry();
        });
    }

    // 5) Resto de inicialización...
    initializeMonthChipsUI(); // Usar la función renombrada del módulo ui-core
    if (elems.form) {
        elems.form.addEventListener('submit', handleFormSubmitUI); // Usar la función renombrada del módulo ui-core
    } else {
        console.warn("Elemento de formulario no encontrado. El envío del formulario no funcionará.");
    }
    initDownloadExcel();
    initAIOverviewAnalysis();
    initStickyActions(); // ✅ NUEVO: Inicializar botones sticky
    initAIOverlay(); // ✅ NUEVO: Inicializar overlay AI
    initUrlPlaceholderFunctionality(); // ✅ NUEVO: Inicializar placeholder dinámico
    initMobileOptimizations(); // ✅ NUEVO: Inicializar optimizaciones móviles automáticas
    // ✅ NUEVO: Inicializar tooltip de información con timeout
    setTimeout(() => {
        initUrlsInfoTooltip();
    }, 500);

    // 6) Botón para borrar URLs
    const clearUrlsBtn = document.getElementById('clearUrlsBtn');
    if (clearUrlsBtn && urlTextarea) {
        clearUrlsBtn.addEventListener('click', () => {
            urlTextarea.value = '';
            storage.urls = '';
            // ✅ NUEVO: Actualizar placeholder cuando se limpien las URLs
            updateUrlPlaceholder();
            
            // ✅ NUEVO: Limpiar cualquier indicador de modo de análisis
            const modeIndicator = document.getElementById('analysisModeIndicator');
            if (modeIndicator) {
                modeIndicator.remove();
            }
            
            // Cerrar tooltip si está abierto
            const urlsTooltip = document.getElementById('urlsInfoTooltip');
            if (urlsTooltip) {
                urlsTooltip.classList.remove('active');
            }
            
            // Opcional: añadir efecto visual
            urlTextarea.classList.add('textarea-flash');
            setTimeout(() => {
                urlTextarea.classList.remove('textarea-flash');
            }, 500);
        });
    }
    console.log('✅ Aplicación inicializada completamente');
}

// 4. Lógica de inicialización al cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Inicializando aplicación...');
    
    // ✅ Inicializar sistema de tema centralizado
    initTheme();
    console.log('✅ Sistema de tema inicializado');
    
    // ✅ Mostrar estado actual del tema
    const themeState = getCurrentTheme();
    console.log('📱 Estado del tema:', themeState);
    
    // ✅ Hacer funciones disponibles globalmente para debugging
    window.themeUtils = {
        toggle: toggleTheme,
        set: setTheme,
        get: getCurrentTheme,
        storage: storage
    };
    
    // ✅ NUEVO: Hacer funciones de análisis disponibles globalmente
    window.displayAnalysisMode = displayAnalysisMode;
    window.updateUrlPlaceholder = updateUrlPlaceholder;
    window.setupTooltipInteraction = setupTooltipInteraction;
    window.initUrlsInfoTooltip = initUrlsInfoTooltip;
    window.updateAIOverlayData = updateAIOverlayData;
    window.resetAIOverlay = resetAIOverlay;
    window.updateRealProgress = updateRealProgress;
    
    // ✅ NUEVO: Hacer utilidades móviles disponibles globalmente
    window.mobileUtils = {
        isMobile: isMobileDevice,
        getDeviceType: getDeviceType,
        optimize: optimizeForMobile,
        showNotice: showMobileOptimizationNotice,
        MobileModalManager: null // Se importará dinámicamente
    };
    
    // Importar MobileModalManager dinámicamente para uso global
    import('./utils.js').then(module => {
        window.mobileUtils.MobileModalManager = module.MobileModalManager;
        window.MobileModalManager = module.MobileModalManager;
    }).catch(err => {
        console.warn('⚠️ No se pudo cargar MobileModalManager:', err);
    });
    
    // ✅ FUNCIÓN DE DEBUG MANUAL PARA TOOLTIPS
    window.testUrlsTooltip = function() {
        console.log('🧪 Prueba manual del tooltip...');
        
        const icon = document.getElementById('urlsInfoIcon');
        const tooltip = document.getElementById('urlsInfoTooltip');
        
        console.log('Elementos encontrados:', {
            icon: !!icon,
            tooltip: !!tooltip,
            iconVisible: icon ? window.getComputedStyle(icon).display !== 'none' : false,
            tooltipClasses: tooltip ? tooltip.classList.toString() : 'N/A'
        });
        
        if (icon) {
            console.log('🔍 Simulando click en icono...');
            icon.click();
        }
        
        if (tooltip) {
            console.log('🔍 Forzando tooltip visible...');
            tooltip.classList.add('active');
            tooltip.style.opacity = '1';
            tooltip.style.visibility = 'visible';
            tooltip.style.transform = 'translateY(0)';
        }
    };
    
    // ✅ NUEVA FUNCIÓN DE DEBUG PARA DARK MODE
    window.debugDarkMode = function() {
        console.log('🔍 Diagnóstico del Dark Mode:');
        
        const toggleBtn = document.getElementById('toggleModeBtn');
        const mobileToggleBtn = document.getElementById('mobileToggleModeBtn');
        const themeIcon = document.getElementById('themeIcon');
        const mobileThemeIcon = document.getElementById('mobileThemeIcon');
        const body = document.body;
        
        console.log('Elementos encontrados:', {
            toggleBtn: !!toggleBtn,
            mobileToggleBtn: !!mobileToggleBtn,
            themeIcon: !!themeIcon,
            mobileThemeIcon: !!mobileThemeIcon,
            bodyHasDarkMode: body.classList.contains('dark-mode'),
            localStorage: localStorage.getItem('darkMode'),
            navbarInstance: !!window.navbar
        });
        
        if (toggleBtn) {
            console.log('Botón desktop event listeners:', getEventListeners(toggleBtn));
        }
        
        if (mobileToggleBtn) {
            console.log('Botón móvil event listeners:', getEventListeners(mobileToggleBtn));
        }
        
        // Forzar toggle manual
        console.log('🔧 Intentando toggle manual...');
        if (window.navbar && window.navbar.handleThemeToggle) {
            window.navbar.handleThemeToggle();
        } else {
            console.warn('⚠️ Navbar o función handleThemeToggle no disponible');
        }
    };
    
    // ✅ NUEVA FUNCIÓN DE DEBUG PARA MÓVILES
    window.debugMobileOptimizations = function() {
        console.log('📱 Diagnóstico de Optimizaciones Móviles:');
        
        const isMobile = isMobileDevice();
        const deviceType = getDeviceType();
        
        console.log('Detección de dispositivo:', {
            isMobile,
            deviceType,
            userAgent: navigator.userAgent,
            screenWidth: window.innerWidth,
            touchSupport: 'ontouchstart' in window,
            maxTouchPoints: navigator.maxTouchPoints
        });
        
        // Verificar modales existentes
        const progressModal = document.getElementById('progressModal');
        const serpModal = document.getElementById('serpModal');
        
        console.log('Estados de modales:', {
            progressModal: {
                exists: !!progressModal,
                visible: progressModal ? progressModal.classList.contains('show') : false,
                opacity: progressModal ? getComputedStyle(progressModal).opacity : 'N/A'
            },
            serpModal: {
                exists: !!serpModal,
                visible: serpModal ? serpModal.classList.contains('show') : false,
                opacity: serpModal ? getComputedStyle(serpModal).opacity : 'N/A'
            }
        });
        
        // Verificar optimizaciones aplicadas
        const inputs = document.querySelectorAll('input[type="text"], input[type="email"], select, textarea');
        const buttons = document.querySelectorAll('button, .btn');
        
        let inputsSized = 0;
        let buttonsSized = 0;
        
        inputs.forEach(input => {
            const fontSize = parseFloat(getComputedStyle(input).fontSize);
            if (fontSize >= 16) inputsSized++;
        });
        
        buttons.forEach(button => {
            const rect = button.getBoundingClientRect();
            if (rect.width >= 44 && rect.height >= 44) buttonsSized++;
        });
        
        console.log('Optimizaciones aplicadas:', {
            inputs: {
                total: inputs.length,
                sized: inputsSized,
                percentage: Math.round((inputsSized / inputs.length) * 100) + '%'
            },
            buttons: {
                total: buttons.length,
                sized: buttonsSized,
                percentage: Math.round((buttonsSized / buttons.length) * 100) + '%'
            }
        });
        
        // Verificar viewport
        const metaViewport = document.querySelector('meta[name="viewport"]');
        console.log('Viewport meta:', {
            exists: !!metaViewport,
            content: metaViewport ? metaViewport.getAttribute('content') : 'N/A'
        });
        
        // Función para forzar optimizaciones
        return {
            forceOptimizations: () => {
                console.log('🔧 Forzando optimizaciones móviles...');
                optimizeForMobile();
                showMobileOptimizationNotice();
            },
            testModalClose: (modalId = 'progressModal') => {
                console.log(`🧪 Probando cierre robusto del modal: ${modalId}`);
                const modal = document.getElementById(modalId);
                if (modal) {
                    modal.classList.add('show');
                    setTimeout(() => {
                        if (modalId === 'progressModal') {
                            import('./ui-progress.js').then(module => {
                                module.completeProgress();
                            });
                        } else {
                            const manager = new window.MobileModalManager(modalId);
                            manager.close();
                        }
                    }, 1000);
                }
            }
        };
    };
    
    // ✅ Log para verificar que todo funciona
    console.log('🎨 Tema disponible globalmente en window.themeUtils');
    
    // ✅ Aquí puedes añadir otras inicializaciones de tu app
    initializeApp();
    setupNavbarIntegration(); // Mover aquí para asegurar que se llama
});

// ✅ FUNCIONES UTILITARIAS EXPORTADAS (Mantener si son usadas externamente, aunque el `app.js` es el punto de entrada)
export {
    initializeApp,
    handleFormSubmitUI, // Exportar la renombrada si se usa externamente
    loadSearchConsoleProperties // Exportar si se necesita llamar desde fuera
};

// ✅ ARREGLO: Detectar entorno sin usar process.env
const isDevelopment = window.location.hostname === 'localhost' || 
                     window.location.hostname === '127.0.0.1' || 
                     window.location.port === '5001';

// ✅ DEBUG: Hacer elementos disponibles globalmente solo en desarrollo
if (isDevelopment) {
    window.appElements = elems;
    window.appStorage = storage;
    console.log('🔧 Elementos de debug disponibles en window.appElements y window.appStorage');
}