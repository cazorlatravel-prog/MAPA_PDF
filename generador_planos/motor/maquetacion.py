"""
Layout matplotlib del plano cartográfico profesional.

Layout v3:
  - Cabecera compacta dentro del área imprimible (8 mm)
  - Mapa principal a ancho completo (~73 % del alto útil)
  - Mini-mapa de localización con fondo topográfico IGN 1:250.000
    superpuesto arriba-derecha (~1/6 del plano)
  - Grid UTM como marco exterior con coordenadas en los bordes
  - Franja inferior con dos zonas:
      · Izquierda (35 %): cajetín de proyecto + escala + norte
      · Derecha  (65 %): datos de la infraestructura en 2 columnas
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

# ── Constantes ──────────────────────────────────────────────────────────

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
_CABECERA_MM = 8  # alto de la cabecera en mm

# Declinación magnética aprox. para España (grados Este, 2024-2026)
_DECL_MAG = {"oeste": 0.5, "centro": 1.0, "este": 1.8, "sur": 0.8}


def _estimar_declinacion(lon_deg):
    if lon_deg < -5:
        return _DECL_MAG["oeste"]
    if lon_deg < -1:
        return _DECL_MAG["centro"]
    if lon_deg < 2:
        return _DECL_MAG["sur"]
    return _DECL_MAG["este"]


# ════════════════════════════════════════════════════════════════════════
#  MaquetadorPlano
# ════════════════════════════════════════════════════════════════════════

class MaquetadorPlano:
    """Crea la maquetación completa del plano cartográfico (layout v3)."""

    def __init__(self, formato_key: str, escala: int):
        self.formato_key = formato_key
        self.fmt_mm = FORMATOS[formato_key]
        self.escala = escala
        self.fig = None
        self.ax_map = None
        self.ax_info = None   # datos infraestructura (der)
        self.ax_mini = None   # mini-mapa localización (inset)
        self.ax_esc = None    # cajetín proyecto + escala + norte (izq)

    # ── Creación de la figura ──────────────────────────────────────────

    def crear_figura(self):
        fig_w = self.fmt_mm[0] / 25.4
        fig_h = self.fmt_mm[1] / 25.4
        self.fig = plt.figure(figsize=(fig_w, fig_h), dpi=DPI,
                              facecolor="white")

        izq = MARGENES_MM["izq"] / self.fmt_mm[0]
        der = MARGENES_MM["der"] / self.fmt_mm[0]
        sup = MARGENES_MM["sup"] / self.fmt_mm[1]
        inf = MARGENES_MM["inf"] / self.fmt_mm[1]
        h_cab = _CABECERA_MM / self.fmt_mm[1]

        # El GridSpec empieza debajo de la cabecera
        gs_top = 1 - sup - h_cab - 0.005

        gs = gridspec.GridSpec(
            2, 2, figure=self.fig,
            left=izq, right=1 - der,
            top=gs_top, bottom=inf,
            width_ratios=[0.35, 0.65],
            height_ratios=[RATIO_MAPA_ALTO, 1 - RATIO_MAPA_ALTO],
            hspace=0.03, wspace=0.02,
        )

        # Mapa principal: fila 0, ancho completo
        self.ax_map = self.fig.add_subplot(gs[0, :])

        # Franja inferior: cajetín/escala (izq) + datos infra (der)
        self.ax_esc = self.fig.add_subplot(gs[1, 0])
        self.ax_info = self.fig.add_subplot(gs[1, 1])

        # Mini-mapa de localización: inset superpuesto arriba-derecha
        map_pos = self.ax_map.get_position()
        inset_w = (1 - izq - der) * 0.20
        inset_h = (gs_top - inf) * RATIO_MAPA_ALTO * 0.30
        inset_x = map_pos.x1 - inset_w - 0.008
        inset_y = map_pos.y1 - inset_h - 0.008
        self.ax_mini = self.fig.add_axes(
            [inset_x, inset_y, inset_w, inset_h], zorder=20)

        return self.fig, self.ax_map, self.ax_info, self.ax_mini, self.ax_esc

    # ── Extensión del mapa ─────────────────────────────────────────────

    def calcular_extension_mapa(self, geom):
        cx, cy = geom.centroid.x, geom.centroid.y
        ancho_util = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        alto_util = self.fmt_mm[1] - MARGENES_MM["sup"] - MARGENES_MM["inf"]
        ancho_mm = ancho_util * RATIO_MAPA_ANCHO
        alto_mm = (alto_util - _CABECERA_MM) * RATIO_MAPA_ALTO
        semi_x = (ancho_mm / 1000.0) * self.escala / 2
        semi_y = (alto_mm / 1000.0) * self.escala / 2
        return cx - semi_x, cx + semi_x, cy - semi_y, cy + semi_y

    def configurar_mapa_principal(self, xmin, xmax, ymin, ymax):
        ax = self.ax_map
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.set_autoscale_on(False)
        ax.tick_params(which="both", length=0, labelbottom=False,
                       labelleft=False)
        for sp in ax.spines.values():
            sp.set_linewidth(1.2)
            sp.set_color("#2C3E50")

    # ── Grid UTM (marco + coordenadas en bordes) ──────────────────────

    def dibujar_grid_utm(self, xmin, xmax, ymin, ymax):
        intervalo = INTERVALOS_GRID.get(self.escala, 1000)
        ax = self.ax_map

        for sp in ax.spines.values():
            sp.set_linewidth(1.5)
            sp.set_color("#1C2333")

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
                       direction="out", labelbottom=True, labelleft=True,
                       pad=1)

        for x in xs:
            for y in ys:
                ax.plot(x, y, "+", color="#2C3E50", markersize=3,
                        markeredgewidth=0.3, alpha=0.35, zorder=3)

    # ── Etiquetas en el mapa ───────────────────────────────────────────

    def dibujar_etiquetas_infra(self, gdf_sel, campo_etiqueta="Nombre_Infra",
                                 campo_mapeo=None):
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

    # ── Numeración de vértices ─────────────────────────────────────────

    def dibujar_vertices_numerados(self, geom):
        coords = []
        gt = str(geom.geom_type).lower()

        if "polygon" in gt:
            raw = (list(geom.exterior.coords) if hasattr(geom, "exterior")
                   else list(geom.geoms[0].exterior.coords)
                   if hasattr(geom, "geoms") else None)
        elif "line" in gt or "string" in gt:
            raw = (list(geom.coords) if hasattr(geom, "coords")
                   else list(geom.geoms[0].coords)
                   if hasattr(geom, "geoms") else None)
        else:
            raw = None

        if not raw:
            return []

        step = max(1, len(raw) // 20)
        verts = raw[::step]
        if raw[-1] not in verts:
            verts.append(raw[-1])

        for i, (x, y, *_) in enumerate(verts, 1):
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

    # ── Leyenda automática ─────────────────────────────────────────────

    def dibujar_leyenda(self, items_leyenda, stats_resumen=None):
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
                lines.append(
                    f"Long. total: {stats_resumen['total_longitud_km']:.2f} km")
            if "total_superficie_ha" in stats_resumen:
                lines.append(
                    f"Sup. total: {stats_resumen['total_superficie_ha']:.2f} ha")
            if "num_infraestructuras" in stats_resumen:
                lines.append(
                    f"N\u00ba infra.: {stats_resumen['num_infraestructuras']}")
            if lines:
                self.ax_map.text(
                    0.01, 0.01, "\n".join(lines),
                    transform=self.ax_map.transAxes,
                    fontsize=4.5, va="bottom", ha="left", color="#333333",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor="#CCCCCC", alpha=0.9),
                    zorder=15,
                )

    # ── Panel de atributos (franja inferior DERECHA, 2 columnas) ──────

    def dibujar_panel_atributos(self, row, campos_visibles, campo_mapeo=None):
        self.dibujar_panel_atributos_multi([row], campos_visibles, campo_mapeo)

    def dibujar_panel_atributos_multi(self, rows, campos_visibles,
                                       campo_mapeo=None):
        ax = self.ax_info
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        ax.add_patch(FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0.01",
            facecolor="#F8F9FA", edgecolor="#2C3E50", linewidth=1.0, zorder=0))

        n_rows = len(rows)
        es_multi = n_rows > 1
        titulo = ("DATOS DE LAS INFRAESTRUCTURAS" if es_multi
                  else "DATOS DE LA INFRAESTRUCTURA")
        ax.text(0.5, 0.96, titulo, ha="center", va="top", fontsize=6,
                fontweight="bold", color="white", transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#2C3E50",
                          edgecolor="none"))

        campos_orden = list(ETIQUETAS_CAMPOS.keys())
        campos_mostrar = [c for c in campos_orden if c in campos_visibles]
        n_campos = len(campos_mostrar)
        if n_campos == 0:
            return

        def _res(campo):
            if campo_mapeo and campo in campo_mapeo:
                return campo_mapeo[campo]
            return campo

        if not es_multi:
            # ── Layout 2 columnas para un registro ──
            row = rows[0]
            y_top = 0.88
            y_bot = 0.04
            # Dividir campos en 2 columnas
            mitad = math.ceil(n_campos / 2)
            col_izq = campos_mostrar[:mitad]
            col_der = campos_mostrar[mitad:]

            for col_idx, col_campos in enumerate([col_izq, col_der]):
                x_base = 0.02 + col_idx * 0.50
                x_end = x_base + 0.47
                n = len(col_campos)
                if n == 0:
                    continue
                row_h = (y_top - y_bot) / max(n, 1)
                for i, campo in enumerate(col_campos):
                    y = y_top - i * row_h
                    valor = str(row.get(_res(campo), "\u2014"))
                    etiq = ETIQUETAS_CAMPOS.get(campo, campo)
                    if i % 2 == 0:
                        ax.add_patch(Rectangle(
                            (x_base, y - row_h + 0.002), x_end - x_base,
                            row_h - 0.002,
                            facecolor="#E8F4F8", edgecolor="none", zorder=1))
                    ax.text(x_base + 0.02, y - row_h / 2, etiq + ":",
                            ha="left", va="center", fontsize=5,
                            fontweight="bold", color="#2C3E50",
                            transform=ax.transAxes, zorder=2)
                    ax.text(x_end - 0.01, y - row_h / 2, valor,
                            ha="right", va="center", fontsize=5,
                            color="#1A1A2E", transform=ax.transAxes, zorder=2)

            # Línea separadora vertical central
            ax.plot([0.50, 0.50], [y_top, y_bot], color="#CCCCCC",
                    linewidth=0.5, transform=ax.transAxes, zorder=2)
        else:
            # ── Tabla multi-registro ──
            max_cols = min(n_campos, 6)
            campos_tabla = campos_mostrar[:max_cols]
            y_start = 0.88
            total_filas = 1 + n_rows
            row_h = (y_start - 0.04) / max(total_filas, 1)
            fsz = max(3.5, min(5.0, 5.0 - (n_rows - 3) * 0.3))
            xl, xr = 0.02, 0.98
            col_w = (xr - xl) / max(len(campos_tabla), 1)

            ax.add_patch(Rectangle(
                (xl, y_start - row_h), xr - xl, row_h,
                facecolor="#2C3E50", edgecolor="none", zorder=1))
            for j, campo in enumerate(campos_tabla):
                etiq = ETIQUETAS_CAMPOS.get(campo, campo)
                if len(etiq) > 12:
                    etiq = etiq[:11] + "."
                ax.text(xl + j * col_w + col_w / 2, y_start - row_h / 2,
                        etiq, ha="center", va="center", fontsize=fsz,
                        fontweight="bold", color="white",
                        transform=ax.transAxes, zorder=2)

            for r_idx, r in enumerate(rows):
                y = y_start - (1 + r_idx) * row_h
                if r_idx % 2 == 0:
                    ax.add_patch(Rectangle(
                        (xl, y - row_h + 0.002), xr - xl, row_h - 0.002,
                        facecolor="#E8F4F8", edgecolor="none", zorder=1))
                for j, campo in enumerate(campos_tabla):
                    val = str(r.get(_res(campo), "\u2014"))
                    if len(val) > 18:
                        val = val[:17] + "\u2026"
                    ax.text(xl + j * col_w + col_w / 2, y - row_h / 2,
                            val, ha="center", va="center", fontsize=fsz,
                            color="#1A1A2E", transform=ax.transAxes, zorder=2)

            for ri in range(total_filas + 1):
                yl = y_start - ri * row_h
                ax.plot([xl, xr], [yl, yl], color="#AAA", linewidth=0.3,
                        transform=ax.transAxes, zorder=2)
            for j in range(len(campos_tabla) + 1):
                xli = xl + j * col_w
                ax.plot([xli, xli],
                        [y_start, y_start - total_filas * row_h],
                        color="#AAA", linewidth=0.3,
                        transform=ax.transAxes, zorder=2)
            ax.text(0.5, y_start - total_filas * row_h - 0.015,
                    f"{n_rows} infraestructuras", ha="center", va="top",
                    fontsize=4.5, color="#555", style="italic",
                    transform=ax.transAxes)

    # ── Mapa de localización (inset con fondo topográfico) ─────────────

    def dibujar_mapa_posicion(self, cx, cy):
        ax = self.ax_mini

        # Extensión del mini-mapa en UTM (~1:250.000, ±15 km)
        radio = 15_000
        xmin_m, xmax_m = cx - radio, cx + radio
        ymin_m, ymax_m = cy - radio, cy + radio

        ax.set_xlim(xmin_m, xmax_m)
        ax.set_ylim(ymin_m, ymax_m)
        ax.set_aspect("equal")
        ax.set_facecolor("#E8E8E0")
        ax.patch.set_alpha(0.95)

        for sp in ax.spines.values():
            sp.set_linewidth(1.2)
            sp.set_color("#2C3E50")
        ax.tick_params(labelbottom=False, labelleft=False,
                       bottom=False, left=False)

        # Intentar cargar fondo topográfico IGN
        try:
            from .cartografia import _descargar_teselas_manual, CAPAS_BASE
            url = CAPAS_BASE.get("IGN Topográfico")
            if url:
                _descargar_teselas_manual(ax, url, xmin_m, xmax_m,
                                          ymin_m, ymax_m)
                ax.set_xlim(xmin_m, xmax_m)
                ax.set_ylim(ymin_m, ymax_m)
        except Exception:
            # Fallback: dibujar silueta de España en lat/lon
            # (requiere cambiar a coords geográficas)
            pass

        # Punto de localización
        ax.plot(cx, cy, "o", color="white", markersize=8, zorder=5)
        ax.plot(cx, cy, "o", color="#E74C3C", markersize=5, zorder=6,
                markeredgecolor="white", markeredgewidth=0.5)

        # Recuadro indicando la extensión del mapa principal
        try:
            map_xlim = self.ax_map.get_xlim()
            map_ylim = self.ax_map.get_ylim()
            rect_w = map_xlim[1] - map_xlim[0]
            rect_h = map_ylim[1] - map_ylim[0]
            ax.add_patch(Rectangle(
                (map_xlim[0], map_ylim[0]), rect_w, rect_h,
                fill=False, edgecolor="#E74C3C", linewidth=1.0, zorder=7,
                linestyle="--"))
        except Exception:
            pass

        ax.set_title("LOCALIZACIÓN", fontsize=5, fontweight="bold",
                      color="#2C3E50", pad=2)

    # ── Cajetín + Escala + Norte (franja inferior IZQUIERDA) ──────────

    def dibujar_barra_escala(self, proveedor: str, cx_utm=None, cy_utm=None,
                              cajetin=None):
        ax = self.ax_esc
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        ax.add_patch(FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0.01",
            facecolor="#F0F0F0", edgecolor="#2C3E50", linewidth=1.0, zorder=0))

        # ── Título ──
        ax.text(0.5, 0.97, "CAJETÍN DE PROYECTO", ha="center", va="top",
                fontsize=5, fontweight="bold", color="white",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#2C3E50",
                          edgecolor="none"))

        # ── Datos del cajetín ──
        y_pos = 0.87
        line_h = 0.075
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
                    (0.03, y - line_h + 0.004), 0.94, line_h - 0.004,
                    facecolor="#E8EEF2", edgecolor="none", zorder=1))
            ax.text(0.06, y - line_h / 2, etiq + ":", ha="left", va="center",
                    fontsize=4.5, fontweight="bold", color="#2C3E50", zorder=2)
            ax.text(0.94, y - line_h / 2, str(valor), ha="right", va="center",
                    fontsize=4.5, color="#1A1A2E", zorder=2)

        # ── Separador ──
        sep_y = y_pos - len(campos_caj) * line_h - 0.005
        ax.plot([0.06, 0.94], [sep_y, sep_y], color="#2C3E50", linewidth=0.5,
                zorder=2)

        # ── Barra de escala (mini) ──
        barra_m = BARRA_ESCALA_M.get(self.escala, 1000)
        barra_frac = 0.45
        esc_y = sep_y - 0.05
        esc_x0 = 0.06

        n_seg = 4
        seg = barra_frac / n_seg
        for i in range(n_seg):
            c = "#1A1A2E" if i % 2 == 0 else "white"
            ax.add_patch(Rectangle(
                (esc_x0 + i * seg, esc_y), seg, 0.035,
                facecolor=c, edgecolor="#1A1A2E", linewidth=0.4))

        ax.text(esc_x0, esc_y - 0.025, "0", ha="center", va="top",
                fontsize=3.5, color="#1A1A2E")
        ax.text(esc_x0 + barra_frac, esc_y - 0.025, f"{barra_m} m",
                ha="center", va="top", fontsize=3.5, color="#1A1A2E")
        ax.text(esc_x0 + barra_frac / 2, esc_y + 0.05,
                f"Escala 1:{self.escala:,}", ha="center", va="bottom",
                fontsize=5, fontweight="bold", color="#1A1A2E")

        # ── Norte geográfico (mini) ──
        norte_x = 0.80
        norte_y_base = esc_y - 0.01
        norte_h = 0.10

        decl = 0.0
        if cx_utm is not None and cy_utm is not None:
            try:
                tr = Transformer.from_crs("EPSG:25830", "EPSG:4326",
                                          always_xy=True)
                lon, _ = tr.transform(cx_utm, cy_utm)
                decl = _estimar_declinacion(lon)
            except Exception:
                pass

        ax.annotate("", xy=(norte_x, norte_y_base + norte_h),
                    xytext=(norte_x, norte_y_base),
                    arrowprops=dict(arrowstyle="->", color="#1A1A2E", lw=1.0))
        ax.text(norte_x, norte_y_base + norte_h + 0.015, "N",
                ha="center", va="bottom", fontsize=6, fontweight="bold",
                color="#1A1A2E")

        if abs(decl) > 0.1:
            rad = math.radians(decl)
            nm_x = norte_x + 0.06
            dx = math.sin(rad) * 0.05
            dy = math.cos(rad) * norte_h
            ax.annotate("", xy=(nm_x + dx, norte_y_base + dy),
                        xytext=(nm_x, norte_y_base),
                        arrowprops=dict(arrowstyle="->", color="#E74C3C",
                                        lw=0.5, linestyle="--"))
            ax.text(nm_x + dx, norte_y_base + dy + 0.015, "NM",
                    ha="center", va="bottom", fontsize=3.5, color="#E74C3C")
            ax.text(norte_x + 0.03, norte_y_base - 0.02,
                    f"Decl: {decl:.1f}\u00b0E", ha="center", va="top",
                    fontsize=3, color="#666")

        # ── Créditos ──
        fecha = date.today().strftime("%d/%m/%Y")
        ax.text(0.5, 0.02,
                f"{proveedor} | ETRS89 UTM H30N | {fecha}",
                ha="center", va="bottom", fontsize=3.5, color="#666",
                style="italic")

    # ── Cajetín (integrado en dibujar_barra_escala) ────────────────────

    def dibujar_cajetin(self, cajetin: dict):
        pass  # integrado en dibujar_barra_escala

    # ── Cabecera (dentro del área imprimible) ──────────────────────────

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

        izq_f = MARGENES_MM["izq"] / self.fmt_mm[0]
        der_f = MARGENES_MM["der"] / self.fmt_mm[0]
        sup_f = MARGENES_MM["sup"] / self.fmt_mm[1]
        h_cab = _CABECERA_MM / self.fmt_mm[1]

        # Cabecera inmediatamente debajo del margen superior
        ax_cab = self.fig.add_axes([
            izq_f,
            1 - sup_f - h_cab,
            1 - izq_f - der_f,
            h_cab,
        ])
        ax_cab.set_xlim(0, 1)
        ax_cab.set_ylim(0, 1)
        ax_cab.axis("off")

        # Fondo degradado simulado con dos rectángulos
        ax_cab.add_patch(Rectangle((0, 0), 1, 1, facecolor=c_fondo,
                                    edgecolor="none"))
        ax_cab.add_patch(Rectangle((0, 0), 1, 0.04, facecolor=c_acento,
                                    edgecolor="none"))  # línea inferior acento

        # Organización (izquierda)
        ax_cab.text(0.015, 0.55, org, ha="left", va="center", fontsize=4.5,
                    fontweight="bold", color=c_acento, linespacing=1.1)

        # Título central
        if titulo_grupo:
            ax_cab.text(0.5, 0.60, titulo_grupo.upper(), ha="center",
                        va="center", fontsize=7, fontweight="bold",
                        color=c_texto)
            subtit = "PLANO DE INFRAESTRUCTURAS FORESTALES"
        else:
            nombre = str(row.get("Nombre_Infra", "INFRAESTRUCTURA FORESTAL"))
            ax_cab.text(0.5, 0.60, nombre.upper(), ha="center", va="center",
                        fontsize=7, fontweight="bold", color=c_texto)

        ax_cab.text(0.5, 0.20, subtit, ha="center", va="center",
                    fontsize=4.5, color="#95A5A6")

        # Número de plano (derecha)
        if num_plano_override is not None:
            num = num_plano_override
        else:
            num = (row.name + 1 if hasattr(row, "name")
                   and isinstance(row.name, int) else 1)
        ax_cab.text(0.985, 0.55, f"Plano n\u00ba {num:04d}",
                    ha="right", va="center", fontsize=5.5, fontweight="bold",
                    color=c_acento)

    # ── Marcos ─────────────────────────────────────────────────────────

    def dibujar_marcos(self, plantilla=None):
        pl = plantilla or {}
        c_ext = pl.get("color_marco_exterior", "#1C2333")
        c_int = pl.get("color_marco_interior", "#2ECC71")

        ax = self.fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, self.fmt_mm[0])
        ax.set_ylim(0, self.fmt_mm[1])
        ax.axis("off")
        ax.set_zorder(-10)
        ax.add_patch(Rectangle(
            (3, 3), self.fmt_mm[0] - 6, self.fmt_mm[1] - 6,
            fill=False, edgecolor=c_ext, linewidth=2.0))
        ax.add_patch(Rectangle(
            (5, 5), self.fmt_mm[0] - 10, self.fmt_mm[1] - 10,
            fill=False, edgecolor=c_int, linewidth=0.5))

    def guardar(self, ruta_out: str):
        self.fig.savefig(ruta_out, format="pdf", dpi=DPI,
                          bbox_inches="tight", facecolor="white")
        plt.close(self.fig)


# ════════════════════════════════════════════════════════════════════════
#  Portada / Índice
# ════════════════════════════════════════════════════════════════════════

def crear_portada(formato_key: str, titulo_proyecto: str,
                   subtitulo: str = "", datos_extra: dict = None,
                   cajetin: dict = None, plantilla: dict = None) -> plt.Figure:
    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#2ECC71")

    fmt = FORMATOS[formato_key]
    fig = plt.figure(figsize=(fmt[0] / 25.4, fmt[1] / 25.4),
                      dpi=DPI, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.add_patch(Rectangle((0, 0.55), 1, 0.45, facecolor=c_fondo))
    ax.add_patch(Rectangle((0.02, 0.02), 0.96, 0.96,
                            fill=False, edgecolor=c_fondo, linewidth=3.0))
    ax.add_patch(Rectangle((0.03, 0.03), 0.94, 0.94,
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
        y = 0.45
        for k, v in datos_extra.items():
            ax.text(0.3, y, f"{k}:", ha="right", va="center", fontsize=9,
                    fontweight="bold", color="#2C3E50")
            ax.text(0.32, y, str(v), ha="left", va="center", fontsize=9,
                    color="#555")
            y -= 0.045

    ax.text(0.5, 0.08,
            f"Fecha de generación: {date.today().strftime('%d/%m/%Y')}",
            ha="center", va="center", fontsize=8, color="#999")

    if cajetin:
        parts = []
        if cajetin.get("autor"):
            parts.append(f"Autor: {cajetin['autor']}")
        if cajetin.get("num_proyecto"):
            parts.append(f"Proyecto: {cajetin['num_proyecto']}")
        if cajetin.get("revision"):
            parts.append(f"Revisión: {cajetin['revision']}")
        if parts:
            ax.text(0.5, 0.12, " | ".join(parts), ha="center", va="center",
                    fontsize=7, color="#777")

    return fig


def crear_indice(formato_key: str, items: list,
                  plantilla: dict = None) -> plt.Figure:
    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#2ECC71")

    fmt = FORMATOS[formato_key]
    fig = plt.figure(figsize=(fmt[0] / 25.4, fmt[1] / 25.4),
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

    mx = min(len(items), 35)
    rh = 0.85 / max(mx + 1, 1)
    for i, (num, nombre, extra) in enumerate(items[:mx]):
        y = 0.88 - i * rh
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.02, y - rh + 0.002), 0.96, rh - 0.002,
                                    facecolor="#F0F4F8", edgecolor="none"))
        txt = nombre + (f" ({extra})" if extra else "")
        ax.text(0.08, y - rh / 2, str(num), ha="center", va="center",
                fontsize=7, color="#333")
        ax.text(0.15, y - rh / 2, txt, ha="left", va="center",
                fontsize=7, color="#333")

    if len(items) > mx:
        ax.text(0.5, 0.03, f"... y {len(items) - mx} planos más",
                ha="center", va="center", fontsize=7, color="#999",
                style="italic")

    return fig
