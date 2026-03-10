"""
Modelo de datos de simbología para capas cartográficas.

Permite configurar colores, grosores, tipos de trazo y marcadores
por categoría de infraestructura o por capa adicional.
"""

# Tipos de trazo disponibles
TIPOS_TRAZO = {
    "Continuo": "-",
    "Discontinuo": "--",
    "Punto-raya": "-.",
    "Punteado": ":",
}

# Marcadores disponibles para puntos
MARCADORES = {
    "Círculo": "o",
    "Cuadrado": "s",
    "Triángulo": "^",
    "Diamante": "D",
    "Estrella": "*",
    "Cruz": "+",
    "X": "x",
}

# Paleta de colores predefinida para categorías
PALETA_CATEGORIAS = [
    "#E74C3C", "#3498DB", "#007932", "#F39C12", "#9B59B6",
    "#1ABC9C", "#E67E22", "#34495E", "#C0392B", "#2980B9",
    "#368f3f", "#D35400", "#8E44AD", "#16A085", "#F1C40F",
]

# Simbología por defecto para capas extra
SIMBOLOGIA_CAPAS_EXTRA = {
    "Hidrografía": {
        "color": "#2980B9",
        "linewidth": 1.0,
        "linestyle": "-",
        "alpha": 0.8,
        "facecolor": "#2980B944",
        "label": "Hidrografía",
    },
    "Vías": {
        "color": "#7F8C8D",
        "linewidth": 1.2,
        "linestyle": "-",
        "alpha": 0.9,
        "facecolor": "#7F8C8D44",
        "label": "Vías / Caminos",
    },
    "Parcelas catastrales": {
        "color": "#D4AC0D",
        "linewidth": 0.6,
        "linestyle": "--",
        "alpha": 0.6,
        "facecolor": "#D4AC0D22",
        "label": "Parcelas catastrales",
    },
    "Zonas protegidas": {
        "color": "#368f3f",
        "linewidth": 1.0,
        "linestyle": "-.",
        "alpha": 0.5,
        "facecolor": "#368f3f33",
        "label": "Zonas protegidas",
    },
}


class ConfigSimbologia:
    """Configuración de simbología para una capa o categoría."""

    def __init__(self, color="#E74C3C", linewidth=1.5, linestyle="-",
                 alpha=1.0, marker="o", markersize=8, facecolor=None,
                 label=""):
        self.color = color
        self.linewidth = float(linewidth)
        self.linestyle = linestyle
        self.alpha = float(alpha)
        self.marker = marker
        self.markersize = float(markersize)
        self.facecolor = facecolor or (color + "55")
        self.label = label

    def to_dict(self) -> dict:
        return {
            "color": self.color,
            "linewidth": self.linewidth,
            "linestyle": self.linestyle,
            "alpha": self.alpha,
            "marker": self.marker,
            "markersize": self.markersize,
            "facecolor": self.facecolor,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConfigSimbologia":
        return cls(**d)


class GestorSimbologia:
    """Gestiona la simbología de todas las capas y categorías."""

    def __init__(self):
        # Simbología por categoría de infraestructura (campo -> {valor: ConfigSimbologia})
        self.categorias = {}
        # Simbología para capas extra (nombre_capa -> ConfigSimbologia)
        self.capas_extra = {}
        # Simbología de montes
        self.montes = ConfigSimbologia(
            color="#1a5c10", linewidth=0.8, facecolor="#229922",
            alpha=0.3, label="Montes",
        )
        # Simbología por categoría de montes (campo -> {valor: ConfigSimbologia})
        self.categorias_montes = {}
        # Simbología por defecto de infraestructuras
        self.infra_fondo = ConfigSimbologia(
            color="#999999", linewidth=0.6, alpha=0.25, label="Otras infraestructuras",
        )

    def generar_por_categoria(self, campo: str, valores: list):
        """Genera simbología automática por categoría de un campo."""
        self.categorias[campo] = {}
        for i, valor in enumerate(valores):
            color = PALETA_CATEGORIAS[i % len(PALETA_CATEGORIAS)]
            self.categorias[campo][str(valor)] = ConfigSimbologia(
                color=color, linewidth=2.0, facecolor=color + "55",
                label=str(valor),
            )

    def generar_por_categoria_montes(self, campo: str, valores: list):
        """Genera simbología automática por categoría para montes."""
        # Usar una paleta diferente (más verde/terrosa) para montes
        paleta_montes = [
            "#1a5c10", "#2E7D32", "#388E3C", "#43A047", "#4CAF50",
            "#66BB6A", "#81C784", "#A5D6A7", "#558B2F", "#33691E",
            "#827717", "#9E9D24", "#AFB42B", "#C0CA33", "#D4E157",
        ]
        self.categorias_montes[campo] = {}
        for i, valor in enumerate(valores):
            color = paleta_montes[i % len(paleta_montes)]
            self.categorias_montes[campo][str(valor)] = ConfigSimbologia(
                color=color, linewidth=0.8, facecolor=color,
                alpha=0.3, label=str(valor),
            )

    def obtener_simbologia_monte(self, campo_cat: str, valor: str) -> ConfigSimbologia:
        """Obtiene la simbología para un monte según su categoría."""
        if campo_cat in self.categorias_montes and str(valor) in self.categorias_montes[campo_cat]:
            return self.categorias_montes[campo_cat][str(valor)]
        return self.montes

    def obtener_simbologia_infra(self, campo_cat: str, valor: str) -> ConfigSimbologia:
        """Obtiene la simbología para una infraestructura según su categoría."""
        if campo_cat in self.categorias and str(valor) in self.categorias[campo_cat]:
            return self.categorias[campo_cat][str(valor)]
        return ConfigSimbologia()

    def obtener_simbologia_capa(self, nombre: str) -> ConfigSimbologia:
        """Obtiene la simbología de una capa extra."""
        if nombre in self.capas_extra:
            return self.capas_extra[nombre]
        if nombre in SIMBOLOGIA_CAPAS_EXTRA:
            d = SIMBOLOGIA_CAPAS_EXTRA[nombre]
            return ConfigSimbologia(**d)
        return ConfigSimbologia(color="#888888", label=nombre)

    def set_simbologia_capa(self, nombre: str, simb: ConfigSimbologia):
        self.capas_extra[nombre] = simb

    def to_dict(self) -> dict:
        return {
            "categorias": {
                campo: {v: s.to_dict() for v, s in vals.items()}
                for campo, vals in self.categorias.items()
            },
            "categorias_montes": {
                campo: {v: s.to_dict() for v, s in vals.items()}
                for campo, vals in self.categorias_montes.items()
            },
            "capas_extra": {n: s.to_dict() for n, s in self.capas_extra.items()},
            "montes": self.montes.to_dict(),
            "infra_fondo": self.infra_fondo.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GestorSimbologia":
        g = cls()
        for campo, vals in d.get("categorias", {}).items():
            g.categorias[campo] = {
                v: ConfigSimbologia.from_dict(s) for v, s in vals.items()
            }
        for campo, vals in d.get("categorias_montes", {}).items():
            g.categorias_montes[campo] = {
                v: ConfigSimbologia.from_dict(s) for v, s in vals.items()
            }
        for nombre, s in d.get("capas_extra", {}).items():
            g.capas_extra[nombre] = ConfigSimbologia.from_dict(s)
        if "montes" in d:
            g.montes = ConfigSimbologia.from_dict(d["montes"])
        if "infra_fondo" in d:
            g.infra_fondo = ConfigSimbologia.from_dict(d["infra_fondo"])
        return g
