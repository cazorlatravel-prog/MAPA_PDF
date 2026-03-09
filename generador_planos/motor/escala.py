"""
Lógica de selección automática de escala.

Escalas permitidas (solo estas):
    1:5.000 | 1:7.500 | 1:10.000 | 1:15.000 | 1:20.000 | 1:25.000 | 1:30.000

La escala se elige automáticamente según la extensión de la geometría + margen del 20%.
"""

ESCALAS = [5000, 7500, 10000, 15000, 20000, 25000, 30000]

INTERVALOS_GRID = {
    5000: 500,
    7500: 500,
    10000: 1000,
    15000: 1000,
    20000: 2000,
    25000: 2000,
    30000: 5000,
}

# Longitud de la barra de escala gráfica (metros)
BARRA_ESCALA_M = {
    5000: 1000,
    7500: 1000,
    10000: 1000,
    15000: 2000,
    20000: 2000,
    25000: 2000,
    30000: 5000,
}

MARGENES_MM = {"izq": 15, "der": 15, "sup": 10, "inf": 12}

FORMATOS = {
    "A4 Vertical":   (210, 297),
    "A4 Horizontal": (297, 210),
    "A3 Vertical":   (297, 420),
    "A3 Horizontal": (420, 297),
    "A2 Vertical":   (420, 594),
    "A2 Horizontal": (594, 420),
}

# Proporción del mapa principal respecto al ancho/alto útil
RATIO_MAPA_ANCHO = 1.0
RATIO_MAPA_ALTO = 0.75

_CABECERA_MM = 8  # Altura de la cabecera (debe coincidir con maquetacion._CABECERA_MM)


def seleccionar_escala(geom, formato_key: str, escala_manual: int = None) -> int:
    """Elige la escala más ajustada de la lista ESCALAS.

    Si escala_manual está definida, la devuelve directamente (override del usuario).
    Si no, calcula automáticamente según la extensión de la geometría.
    """
    if escala_manual is not None and escala_manual > 0:
        return escala_manual

    fmt_mm = FORMATOS[formato_key]

    ancho_util_mm = fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
    alto_util_mm = fmt_mm[1] - MARGENES_MM["sup"] - MARGENES_MM["inf"]

    ancho_mapa_mm = ancho_util_mm * RATIO_MAPA_ANCHO
    alto_mapa_mm = (alto_util_mm - _CABECERA_MM) * RATIO_MAPA_ALTO

    bounds = geom.bounds  # (minx, miny, maxx, maxy) en metros ETRS89
    ext_x = bounds[2] - bounds[0]
    ext_y = bounds[3] - bounds[1]

    # Margen del 20%
    ext_x *= 1.20
    ext_y *= 1.20

    # Geometrías punto: usar radio mínimo de 500 m
    if ext_x < 1.0 and ext_y < 1.0:
        ext_x = ext_y = 1000  # 500 m a cada lado del centro

    for escala in ESCALAS:
        # metros que caben: mm_papel * (escala / 1000)
        cap_x = (ancho_mapa_mm / 1000.0) * escala
        cap_y = (alto_mapa_mm / 1000.0) * escala
        if cap_x >= ext_x and cap_y >= ext_y:
            return escala

    return ESCALAS[-1]
