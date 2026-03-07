"""
Layout matplotlib del plano cartográfico profesional.

Estructura del plano (GridSpec):
    ┌──────────────────────────────────────────────────────────┐
    │  CABECERA: Logo org. | Título infra | Nº plano           │
    ├─────────────────────────────┬────────────────────────────┤
    │                             │                            │
    │     MAPA PRINCIPAL (63%)    │  PANEL ATRIBUTOS (37%)     │
    │     con grid UTM            │  tabla campos + escala     │
    │     + fondo WMS             │  + CRS                     │
    │     + capa montes           ├────────────────────────────┤
    │     + infraestructura       │  MAPA DE POSICIÓN          │
    │       resaltada             │  (España con punto rojo)   │
    ├─────────────────────────────┴────────────────────────────┤
    │  BARRA ESCALA GRÁFICA + NORTE + CRÉDITOS                 │
    ├──────────────────────────────────────────────────────────┤
    │  MARCO DOBLE EXTERIOR (profesional)                      │
    └──────────────────────────────────────────────────────────┘
"""

import math
from datetime import date

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch, Rectangle
from pyproj import Transformer

from .escala import (
    MARGENES_MM, FORMATOS, INTERVALOS_GRID, BARRA_ESCALA_M,
    RATIO_MAPA_ANCHO, RATIO_MAPA_ALTO,
)

# Campos del shapefile -> etiquetas en el plano
ETIQUETAS_CAMPOS = {
    "Provincia": "Provincia",
    "Municipio": "Municipio",
    "Monte": "Monte",
    "Cod_Monte": "Código Monte",
    "CEDEFO": "CEDEFO",
    "Cod_Infoca": "Cód. INFOCA",
    "Nombre_Infra": "Nombre Infraestructura",
    "Superficie": "Superficie (ha)",
    "Longitud": "Longitud (m)",
    "Ancho": "Ancho (m)",
    "Tipo_Trabajos": "Tipo de Trabajos",
}

# Contorno simplificado de España (lon/lat)
SPAIN_X = [
    -9.2, -8.8, -8.2, -7.5, -6.8, -5.5, -4.5, -3.3,
    -1.8, -0.5, 0.3, 1.8, 3.3, 3.3, 3.0, 2.0,
    1.0, 0.2, -0.8, -1.7, -2.0, -1.8, -1.6, -2.5,
    -4.5, -6.0, -7.2, -8.5, -9.2, -9.2,
]
SPAIN_Y = [
    41.8, 43.7, 43.7, 43.7, 43.7, 43.7, 43.5, 43.4,
    43.5, 43.4, 42.8, 42.3, 42.4, 41.0, 40.5, 40.8,
    40.7, 40.0, 38.8, 37.5, 37.0, 36.6, 36.2, 36.0,
    36.0, 36.2, 36.7, 37.5, 39.0, 41.8,
]

DPI = 150


class MaquetadorPlano:
    """Crea la maquetación completa del plano cartográfico."""

    def __init__(self, formato_key: str, escala: int):
        self.formato_key = formato_key
        self.fmt_mm = FORMATOS[formato_key]
        self.escala = escala
        self.fig = None
        self.ax_map = None
        self.ax_info = None
        self.ax_mini = None
        self.ax_esc = None

    def crear_figura(self):
        """Crea la figura matplotlib y devuelve los ejes."""
        fig_w_in = self.fmt_mm[0] / 25.4
        fig_h_in = self.fmt_mm[1] / 25.4
        self.fig = plt.figure(figsize=(fig_w_in, fig_h_in), dpi=DPI, facecolor="white")

        gs = gridspec.GridSpec(
            2, 2,
            figure=self.fig,
            left=MARGENES_MM["izq"] / self.fmt_mm[0],
            right=1 - MARGENES_MM["der"] / self.fmt_mm[0],
            top=1 - MARGENES_MM["sup"] / self.fmt_mm[1],
            bottom=MARGENES_MM["inf"] / self.fmt_mm[1],
            width_ratios=[0.63, 0.37],
            height_ratios=[RATIO_MAPA_ALTO, 1 - RATIO_MAPA_ALTO],
            hspace=0.06,
            wspace=0.04,
        )

        self.ax_map = self.fig.add_subplot(gs[0, 0])
        self.ax_info = self.fig.add_subplot(gs[0, 1])
        self.ax_mini = self.fig.add_subplot(gs[1, 1])
        self.ax_esc = self.fig.add_subplot(gs[1, 0])

        return self.fig, self.ax_map, self.ax_info, self.ax_mini, self.ax_esc

    def calcular_extension_mapa(self, geom):
        """Calcula los límites exactos del mapa para la escala métrica real.

        1 mm en papel = escala/1000 metros en el terreno.
        Los límites se fijan exactamente para que matplotlib no reajuste.
        """
        cx, cy = geom.centroid.x, geom.centroid.y

        ancho_util_mm = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        alto_util_mm = self.fmt_mm[1] - MARGENES_MM["sup"] - MARGENES_MM["inf"]

        ancho_mapa_mm = ancho_util_mm * RATIO_MAPA_ANCHO
        alto_mapa_mm = alto_util_mm * RATIO_MAPA_ALTO

        # Metros que caben: mm * (escala / 1000)
        semiancho_m = (ancho_mapa_mm / 1000.0) * self.escala / 2
        semialto_m = (alto_mapa_mm / 1000.0) * self.escala / 2

        xmin = cx - semiancho_m
        xmax = cx + semiancho_m
        ymin = cy - semialto_m
        ymax = cy + semialto_m

        return xmin, xmax, ymin, ymax

    def configurar_mapa_principal(self, xmin, xmax, ymin, ymax):
        """Configura el eje del mapa principal con límites exactos."""
        self.ax_map.set_xlim(xmin, xmax)
        self.ax_map.set_ylim(ymin, ymax)
        self.ax_map.set_aspect("equal")

        # Fijar límites para que matplotlib no reajuste
        self.ax_map.set_autoscale_on(False)

        # Estilo del borde
        self.ax_map.tick_params(which="both", length=0)
        for spine in self.ax_map.spines.values():
            spine.set_linewidth(0.8)
            spine.set_color("#333333")

    def dibujar_grid_utm(self, xmin, xmax, ymin, ymax):
        """Dibuja grid de coordenadas UTM con cruces en intersecciones."""
        intervalo = INTERVALOS_GRID.get(self.escala, 1000)

        # Líneas verticales
        x0 = math.ceil(xmin / intervalo) * intervalo
        xs = np.arange(x0, xmax, intervalo)
        for x in xs:
            self.ax_map.axvline(
                x, color="#2255AA", linewidth=0.25, linestyle="--",
                alpha=0.5, zorder=2,
            )
            self.ax_map.text(
                x, ymin + (ymax - ymin) * 0.01, f"{int(x):,}",
                ha="center", va="bottom", fontsize=5.5, color="#2255AA",
                rotation=90, alpha=0.8,
            )

        # Líneas horizontales
        y0 = math.ceil(ymin / intervalo) * intervalo
        ys = np.arange(y0, ymax, intervalo)
        for y in ys:
            self.ax_map.axhline(
                y, color="#2255AA", linewidth=0.25, linestyle="--",
                alpha=0.5, zorder=2,
            )
            self.ax_map.text(
                xmin + (xmax - xmin) * 0.005, y, f"{int(y):,}",
                ha="left", va="center", fontsize=5.5, color="#2255AA",
                alpha=0.8,
            )

        # Cruces en intersecciones
        for x in xs:
            for y in ys:
                self.ax_map.plot(
                    x, y, "+", color="#2255AA", markersize=4,
                    markeredgewidth=0.4, alpha=0.6, zorder=3,
                )

    def dibujar_panel_atributos(self, row, campos_visibles, campo_mapeo=None):
        """Dibuja la tabla de atributos en el panel derecho.

        campo_mapeo: dict opcional {campo_real: campo_shapefile} para
                     shapefiles con nombres de campo distintos.
        """
        ax = self.ax_info
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Fondo
        fondo = FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0.01",
            facecolor="#F8F9FA", edgecolor="#2C3E50", linewidth=1.2, zorder=0,
        )
        ax.add_patch(fondo)

        # Título
        ax.text(
            0.5, 0.97, "DATOS DE LA INFRAESTRUCTURA",
            ha="center", va="top", fontsize=7.5, fontweight="bold",
            color="white", transform=ax.transAxes,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#2C3E50", edgecolor="none"),
        )

        # Filtrar campos que existen
        campos_orden = list(ETIQUETAS_CAMPOS.keys())
        campos_mostrar = [c for c in campos_orden if c in campos_visibles]
        n = len(campos_mostrar)
        if n == 0:
            return

        y_start = 0.90
        row_h = (y_start - 0.12) / max(n, 1)

        for i, campo in enumerate(campos_mostrar):
            y = y_start - i * row_h
            # Soporte para mapeo de campos
            campo_real = campo
            if campo_mapeo and campo in campo_mapeo:
                campo_real = campo_mapeo[campo]
            valor = str(row.get(campo_real, "\u2014"))
            etiq = ETIQUETAS_CAMPOS.get(campo, campo)

            # Fondo alterno
            if i % 2 == 0:
                rect = Rectangle(
                    (0.01, y - row_h + 0.005), 0.98, row_h - 0.005,
                    facecolor="#E8F4F8", edgecolor="none", zorder=1,
                )
                ax.add_patch(rect)

            ax.text(
                0.04, y - row_h / 2, etiq + ":",
                ha="left", va="center", fontsize=6.5, fontweight="bold",
                color="#2C3E50", transform=ax.transAxes, zorder=2,
            )
            ax.text(
                0.98, y - row_h / 2, valor,
                ha="right", va="center", fontsize=6.5,
                color="#1A1A2E", transform=ax.transAxes, zorder=2,
                wrap=True,
            )

        # Líneas separadoras
        for i in range(1, n):
            y_line = y_start - i * row_h
            ax.axhline(
                y=y_line, xmin=0.02, xmax=0.98, color="#CCCCCC",
                linewidth=0.4, transform=ax.transAxes, zorder=2,
            )

        # Sistema de coordenadas
        ax.text(
            0.5, 0.03,
            "Sistema de Referencia: ETRS89 / UTM Huso 30N (EPSG:25830)",
            ha="center", va="bottom", fontsize=5.5, color="#555555",
            style="italic", transform=ax.transAxes,
        )

        # Escala
        ax.text(
            0.5, 0.07, f"Escala 1:{self.escala:,}",
            ha="center", va="bottom", fontsize=7, fontweight="bold",
            color="#2C3E50", transform=ax.transAxes,
        )

    def dibujar_mapa_posicion(self, cx, cy):
        """Mapa de posición: contorno de España + punto rojo."""
        ax = self.ax_mini
        ax.set_xlim(-9.5, 4.5)
        ax.set_ylim(35.5, 44.0)
        ax.set_aspect("equal")
        ax.set_facecolor("#D6EAF8")

        for spine in ax.spines.values():
            spine.set_linewidth(1.0)
            spine.set_color("#2C3E50")

        ax.tick_params(labelbottom=False, labelleft=False, bottom=False, left=False)

        # Contorno de España
        ax.fill(SPAIN_X, SPAIN_Y, color="#C8E6C9", edgecolor="#2C3E50",
                linewidth=0.6, alpha=0.9)

        # Punto rojo (convertir UTM a geográfico)
        try:
            transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(cx, cy)
            ax.plot(lon, lat, "o", color="white", markersize=8, zorder=5)
            ax.plot(lon, lat, "o", color="#E74C3C", markersize=5,
                    zorder=6, markeredgecolor="white", markeredgewidth=0.5)
        except Exception:
            pass

        ax.set_title("LOCALIZACIÓN", fontsize=6, fontweight="bold",
                      color="#2C3E50", pad=2)

    def dibujar_barra_escala(self, proveedor: str):
        """Barra de escala gráfica bicolor + Norte + créditos."""
        ax = self.ax_esc
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        barra_m = BARRA_ESCALA_M.get(self.escala, 1000)

        # Calcular tamaño de barra basándose en DPI y tamaño real de figura
        ancho_util_mm = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        fig_w_mm = ancho_util_mm * RATIO_MAPA_ANCHO
        barra_mm_papel = (barra_m / self.escala) * 1000  # mm en papel
        frac = min(barra_mm_papel / fig_w_mm, 0.4)

        x0, y0 = 0.02, 0.55

        # Barra bicolor
        n_seg = 4
        seg = frac / n_seg
        for i in range(n_seg):
            color = "#1A1A2E" if i % 2 == 0 else "white"
            rect = Rectangle(
                (x0 + i * seg, y0), seg, 0.18,
                facecolor=color, edgecolor="#1A1A2E", linewidth=0.6,
            )
            ax.add_patch(rect)

        # Etiquetas
        ax.text(x0, y0 - 0.12, "0", ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac / 2, y0 - 0.12, f"{barra_m // 2} m",
                ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac, y0 - 0.12, f"{barra_m} m",
                ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac / 2, y0 + 0.28, f"Escala 1:{self.escala:,}",
                ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1A1A2E")

        # Flecha de Norte
        ax.annotate(
            "", xy=(0.55, 0.95), xytext=(0.55, 0.50),
            arrowprops=dict(arrowstyle="->", color="#1A1A2E", lw=1.5),
        )
        ax.text(0.55, 0.98, "N", ha="center", va="top",
                fontsize=11, fontweight="bold", color="#1A1A2E")

        # Créditos
        fecha = date.today().strftime("%d/%m/%Y")
        ax.text(
            0.98, 0.05,
            f"Cartograf\u00eda base: {proveedor} | ETRS89 UTM H30N | Fecha: {fecha}",
            ha="right", va="bottom", fontsize=5.5, color="#666666", style="italic",
        )

    def dibujar_cabecera(self, row):
        """Banda superior con logo org., título y nº de plano."""
        # Calcular posición dinámica basada en el GridSpec real
        izq_frac = MARGENES_MM["izq"] / self.fmt_mm[0]
        der_frac = MARGENES_MM["der"] / self.fmt_mm[0]
        sup_frac = MARGENES_MM["sup"] / self.fmt_mm[1]

        ax_cab = self.fig.add_axes([
            izq_frac,
            1 - sup_frac,
            1 - izq_frac - der_frac,
            (sup_frac - 2 / self.fmt_mm[1]),
        ])
        ax_cab.set_xlim(0, 1)
        ax_cab.set_ylim(0, 1)
        ax_cab.axis("off")

        ax_cab.add_patch(Rectangle((0, 0), 1, 1, facecolor="#1C2333",
                                    edgecolor="#2ECC71", linewidth=1.2))

        # Logo / Título organización
        ax_cab.text(
            0.01, 0.5, "CONSEJER\u00cdA DE SOSTENIBILIDAD\nJUNTA DE ANDALUC\u00cdA",
            ha="left", va="center", fontsize=6.5, fontweight="bold",
            color="#2ECC71", linespacing=1.4,
        )

        # Título del plano
        nombre = str(row.get("Nombre_Infra", "INFRAESTRUCTURA FORESTAL"))
        ax_cab.text(0.5, 0.65, nombre.upper(), ha="center", va="center",
                    fontsize=9, fontweight="bold", color="white")
        ax_cab.text(0.5, 0.25, "PLANO DE INFRAESTRUCTURA FORESTAL",
                    ha="center", va="center", fontsize=6.5, color="#95A5A6")

        # Número de plano
        num_plano = row.name + 1 if hasattr(row, "name") and isinstance(row.name, int) else 1
        ax_cab.text(0.99, 0.5, f"Plano n\u00ba\n{num_plano:04d}",
                    ha="right", va="center", fontsize=7, fontweight="bold",
                    color="#2ECC71")

    def dibujar_marcos(self):
        """Marco exterior e interior profesional (doble)."""
        ax_marco = self.fig.add_axes([0, 0, 1, 1])
        ax_marco.set_xlim(0, self.fmt_mm[0])
        ax_marco.set_ylim(0, self.fmt_mm[1])
        ax_marco.axis("off")
        ax_marco.set_zorder(-10)

        # Marco doble exterior
        ax_marco.add_patch(Rectangle(
            (3, 3), self.fmt_mm[0] - 6, self.fmt_mm[1] - 6,
            fill=False, edgecolor="#1C2333", linewidth=2.0,
        ))
        ax_marco.add_patch(Rectangle(
            (5, 5), self.fmt_mm[0] - 10, self.fmt_mm[1] - 10,
            fill=False, edgecolor="#2ECC71", linewidth=0.5,
        ))

    def guardar(self, ruta_out: str):
        """Guarda la figura como PDF."""
        self.fig.savefig(
            ruta_out, format="pdf", dpi=DPI,
            bbox_inches="tight", facecolor="white",
        )
        plt.close(self.fig)
