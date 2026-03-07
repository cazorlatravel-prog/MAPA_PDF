"""
Layout matplotlib del plano cartográfico profesional.

Incluye: leyenda automática, etiquetas, cajetín configurable, numeración de
vértices, norte geográfico con declinación magnética, perfil topográfico
y portada para PDF multipágina.

Layout v2:
  - Cabecera compacta (~10 mm)
  - Mapa principal a ancho completo (~75 % del alto útil)
  - Mini-mapa de localización superpuesto (inset arriba-derecha)
  - Grid UTM como marco exterior con coordenadas en los bordes
  - Franja inferior con dos columnas:
      · Izquierda: datos de la infraestructura
      · Derecha:  cajetín de proyecto + escala + norte (integrados)
"""

import math
from datetime import date

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch, Rectangle
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
    """Crea la maquetación completa del plano cartográfico.

    Layout v2: mapa protagonista + franja inferior informativa.
    """

    def __init__(self, formato_key: str, escala: int):
        self.formato_key = formato_key
        self.fmt_mm = FORMATOS[formato_key]
        self.escala = escala
        self.fig = None
        self.ax_map = None
        self.ax_info = None
        self.ax_mini = None
        self.ax_esc = None

    # ── Creación de la figura ──────────────────────────────────────────

    def crear_figura(self):
        fig_w_in = self.fmt_mm[0] / 25.4
        fig_h_in = self.fmt_mm[1] / 25.4
        self.fig = plt.figure(figsize=(fig_w_in, fig_h_in), dpi=DPI,
                              facecolor="white")

        izq = MARGENES_MM["izq"] / self.fmt_mm[0]
        der = MARGENES_MM["der"] / self.fmt_mm[0]
        sup = MARGENES_MM["sup"] / self.fmt_mm[1]
        inf = MARGENES_MM["inf"] / self.fmt_mm[1]

        gs = gridspec.GridSpec(
            2, 2, figure=self.fig,
            left=izq, right=1 - der,
            top=1 - sup, bottom=inf,
            width_ratios=[0.55, 0.45],
            height_ratios=[RATIO_MAPA_ALTO, 1 - RATIO_MAPA_ALTO],
            hspace=0.04, wspace=0.03,
        )

        # Mapa principal: fila 0, ambas columnas (ancho completo)
        self.ax_map = self.fig.add_subplot(gs[0, :])

        # Franja inferior: datos infra (izq) + cajetín/escala (der)
        self.ax_info = self.fig.add_subplot(gs[1, 0])
        self.ax_esc = self.fig.add_subplot(gs[1, 1])

        # Mini-mapa de localización: inset superpuesto arriba-derecha
        # Ocupa aprox. 1/6 del plano
        map_pos = self.ax_map.get_position()
        inset_w = (1 - izq - der) * 0.20
        inset_h = (1 - sup - inf) * RATIO_MAPA_ALTO * 0.28
        inset_x = map_pos.x1 - inset_w - 0.01
        inset_y = map_pos.y1 - inset_h - 0.01
        self.ax_mini = self.fig.add_axes(
            [inset_x, inset_y, inset_w, inset_h], zorder=20)

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
        self.ax_map.tick_params(which="both", length=0, labelbottom=False,
                                labelleft=False)
        for spine in self.ax_map.spines.values():
            spine.set_linewidth(1.2)
            spine.set_color("#2C3E50")

    # ── Grid UTM como marco exterior ───────────────────────────────────

    def dibujar_grid_utm(self, xmin, xmax, ymin, ymax):
        """Dibuja un marco alrededor del mapa con coordenadas UTM en bordes."""
        intervalo = INTERVALOS_GRID.get(self.escala, 1000)
        ax = self.ax_map

        # Marco grueso exterior
        for spine in ax.spines.values():
            spine.set_linewidth(1.5)
            spine.set_color("#1C2333")

        # Ticks y etiquetas en los bordes (coordenadas UTM)
        x0 = math.ceil(xmin / intervalo) * intervalo
        xs = np.arange(x0, xmax, intervalo)
        y0 = math.ceil(ymin / intervalo) * intervalo
        ys = np.arange(y0, ymax, intervalo)

        ax.set_xticks(xs)
        ax.set_yticks(ys)
        ax.set_xticklabels([f"{int(x):,}" for x in xs], fontsize=4.5,
                           color="#2C3E50", rotation=45, ha="right")
        ax.set_yticklabels([f"{int(y):,}" for y in ys], fontsize=4.5,
                           color="#2C3E50")
        ax.tick_params(which="major", length=4, width=0.6, color="#2C3E50",
                       direction="outside", labelbottom=True, labelleft=True,
                       pad=1)

        # Cruces interiores sutiles en las intersecciones
        for x in xs:
            for y in ys:
                ax.plot(x, y, "+", color="#2C3E50", markersize=3,
                        markeredgewidth=0.3, alpha=0.35, zorder=3)

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
        """Numera los vértices de polígonos/líneas y devuelve tabla de coords."""
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
        """Dibuja leyenda en esquina inferior izquierda del mapa."""
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

    # ── Panel de atributos (franja inferior izquierda) ─────────────────

    def dibujar_panel_atributos(self, row, campos_visibles, campo_mapeo=None):
        self.dibujar_panel_atributos_multi([row], campos_visibles, campo_mapeo)

    def dibujar_panel_atributos_multi(self, rows, campos_visibles, campo_mapeo=None):
        ax = self.ax_info
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        fondo = FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0.01",
            facecolor="#F8F9FA", edgecolor="#2C3E50", linewidth=1.0, zorder=0,
        )
        ax.add_patch(fondo)

        n_rows = len(rows)
        es_multi = n_rows > 1
        titulo = "DATOS DE LAS INFRAESTRUCTURAS" if es_multi else "DATOS DE LA INFRAESTRUCTURA"
        ax.text(0.5, 0.96, titulo, ha="center", va="top", fontsize=6,
                fontweight="bold", color="white", transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#2C3E50",
                          edgecolor="none"))

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
            y_start = 0.88
            row_h = (y_start - 0.04) / max(n_campos, 1)
            for i, campo in enumerate(campos_mostrar):
                y = y_start - i * row_h
                valor = str(row.get(_resolver(campo), "\u2014"))
                etiq = ETIQUETAS_CAMPOS.get(campo, campo)
                if i % 2 == 0:
                    ax.add_patch(Rectangle(
                        (0.01, y - row_h + 0.003), 0.98, row_h - 0.003,
                        facecolor="#E8F4F8", edgecolor="none", zorder=1))
                ax.text(0.04, y - row_h / 2, etiq + ":", ha="left", va="center",
                        fontsize=5.5, fontweight="bold", color="#2C3E50",
                        transform=ax.transAxes, zorder=2)
                ax.text(0.96, y - row_h / 2, valor, ha="right", va="center",
                        fontsize=5.5, color="#1A1A2E", transform=ax.transAxes,
                        zorder=2, wrap=True)
            for i in range(1, n_campos):
                y_line = y_start - i * row_h
                ax.plot([0.02, 0.98], [y_line, y_line],
                        color="#CCCCCC", linewidth=0.3,
                        transform=ax.transAxes, zorder=2)
        else:
            max_cols = min(n_campos, 6)
            campos_tabla = campos_mostrar[:max_cols]
            y_start = 0.88
            total_filas = 1 + n_rows
            row_h = (y_start - 0.04) / max(total_filas, 1)
            font_size = max(3.5, min(5.0, 5.0 - (n_rows - 3) * 0.3))
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
                        (x_left, y - row_h + 0.002), x_right - x_left,
                        row_h - 0.002, facecolor="#E8F4F8", edgecolor="none",
                        zorder=1))
                for j, campo in enumerate(campos_tabla):
                    valor = str(row.get(_resolver(campo), "\u2014"))
                    if len(valor) > 18:
                        valor = valor[:17] + "\u2026"
                    ax.text(x_left + j * col_w + col_w / 2, y - row_h / 2,
                            valor, ha="center", va="center",
                            fontsize=font_size, color="#1A1A2E",
                            transform=ax.transAxes, zorder=2)

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
            ax.text(0.5, y_start - total_filas * row_h - 0.015,
                    f"{n_rows} infraestructuras", ha="center", va="top",
                    fontsize=4.5, color="#555555", style="italic",
                    transform=ax.transAxes)

    # ── Mapa de localización (inset superpuesto) ───────────────────────

    def dibujar_mapa_posicion(self, cx, cy):
        ax = self.ax_mini
        ax.set_xlim(-9.5, 4.5)
        ax.set_ylim(35.5, 44.0)
        ax.set_aspect("equal")
        ax.set_facecolor("#D6EAF8")
        ax.patch.set_alpha(0.95)
        for spine in ax.spines.values():
            spine.set_linewidth(1.2)
            spine.set_color("#2C3E50")
        ax.tick_params(labelbottom=False, labelleft=False, bottom=False,
                       left=False)
        ax.fill(SPAIN_X, SPAIN_Y, color="#C8E6C9", edgecolor="#2C3E50",
                linewidth=0.6, alpha=0.9)
        try:
            transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326",
                                               always_xy=True)
            lon, lat = transformer.transform(cx, cy)
            ax.plot(lon, lat, "o", color="white", markersize=8, zorder=5)
            ax.plot(lon, lat, "o", color="#E74C3C", markersize=5, zorder=6,
                    markeredgecolor="white", markeredgewidth=0.5)
        except Exception:
            pass
        ax.set_title("LOCALIZACIÓN", fontsize=5, fontweight="bold",
                      color="#2C3E50", pad=2)

    # ── Cajetín + Escala + Norte (franja inferior derecha, integrados) ─

    def dibujar_barra_escala(self, proveedor: str, cx_utm=None, cy_utm=None,
                              cajetin=None):
        """Dibuja cajetín de proyecto con escala y norte integrados."""
        ax = self.ax_esc
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Fondo del panel
        ax.add_patch(FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0.01",
            facecolor="#F0F0F0", edgecolor="#2C3E50", linewidth=1.0, zorder=0))

        # ── Título del cajetín ──
        ax.text(0.5, 0.96, "CAJETÍN DE PROYECTO", ha="center", va="top",
                fontsize=5.5, fontweight="bold", color="white",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#2C3E50",
                          edgecolor="none"))

        # ── Datos del cajetín ──
        y_pos = 0.86
        line_h = 0.085
        campos_caj = [
            ("Proyecto", cajetin.get("proyecto", "") if cajetin else ""),
            ("Nº Proyecto", cajetin.get("num_proyecto", "") if cajetin else ""),
            ("Autor", cajetin.get("autor", "") if cajetin else ""),
            ("Revisión", cajetin.get("revision", "") if cajetin else ""),
            ("Firma", cajetin.get("firma", "") if cajetin else ""),
        ]
        for i, (etiq, valor) in enumerate(campos_caj):
            y = y_pos - i * line_h
            if i % 2 == 0:
                ax.add_patch(Rectangle(
                    (0.02, y - line_h + 0.005), 0.96, line_h - 0.005,
                    facecolor="#E8EEF2", edgecolor="none", zorder=1))
            ax.text(0.05, y - line_h / 2, etiq + ":", ha="left", va="center",
                    fontsize=4.5, fontweight="bold", color="#2C3E50", zorder=2)
            ax.text(0.95, y - line_h / 2, str(valor), ha="right", va="center",
                    fontsize=4.5, color="#1A1A2E", zorder=2)

        # ── Separador ──
        sep_y = y_pos - len(campos_caj) * line_h - 0.01
        ax.plot([0.05, 0.95], [sep_y, sep_y], color="#2C3E50", linewidth=0.5,
                zorder=2)

        # ── Barra de escala (mini) ──
        barra_m = BARRA_ESCALA_M.get(self.escala, 1000)
        barra_frac = 0.30  # ancho relativo de la barra
        esc_y = sep_y - 0.06
        esc_x0 = 0.05

        n_seg = 4
        seg = barra_frac / n_seg
        for i in range(n_seg):
            color = "#1A1A2E" if i % 2 == 0 else "white"
            ax.add_patch(Rectangle(
                (esc_x0 + i * seg, esc_y), seg, 0.04,
                facecolor=color, edgecolor="#1A1A2E", linewidth=0.4))

        ax.text(esc_x0, esc_y - 0.03, "0", ha="center", va="top",
                fontsize=4, color="#1A1A2E")
        ax.text(esc_x0 + barra_frac, esc_y - 0.03, f"{barra_m} m",
                ha="center", va="top", fontsize=4, color="#1A1A2E")
        ax.text(esc_x0 + barra_frac / 2, esc_y + 0.06,
                f"Escala 1:{self.escala:,}", ha="center", va="bottom",
                fontsize=5.5, fontweight="bold", color="#1A1A2E")

        # ── Norte geográfico (mini) ──
        norte_x = 0.75
        norte_y_base = esc_y - 0.02
        norte_h = 0.12

        decl = 0.0
        if cx_utm is not None and cy_utm is not None:
            try:
                transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326",
                                                   always_xy=True)
                lon, _ = transformer.transform(cx_utm, cy_utm)
                decl = _estimar_declinacion(lon)
            except Exception:
                pass

        ax.annotate("", xy=(norte_x, norte_y_base + norte_h),
                    xytext=(norte_x, norte_y_base),
                    arrowprops=dict(arrowstyle="->", color="#1A1A2E", lw=1.0))
        ax.text(norte_x, norte_y_base + norte_h + 0.02, "N",
                ha="center", va="bottom", fontsize=6, fontweight="bold",
                color="#1A1A2E")

        if abs(decl) > 0.1:
            rad = math.radians(decl)
            nm_x = norte_x + 0.05
            dx = math.sin(rad) * 0.06
            dy = math.cos(rad) * norte_h
            ax.annotate("", xy=(nm_x + dx, norte_y_base + dy),
                        xytext=(nm_x, norte_y_base),
                        arrowprops=dict(arrowstyle="->", color="#E74C3C",
                                        lw=0.5, linestyle="--"))
            ax.text(nm_x + dx, norte_y_base + dy + 0.02, "NM",
                    ha="center", va="bottom", fontsize=3.5, color="#E74C3C")
            ax.text(norte_x + 0.03, norte_y_base - 0.03,
                    f"Decl: {decl:.1f}\u00b0E", ha="center", va="top",
                    fontsize=3.5, color="#666666")

        # ── Créditos ──
        fecha = date.today().strftime("%d/%m/%Y")
        ax.text(0.5, 0.02,
                f"Cartografía: {proveedor} | ETRS89 UTM H30N | {fecha}",
                ha="center", va="bottom", fontsize=4, color="#666666",
                style="italic")

    # ── Cajetín (ahora integrado en dibujar_barra_escala, no-op) ───────

    def dibujar_cajetin(self, cajetin: dict):
        """No-op: el cajetín ahora se dibuja integrado en dibujar_barra_escala."""
        pass

    # ── Cabecera compacta ──────────────────────────────────────────────

    def dibujar_cabecera(self, row, titulo_grupo=None, num_plano_override=None,
                          cajetin=None, plantilla=None):
        pl = plantilla or {}
        c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
        c_texto = pl.get("color_cabecera_texto", "#FFFFFF")
        c_acento = pl.get("color_cabecera_acento", "#2ECC71")
        org = "CONSEJERÍA DE SOSTENIBILIDAD\nJUNTA DE ANDALUCÍA"
        subtit = "PLANO DE INFRAESTRUCTURA FORESTAL"
        if cajetin:
            if cajetin.get("organizacion"):
                org = cajetin["organizacion"]
            if cajetin.get("subtitulo"):
                subtit = cajetin["subtitulo"]

        izq_frac = MARGENES_MM["izq"] / self.fmt_mm[0]
        der_frac = MARGENES_MM["der"] / self.fmt_mm[0]
        sup_frac = MARGENES_MM["sup"] / self.fmt_mm[1]

        # Cabecera compacta: 8mm de alto
        h_cab = 8 / self.fmt_mm[1]
        ax_cab = self.fig.add_axes([
            izq_frac, 1 - sup_frac + 1 / self.fmt_mm[1],
            1 - izq_frac - der_frac, h_cab,
        ])
        ax_cab.set_xlim(0, 1)
        ax_cab.set_ylim(0, 1)
        ax_cab.axis("off")
        ax_cab.add_patch(Rectangle((0, 0), 1, 1, facecolor=c_fondo,
                                    edgecolor=c_acento, linewidth=1.0))

        ax_cab.text(0.01, 0.5, org, ha="left", va="center", fontsize=5,
                    fontweight="bold", color=c_acento, linespacing=1.2)

        if titulo_grupo:
            ax_cab.text(0.5, 0.55, titulo_grupo.upper(), ha="center",
                        va="center", fontsize=7, fontweight="bold",
                        color=c_texto)
            subtit = "PLANO DE INFRAESTRUCTURAS FORESTALES"
        else:
            nombre = str(row.get("Nombre_Infra", "INFRAESTRUCTURA FORESTAL"))
            ax_cab.text(0.5, 0.55, nombre.upper(), ha="center", va="center",
                        fontsize=7, fontweight="bold", color=c_texto)
        ax_cab.text(0.5, 0.15, subtit, ha="center", va="center",
                    fontsize=5, color="#95A5A6")

        if num_plano_override is not None:
            num_plano = num_plano_override
        else:
            num_plano = row.name + 1 if hasattr(row, "name") and isinstance(
                row.name, int) else 1
        ax_cab.text(0.99, 0.5, f"Plano n\u00ba {num_plano:04d}",
                    ha="right", va="center", fontsize=5.5, fontweight="bold",
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

    ax.add_patch(Rectangle((0, 0.55), 1, 0.45, facecolor=c_fondo))

    ax.add_patch(Rectangle(
        (0.02, 0.02), 0.96, 0.96,
        fill=False, edgecolor=c_fondo, linewidth=3.0))
    ax.add_patch(Rectangle(
        (0.03, 0.03), 0.94, 0.94,
        fill=False, edgecolor=c_acento, linewidth=0.8))

    ax.text(0.5, 0.80, titulo_proyecto.upper(), ha="center", va="center",
            fontsize=20, fontweight="bold", color=c_acento)

    if subtitulo:
        ax.text(0.5, 0.72, subtitulo.upper(), ha="center", va="center",
                fontsize=12, color="white")

    org = "CONSEJERÍA DE SOSTENIBILIDAD - JUNTA DE ANDALUCÍA"
    if cajetin and cajetin.get("organizacion"):
        org = cajetin["organizacion"].replace("\n", " - ")
    ax.text(0.5, 0.62, org, ha="center", va="center", fontsize=8,
            color="#95A5A6")

    if datos_extra:
        y_pos = 0.45
        for clave, valor in datos_extra.items():
            ax.text(0.3, y_pos, f"{clave}:", ha="right", va="center",
                    fontsize=9, fontweight="bold", color="#2C3E50")
            ax.text(0.32, y_pos, str(valor), ha="left", va="center",
                    fontsize=9, color="#555555")
            y_pos -= 0.045

    ax.text(0.5, 0.08, f"Fecha de generación: {date.today().strftime('%d/%m/%Y')}",
            ha="center", va="center", fontsize=8, color="#999999")

    if cajetin:
        y_caj = 0.12
        info_parts = []
        if cajetin.get("autor"):
            info_parts.append(f"Autor: {cajetin['autor']}")
        if cajetin.get("num_proyecto"):
            info_parts.append(f"Proyecto: {cajetin['num_proyecto']}")
        if cajetin.get("revision"):
            info_parts.append(f"Revisión: {cajetin['revision']}")
        if info_parts:
            ax.text(0.5, y_caj, " | ".join(info_parts), ha="center",
                    va="center", fontsize=7, color="#777777")

    return fig


def crear_indice(formato_key: str, items: list,
                  plantilla: dict = None) -> plt.Figure:
    """Crea una página de índice para PDF multipágina."""
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

    ax.text(0.5, 0.97, "ÍNDICE DE PLANOS", ha="center", va="top",
            fontsize=14, fontweight="bold", color=c_fondo)
    ax.axhline(y=0.94, xmin=0.1, xmax=0.9, color=c_acento, linewidth=1.5)

    ax.text(0.08, 0.91, "N\u00ba", ha="center", va="center", fontsize=8,
            fontweight="bold", color=c_fondo)
    ax.text(0.55, 0.91, "Nombre", ha="center", va="center", fontsize=8,
            fontweight="bold", color=c_fondo)

    max_items = min(len(items), 35)
    row_h = 0.85 / max(max_items + 1, 1)
    for i, (num, nombre, extra) in enumerate(items[:max_items]):
        y = 0.88 - i * row_h
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.02, y - row_h + 0.002), 0.96,
                                    row_h - 0.002, facecolor="#F0F4F8",
                                    edgecolor="none"))
        texto = nombre
        if extra:
            texto += f" ({extra})"
        ax.text(0.08, y - row_h / 2, str(num), ha="center", va="center",
                fontsize=7, color="#333333")
        ax.text(0.15, y - row_h / 2, texto, ha="left", va="center",
                fontsize=7, color="#333333")

    if len(items) > max_items:
        ax.text(0.5, 0.03, f"... y {len(items) - max_items} planos más",
                ha="center", va="center", fontsize=7, color="#999999",
                style="italic")

    return fig
