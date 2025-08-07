# 🎨 Imágenes y Branding - README

## 📁 Estructura Actual

Se han creado imágenes **PLACEHOLDER/TEMPORALES** para desarrollo:

```
static/images/
├── favicons/
│   └── favicon.svg          # Favicon temporal SVG
├── logos/
│   ├── logo.svg             # Logo principal temporal
│   └── logo-square.svg      # Logo cuadrado temporal
└── social/
    └── og-image.svg         # Imagen social temporal
```

## 🚨 IMPORTANTE: Estas son imágenes temporales

Estas imágenes SVG son **SOLO PARA DESARROLLO** mientras preparas tu branding real.

## 🔄 Cómo reemplazar con tu branding real:

### 1. **Favicon** (Obligatorio)
Reemplaza `static/images/favicons/favicon.svg` y añade:
- `favicon.ico` (multi-size: 16x16, 32x32, 48x48)
- `favicon-16x16.png`
- `favicon-32x32.png`
- `apple-touch-icon.png` (180x180)
- `android-chrome-192x192.png`
- `android-chrome-512x512.png`

**Herramienta recomendada**: https://realfavicongenerator.net/

### 2. **Logos**
Reemplaza estos archivos con tu logo real:
- `logo.svg` → Tu logo principal (formato vectorial preferido)
- `logo.png` → Versión PNG (200x50px aprox, fondo transparente)
- `logo-white.png` → Versión para modo oscuro
- `logo-square.png` → Versión cuadrada (100x100px)

### 3. **Redes Sociales**
Reemplaza:
- `og-image.png` → 1200x630px para Facebook/LinkedIn
- `twitter-card.png` → 1200x600px para Twitter

## ✅ El código ya está preparado

- ✅ Meta tags añadidos a todas las plantillas HTML
- ✅ CSS responsive para logos
- ✅ Fallback automático si faltan imágenes
- ✅ Soporte PWA con manifest.json
- ✅ Open Graph y Twitter Cards configurados

## 🎯 Próximos pasos:

1. **Crear tu logo real** (recomendado formato SVG + PNG)
2. **Generar favicons** con https://realfavicongenerator.net/
3. **Crear imágenes sociales** (1200x630px)
4. **Reemplazar archivos** en las carpetas correspondientes
5. **Probar en navegador** para verificar que todo funciona
6. **Validar SEO** con https://metatags.io/

## 💡 Tips:

- **SVG es preferido** para logos (escalable, mejor calidad)
- **PNG con fondo transparente** para compatibilidad
- **Optimiza imágenes** con https://tinypng.com/
- **Mantén consistencia** en colores y estilo
- **Prueba en dispositivos móviles**

## 🆘 Si necesitas ayuda:

- **Favicon no aparece**: Borra caché del navegador
- **Logo muy grande**: Ajusta CSS en navbar.css
- **Imágenes no cargan**: Verifica rutas en plantillas HTML
- **Meta tags no funcionan**: Valida con metatags.io

## 🎨 Inspiración para tu logo:

- Mantén simplicidad para buena legibilidad
- Usa colores que representen SEO/Analytics
- Asegúrate que se vea bien en tamaños pequeños
- Crea versiones para modo claro y oscuro
