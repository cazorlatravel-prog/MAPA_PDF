"""
Definición de plantillas de layout para el plano cartográfico.

Plantilla 1 (Clásica): Mapa arriba, franja inferior con 3 paneles.
Plantilla 2 (Panel lateral): Mapa a la izquierda, panel derecho vertical.
"""

PLANTILLAS_DISPONIBLES = [
    "Plantilla 1 (Clásica)",
    "Plantilla 2 (Panel lateral)",
]

# Configuración de cada plantilla
LAYOUTS = {
    "Plantilla 1 (Clásica)": {
        "descripcion": "Mapa arriba (75%), franja inferior con cajetín, datos y minimapa",
        "tipo": "clasica",
        # GridSpec: 2 filas x 3 columnas
        "nrows": 2,
        "ncols": 3,
        "width_ratios": [0.28, 0.42, 0.30],
        "height_ratios_fn": "ratio_mapa",  # usa RATIO_MAPA_ALTO
        "mapa_pos": (0, slice(None)),       # fila 0, todas las columnas
        "cajetin_pos": (1, 0),              # fila 1, col 0
        "datos_pos": (1, 1),                # fila 1, col 1
        "mini_pos": (1, 2),                 # fila 1, col 2
        "hspace": 0.04,
        "wspace": 0.005,
    },
    "Plantilla 2 (Panel lateral)": {
        "descripcion": "Mapa izquierda (72%), panel lateral derecho con minimapa, datos, leyenda y cajetín",
        "tipo": "lateral",
        # GridSpec: 1 fila x 2 columnas (panel derecho se subdivide internamente)
        "nrows": 1,
        "ncols": 2,
        "width_ratios": [0.72, 0.28],
        "height_ratios_fn": None,
        "mapa_pos": (0, 0),                # fila 0, col 0
        "panel_lateral_pos": (0, 1),        # fila 0, col 1 (se subdivide)
        "hspace": 0.02,
        "wspace": 0.008,
        # Subdivisiones del panel lateral (proporciones verticales)
        "lateral_ratios": [0.28, 0.32, 0.40],  # minimapa, datos, cajetín+escala
    },
}
