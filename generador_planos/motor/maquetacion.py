"""
Layout matplotlib del plano cartográfico profesional.

Incluye: leyenda automática, etiquetas, cajetín configurable, numeración de
vértices, norte geográfico con declinación magnética, perfil topográfico
y portada para PDF multipágina.
"""

import math
from datetime import date

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D
from pyproj import Transformer

from .escala import (
    MARGENES_MM, FORMATOS, INTERVALOS_GRID, BARRA_ESCALA_M,
    RATIO_MAPA_ANCHO, RATIO_MAPA_ALTO,
)

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

# Declinación magnética aprox. para España (grados Este, 2024-2026)
DECLINACION_MAGNETICA_ESPANA = {
    "oeste": 0.5,    # Galicia/Portugal
    "centro": 1.0,   # Madrid/Castilla
    "este": 1.8,     # Cataluña/Baleares
    "sur": 0.8,      # Andalucía
}


def _estimar_declinacion(lon_deg):
    """Estima la declinación magnética según la longitud geográfica."""
    if lon_deg < -5:
        return DECLINACION_MAGNETICA_ESPANA["oeste"]
    elif lon_deg < -1:
        return DECLINACION_MAGNETICA_ESPANA["centro"]
    elif lon_deg < 2:
        return DECLINACION_MAGNETICA_ESPANA["sur"]
    else:
        return DECLINACION_MAGNETICA_ESPANA["este"]


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
        fig_w_in = self.fmt_mm[0] / 25.4
        fig_h_in = self.fmt_mm[1] / 25.4
        self.fig = plt.figure(figsize=(fig_w_in, fig_h_in), dpi=DPI, facecolor="white")

        gs = gridspec.GridSpec(
            2, 2, figure=self.fig,
            left=MARGENES_MM["izq"] / self.fmt_mm[0],
            right=1 - MARGENES_MM["der"] / self.fmt_mm[0],
            top=1 - MARGENES_MM["sup"] / self.fmt_mm[1],
            bottom=MARGENES_MM["inf"] / self.fmt_mm[1],
            width_ratios=[0.63, 0.37],
            height_ratios=[RATIO_MAPA_ALTO, 1 - RATIO_MAPA_ALTO],
            hspace=0.06, wspace=0.04,
        )

        self.ax_map = self.fig.add_subplot(gs[0, 0])
        self.ax_info = self.fig.add_subplot(gs[0, 1])
        self.ax_mini = self.fig.add_subplot(gs[1, 1])
        self.ax_esc = self.fig.add_subplot(gs[1, 0])

        return self.fig, self.ax_map, self.ax_info, self.ax_mini, self.ax_esc

    def calcular_extension_mapa(self, geom):
        cx, cy = geom.centroid.x, geom.centroid.y
        ancho_util_mm = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        alto_util_mm = self.fmt_mm[1] - MARGENES_MM["sup"] - MARGENES_MM["inf"]
        ancho_mapa_mm = ancho_util_mm * RATIO_MAPA_ANCHO
        alto_mapa_mm = alto_util_mm * RATIO_MAPA_ALTO
        semiancho_m = (ancho_mapa_mm / 1000.0) * self.escala / 2
        semialto_m = (alto_mapa_mm / 1000.0) * self.escala / 2
        return cx - semiancho_m, cx + semiancho_m, cy - semialto_m, cy + semialto_m

    def configurar_mapa_principal(self, xmin, xmax, ymin, ymax):
        self.ax_map.set_xlim(xmin, xmax)
        self.ax_map.set_ylim(ymin, ymax)
        self.ax_map.set_aspect("equal")
        self.ax_map.set_autoscale_on(False)
        self.ax_map.tick_params(which="both", length=0)
        for spine in self.ax_map.spines.values():
            spine.set_linewidth(0.8)
            spine.set_color("#333333")

    def dibujar_grid_utm(self, xmin, xmax, ymin, ymax):
        intervalo = INTERVALOS_GRID.get(self.escala, 1000)
        x0 = math.ceil(xmin / intervalo) * intervalo
        xs = np.arange(x0, xmax, intervalo)
        for x in xs:
            self.ax_map.axvline(x, color="#2255AA", linewidth=0.25,
                                 linestyle="--", alpha=0.5, zorder=2)
            self.ax_map.text(x, ymin + (ymax - ymin) * 0.01, f"{int(x):,}",
                              ha="center", va="bottom", fontsize=5.5,
                              color="#2255AA", rotation=90, alpha=0.8)
        y0 = math.ceil(ymin / intervalo) * intervalo
        ys = np.arange(y0, ymax, intervalo)
        for y in ys:
            self.ax_map.axhline(y, color="#2255AA", linewidth=0.25,
                                 linestyle="--", alpha=0.5, zorder=2)
            self.ax_map.text(xmin + (xmax - xmin) * 0.005, y, f"{int(y):,}",
                              ha="left", va="center", fontsize=5.5,
                              color="#2255AA", alpha=0.8)
        for x in xs:
            for y in ys:
                self.ax_map.plot(x, y, "+", color="#2255AA", markersize=4,
                                  markeredgewidth=0.4, alpha=0.6, zorder=3)

    # ── Etiquetas en el mapa ────────────────────────────────────────────

    def dibujar_etiquetas_infra(self, gdf_sel, campo_etiqueta="Nombre_Infra",
                                 campo_mapeo=None):
        """Dibuja etiquetas con nombre/código sobre cada infraestructura."""
        campo_real = campo_etiqueta
        if campo_mapeo and campo_etiqueta in campo_mapeo:
            campo_real = campo_mapeo[campo_etiqueta]

        for _, row in gdf_sel.iterrows():
            geom = row.geometry
            if geom is None:
                continue
            texto = str(row.get(campo_real, ""))
            if not texto or texto == "nan":
                continue
            # Truncar si es muy largo
            if len(texto) > 25:
                texto = texto[:24] + "\u2026"
            cx, cy = geom.centroid.x, geom.centroid.y
            self.ax_map.annotate(
                texto, xy=(cx, cy), fontsize=4.5, fontweight="bold",
                color="#1A1A2E", ha="center", va="bottom", zorder=8,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor="#666666", linewidth=0.3, alpha=0.85),
            )

    # ── Numeración de vértices ──────────────────────────────────────────

    def dibujar_vertices_numerados(self, geom):
        """Numera los vértices de polígonos/líneas y devuelve tabla de coords.

        Devuelve lista de (nº, x_utm, y_utm) para mostrar en tabla.
        """
        coords = []
        geom_type = str(geom.geom_type).lower()

        if "polygon" in geom_type:
            if hasattr(geom, "exterior"):
                raw = list(geom.exterior.coords)
            elif hasattr(geom, "geoms"):
                raw = list(geom.geoms[0].exterior.coords)
            else:
                return []
        elif "line" in geom_type or "string" in geom_type:
            if hasattr(geom, "coords"):
                raw = list(geom.coords)
            elif hasattr(geom, "geoms"):
                raw = list(geom.geoms[0].coords)
            else:
                return []
        else:
            return []

        # Limitar a 20 vértices para no saturar el plano
        step = max(1, len(raw) // 20)
        vertices = raw[::step]
        if raw[-1] not in vertices:
            vertices.append(raw[-1])

        for i, (x, y, *_rest) in enumerate(vertices, 1):
            self.ax_map.plot(x, y, "s", color="#E74C3C", markersize=3,
                              zorder=9, markeredgecolor="white",
                              markeredgewidth=0.3)
            self.ax_map.annotate(
                str(i), xy=(x, y), fontsize=4, fontweight="bold",
                color="white", ha="center", va="center", zorder=10,
                bbox=dict(boxstyle="circle,pad=0.15", facecolor="#E74C3C",
                          edgecolor="none"),
                xytext=(5, 5), textcoords="offset points",
            )
            coords.append((i, x, y))

        return coords

    # ── Leyenda automática ──────────────────────────────────────────────

    def dibujar_leyenda(self, items_leyenda, stats_resumen=None):
        """Dibuja una leyenda en la esquina inferior izquierda del mapa.

        items_leyenda: lista de (label, color, geom_type, linestyle, marker, facecolor)
        stats_resumen: dict con estadísticas del grupo (opcional)
        """
        handles = []
        for label, color, geom_type, linestyle, marker, facecolor in items_leyenda:
            if "point" in geom_type:
                h = Line2D([0], [0], marker=marker or "o", color="w",
                           markerfacecolor=color, markersize=5, label=label)
            elif "line" in geom_type or "string" in geom_type:
                h = Line2D([0], [0], color=color, linewidth=1.5,
                           linestyle=linestyle or "-", label=label)
            else:
                h = Line2D([0], [0], marker="s", color="w",
                           markerfacecolor=facecolor or color, markersize=8,
                           markeredgecolor=color, markeredgewidth=0.8,
                           label=label)
            handles.append(h)

        if handles:
            leg = self.ax_map.legend(
                handles=handles, loc="lower left", fontsize=5,
                frameon=True, framealpha=0.9, facecolor="white",
                edgecolor="#CCCCCC", borderpad=0.5, labelspacing=0.4,
            )
            leg.set_zorder(15)

        # Resumen estadístico si hay
        if stats_resumen:
            lines = []
            if "total_longitud_km" in stats_resumen:
                lines.append(f"Long. total: {stats_resumen['total_longitud_km']:.2f} km")
            if "total_superficie_ha" in stats_resumen:
                lines.append(f"Sup. total: {stats_resumen['total_superficie_ha']:.2f} ha")
            if "num_infraestructuras" in stats_resumen:
                lines.append(f"N\u00ba infra.: {stats_resumen['num_infraestructuras']}")

            if lines:
                texto_stats = "\n".join(lines)
                self.ax_map.text(
                    0.01, 0.01, texto_stats, transform=self.ax_map.transAxes,
                    fontsize=4.5, va="bottom", ha="left", color="#333333",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor="#CCCCCC", alpha=0.9),
                    zorder=15,
                )

    # ── Panel de atributos ──────────────────────────────────────────────

    def dibujar_panel_atributos(self, row, campos_visibles, campo_mapeo=None):
        self.dibujar_panel_atributos_multi([row], campos_visibles, campo_mapeo)

    def dibujar_panel_atributos_multi(self, rows, campos_visibles, campo_mapeo=None):
        ax = self.ax_info
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        fondo = FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0.01",
            facecolor="#F8F9FA", edgecolor="#2C3E50", linewidth=1.2, zorder=0,
        )
        ax.add_patch(fondo)

        n_rows = len(rows)
        es_multi = n_rows > 1
        titulo = "DATOS DE LAS INFRAESTRUCTURAS" if es_multi else "DATOS DE LA INFRAESTRUCTURA"
        ax.text(0.5, 0.97, titulo, ha="center", va="top", fontsize=7.5,
                fontweight="bold", color="white", transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#2C3E50", edgecolor="none"))

        campos_orden = list(ETIQUETAS_CAMPOS.keys())
        campos_mostrar = [c for c in campos_orden if c in campos_visibles]
        n_campos = len(campos_mostrar)
        if n_campos == 0:
            return

        def _resolver(campo):
            if campo_mapeo and campo in campo_mapeo:
                return campo_mapeo[campo]
            return campo

        if not es_multi:
            row = rows[0]
            y_start = 0.90
            row_h = (y_start - 0.12) / max(n_campos, 1)
            for i, campo in enumerate(campos_mostrar):
                y = y_start - i * row_h
                valor = str(row.get(_resolver(campo), "\u2014"))
                etiq = ETIQUETAS_CAMPOS.get(campo, campo)
                if i % 2 == 0:
                    ax.add_patch(Rectangle(
                        (0.01, y - row_h + 0.005), 0.98, row_h - 0.005,
                        facecolor="#E8F4F8", edgecolor="none", zorder=1))
                ax.text(0.04, y - row_h / 2, etiq + ":", ha="left", va="center",
                        fontsize=6.5, fontweight="bold", color="#2C3E50",
                        transform=ax.transAxes, zorder=2)
                ax.text(0.98, y - row_h / 2, valor, ha="right", va="center",
                        fontsize=6.5, color="#1A1A2E", transform=ax.transAxes,
                        zorder=2, wrap=True)
            for i in range(1, n_campos):
                y_line = y_start - i * row_h
                ax.plot([0.02, 0.98], [y_line, y_line],
                        color="#CCCCCC", linewidth=0.4,
                        transform=ax.transAxes, zorder=2)
        else:
            max_cols = min(n_campos, 6)
            campos_tabla = campos_mostrar[:max_cols]
            y_start = 0.90
            total_filas = 1 + n_rows
            row_h = (y_start - 0.12) / max(total_filas, 1)
            font_size = max(4.0, min(6.0, 6.0 - (n_rows - 3) * 0.3))
            x_left, x_right = 0.02, 0.98
            col_w = (x_right - x_left) / max(len(campos_tabla), 1)

            ax.add_patch(Rectangle(
                (x_left, y_start - row_h), x_right - x_left, row_h,
                facecolor="#2C3E50", edgecolor="none", zorder=1))
            for j, campo in enumerate(campos_tabla):
                etiq = ETIQUETAS_CAMPOS.get(campo, campo)
                if len(etiq) > 12:
                    etiq = etiq[:11] + "."
                ax.text(x_left + j * col_w + col_w / 2, y_start - row_h / 2,
                        etiq, ha="center", va="center", fontsize=font_size,
                        fontweight="bold", color="white",
                        transform=ax.transAxes, zorder=2)

            for r_idx, row in enumerate(rows):
                y = y_start - (1 + r_idx) * row_h
                if r_idx % 2 == 0:
                    ax.add_patch(Rectangle(
                        (x_left, y - row_h + 0.002), x_right - x_left, row_h - 0.002,
                        facecolor="#E8F4F8", edgecolor="none", zorder=1))
                for j, campo in enumerate(campos_tabla):
                    valor = str(row.get(_resolver(campo), "\u2014"))
                    if len(valor) > 18:
                        valor = valor[:17] + "\u2026"
                    ax.text(x_left + j * col_w + col_w / 2, y - row_h / 2,
                            valor, ha="center", va="center", fontsize=font_size,
                            color="#1A1A2E", transform=ax.transAxes, zorder=2)

            for r_idx in range(total_filas + 1):
                y_line = y_start - r_idx * row_h
                ax.plot([x_left, x_right], [y_line, y_line],
                        color="#AAAAAA", linewidth=0.3,
                        transform=ax.transAxes, zorder=2)
            for j in range(len(campos_tabla) + 1):
                x_line = x_left + j * col_w
                ax.plot([x_line, x_line],
                        [y_start, y_start - total_filas * row_h],
                        color="#AAAAAA", linewidth=0.3,
                        transform=ax.transAxes, zorder=2)
            ax.text(0.5, y_start - total_filas * row_h - 0.02,
                    f"{n_rows} infraestructuras", ha="center", va="top",
                    fontsize=5.5, color="#555555", style="italic",
                    transform=ax.transAxes)

        ax.text(0.5, 0.03,
                "Sistema de Referencia: ETRS89 / UTM Huso 30N (EPSG:25830)",
                ha="center", va="bottom", fontsize=5.5, color="#555555",
                style="italic", transform=ax.transAxes)
        ax.text(0.5, 0.07, f"Escala 1:{self.escala:,}", ha="center",
                va="bottom", fontsize=7, fontweight="bold", color="#2C3E50",
                transform=ax.transAxes)

    # ── Mapa de posición ────────────────────────────────────────────────

    def dibujar_mapa_posicion(self, cx, cy):
        ax = self.ax_mini
        ax.set_xlim(-9.5, 4.5)
        ax.set_ylim(35.5, 44.0)
        ax.set_aspect("equal")
        ax.set_facecolor("#D6EAF8")
        for spine in ax.spines.values():
            spine.set_linewidth(1.0)
            spine.set_color("#2C3E50")
        ax.tick_params(labelbottom=False, labelleft=False, bottom=False, left=False)
        ax.fill(SPAIN_X, SPAIN_Y, color="#C8E6C9", edgecolor="#2C3E50",
                linewidth=0.6, alpha=0.9)
        try:
            transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(cx, cy)
            ax.plot(lon, lat, "o", color="white", markersize=8, zorder=5)
            ax.plot(lon, lat, "o", color="#E74C3C", markersize=5, zorder=6,
                    markeredgecolor="white", markeredgewidth=0.5)
        except Exception:
            pass
        ax.set_title("LOCALIZACIÓN", fontsize=6, fontweight="bold",
                      color="#2C3E50", pad=2)

    # ── Barra de escala + Norte con declinación magnética ───────────────

    def dibujar_barra_escala(self, proveedor: str, cx_utm=None, cy_utm=None,
                              cajetin=None):
        ax = self.ax_esc
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        barra_m = BARRA_ESCALA_M.get(self.escala, 1000)
        ancho_util_mm = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        fig_w_mm = ancho_util_mm * RATIO_MAPA_ANCHO
        barra_mm_papel = (barra_m / self.escala) * 1000
        frac = min(barra_mm_papel / fig_w_mm, 0.4)
        x0, y0 = 0.02, 0.55

        n_seg = 4
        seg = frac / n_seg
        for i in range(n_seg):
            color = "#1A1A2E" if i % 2 == 0 else "white"
            ax.add_patch(Rectangle(
                (x0 + i * seg, y0), seg, 0.18,
                facecolor=color, edgecolor="#1A1A2E", linewidth=0.6))

        ax.text(x0, y0 - 0.12, "0", ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac / 2, y0 - 0.12, f"{barra_m // 2} m",
                ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac, y0 - 0.12, f"{barra_m} m",
                ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac / 2, y0 + 0.28, f"Escala 1:{self.escala:,}",
                ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1A1A2E")

        # Norte geográfico + declinación magnética
        norte_x = 0.55
        decl = 0.0
        if cx_utm is not None and cy_utm is not None:
            try:
                transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
                lon, _ = transformer.transform(cx_utm, cy_utm)
                decl = _estimar_declinacion(lon)
            except Exception:
                pass

        # Flecha norte geográfico
        ax.annotate("", xy=(norte_x, 0.95), xytext=(norte_x, 0.45),
                    arrowprops=dict(arrowstyle="->", color="#1A1A2E", lw=1.5))
        ax.text(norte_x, 0.98, "NG", ha="center", va="top",
                fontsize=9, fontweight="bold", color="#1A1A2E")

        # Flecha norte magnético (rotada por declinación)
        if abs(decl) > 0.1:
            rad = math.radians(decl)
            nm_x = norte_x + 0.08
            dx = math.sin(rad) * 0.12
            dy = math.cos(rad) * 0.45
            ax.annotate("", xy=(nm_x + dx, 0.45 + dy), xytext=(nm_x, 0.45),
                        arrowprops=dict(arrowstyle="->", color="#E74C3C",
                                        lw=0.8, linestyle="--"))
            ax.text(nm_x + dx, 0.45 + dy + 0.04, "NM", ha="center", va="bottom",
                    fontsize=6, color="#E74C3C")
            ax.text(norte_x + 0.04, 0.38, f"Decl: {decl:.1f}\u00b0E",
                    ha="center", va="top", fontsize=4.5, color="#666666")

        # Créditos / cajetín inferior
        fecha = date.today().strftime("%d/%m/%Y")
        creditos = f"Cartograf\u00eda base: {proveedor} | ETRS89 UTM H30N | Fecha: {fecha}"
        if cajetin:
            if cajetin.get("autor"):
                creditos += f" | Autor: {cajetin['autor']}"
            if cajetin.get("num_proyecto"):
                creditos += f" | Proy: {cajetin['num_proyecto']}"
            if cajetin.get("revision"):
                creditos += f" | Rev: {cajetin['revision']}"
        ax.text(0.98, 0.05, creditos, ha="right", va="bottom", fontsize=5.5,
                color="#666666", style="italic")

    # ── Cajetín profesional ─────────────────────────────────────────────

    def dibujar_cajetin(self, cajetin: dict):
        """Dibuja un cajetín profesional en la zona inferior del plano.

        cajetin: dict con claves: autor, proyecto, num_proyecto, revision, firma
        """
        if not cajetin or not any(cajetin.get(k) for k in ["autor", "proyecto", "firma"]):
            return

        izq_frac = MARGENES_MM["izq"] / self.fmt_mm[0]
        der_frac = MARGENES_MM["der"] / self.fmt_mm[0]
        h_caj = 12 / self.fmt_mm[1]  # 12 mm de alto

        ax_caj = self.fig.add_axes([
            izq_frac, 2 / self.fmt_mm[1],
            1 - izq_frac - der_frac, h_caj,
        ])
        ax_caj.set_xlim(0, 1)
        ax_caj.set_ylim(0, 1)
        ax_caj.axis("off")

        ax_caj.add_patch(Rectangle((0, 0), 1, 1, facecolor="#F0F0F0",
                                    edgecolor="#2C3E50", linewidth=0.8))

        # Dividir en 5 columnas
        cols = ["Proyecto", "N\u00ba Proyecto", "Autor", "Revisi\u00f3n", "Firma"]
        vals = [
            cajetin.get("proyecto", ""),
            cajetin.get("num_proyecto", ""),
            cajetin.get("autor", ""),
            cajetin.get("revision", ""),
            cajetin.get("firma", ""),
        ]
        n = len(cols)
        for i in range(n):
            x = i / n
            w = 1 / n
            # Línea vertical
            if i > 0:
                ax_caj.plot([x, x], [0, 1], color="#2C3E50", linewidth=0.5)
            # Etiqueta
            ax_caj.text(x + w / 2, 0.75, cols[i], ha="center", va="center",
                        fontsize=4.5, fontweight="bold", color="#2C3E50")
            # Valor
            ax_caj.text(x + w / 2, 0.3, vals[i], ha="center", va="center",
                        fontsize=5, color="#1A1A2E")

    # ── Cabecera ────────────────────────────────────────────────────────

    def dibujar_cabecera(self, row, titulo_grupo=None, num_plano_override=None,
                          cajetin=None, plantilla=None):
        pl = plantilla or {}
        c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
        c_texto = pl.get("color_cabecera_texto", "#FFFFFF")
        c_acento = pl.get("color_cabecera_acento", "#2ECC71")
        org = "CONSEJER\u00cdA DE SOSTENIBILIDAD\nJUNTA DE ANDALUC\u00cdA"
        subtit = "PLANO DE INFRAESTRUCTURA FORESTAL"
        if cajetin:
            if cajetin.get("organizacion"):
                org = cajetin["organizacion"]
            if cajetin.get("subtitulo"):
                subtit = cajetin["subtitulo"]

        izq_frac = MARGENES_MM["izq"] / self.fmt_mm[0]
        der_frac = MARGENES_MM["der"] / self.fmt_mm[0]
        sup_frac = MARGENES_MM["sup"] / self.fmt_mm[1]

        ax_cab = self.fig.add_axes([
            izq_frac, 1 - sup_frac,
            1 - izq_frac - der_frac, sup_frac - 2 / self.fmt_mm[1],
        ])
        ax_cab.set_xlim(0, 1)
        ax_cab.set_ylim(0, 1)
        ax_cab.axis("off")
        ax_cab.add_patch(Rectangle((0, 0), 1, 1, facecolor=c_fondo,
                                    edgecolor=c_acento, linewidth=1.2))

        ax_cab.text(0.01, 0.5, org, ha="left", va="center", fontsize=6.5,
                    fontweight="bold", color=c_acento, linespacing=1.4)

        if titulo_grupo:
            ax_cab.text(0.5, 0.65, titulo_grupo.upper(), ha="center", va="center",
                        fontsize=9, fontweight="bold", color=c_texto)
            subtit = "PLANO DE INFRAESTRUCTURAS FORESTALES"
        else:
            nombre = str(row.get("Nombre_Infra", "INFRAESTRUCTURA FORESTAL"))
            ax_cab.text(0.5, 0.65, nombre.upper(), ha="center", va="center",
                        fontsize=9, fontweight="bold", color=c_texto)
        ax_cab.text(0.5, 0.25, subtit, ha="center", va="center",
                    fontsize=6.5, color="#95A5A6")

        if num_plano_override is not None:
            num_plano = num_plano_override
        else:
            num_plano = row.name + 1 if hasattr(row, "name") and isinstance(row.name, int) else 1
        ax_cab.text(0.99, 0.5, f"Plano n\u00ba\n{num_plano:04d}",
                    ha="right", va="center", fontsize=7, fontweight="bold",
                    color=c_acento)

    # ── Marcos ──────────────────────────────────────────────────────────

    def dibujar_marcos(self, plantilla=None):
        pl = plantilla or {}
        c_ext = pl.get("color_marco_exterior", "#1C2333")
        c_int = pl.get("color_marco_interior", "#2ECC71")

        ax_marco = self.fig.add_axes([0, 0, 1, 1])
        ax_marco.set_xlim(0, self.fmt_mm[0])
        ax_marco.set_ylim(0, self.fmt_mm[1])
        ax_marco.axis("off")
        ax_marco.set_zorder(-10)
        ax_marco.add_patch(Rectangle(
            (3, 3), self.fmt_mm[0] - 6, self.fmt_mm[1] - 6,
            fill=False, edgecolor=c_ext, linewidth=2.0))
        ax_marco.add_patch(Rectangle(
            (5, 5), self.fmt_mm[0] - 10, self.fmt_mm[1] - 10,
            fill=False, edgecolor=c_int, linewidth=0.5))

    def guardar(self, ruta_out: str):
        self.fig.savefig(ruta_out, format="pdf", dpi=DPI,
                          bbox_inches="tight", facecolor="white")
        plt.close(self.fig)


# ── Portada / Índice para PDF multipágina ───────────────────────────────

def crear_portada(formato_key: str, titulo_proyecto: str,
                   subtitulo: str = "", datos_extra: dict = None,
                   cajetin: dict = None, plantilla: dict = None) -> plt.Figure:
    """Crea una página de portada/índice para PDF multipágina."""
    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#2ECC71")

    fmt_mm = FORMATOS[formato_key]
    fig_w = fmt_mm[0] / 25.4
    fig_h = fmt_mm[1] / 25.4
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=DPI, facecolor="white")

    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Fondo superior
    ax.add_patch(Rectangle((0, 0.55), 1, 0.45, facecolor=c_fondo))

    # Marcos
    ax.add_patch(Rectangle(
        (0.02, 0.02), 0.96, 0.96,
        fill=False, edgecolor=c_fondo, linewidth=3.0))
    ax.add_patch(Rectangle(
        (0.03, 0.03), 0.94, 0.94,
        fill=False, edgecolor=c_acento, linewidth=0.8))

    # Título
    ax.text(0.5, 0.80, titulo_proyecto.upper(), ha="center", va="center",
            fontsize=20, fontweight="bold", color=c_acento)

    if subtitulo:
        ax.text(0.5, 0.72, subtitulo.upper(), ha="center", va="center",
                fontsize=12, color="white")

    org = "CONSEJER\u00cdA DE SOSTENIBILIDAD - JUNTA DE ANDALUC\u00cdA"
    if cajetin and cajetin.get("organizacion"):
        org = cajetin["organizacion"].replace("\n", " - ")
    ax.text(0.5, 0.62, org, ha="center", va="center", fontsize=8,
            color="#95A5A6")

    # Datos extra
    if datos_extra:
        y_pos = 0.45
        for clave, valor in datos_extra.items():
            ax.text(0.3, y_pos, f"{clave}:", ha="right", va="center",
                    fontsize=9, fontweight="bold", color="#2C3E50")
            ax.text(0.32, y_pos, str(valor), ha="left", va="center",
                    fontsize=9, color="#555555")
            y_pos -= 0.045

    # Fecha
    ax.text(0.5, 0.08, f"Fecha de generaci\u00f3n: {date.today().strftime('%d/%m/%Y')}",
            ha="center", va="center", fontsize=8, color="#999999")

    # Cajetín info
    if cajetin:
        y_caj = 0.12
        info_parts = []
        if cajetin.get("autor"):
            info_parts.append(f"Autor: {cajetin['autor']}")
        if cajetin.get("num_proyecto"):
            info_parts.append(f"Proyecto: {cajetin['num_proyecto']}")
        if cajetin.get("revision"):
            info_parts.append(f"Revisi\u00f3n: {cajetin['revision']}")
        if info_parts:
            ax.text(0.5, y_caj, " | ".join(info_parts), ha="center", va="center",
                    fontsize=7, color="#777777")

    return fig


def crear_indice(formato_key: str, items: list, plantilla: dict = None) -> plt.Figure:
    """Crea una página de índice para PDF multipágina.

    items: lista de (nº_plano, nombre, campo_grupo_valor)
    """
    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#2ECC71")

    fmt_mm = FORMATOS[formato_key]
    fig = plt.figure(figsize=(fmt_mm[0] / 25.4, fmt_mm[1] / 25.4),
                      dpi=DPI, facecolor="white")
    ax = fig.add_axes([0.08, 0.05, 0.84, 0.88])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Título
    ax.text(0.5, 0.97, "\u00cdNDICE DE PLANOS", ha="center", va="top",
            fontsize=14, fontweight="bold", color=c_fondo)
    ax.axhline(y=0.94, xmin=0.1, xmax=0.9, color=c_acento, linewidth=1.5)

    # Cabecera de tabla
    ax.text(0.08, 0.91, "N\u00ba", ha="center", va="center", fontsize=8,
            fontweight="bold", color=c_fondo)
    ax.text(0.55, 0.91, "Nombre", ha="center", va="center", fontsize=8,
            fontweight="bold", color=c_fondo)

    # Filas
    max_items = min(len(items), 35)
    row_h = 0.85 / max(max_items + 1, 1)
    for i, (num, nombre, extra) in enumerate(items[:max_items]):
        y = 0.88 - i * row_h
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.02, y - row_h + 0.002), 0.96, row_h - 0.002,
                                    facecolor="#F0F4F8", edgecolor="none"))
        texto = nombre
        if extra:
            texto += f" ({extra})"
        ax.text(0.08, y - row_h / 2, str(num), ha="center", va="center",
                fontsize=7, color="#333333")
        ax.text(0.15, y - row_h / 2, texto, ha="left", va="center",
                fontsize=7, color="#333333")

    if len(items) > max_items:
        ax.text(0.5, 0.03, f"... y {len(items) - max_items} planos m\u00e1s",
                ha="center", va="center", fontsize=7, color="#999999", style="italic")

    return fig
