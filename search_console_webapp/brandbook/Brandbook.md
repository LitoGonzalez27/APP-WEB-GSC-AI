# Clicandseo — Brand Guide for Claude

> Version 1.1 — Febrero 2026
> Fuente de verdad única para decisiones de UI, copy y diseño.

---

## Brand Overview

**Producto**: Clicandseo — Herramienta SaaS de SEO para el mercado español
**Tagline**: *Inteligencia artificial al servicio de tu visibilidad en buscadores*
**Idioma**: Español (mercado hispanohablante)

### Misión
Democratizar el SEO profesional — hacer accesible la optimización para buscadores a empresas de todos los tamaños, con herramientas inteligentes que simplifican lo complejo sin sacrificar profundidad.

### Visión
El estándar en SEO inteligente — ser la referencia del sector, combinando IA de vanguardia con una experiencia de usuario excepcional.

### Valores
- Transparencia radical de los datos
- Resultados medibles sobre promesas vacías
- Innovación constante como motor de crecimiento

### Personalidad de Marca
| Rasgo       | Descripción               |
|-------------|---------------------------|
| Orgánica    | Natural y auténtica       |
| Premium     | Sofisticada y refinada    |
| Data-Driven | Profesional y precisa     |
| Moderna     | Limpia y actual           |

---

## 02. Logo System

El logo es un **wordmark tipográfico** — sin ícono independiente. La marca vive únicamente en su tipografía.

### Construcción del Wordmark

```
Clic(800) + and(400, 50% opacity) + seo(700) + .(800, #d9f9b8)
```

| Parte | Font        | Weight | Opacity | Color          |
|-------|-------------|--------|---------|----------------|
| Clic  | Inter Tight | 800    | 100%    | text-primary   |
| and   | Inter Tight | 400    | 50%     | text-primary   |
| seo   | Inter Tight | 700    | 100%    | text-primary   |
| .     | Inter Tight | 800    | 100%    | #d9f9b8 (Bio-Lime) |

### Tamaño Mínimo y Espacio Libre
| Contexto         | Mínimo          |
|------------------|-----------------|
| Pantalla (web)   | 120px de ancho  |
| Impresión        | 30mm de ancho   |
| Favicon          | Solo "C." en 16×16 |
| Espacio libre    | 1× altura de la "C" |

### Aplicaciones sobre Fondo
- **Fondo Claro**: Texto oscuro sobre blanco — uso principal
- **Fondo Oscuro**: Texto claro (#F8FAFC) sobre #0A0A0B — versión invertida

---

## 03. Color System

Paleta inspirada en la **bioluminiscencia natural**. Bio-Lime es el color insignia: energía, crecimiento orgánico, tecnología viva.

### Regla fundamental de color
**Nunca se inventan colores.** Solo se usan los colores definidos en este brand book. Si un color no aparece en las tablas de esta sección, no existe en la marca y no debe usarse bajo ningún concepto — ni como variante, ni como aproximación, ni como tinte.

### Color Primario — Bio-Lime
| Nombre         | Hex       | RGB           | CSS Variable         |
|----------------|-----------|---------------|----------------------|
| Bio-Lime       | #d9f9b8   | 217, 249, 184 | `--color-accent`     |

### Colores Neutros (Texto)
| Nombre          | Hex       | CSS Variable              |
|-----------------|-----------|---------------------------|
| Text Primary    | #0F172A   | `--color-text-primary`    |
| Text Secondary  | #64748B   | `--color-text-secondary`  |
| Text Tertiary   | #94A3B8   | `--color-text-tertiary`   |
| Text Inverse    | #F8FAFC   | `--color-text-inverse`    |

### Colores de Fondo
| Nombre          | Hex       | CSS Variable              |
|-----------------|-----------|---------------------------|
| Paper (Blanco)  | #FFFFFF   | `--color-bg-paper`        |
| Subtle (Gris)   | #F1F5F9   | `--color-bg-subtle`       |
| Dark (Casi negro)| #0A0A0B  | `--color-bg-dark`         |
| Border          | #E2E8F0   | `--color-border`          |
| Border Subtle   | #EEF2F7   | `--color-border-subtle`   |

### Colores Utilitarios
| Nombre  | Hex     |
|---------|---------|
| Success | #3CB371 |
| Error   | #E05252 |

### Reglas de Uso Bio-Lime
- ✅ Bio-Lime como acento en fondos oscuros o claros
- ✅ Texto/ícono en Bio-Lime **solo sobre #0A0A0B**
- ❌ Nunca texto blanco sobre Bio-Lime (bajo contraste)
- ❌ Nunca texto Bio-Lime sobre blanco (#FFFFFF)
- ❌ Nunca texto Bio-Lime sobre gris (#F1F5F9)
- ❌ Nunca Bio-Lime como fondo completo de página

---

## 04. Sistema Tipográfico

Combina la precisión geométrica de **Inter Tight** con la elegancia clásica de **Libre Baskerville** — contraste sofisticado entre técnico y editorial.

### Familias Tipográficas
| Rol                      | Fuente             | Google Fonts                  |
|--------------------------|--------------------|-------------------------------|
| Principal (Display/Body) | Inter Tight        | `family=Inter+Tight`          |
| Acento (Serif)           | Libre Baskerville  | `family=Libre+Baskerville`    |

### Inter Tight — Pesos y Usos
| Weight | Nombre    | Uso                               | Letter Spacing |
|--------|-----------|-----------------------------------|----------------|
| 800    | ExtraBold | Headlines principales, "Clic"     | -0.04em        |
| 700    | Bold      | Subtítulos, "seo"                 | -0.02em        |
| 600    | SemiBold  | Eyebrow labels (uppercase)        | +0.1em         |
| 500    | Medium    | Labels de UI, nav links           | 0              |
| 400    | Regular   | Cuerpo de texto, "and"            | 0              |
| 300    | Light     | Texto decorativo, citas grandes   | 0              |

### Libre Baskerville — Usos
- **Italic 400**: Palabras destacadas en headlines, citas hero, acentos editoriales
- **Bold 700**: Énfasis editorial fuerte
- **SOLO** para palabras acento dentro de headlines Inter Tight — nunca para cuerpo de texto

### Escala Tipográfica
| Token   | Tamaño (fluid)                     | Uso                     | Notas            |
|---------|------------------------------------|-------------------------|------------------|
| H1      | clamp(3.2rem, 7vw, 5.5rem)        | Headlines hero          | weight 800, ls -0.04em |
| H2      | clamp(2.8rem, 5vw, 4rem)          | Títulos de sección      | weight 800       |
| H3      | clamp(1.8rem, 3vw, 2.5rem)        | Subsecciones            | weight 700       |
| Body    | 1rem (16px)                        | Texto principal         | leading 1.6      |
| Small   | 0.875rem                           | Texto secundario        |                  |
| Eyebrow | 0.85rem                            | Etiquetas (uppercase)   | tracking 0.1em   |
| Caption | 0.75rem                            | Notas, metadatos        |                  |

### CSS Size Tokens (fluid)
```css
--text-xs:   clamp(0.7rem, 0.65rem + 0.25vw, 0.75rem)
--text-sm:   clamp(0.8rem, 0.75rem + 0.25vw, 0.875rem)
--text-base: clamp(0.9rem, 0.85rem + 0.3vw, 1rem)
--text-lg:   clamp(1.05rem, 0.95rem + 0.5vw, 1.25rem)
--text-xl:   clamp(1.2rem, 1rem + 1vw, 1.5rem)
--text-2xl:  clamp(1.5rem, 1.2rem + 1.5vw, 2rem)
--text-3xl:  clamp(1.8rem, 1.4rem + 2vw, 2.5rem)
--text-4xl:  clamp(2.2rem, 1.6rem + 3vw, 3.5rem)
--text-5xl:  clamp(2.8rem, 2rem + 4vw, 5rem)
--text-hero: clamp(4rem, 3rem + 7vw, 10rem)
```

### Line Heights
```css
--leading-none:    1
--leading-tight:   1.15
--leading-snug:    1.3
--leading-normal:  1.6
--leading-relaxed: 1.75
```

### Letter Spacing
```css
--tracking-tight:   -0.03em
--tracking-normal:   0em
--tracking-wide:     0.05em
--tracking-wider:    0.1em
--tracking-widest:   0.2em
```

---

## 05. Sistema de Espaciado

Basado en múltiplos de 4px. Consistencia y ritmo vertical en todos los soportes.

| Token        | Rem      | Pixels |
|--------------|----------|--------|
| `--space-xs` | 0.25rem  | 4px    |
| `--space-sm` | 0.5rem   | 8px    |
| `--space-md` | 1rem     | 16px   |
| `--space-lg` | 2rem     | 32px   |
| `--space-xl` | 4rem     | 64px   |
| `--space-2xl`| 8rem     | 128px  |

### Grid y Layout
| Propiedad           | Valor                    | Uso                             |
|---------------------|--------------------------|---------------------------------|
| Container Max Width | 1400px                   | Ancho máximo de contenido       |
| Header Height       | 80px                     | Altura fija del navbar          |
| Content Padding     | 0 2rem                   | Padding lateral del container   |
| Section Padding Y   | clamp(4rem, 6vw, 8rem)   | Espaciado vertical entre secciones |
| Breakpoint Mobile   | 768px                    | Tablet y móvil                  |
| Breakpoint Desktop  | 1024px                   | Escritorio                      |
| Breakpoint Wide     | 1400px                   | Pantallas grandes               |

---

## 06. Border Radius — Lenguaje "Ultra Soft"

La marca usa formas suaves y redondeadas. **Nunca esquinas rectas (border-radius: 0).**

| Token           | Valor  | Uso                                          |
|-----------------|--------|----------------------------------------------|
| `--radius-sm`   | 8px    | Inputs, elementos pequeños, code blocks      |
| `--radius-md`   | 20px   | Tarjetas, contenedores, imágenes, modals     |
| `--radius-lg`   | 30px   | Tarjetas destacadas, áreas visuales grandes  |
| `--radius-xl`   | 60px   | Hero cards, login cards, elementos de acento |
| `--radius-full` | 9999px | **Solo botones y nav links** — ningún otro elemento |

---

## 07. Sistema de Sombras — Elevación

Sombras sutiles para jerarquía visual. Opacidades bajas — nunca decorativas.

| Token            | Valor                                | Uso                        |
|------------------|--------------------------------------|----------------------------|
| `--shadow-sm`    | `0 1px 2px rgba(15,23,42,0.04), 0 2px 8px rgba(15,23,42,0.06)` | Elevación sutil            |
| `--shadow-md`    | `0 2px 4px rgba(15,23,42,0.04), 0 8px 24px rgba(15,23,42,0.08)` | Cards, dropdowns           |
| `--shadow-lg`    | `0 4px 8px rgba(15,23,42,0.04), 0 20px 50px rgba(15,23,42,0.12)` | Modals, overlays           |
| `--shadow-float` | `0 8px 16px rgba(15,23,42,0.08), 0 30px 60px rgba(15,23,42,0.16)` | Elementos flotantes/hover  |

---

## 08. Iconografía

**Librería**: Lucide Icons (open-source, outline)
**Estilo**: Siempre outline — nunca filled
**Stroke Width**: Siempre 2px
**Alineación**: Siempre centrado verticalmente con el texto adyacente. Gap 8px (`--space-sm`)

### Tamaños
| Tamaño | Uso               |
|--------|-------------------|
| 16px   | Texto inline      |
| 20px   | Interfaz/UI       |
| 24px   | Navegación        |

---

## 09. Sistema de Botones

Todos los botones son **pill-shaped** (border-radius: 9999px) con transiciones suaves.

> **IMPORTANTE**: La forma pill (border-radius: 9999px) está reservada **exclusivamente para botones y nav links**. Nunca se usa para crear badges, pills de estado, etiquetas, tags u otros elementos de UI informativos. El estado de los datos se comunica mediante texto plano, íconos Lucide y los colores del sistema — nunca mediante elementos capsulados.

### Variantes
| Variante  | Background  | Color   | Border                   | Hover                      |
|-----------|-------------|---------|--------------------------|----------------------------|
| Primary   | #0F172A     | #F8FAFC | Ninguno                  | translateY(-3px)           |
| Secondary | Transparente| #0F172A | 1.5px solid #E2E8F0      | translateY(-2px)           |
| Accent    | #d9f9b8     | #0F172A | Ninguno                  | translateY(-2px) + shadow  |
| Ghost     | Transparente| #0F172A | Ninguno                  | bg subtle                  |

### Especificaciones Comunes
- Padding default: 14px 32px
- Font weight: 600
- Border radius: 9999px (pill)
- Transition: `0.3s cubic-bezier(0.2, 0.8, 0.2, 1)`

### Tamaños
- Small: padding reducido
- Default: 14px 32px
- Large: padding mayor

### Botones en Dark Mode
En modo oscuro, el Primary adopta estilo Accent: `background: #d9f9b8; color: #0F172A`

---

## 10. Patrón de Cards

Las tarjetas son el contenedor fundamental de información.

### Estilos Base
- Padding: 2rem
- Border Radius: `--radius-md` (20px)
- Border: `1px solid --color-border-subtle` (#EEF2F7)
- Background: `--color-bg-paper` (#FFFFFF)

### Estado Hover
- Transform: `translateY(-4px)`
- Box Shadow: `--shadow-md`
- Border: `1px solid --color-accent` (#d9f9b8) — cambia a Bio-Lime

### Estructura Interna
```
[eyebrow text]    ← pequeño, uppercase, --color-text-tertiary
[título]          ← font-weight 700
[descripción]     ← --color-text-secondary
[footer]          ← separado por border-top, opcional
```

---

## 11. Patrones Decorativos

La identidad usa un repertorio de elementos decorativos sutiles. Son el lenguaje visual que conecta todas las piezas.

### 11.1 — Texto Destacado (Highlight)
Palabra o frase en **Libre Baskerville italic** con subrayado rotado Bio-Lime.
```css
.highlight {
  position: relative;
  font-family: 'Libre Baskerville', serif;
  font-style: italic;
}
.highlight::after {
  content: '';
  position: absolute;
  bottom: 0.1em;
  left: -6px; right: -6px;
  height: 0.4em;
  background: #d9f9b8;
  opacity: 0.85;
  transform: rotate(-1.5deg);
  z-index: -1;
}
```

### 11.2 — Headline con Serif Accent Word
Dentro de H1/H2 (Inter Tight 800), una palabra clave cambia a Libre Baskerville italic con el subrayado Bio-Lime. Crea tensión visual sans/serif.

| Prop    | Texto base     | Palabra accent       | Subrayado (::after)      |
|---------|----------------|----------------------|--------------------------|
| Font    | Inter Tight    | Libre Baskerville    | —                        |
| Weight  | 800            | 400 italic           | —                        |
| H1 size | clamp(3.2rem, 7vw, 5.5rem) | Hereda | —                        |
| H2 size | clamp(2.5rem, 4vw, 3.5rem) | Hereda | —                        |
| Height  | —              | —                    | 0.4em                    |
| Color   | —              | —                    | #d9f9b8                  |
| Rotate  | —              | —                    | -1.5deg                  |
| Opacity | —              | —                    | 0.85                     |
| Inset   | —              | —                    | left: -6px, right: -6px  |

### 11.3 — Dot Grid Pattern
Textura de fondo vía `radial-gradient`. Aporta textura sin competir con el contenido.
```css
/* Hero (32px) */
background: radial-gradient(circle at 1px 1px, #CBD5E1 1px, transparent 0);
background-size: 32px 32px;
opacity: 0.3;

/* Cards (24px) */
background: radial-gradient(circle at 1px 1px, #CBD5E1 1px, transparent 0);
background-size: 24px 24px;
opacity: 0.5;
```

### 11.4 — Líneas Accent en Hover
- **Bottom Accent** (blog cards, steps): 2px high, #d9f9b8, opacity 0→1 en hover
- **Top Accent Bar** (testimonials): 3px high, #d9f9b8, opacity 0→1 en hover

### 11.5 — Toggle Switch
- Contenedor: 48×26px, pill shape
- Thumb: 22px circle, `translateX(22px)` cuando está activo
- Background activo: `--color-text-primary` (#0F172A)
- Transición: brand ease

### 11.6 — Read More Arrow (Micro-interacción)
```css
.read-more { display: flex; align-items: center; gap: 6px; transition: gap 0.3s, color 0.3s; }
.read-more:hover { gap: 10px; }
```

### Tabla Completa de Especificaciones Decorativas
| Elemento         | CSS Prop         | Valor                                   | Uso                     |
|------------------|------------------|-----------------------------------------|-------------------------|
| Highlight Text   | `::after`        | h:0.4em, rotate(-1.5deg), #d9f9b8, 0.85 | Títulos hero            |
| Logo Underline   | `::after`        | h:3px, scaleX(0→1), #d9f9b8             | Logo hover, links       |
| Left Border      | `border-left`    | 3px solid #d9f9b8, pl:1.5rem            | Descripciones, citas    |
| Dot Grid 32px    | `radial-gradient`| circle 1px, 32×32, opacity:0.3          | Hero background         |
| Dot Grid 24px    | `radial-gradient`| circle 1px, 24×24, opacity:0.5          | Feature cards           |
| Bottom Accent    | `opacity`        | h:2px, accent, 0→1 on hover             | Blog cards              |
| Top Accent Bar   | `opacity`        | h:3px, accent, 0→1 on hover             | Testimonial cards       |
| Corner Circles   | `border`         | 1px accent, 50%, 60–500px, op.0.03–0.15 | Cards, hero             |
| Toggle Switch    | `transition`     | 48×26px, thumb 22px, translateX(22px)   | Pricing toggle          |
| Read More Arrow  | `gap`            | 6px→10px, 0.3s                          | Blog, CTAs textuales    |

---

## 12. Fotografía e Imagen

Estilo: "tecnología orgánica" — data visualizations, abstractos con tonalidades verdes, interfaces limpias.

| Regla                  | Especificación                                     |
|------------------------|----------------------------------------------------|
| Border radius          | Siempre radius-md (20px)                           |
| Proporción recomendada | 16:9, 4:3 o 1:1                                   |
| Tratamiento de color   | Desaturar parcialmente + overlay Bio-Lime (10–20%) |
| Fondos abstractos      | Colores planos + dot grid + noise. **Sin gradientes** |
| Íconos e ilustraciones | Lineal, stroke 2px, estilo Lucide                  |

---

## 13. Modo Oscuro

El dark mode se usa **puntualmente** para dar énfasis visual a secciones concretas — por ejemplo, el footer, una sección de CTA final, o una sección de comparativa especialmente destacada. **No es el modo dominante de ninguna página.** El modo claro (`--color-bg-paper: #FFFFFF`) es el estilo base de toda interfaz; el fondo oscuro (`#0A0A0B`) aparece solo donde aporta contraste y jerarquía narrativa. Una página no debe tener más de 2–3 secciones oscuras, y nunca deben ser consecutivas de forma mayoritaria.

### Tokens Dark Mode
| Elemento          | Valor                       |
|-------------------|-----------------------------|
| Background        | #0A0A0B                     |
| Text Primary      | #F8FAFC                     |
| Text Secondary    | rgba(255,255,255,0.6)       |
| Text Tertiary     | rgba(255,255,255,0.4)       |
| Card Background   | rgba(255,255,255,0.03)      |
| Borders           | rgba(255,255,255,0.06)      |
| Hover Border      | rgba(217,249,184,0.2)       |
| Accent Highlight  | `var(--color-accent)` border|

### Botones en Dark Mode
- Primary → usa estilo Accent: `background: #d9f9b8; color: #0F172A`
- Secondary y Ghost: igual que light mode

---

## 14. Voz y Tono

Profesional pero accesible, técnica pero comprensible. Autoridad en SEO sin ser condescendiente.

### Principios
1. **Clara y Directa**: Frases cortas. Sin jerga innecesaria. Si un término técnico es imprescindible, se explica brevemente.
2. **Data-Driven**: Afirmaciones respaldadas con datos. Números concretos sobre adjetivos vagos. "Incrementa tu CTR un 40%" — no "Mejora mucho tu CTR".
3. **Empoderada**: El usuario es el protagonista. Las herramientas son el medio; el éxito del usuario es el fin. "Tu estrategia, potenciada por IA".

### Tono por Contexto
| Contexto        | Tono                        | Ejemplo                                             |
|-----------------|-----------------------------|-----------------------------------------------------|
| Landing Page    | Inspirador, ambicioso       | "Domina la búsqueda zero-click"                     |
| Blog / Contenido| Educativo, autoridad        | "Analicemos cómo Google interpreta..."              |
| UI / Producto   | Preciso, funcional          | "3 oportunidades de mejora detectadas"              |
| Error / Soporte | Empático, solucionador      | "No pudimos completar el análisis. Reintentando..." |
| Redes Sociales  | Cercano, actual             | "Nuevas funcionalidades que te van a encantar"      |

---

## 15. DO's & DON'Ts

### Logo
- ✅ Usar pesos y colores correctos por componente. El punto siempre en Bio-Lime.
- ❌ No usar peso uniforme. No escribir todo en minúsculas sin diferenciación tipográfica.

### Color
- ✅ Bio-Lime como acento sobre fondos oscuros o en elementos de acción
- ✅ Texto Bio-Lime solo sobre #0A0A0B
- ❌ Nunca inventar colores. Solo usar los definidos en el brand book. Ningún hex, rgb o variable que no aparezca en la paleta oficial.
- ❌ Nunca texto blanco sobre Bio-Lime (contraste insuficiente)
- ❌ Nunca texto Bio-Lime sobre blanco (#FFFFFF)
- ❌ Nunca texto Bio-Lime sobre gris (#F1F5F9)
- ❌ Nunca Bio-Lime como fondo de página completo
- ❌ **Nunca Bio-Lime (#d9f9b8) como fondo de ningún elemento.** La única excepción es el botón `btn--accent`. Eyebrow labels: solo texto uppercase en `--color-text-tertiary`, sin fondo.

### Tipografía
- ✅ Inter Tight para headlines + Libre Baskerville italic para acentos editoriales
- ❌ No sustituir fuentes de marca por genéricas (Arial, Helvetica, system fonts)

### Formas
- ✅ Botones pill (radius-full). Tarjetas con radius-md (20px). Formas suaves y orgánicas.
- ❌ Nunca esquinas rectas (border-radius: 0). La marca es "Ultra Soft" en todos los elementos.
- ❌ **Nunca pills ni badges como elementos de UI informativo** (etiquetas de estado, tags, chips, status indicators). El estado se comunica mediante texto plano + íconos + colores del sistema. La forma pill está reservada únicamente para botones y nav links.

### Fondos y Efectos
- ✅ Fondos siempre planos y sólidos: #0A0A0B, #FFFFFF, #F1F5F9, #d9f9b8
- ✅ Textura solo vía noise al 5% u opacidad o dot grid pattern
- ✅ Profundidad mediante box-shadow suaves únicamente
- ❌ **REGLA ABSOLUTA**: Nunca usar gradientes de ningún tipo (lineales, radiales, mesh, sutiles)
- ❌ Nunca glow, orbes luminosos, glassmorphism, efectos translúcidos ni blur decorativos
- ❌ No backdrop-filter blur, no glow shadows

---

## Transiciones y Movimiento

| Token          | Valor                                |
|----------------|--------------------------------------|
| `--ease-brand` | `cubic-bezier(0.2, 0.8, 0.2, 1)`    |
| `--duration`   | `0.3s`                               |
| `--transition` | `0.3s cubic-bezier(0.2, 0.8, 0.2, 1)` |

Respuesta inmediata. Todos los elementos interactivos usan el easing de marca.

---

## Reglas Críticas — Quick Reference

> Estas 14 reglas son innegociables. Aplican a todo lo que se construya bajo esta marca.

1. **SIN GRADIENTES** — nunca, de ningún tipo. Regla absoluta.
2. **SIN esquinas rectas** — siempre usar border-radius.
3. **Bio-Lime como texto SOLO sobre #0A0A0B** — nunca sobre blanco o gris.
4. **Fuentes**: Inter Tight (principal) + Libre Baskerville (solo como acento serif).
5. **Botones**: Siempre pill-shaped (border-radius: 9999px).
6. **Íconos**: Lucide, outline únicamente, stroke 2px.
7. **Sombras**: Opacidad sutil (0.04–0.15). Nunca glow decorativo.
8. **Sin glassmorphism** — sin frosted glass, sin blur effects decorativos.
9. **Fondos**: Solo colores sólidos planos + noise opcional (5%) o dot grid.
10. **Idioma**: Español. Tono según contexto (ver tabla Voice & Tone).
11. **Sin Bio-Lime como fondo** — nunca usar #d9f9b8 como fondo de ningún elemento salvo `btn--accent`. Eyebrow labels: solo texto uppercase en `--color-text-tertiary`, sin fondo.
12. **Sin colores inventados** — solo los colores definidos en el brand book. Ningún hex que no esté en la paleta oficial.
13. **Sin pills ni badges de UI** — la forma pill y el concepto badge están prohibidos en elementos informativos (estados, tags, chips). Solo permitidos en botones y nav links.
14. **Dark mode = énfasis puntual** — máximo 2–3 secciones oscuras por página, nunca mayoritarias. El fondo base de toda interfaz es claro (#FFFFFF).

---

## CSS Import Reference

```html
<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400;1,700&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">

<!-- Design Tokens -->
<link rel="stylesheet" href="brand-tokens.css">
```

```css
/* Font variables */
--font-sans: 'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-serif: 'Libre Baskerville', 'Georgia', serif;
```

---

## Design Context

### Users
Clicandseo serves a mixed audience: small business owners doing SEO themselves, dedicated SEO professionals managing client campaigns, and digital marketing agencies handling multiple accounts. Users arrive seeking clarity in a domain full of complexity — they need to understand their search performance, find opportunities, and take action without being overwhelmed by data. The tool must serve both the non-technical marketer who needs guidance and the experienced SEO specialist who needs depth and precision.

### Brand Personality
**Orgánica, Premium, Data-Driven** — the brand speaks with authority on SEO without being condescending. Professional but accessible, technical but comprehensible. The interface should feel like a trusted expert advisor: confident, clear, and always backed by data. The user is the protagonist; the tool empowers their success.

### Emotional Goals
The primary emotional response is **confidence and clarity**. Users should feel in control of their SEO strategy, never overwhelmed. Data is presented clearly and actionably. Every screen answers "what should I do next?" without noise or distraction.

### Aesthetic Direction
- **Visual tone**: Sophisticated minimalism with organic warmth — the Bio-Lime accent adds life to an otherwise precise, clean interface
- **Theme**: Light mode dominant, dark mode only for narrative emphasis (max 2-3 sections per page)
- **References**: The brand sits at the intersection of editorial elegance (serif accents, careful typography) and technical precision (data-driven, structured layouts)
- **Anti-references**: Generic SaaS templates (Bootstrap/Tailwind cookie-cutter), overly playful/gamified interfaces (cartoon illustrations, excessive animation, childish feel)

### Design Principles
1. **Clarity over density** — Present data in digestible layers. Never overwhelm. White space is a feature, not waste.
2. **Organic precision** — Ultra-soft forms (always rounded), solid flat colors, subtle shadows. The aesthetic is natural and warm, but the data is sharp and exact.
3. **Purposeful restraint** — Every element earns its place. No decorative gradients, no glow effects, no visual noise. Bio-Lime appears only where it creates meaning.
4. **Typography as identity** — The tension between Inter Tight (technical, geometric) and Libre Baskerville (editorial, elegant) IS the brand. Use it intentionally.
5. **Empowered simplicity** — Complex SEO data, simple interface. The user feels smart, not the tool.
