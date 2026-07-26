"""
CLICANDSEO — Paleta de datos de marca (lado servidor).

El navegador lee estos colores de los tokens `--cs-series-*` de
`static/brand-dashboard-tokens.css` a través de `CSChartTheme`. Pero el backend
TAMBIÉN pinta: los datasets que viajan en JSON a Chart.js y, sobre todo, el PDF
de ReportLab, que no tiene CSS. Este módulo es la única copia servidor de esa
paleta; antes estaba repetida como literales en 8 sitios de
`llm_monitoring_routes.py` con comentarios de "mantener sincronizado".

El ORDEN es el mecanismo de accesibilidad, no una preferencia estética: estos
tonos pasan los checks de separación bajo protanopia y deuteranopia (peor par
ΔE 9.2). No reordenar ni añadir sin re-validar — la paleta anterior hacía que
dos series fueran el mismo color para quien tiene daltonismo (ΔE 0.9).

Cualquier cambio aquí debe replicarse en `brand-dashboard-tokens.css`.
"""

# Slots 1-4: paleta categórica validada. El slot 1 se reserva siempre a la
# marca propia, para que su color no cambie de una gráfica a otra.
SERIES = [
    '#2a78d6',  # --cs-series-1 · azul    (marca propia)
    '#1baf7a',  # --cs-series-2 · aqua
    '#eb6834',  # --cs-series-3 · naranja
    '#4a3aa7',  # --cs-series-4 · violeta
]

# Slots 5-6: ampliación para donut y barras, donde solo importa la separación
# entre pares adyacentes. No usar en dispersión ni en líneas superpuestas.
SERIES_EXTENDED = SERIES + [
    '#eda100',  # --cs-series-5 · ámbar
    '#e87ba4',  # --cs-series-6 · rosa
]

BRAND = SERIES[0]
"""Color de la marca propia. Siempre el slot 1."""

COMPETITORS = SERIES_EXTENDED[1:]
"""Colores para competidores, en orden. El slot 1 queda para la marca."""


def hex_to_rgba(hex_color, alpha):
    """'#2a78d6' + 0.1 -> 'rgba(42, 120, 214, 0.1)' (para los fills de Chart.js)."""
    h = hex_color.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f'rgba({r}, {g}, {b}, {alpha})'
