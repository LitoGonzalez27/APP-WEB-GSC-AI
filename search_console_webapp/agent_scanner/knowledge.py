# -*- coding: utf-8 -*-
"""Base de conocimiento CMO-friendly.

Para cada check: qué falla (sin jerga), por qué le importa al negocio,
cómo se arregla (instrucción lista para el equipo técnico) y esfuerzo × impacto.
El dashboard usa estos textos cuando un check puntúa 0 o 0.5.
"""

KB = {
    "1.1": {
        "titulo": "El fichero de instrucciones para robots no funciona",
        "por_que": "Es la puerta de entrada: si robots.txt falla o devuelve una página de error, los sistemas de IA no saben qué pueden leer y muchos directamente se van. Estás invisible por un fallo de 5 minutos.",
        "como": "Servir /robots.txt como texto plano con HTTP 200. Si la web es una SPA, excluir /robots.txt del enrutado del framework.",
        "esfuerzo": "Bajo", "impacto": "Alto",
    },
    "1.2": {
        "titulo": "No hay una decisión consciente sobre qué IAs pueden leer la web",
        "por_que": "Sin reglas explícitas, o lo permites todo sin control o —peor— alguien bloqueó 'la IA' entera y te sacó de las respuestas de ChatGPT y Perplexity, donde tus clientes ya buscan. Cada bot tiene una función distinta: bloquear el de entrenamiento no te saca de las respuestas; bloquear el de búsqueda, sí.",
        "como": "Definir en robots.txt reglas nominales por bot: permitir OAI-SearchBot, ChatGPT-User y PerplexityBot (visibilidad); decidir según estrategia GPTBot/ClaudeBot/Google-Extended (entrenamiento).",
        "esfuerzo": "Bajo", "impacto": "Alto",
    },
    "1.3": {
        "titulo": "Lo que decís permitir y lo que el firewall hace no coinciden",
        "por_que": "Vuestro robots.txt dice 'adelante' pero el firewall/CDN devuelve un portazo a los bots de IA. Creéis estar abiertos y no lo estáis: cero visibilidad en IA sin que nadie lo haya decidido.",
        "como": "Revisar las reglas del WAF/CDN (Cloudflare, Akamai…) y alinear la lista de bots permitidos con robots.txt. Verificar después con peticiones de prueba usando los user-agents de cada bot.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "1.4": {
        "titulo": "El mapa del sitio falta o está desactualizado",
        "por_que": "El sitemap es la lista oficial de contenido que ofreces a los sistemas de IA. Sin él (o caducado), descubren tus páginas tarde, mal o nunca — especialmente las nuevas, que son las que te interesa que citen.",
        "como": "Generar sitemap.xml automático con fechas lastmod reales, referenciarlo en robots.txt y regenerarlo con cada publicación.",
        "esfuerzo": "Bajo", "impacto": "Medio",
    },
    "1.5": {
        "titulo": "Faltan señales de descubrimiento en las cabeceras",
        "por_que": "Es una señal técnica menor que los sistemas más avanzados usan para orientarse. No es urgente: es de las cosas baratas que te diferencian cuando lo básico ya está.",
        "como": "Añadir cabeceras Link (RFC 8288) con relaciones canonical/alternate/api en las respuestas del servidor.",
        "esfuerzo": "Bajo", "impacto": "Bajo",
    },
    "1.6": {
        "titulo": "Parte del contenido clave está escondido tras login o muros",
        "por_que": "Un agente de IA llega como un visitante anónimo: si el contenido que quieres que cite (productos, precios, servicios) exige registro o queda tapado por avisos, para la IA no existe y citará al competidor que sí lo enseña.",
        "como": "Garantizar que las páginas de negocio rinden su contenido completo sin sesión ni interacción. Los avisos (cookies, popups) no deben bloquear el HTML del contenido.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "1.7": {
        "titulo": "El dominio no anuncia sus capacidades de IA a nivel DNS",
        "por_que": "DNS-AID es el estándar experimental para que los agentes descubran qué ofrece un dominio antes siquiera de visitarlo. Honestidad: casi nadie lo tiene y ningún agente mayoritario lo consulta aún. Es un check de posicionamiento pionero, no de resultados.",
        "como": "Publicar un registro TXT de descubrimiento (_aid) en el DNS apuntando a las capacidades del sitio. 15 minutos de trabajo cuando el estándar madure.",
        "esfuerzo": "Bajo", "impacto": "Bajo (hoy)",
    },
    "2.1": {
        "titulo": "No declaráis qué puede hacer la IA con vuestro contenido",
        "por_que": "Los Content Signals son la forma emergente de decir 'esto puedes usarlo para responder, esto no para entrenar'. Solo el 4% de sitios lo hace: declararlo os pone en el grupo de cabeza y protege vuestros intereses sin renunciar a visibilidad.",
        "como": "Añadir Content Signals en robots.txt declarando el propósito de cada uso: search=yes (visible en buscadores IA), ai-input=yes (elegible para ser citado en respuestas — la palanca GEO), ai-train según estrategia de propiedad intelectual.",
        "esfuerzo": "Bajo", "impacto": "Medio",
    },
    "2.2": {
        "titulo": "Nadie vigila qué bots de IA entran ni cuánto os cuestan",
        "por_que": "Sin un panel de control, no sabéis quién os lee, con qué frecuencia ni a qué coste de servidor. No se puede gestionar (ni monetizar) lo que no se mide.",
        "como": "Activar la gestión de crawlers de IA en el CDN (en Cloudflare: AI Crawl Control, incluido en planes de pago) y revisar el informe mensualmente.",
        "esfuerzo": "Bajo", "impacto": "Medio",
    },
    "2.3": {
        "titulo": "No verificáis la identidad real de los agentes",
        "por_que": "Cualquiera puede disfrazarse de 'bot de OpenAI'. El estándar emergente (Web Bot Auth) permite verificar criptográficamente quién es quién. Hoy es adelantarse; en 1-2 años será lo normal.",
        "como": "Habilitar la verificación de bots firmados en el CDN (Cloudflare Verified Bots). Anotar como roadmap, no como urgencia.",
        "esfuerzo": "Medio", "impacto": "Bajo (hoy)",
    },
    "2.4": {
        "titulo": "El control de tráfico expulsa a los bots buenos",
        "por_que": "Un límite demasiado agresivo banea a los bots de IA legítimos tras pocas páginas: leen un 5% de tu web y se van. Resultado: apareces poco y mal en las respuestas.",
        "como": "Configurar rate limiting suave para bots verificados (HTTP 429 con Retry-After en vez de baneo 403 permanente).",
        "esfuerzo": "Medio", "impacto": "Medio",
    },
    "3.1": {
        "titulo": "El contenido no lleva datos estructurados (o están rotos)",
        "por_que": "Los datos estructurados son la ficha técnica que la IA lee sin adivinar: qué vendes, a qué precio, quién eres. Sin ellos, la IA interpreta a ojo — y cuando adivina, se equivoca con TU precio y TU marca.",
        "como": "Implementar JSON-LD válido en todas las plantillas (Organization, Product, Article, FAQPage según corresponda) y validarlo con Rich Results Test en el CI.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "3.2": {
        "titulo": "Vuestra identidad de marca no está declarada para las máquinas",
        "por_que": "Si no declaras quién eres (marca, logo, perfiles oficiales), la IA puede confundirte con otro, describirte mal o no vincularte con tus propias menciones. La entidad es la base de toda la visibilidad en IA.",
        "como": "Añadir schema Organization completo en la home: name, url, logo, sameAs (perfiles sociales, Wikipedia si existe) y contactPoint.",
        "esfuerzo": "Bajo", "impacto": "Alto",
    },
    "3.3": {
        "titulo": "Las fichas de producto no dan los datos mínimos de compra",
        "por_que": "Sin precio, moneda y disponibilidad estructurados, un asistente de compra no puede recomendar tus productos con seguridad — y recomendará los del competidor que sí los da. Es el requisito de entrada al comercio conversacional.",
        "como": "Completar el schema Product/Offer en todas las fichas: price, priceCurrency, availability, más name, image, brand y GTIN/SKU.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "3.4": {
        "titulo": "Los productos/contenidos van 'desnudos' de atributos",
        "por_que": "Cuantos más atributos estructurados (marca, material, medidas, valoraciones), más preguntas del cliente puede responder la IA con tus datos: '¿es de algodón?', '¿qué opinan?'. Cada atributo que falta es una respuesta que no protagonizas.",
        "como": "Enriquecer el marcado con GTIN, SKU, brand, material, color, size, aggregateRating y review donde existan. En contenidos: author, datePublished, dateModified.",
        "esfuerzo": "Medio", "impacto": "Medio",
    },
    "3.5": {
        "titulo": "La estructura de la página no comunica jerarquía",
        "por_que": "Los agentes entienden la página por su esqueleto (títulos, secciones, botones reales). Una 'sopa de divs' funciona para el ojo humano pero es ilegible para una máquina: no sabe qué es título, qué es navegación ni qué es un botón.",
        "como": "Usar HTML semántico: un solo h1, jerarquía h2/h3 coherente, landmarks (main, nav, header, footer), <button> reales y labels en formularios.",
        "esfuerzo": "Medio", "impacto": "Medio",
    },
    "3.6": {
        "titulo": "Hay botones 'fantasma' que los agentes no pueden usar",
        "por_que": "El navegador convierte tu web en un árbol de accesibilidad: es lo que leen los lectores de pantalla Y los agentes de IA. Un <div> disfrazado de botón es invisible en ese árbol — el agente visual lo ve, pero el estructural no sabe que es interactivo. Cada botón fantasma es una acción (comprar, reservar, contactar) que un agente no puede ejecutar.",
        "como": "Sustituir los <div>/<span> clicables por <button> y <a> nativos. Donde no sea posible, añadir role='button' + tabindex='0' + manejo de teclado. Regla: si se puede clicar, debe existir en el árbol de accesibilidad.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "4.1": {
        "titulo": "El contenido solo existe si se ejecuta JavaScript",
        "por_que": "Los rastreadores de IA (los de ChatGPT, Claude o Perplexity) NO ejecutan JavaScript. Si tu web se construye en el navegador, para ellos está VACÍA: es el fallo más grave posible — equivale a no tener web en el canal IA.",
        "como": "Implementar renderizado en servidor (SSR) o pre-renderizado (SSG) para que el HTML llegue completo: contenido, precios y CTAs presentes sin ejecutar JS.",
        "esfuerzo": "Alto", "impacto": "Crítico",
    },
    "4.2": {
        "titulo": "El precio o el botón de compra no están en el HTML base",
        "por_que": "Si el precio se pinta con JavaScript, los sistemas de IA no lo ven o citan uno viejo. Un asistente que no ve el precio no recomienda el producto.",
        "como": "Renderizar precio, disponibilidad y CTA en el HTML del servidor, coherentes con el schema Product/Offer.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "4.3": {
        "titulo": "La web responde demasiado lenta para los sistemas de IA",
        "por_que": "Cuando ChatGPT consulta tu web en vivo para responder a un usuario, tiene un presupuesto de segundos. Si no llegas, responde con la fuente de tu competidor. La lentitud aquí no baja posiciones: te borra de la respuesta.",
        "como": "Optimizar TTFB por debajo de 0,8s: cache de página completa, CDN, y revisar el tiempo de respuesta del servidor de origen.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "4.4": {
        "titulo": "No se puede llegar a cada contenido con un enlace directo",
        "por_que": "Los agentes navegan por URLs, no por clics. Si un producto o estado solo se alcanza interactuando (filtros, sesiones), el agente no puede volver a él ni recomendarlo con enlace.",
        "como": "Dar URL única y estable a cada producto, variante y estado relevante; verificar que abren en incógnito sin sesión.",
        "esfuerzo": "Medio", "impacto": "Medio",
    },
    "4.5": {
        "titulo": "No hay una vía programática documentada",
        "por_que": "El siguiente nivel: que un agente no tenga que 'leer' tu web sino consultarla como servicio. Sin API documentada, cada interacción es scraping frágil.",
        "como": "Publicar spec OpenAPI de los endpoints públicos (catálogo, disponibilidad, búsqueda) en /openapi.json.",
        "esfuerzo": "Alto", "impacto": "Medio (creciente)",
    },
    "4.6": {
        "titulo": "La página 'salta' mientras carga (layout inestable)",
        "por_que": "Los agentes que operan tu web toman capturas entre acciones. Si el layout se reordena mientras carga (banners que empujan, imágenes sin altura reservada), el agente clica donde YA no está el botón — igual que le pasa a tus usuarios. Un CLS alto rompe tareas de agente y conversiones humanas a la vez.",
        "como": "Reservar dimensiones para imágenes/embeds (width/height o aspect-ratio), cargar banners y avisos sin desplazar contenido, y mantener CLS ≤ 0,1 en las plantillas clave.",
        "esfuerzo": "Medio", "impacto": "Medio",
    },
    "4.7": {
        "titulo": "Hay botones y enlaces demasiado pequeños para que un agente los acierte",
        "por_que": "Un agente que opera tu web clica por coordenadas sobre una captura de pantalla, no 'entiende' el botón como tú. Si un control mide menos de 24 píxeles, falla el clic o pulsa el de al lado, y la tarea se rompe justo en el paso final. Es exactamente el mismo problema que sufre un usuario con el dedo en el móvil: lo que arreglas para el agente lo arreglas para tus clientes.",
        "como": "Garantizar un área clicable mínima de 24×24 px (WCAG 2.2 'Target Size') en todos los controles, ampliando con padding en vez de agrandando el icono. Y que todo elemento clicable tenga cursor:pointer y sea un <button>/<a> real, no un div con onclick.",
        "esfuerzo": "Bajo", "impacto": "Medio",
    },
    "4.8": {
        "titulo": "Las páginas que no existen devuelven 'todo correcto'",
        "por_que": "Es el fallo silencioso más peligroso para un agente. Una persona ve el mensaje de 'página no encontrada' y da media vuelta; el agente solo mira el código de respuesta, lee un 200 = 'éxito' y sigue trabajando sobre una página vacía. El error se propaga sin que nadie lo detecte y acaba en un dato inventado o una tarea abandonada a medias.",
        "como": "Devolver HTTP 404 real (o 410) en las URLs inexistentes, nunca 200 ni una redirección a la home. Y que la página de error incluya navegación o buscador para que el agente pueda recuperarse en vez de quedarse sin salida.",
        "esfuerzo": "Bajo", "impacto": "Alto",
    },
    "5.1": {
        "titulo": "Las páginas no responden: dan rodeos",
        "por_que": "Los LLMs citan el fragmento que mejor responde. Si tus primeras líneas son 'bienvenidos a la web líder…', la respuesta citable está en otra parte — normalmente en la web del competidor que va al grano.",
        "como": "Reescribir las páginas clave con la respuesta en el primer bloque tras el H1 (30-100 palabras directas), y el desarrollo después.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "5.2": {
        "titulo": "El contenido no está troceado en secciones autoexplicativas",
        "por_que": "La IA no lee tu página entera: extrae trozos. Si cada sección no se entiende sola (título descriptivo + contenido autocontenido), el trozo extraído pierde el sentido y no se cita.",
        "como": "Estructurar con H2/H3 descriptivos tipo pregunta o afirmación ('Cuánto cuesta X', 'X frente a Y') y secciones de 40-300 palabras que funcionen fuera de contexto.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "5.3": {
        "titulo": "El contenido no demuestra quién lo firma ni cuándo",
        "por_que": "Los sistemas de IA ponderan la fiabilidad de la fuente al elegir a quién citar. Sin autor identificable, fecha ni fuentes, tu contenido compite en desventaja contra el que sí demuestra autoridad.",
        "como": "Añadir autor con bio enlazada, fechas visibles y en schema (datePublished/dateModified) y fuentes citadas en el contenido experto.",
        "esfuerzo": "Bajo", "impacto": "Medio",
    },
    "5.5": {
        "titulo": "Falta el fichero-guía para LLMs (llms.txt)",
        "por_que": "Honestidad: hoy casi ningún LLM lo lee (97% nunca reciben una visita). Pero cuesta una hora, Google ya lo mide en Lighthouse, y tenerlo os deja listos si despega. Higiene, no palanca.",
        "como": "Publicar /llms.txt en Markdown con la estructura del sitio y enlaces a las páginas clave.",
        "esfuerzo": "Bajo", "impacto": "Bajo",
    },
    "5.6": {
        "titulo": "La web no ofrece versión ligera para máquinas (Markdown)",
        "por_que": "Un agente que pide tu página 'en Markdown' (content negotiation) recibe HTML pesado que tiene que limpiar, gastando tokens y perdiendo precisión. Servir Markdown directamente hace tu contenido más barato y fiable de consumir — solo el 3,9% de sitios lo hace, y es una de las 4 dimensiones que puntúa el scanner de Cloudflare.",
        "como": "Configurar content negotiation en el servidor/CDN: cuando la petición llegue con Accept: text/markdown, servir la versión Markdown de la página (Cloudflare lo ofrece como feature; también se puede generar en el build).",
        "esfuerzo": "Medio", "impacto": "Medio (creciente)",
    },
    "6.1": {
        "titulo": "La web no ofrece ninguna 'ventanilla' para agentes",
        "por_que": "Los agentes prefieren consultar un servicio estructurado (MCP) a interpretar HTML. Menos de 15 de los 200.000 sitios más visitados lo ofrecen: quien lo tenga primero en su sector será el sitio 'fácil' que los agentes usen por defecto.",
        "como": "Evaluar exponer un servidor MCP (o NLWeb, que reutiliza el schema existente) con las capacidades clave: consultar catálogo, disponibilidad, reservar/comprar.",
        "esfuerzo": "Alto", "impacto": "Alto (apuesta de futuro)",
    },
    "6.2": {
        "titulo": "Los formularios son difíciles de operar para un agente",
        "por_que": "Un agente que intenta pedir presupuesto o registrarse necesita campos etiquetados y botones reales. Formularios sin etiquetas o con CAPTCHA en cada paso significan tareas abandonadas — y el agente se lleva la conversión a otra parte.",
        "como": "Vincular cada campo a su etiqueta con <label for='id'> (no basta con que la etiqueta exista al lado), añadir autocomplete estándar para que el agente sepa qué dato pide cada campo, y reservar el CAPTCHA solo para señales de riesgo en vez de para todo el mundo.",
        "esfuerzo": "Medio", "impacto": "Medio",
    },
    "6.3": {
        "titulo": "Prueba con agente real pendiente",
        "por_que": "La prueba definitiva: dar a un agente (Operator, Claude) una tarea real en la web y ver dónde se atasca. El vídeo del atasco vale más que cualquier informe para entender el problema.",
        "como": "Sesión guiada: se define una tarea típica de cliente y se documenta la ejecución del agente paso a paso.",
        "esfuerzo": "Bajo", "impacto": "Diagnóstico",
    },
    "6.4": {
        "titulo": "Un agente no puede identificarse en el área privada",
        "por_que": "Todo lo que hay detrás del login (pedidos, presupuestos, facturas, historial) es invisible y inoperable para un asistente que actúa en nombre de tu cliente. Si además hay CAPTCHA, el bloqueo es total: le cierras la puerta al agente legítimo del propio usuario, no a un atacante. El patrón correcto no es darle la contraseña al agente, sino ofrecer permiso delegado.",
        "como": "Ideal: exponer OAuth 2.0 descubrible (/.well-known/oauth-authorization-server) para que el agente obtenga un permiso acotado sin manejar la contraseña. Mínimo: formulario de acceso con autocomplete='username' y 'current-password', sin CAPTCHA en el flujo normal (reservarlo para intentos sospechosos).",
        "esfuerzo": "Alto", "impacto": "Alto",
    },
    "7.5": {
        "titulo": "Los plazos y costes de envío no se pueden leer automáticamente",
        "por_que": "Cuando un asistente compara tu tienda con otras dos, el envío decide la compra tanto como el precio. Si tus condiciones están en prosa o en una página aparte, el agente no las encuentra: o te descarta por falta de datos, o —peor— se inventa un plazo y genera una incidencia cuando el pedido no llega cuando prometió.",
        "como": "Añadir shippingDetails (OfferShippingDetails) dentro del Offer de cada producto, con shippingRate, deliveryTime y shippingDestination. Es el mismo marcado que ya exige Google Merchant Center, así que suele ser reaprovechable.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "7.6": {
        "titulo": "La política de devoluciones no está en un formato que la IA entienda",
        "por_que": "La devolución es el seguro que hace que un agente se atreva a comprar por su cuenta. Sin ese dato estructurado, un asistente prudente elige al competidor que sí declara '30 días, gratis'. Tener buena política y no publicarla de forma legible es perder la venta teniendo el argumento ganador.",
        "como": "Declarar hasMerchantReturnPolicy (MerchantReturnPolicy) con merchantReturnDays, returnPolicyCategory y returnMethod en el Offer del producto, y mantenerlo sincronizado con la política real.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "7.1": {
        "titulo": "El catálogo no está listo para asistentes de compra",
        "por_que": "ChatGPT ya permite comprar dentro del chat (con Etsy y más de un millón de tiendas Shopify). Para aparecer ahí, tu catálogo debe poder ingerirse de forma estructurada. Sin feed, no existes en el escaparate conversacional.",
        "como": "Generar feed de producto completo (tipo Google Merchant) y mantenerlo sincronizado; si la tienda es Shopify/WooCommerce, activar las integraciones nativas.",
        "esfuerzo": "Medio", "impacto": "Alto",
    },
    "7.2": {
        "titulo": "El precio marcado y el visible no coinciden",
        "por_que": "Si tus propios datos se contradicen, el asistente de compra servirá el precio equivocado: reclamaciones, carritos rotos y desconfianza. Es el error más peligroso del canal IA porque afecta a dinero.",
        "como": "Sincronizar el JSON-LD con el precio/stock real en cada render (misma fuente de datos) y auditar la coherencia semanalmente.",
        "esfuerzo": "Medio", "impacto": "Crítico",
    },
    "7.3": {
        "titulo": "El checkout no está preparado para compras por agente",
        "por_que": "El estándar de compra agéntica (ACP, de OpenAI y Stripe) ya funciona en producción. La buena noticia: el comercio sigue siendo el vendedor oficial y conserva el cliente. Quien se integre antes, aparece antes en el 'comprar en ChatGPT'.",
        "como": "Verificar que el PSP soporta la Delegated Payment Spec (Stripe ya); solicitar acceso al programa de comercio de OpenAI; preparar el catálogo para ingesta ACP.",
        "esfuerzo": "Alto", "impacto": "Alto (ventana de oportunidad)",
    },
}


def advice_for(check_id):
    return KB.get(check_id)
