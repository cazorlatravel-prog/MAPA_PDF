"""
Layout matplotlib del plano cartográfico profesional.

Layout v4:
  - Cabecera compacta dentro del área imprimible (8 mm)
  - Mapa principal a ancho completo (~73 % del alto útil)
  - Grid UTM como marco exterior con coordenadas en los bordes
  - Franja inferior con tres paneles alineados:
      · Izquierda  (28 %): cajetín de proyecto + escala + norte
      · Centro     (42 %): datos de la infraestructura (2 columnas)
      · Derecha    (30 %): mapa de localización con fondo topográfico
  - Campos dinámicos: se muestran las columnas reales del shapefile
"""

import math
from datetime import date

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.font_manager as fm

# ── Tipografía corporativa para PDFs: Noto Sans HK ──
_FONT_CORP = "Noto Sans HK"
for _fpath in ["/root/.fonts/NotoSansHK-Variable.ttf",
               "/usr/share/fonts/truetype/noto/NotoSansHK-Regular.ttf"]:
    try:
        fm.fontManager.addfont(_fpath)
    except Exception:
        pass
if any(f.name == _FONT_CORP for f in fm.fontManager.ttflist):
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = [_FONT_CORP, "DejaVu Sans"]
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D
from .escala import (
    MARGENES_MM, FORMATOS, INTERVALOS_GRID, BARRA_ESCALA_M,
    RATIO_MAPA_ANCHO, RATIO_MAPA_ALTO,
)

# ── Etiquetas embellecidas para campos conocidos (opcional) ─────────────

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

DPI_DEFAULT = 400  # calidad de impresión alta


def _fmt_valor(valor_raw):
    """Formatea un valor para mostrar: floats a 2 decimales."""
    if valor_raw is None:
        return "\u2014"
    try:
        f = float(valor_raw)
        if f != f:  # NaN
            return "\u2014"
        if f == int(f) and abs(f) < 1e9:
            return str(int(f))
        return f"{f:.2f}"
    except (ValueError, TypeError):
        s = str(valor_raw)
        return "\u2014" if s == "nan" else s

# Presets de calidad: (DPI figura, DPI guardado)
CALIDADES_PDF = {
    "Alta (400 DPI)": (400, 300),
    "Media (300 DPI)": (300, 300),
    "Media (200 DPI)": (200, 150),
    "Baja (100 DPI)": (100, 100),
}
_CABECERA_MM = 8

def _etiqueta_campo(campo):
    """Devuelve una etiqueta embellecida o el nombre del campo tal cual."""
    return ETIQUETAS_CAMPOS.get(campo, campo)


# ════════════════════════════════════════════════════════════════════════
#  MaquetadorPlano
# ════════════════════════════════════════════════════════════════════════

class MaquetadorPlano:
    """Crea la maquetación completa del plano cartográfico (layout v4)."""

    def __init__(self, formato_key: str, escala: int, layout_key: str = None,
                 dpi: int = None):
        self.formato_key = formato_key
        self.fmt_mm = FORMATOS[formato_key]
        self.escala = escala
        self.layout_key = layout_key or "Plantilla 1 (Clásica)"
        self.dpi = dpi or DPI_DEFAULT
        self.fig = None
        self.ax_map = None
        self.ax_info = None   # datos infraestructura (centro) / leyenda (lateral)
        self.ax_mini = None   # mapa localización (derecha)
        self.ax_esc = None    # cajetín proyecto + escala + norte (izquierda)
        self.ax_tabla = None  # tabla de datos infraestructura (lateral)

    @property
    def es_lateral(self):
        return self.layout_key == "Plantilla 2 (Panel lateral)"

    # ── Creación de la figura ──────────────────────────────────────────

    def crear_figura(self):
        if self.es_lateral:
            return self._crear_figura_lateral()
        return self._crear_figura_clasica()

    def _crear_figura_clasica(self):
        fig_w = self.fmt_mm[0] / 25.4
        fig_h = self.fmt_mm[1] / 25.4
        self.fig = plt.figure(figsize=(fig_w, fig_h), dpi=self.dpi,
                              facecolor="white")

        izq = MARGENES_MM["izq"] / self.fmt_mm[0]
        der = MARGENES_MM["der"] / self.fmt_mm[0]
        sup = MARGENES_MM["sup"] / self.fmt_mm[1]
        inf = MARGENES_MM["inf"] / self.fmt_mm[1]
        h_cab = _CABECERA_MM / self.fmt_mm[1]

        gs_top = 1 - sup - h_cab - 0.005

        gs = gridspec.GridSpec(
            2, 3, figure=self.fig,
            left=izq, right=1 - der,
            top=gs_top, bottom=inf,
            width_ratios=[0.28, 0.42, 0.30],
            height_ratios=[RATIO_MAPA_ALTO, 1 - RATIO_MAPA_ALTO],
            hspace=0.04, wspace=0.005,
        )

        # Mapa principal: fila 0, ancho completo (3 columnas)
        self.ax_map = self.fig.add_subplot(gs[0, :])

        # Franja inferior: 3 paneles alineados
        self.ax_esc = self.fig.add_subplot(gs[1, 0])    # cajetín (izq)
        self.ax_info = self.fig.add_subplot(gs[1, 1])   # datos infra (centro)
        self.ax_mini = self.fig.add_subplot(gs[1, 2])   # localización (der)

        return self.fig, self.ax_map, self.ax_info, self.ax_mini, self.ax_esc

    def _crear_figura_lateral(self):
        """Plantilla 2: Mapa a la izquierda, panel lateral derecho.

        Panel lateral (de arriba a abajo):
          1. Mapa de localización
          2. Tabla de datos de infraestructuras
          3. Leyenda (Tipo Infraestructura + Montes Públicos)
          4. Cajetín (organización, proyecto, escala, autores, fecha)
        """
        fig_w = self.fmt_mm[0] / 25.4
        fig_h = self.fmt_mm[1] / 25.4
        self.fig = plt.figure(figsize=(fig_w, fig_h), dpi=self.dpi,
                              facecolor="white")

        izq = MARGENES_MM["izq"] / self.fmt_mm[0]
        der = MARGENES_MM["der"] / self.fmt_mm[0]
        sup = MARGENES_MM["sup"] / self.fmt_mm[1]
        inf = MARGENES_MM["inf"] / self.fmt_mm[1]
        h_cab = _CABECERA_MM / self.fmt_mm[1]

        gs_top = 1 - sup - h_cab - 0.005

        # Grid principal: 1 fila x 2 columnas
        gs = gridspec.GridSpec(
            1, 2, figure=self.fig,
            left=izq, right=1 - der,
            top=gs_top, bottom=inf,
            width_ratios=[0.80, 0.20],
            hspace=0.02, wspace=0.008,
        )

        # Mapa principal: columna izquierda
        self.ax_map = self.fig.add_subplot(gs[0, 0])

        # Panel lateral derecho: subdividido en 4 filas
        # Minimapa (pequeño) | Tabla datos (compacta) | Leyenda | Cajetín
        gs_lateral = gridspec.GridSpecFromSubplotSpec(
            4, 1, subplot_spec=gs[0, 1],
            height_ratios=[0.22, 0.08, 0.20, 0.50],
            hspace=0.01,
        )

        self.ax_mini = self.fig.add_subplot(gs_lateral[0, 0])    # minimapa
        self.ax_tabla = self.fig.add_subplot(gs_lateral[1, 0])   # tabla datos
        self.ax_info = self.fig.add_subplot(gs_lateral[2, 0])    # leyenda
        self.ax_esc = self.fig.add_subplot(gs_lateral[3, 0])     # cajetín

        return self.fig, self.ax_map, self.ax_info, self.ax_mini, self.ax_esc

    # ── Extensión del mapa ─────────────────────────────────────────────

    def calcular_extension_mapa(self, geom):
        cx, cy = geom.centroid.x, geom.centroid.y
        ancho_util = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        alto_util = self.fmt_mm[1] - MARGENES_MM["sup"] - MARGENES_MM["inf"]
        if self.es_lateral:
            # Plantilla 2: mapa ocupa 80% del ancho y toda la altura
            ancho_mm = ancho_util * 0.80
            alto_mm = (alto_util - _CABECERA_MM)
        else:
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

    # ── Grid UTM ──────────────────────────────────────────────────────

    @staticmethod
    def _formato_coord(valor):
        """Formatea coordenada UTM con punto como separador de miles (convención española).
        Ej: 508000 → '508.000', 4217500 → '4.217.500'
        """
        s = f"{int(valor):,}".replace(",", ".")
        return s

    def dibujar_grid_utm(self, xmin, xmax, ymin, ymax):
        intervalo = INTERVALOS_GRID.get(self.escala, 1000)
        ax = self.ax_map

        for sp in ax.spines.values():
            sp.set_linewidth(1.5)
            sp.set_color("#1C2333")

        # Margenes para filtrar etiquetas demasiado cerca de los bordes
        margen_x = (xmax - xmin) * 0.03
        margen_y = (ymax - ymin) * 0.04

        x0 = math.ceil(xmin / intervalo) * intervalo
        xs = np.arange(x0, xmax, intervalo)
        y0 = math.ceil(ymin / intervalo) * intervalo
        ys = np.arange(y0, ymax, intervalo)

        # Filtrar ticks cercanos a los bordes
        xs_filt = [x for x in xs if x > xmin + margen_x and x < xmax - margen_x]
        ys_filt = [y for y in ys if y > ymin + margen_y and y < ymax - margen_y]

        # Formato español con punto de miles: 508.000, 4.217.500
        ax.set_xticks(xs_filt)
        ax.set_yticks(ys_filt)
        ax.set_xticklabels([self._formato_coord(x) for x in xs_filt],
                           fontsize=4.5, color="#2C3E50", rotation=0, ha="center")
        ax.set_yticklabels([self._formato_coord(y) for y in ys_filt],
                           fontsize=4.5, color="#2C3E50")

        # Etiquetas en los cuatro lados del mapa, fuera del marco
        ax.tick_params(which="major", length=4, width=0.6, color="#2C3E50",
                       direction="out", labelbottom=True, labeltop=True,
                       labelleft=True, labelright=True, pad=2)

        # Líneas de cuadrícula continuas (estilo cartográfico profesional)
        for x in xs:
            ax.axvline(x, color="#2C3E50", linewidth=0.25, alpha=0.45,
                       zorder=3)
        for y in ys:
            ax.axhline(y, color="#2C3E50", linewidth=0.25, alpha=0.45,
                       zorder=3)

        # Indicación del sistema de referencia (esquina inferior derecha del mapa)
        ax.text(0.995, 0.005, "ETRS89 / UTM zona 30N · EPSG:25830",
                ha="right", va="bottom", fontsize=3.2, color="#2C3E50",
                transform=ax.transAxes, zorder=12,
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white",
                          edgecolor="#BDC3C7", linewidth=0.3, alpha=0.85))

    # ── Escala gráfica sobre el mapa ─────────────────────────────────

    def dibujar_escala_grafica_mapa(self):
        """Dibuja una barra de escala discreta en la esquina inferior izquierda del mapa."""
        ax = self.ax_map
        barra_m = BARRA_ESCALA_M.get(self.escala, 1000)

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        rango_x = xlim[1] - xlim[0]
        rango_y = ylim[1] - ylim[0]

        # Posición: esquina inferior izquierda con margen
        x0 = xlim[0] + rango_x * 0.02
        y0 = ylim[0] + rango_y * 0.025
        bar_h = rango_y * 0.006  # altura de la barra

        n_seg = 4
        seg_m = barra_m / n_seg
        colores = ["#1C2333", "white"]

        # Segmentos alternados
        for i in range(n_seg):
            x_seg = x0 + i * seg_m
            rect = Rectangle((x_seg, y0), seg_m, bar_h,
                              facecolor=colores[i % 2], edgecolor="#1C2333",
                              linewidth=0.4, zorder=11)
            ax.add_patch(rect)

        # Etiqueta: "0" al inicio y distancia total al final
        fsz = 3.5
        y_txt = y0 + bar_h + rango_y * 0.004
        _txt_bbox = dict(boxstyle="round,pad=0.08", facecolor="white",
                         edgecolor="none", alpha=0.6)
        ax.text(x0, y_txt, "0", ha="center", va="bottom",
                fontsize=fsz, color="#1C2333", zorder=12, bbox=_txt_bbox)

        # Etiqueta final con unidad
        if barra_m >= 1000:
            label_fin = f"{barra_m // 1000} km"
        else:
            label_fin = f"{barra_m} m"
        ax.text(x0 + barra_m, y_txt, label_fin, ha="center", va="bottom",
                fontsize=fsz, color="#1C2333", zorder=12, bbox=_txt_bbox)

        # Marca intermedia
        mid_m = barra_m // 2
        if mid_m >= 1000:
            label_mid = f"{mid_m // 1000}"
        else:
            label_mid = str(mid_m)
        ax.text(x0 + mid_m, y_txt, label_mid, ha="center", va="bottom",
                fontsize=fsz, color="#1C2333", zorder=12, bbox=_txt_bbox)

    # ── Etiquetas ──────────────────────────────────────────────────────

    def dibujar_etiquetas_infra(self, gdf_sel, campo_etiqueta="Nombre_Infra",
                                 campo_mapeo=None):
        campo_real = campo_etiqueta
        if campo_mapeo and campo_etiqueta in campo_mapeo:
            campo_real = campo_mapeo[campo_etiqueta]

        # Offset vertical proporcional a la extensión del mapa
        ylim = self.ax_map.get_ylim()
        offset_y = (ylim[1] - ylim[0]) * 0.012

        textos_anotados = []  # para adjustText
        etiquetas_vistas = set()  # evitar duplicados

        for _, row in gdf_sel.iterrows():
            geom = row.geometry
            if geom is None:
                continue
            texto = str(row.get(campo_real, ""))
            if not texto or texto == "nan":
                continue
            if len(texto) > 25:
                texto = texto[:24] + "\u2026"

            # Saltar si ya se dibujó una etiqueta con este mismo texto
            if texto in etiquetas_vistas:
                continue
            etiquetas_vistas.add(texto)

            # Para líneas: punto medio real de la línea
            gt = str(geom.geom_type).lower()
            if "line" in gt or "string" in gt:
                try:
                    pt = geom.interpolate(0.5, normalized=True)
                    cx, cy = pt.x, pt.y
                except Exception:
                    cx, cy = geom.centroid.x, geom.centroid.y
            else:
                cx, cy = geom.centroid.x, geom.centroid.y

            # Centrada horizontalmente, desplazada encima de la geometría
            txt = self.ax_map.annotate(
                texto, xy=(cx, cy + offset_y), fontsize=4.5, fontweight="bold",
                color="#1A1A2E", ha="center", va="bottom", zorder=8,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor="#666666", linewidth=0.3, alpha=0.85),
            )
            textos_anotados.append(txt)

        # Anti-solapamiento: mover etiquetas que se pisan
        if len(textos_anotados) > 1:
            try:
                from adjustText import adjust_text
                adjust_text(textos_anotados, ax=self.ax_map,
                            arrowprops=dict(arrowstyle="-", color="#999999",
                                            lw=0.4))
            except Exception:
                pass  # Si adjustText falla o no está instalado, continuar

    # ── Etiquetas de montes ─────────────────────────────────────────────

    def dibujar_etiquetas_montes(self, gdf_montes, campo_etiqueta="Monte",
                                  campo_mapeo=None):
        """Etiquetas para la capa de montes: rosa oscuro, grande, negrita."""
        campo_real = campo_etiqueta
        if campo_mapeo and campo_etiqueta in campo_mapeo:
            campo_real = campo_mapeo[campo_etiqueta]

        ylim = self.ax_map.get_ylim()
        offset_y = (ylim[1] - ylim[0]) * 0.015

        textos_anotados = []
        etiquetas_vistas = set()

        for _, row in gdf_montes.iterrows():
            geom = row.geometry
            if geom is None:
                continue
            texto = str(row.get(campo_real, ""))
            if not texto or texto == "nan":
                continue
            if len(texto) > 30:
                texto = texto[:29] + "\u2026"

            if texto in etiquetas_vistas:
                continue
            etiquetas_vistas.add(texto)

            cx, cy = geom.centroid.x, geom.centroid.y

            txt = self.ax_map.annotate(
                texto, xy=(cx, cy + offset_y), fontsize=6.5,
                fontweight="bold", fontstyle="italic",
                color="#C2185B", ha="center", va="bottom", zorder=7,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor="#C2185B", linewidth=0.5, alpha=0.9),
            )
            textos_anotados.append(txt)

        if len(textos_anotados) > 1:
            try:
                from adjustText import adjust_text
                adjust_text(textos_anotados, ax=self.ax_map,
                            arrowprops=dict(arrowstyle="-", color="none",
                                            lw=0))
            except Exception:
                pass

    # ── Vértices ───────────────────────────────────────────────────────

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

    # ── Leyenda ────────────────────────────────────────────────────────

    def dibujar_leyenda(self, items_leyenda, stats_resumen=None):  # noqa: ARG002
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
                handles=handles, loc="lower left", fontsize=4.5,
                title="LEYENDA", title_fontsize=5,
                frameon=True, framealpha=0.92, facecolor="white",
                edgecolor="#2C3E50", borderpad=0.6, labelspacing=0.5,
                handlelength=1.8, handletextpad=0.6,
                shadow=False, fancybox=True,
            )
            leg.set_zorder(15)
            leg.get_title().set_fontweight("bold")
            leg.get_title().set_color("#2C3E50")
            leg.get_frame().set_linewidth(0.6)


    # ── Panel de atributos (centro, 2 columnas, campos dinámicos) ─────

    def dibujar_panel_atributos(self, row, campos_visibles, campo_mapeo=None,
                                campo_encabezado=None):
        self.dibujar_panel_atributos_multi([row], campos_visibles, campo_mapeo,
                                            campo_encabezado=campo_encabezado)

    def dibujar_panel_atributos_multi(self, rows, campos_visibles,
                                       campo_mapeo=None,
                                       campo_encabezado=None):
        ax = self.ax_info
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Fondo
        ax.add_patch(FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0.01",
            facecolor="#F8F9FA", edgecolor="#2C3E50", linewidth=1.0, zorder=0))

        n_rows = len(rows)
        titulo = ("DATOS DE LAS INFRAESTRUCTURAS" if n_rows > 1
                  else "DATOS DE LA INFRAESTRUCTURA")
        ax.text(0.5, 0.97, titulo, ha="center", va="top", fontsize=5,
                fontweight="bold", color="white", transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.12", facecolor="#2C3E50",
                          edgecolor="none"))

        campos_mostrar = list(campos_visibles) if campos_visibles else []
        n_campos = len(campos_mostrar)
        if n_campos == 0:
            ax.text(0.5, 0.5, "Sin campos seleccionados", ha="center",
                    va="center", fontsize=5, color="#999",
                    transform=ax.transAxes)
            return

        def _resolver_campo(campo):
            if campo_mapeo and campo in campo_mapeo:
                return campo_mapeo[campo]
            return campo

        # ────────────────────────────────────────────────────────────────
        # Diseño unificado: 2 columnas de fichas (tarjetas) de infra.
        # Funciona igual para 1 que para 20 registros.
        # ────────────────────────────────────────────────────────────────

        y_top = 0.90
        y_bot = 0.02
        area_h = y_top - y_bot

        # Distribución en 2 columnas
        col_margin = 0.02
        col_gap = 0.02
        col_w = (1.0 - 2 * col_margin - col_gap) / 2
        col_x = [col_margin, col_margin + col_w + col_gap]

        mitad = math.ceil(n_rows / 2)
        col_izq = list(range(mitad))
        col_der = list(range(mitad, n_rows))

        # Calcular tamaños adaptativos
        max_per_col = max(len(col_izq), len(col_der), 1)
        # Espacio por ficha: cabecera + campos
        card_gap = 0.008
        card_h_total = (area_h - (max_per_col - 1) * card_gap) / max_per_col
        # Dentro de cada ficha: cabecera (20%) + campos
        header_h = min(card_h_total * 0.18, 0.025)
        field_area = card_h_total - header_h
        field_h = field_area / max(n_campos, 1)

        # Tamaños de fuente fijos
        fsz_header = 3.5
        fsz_field = 3.2
        # Truncado adaptativo según espacio disponible (más generoso)
        max_label = max(12, min(22, 22 - (max_per_col - 2)))
        max_val = max(18, min(35, 35 - (max_per_col - 2)))

        for col_idx, indices_col in enumerate([col_izq, col_der]):
            x0 = col_x[col_idx]
            x1 = x0 + col_w

            for card_i, row_idx in enumerate(indices_col):
                r = rows[row_idx]
                card_top = y_top - card_i * (card_h_total + card_gap)

                # ── Cabecera de la ficha ──
                ax.add_patch(Rectangle(
                    (x0, card_top - header_h), col_w, header_h,
                    facecolor="#2C3E50", edgecolor="none", zorder=1))

                # Obtener nombre para el encabezado de la ficha
                nombre = None
                if campo_encabezado:
                    # El usuario eligió un campo concreto
                    clave = _resolver_campo(campo_encabezado)
                    val = str(r.get(clave, ""))
                    if val and val != "nan":
                        nombre = val
                if not nombre:
                    # Fallback automático: buscar NOMBRE_INF
                    for candidato in ["NOMBRE_INF", "Nombre_Infra", "NOMBRE INF",
                                      "nombre_inf", "Nombre_inf"]:
                        clave = _resolver_campo(candidato)
                        val = str(r.get(clave, ""))
                        if val and val != "nan":
                            nombre = val
                            break
                if not nombre:
                    nombre = f"Infra. {row_idx + 1}"
                if len(nombre) > max_val + 8:
                    nombre = nombre[:max_val + 7] + "\u2026"
                ax.text(x0 + 0.01, card_top - header_h / 2,
                        f"{row_idx + 1}. {nombre}",
                        ha="left", va="center", fontsize=fsz_header,
                        fontweight="bold", color="white",
                        transform=ax.transAxes, zorder=2)

                # ── Campos ──
                fields_top = card_top - header_h
                for fi, campo in enumerate(campos_mostrar):
                    fy = fields_top - fi * field_h
                    campo_real = _resolver_campo(campo)
                    valor = _fmt_valor(r.get(campo_real, None))
                    etiq = _etiqueta_campo(campo)
                    if len(etiq) > max_label:
                        etiq = etiq[:max_label - 1] + "."
                    if len(valor) > max_val:
                        valor = valor[:max_val - 1] + "\u2026"

                    # Fondo alternado
                    if fi % 2 == 0:
                        ax.add_patch(Rectangle(
                            (x0, fy - field_h + 0.001), col_w,
                            field_h - 0.001,
                            facecolor="#E8F4F8", edgecolor="none", zorder=1))

                    ax.text(x0 + 0.01, fy - field_h / 2, etiq + ":",
                            ha="left", va="center", fontsize=fsz_field,
                            fontweight="bold", color="#2C3E50",
                            transform=ax.transAxes, zorder=2)
                    # Reducir fuente para valores largos
                    fsz_val = fsz_field
                    if len(valor) > 20:
                        fsz_val = max(2.5, fsz_field - 0.4)
                    ax.text(x1 - 0.01, fy - field_h / 2, valor,
                            ha="right", va="center", fontsize=fsz_val,
                            color="#1A1A2E", transform=ax.transAxes, zorder=2)

                # Borde de la ficha
                card_bottom = fields_top - n_campos * field_h
                ax.add_patch(FancyBboxPatch(
                    (x0, card_bottom), col_w, card_top - card_bottom,
                    boxstyle="round,pad=0.003",
                    facecolor="none", edgecolor="#B0BEC5",
                    linewidth=0.4, zorder=3))

        # Separador vertical central
        ax.plot([0.50, 0.50], [y_top, y_bot], color="#CCC",
                linewidth=0.3, transform=ax.transAxes, zorder=2)

        # Pie: contador de infraestructuras
        if n_rows > 1:
            ax.text(0.5, 0.005, f"{n_rows} infraestructuras",
                    ha="center", va="bottom", fontsize=3.5, color="#555",
                    style="italic", transform=ax.transAxes)

    # ── Tabla de datos de infraestructuras (panel lateral) ──────────────

    def dibujar_tabla_infra(self, rows, campos_visibles, campo_mapeo=None):
        """Dibuja tabla compacta de infraestructuras pegada al minimapa.

        Estilo plano de referencia Junta de Andalucía: fondo blanco,
        bordes negros finos, cabecera bold, texto muy pequeño.
        La tabla ocupa solo la parte superior del axes y se pega al minimapa.
        """
        ax = self.ax_tabla
        if ax is None:
            return
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        C_BORDER = "#2C2C2C"
        C_BORDER_LIGHT = "#AAAAAA"
        C_TXT = "#1A1A2E"
        C_TXT_LIGHT = "#4A4A5A"
        C_HDR_BG = "#007932"       # Verde institucional para cabecera
        C_HDR_TXT = "#FFFFFF"       # Texto blanco en cabecera
        C_ROW_EVEN = "#FFFFFF"      # Filas pares: blanco
        C_ROW_ODD = "#F5F8F5"       # Filas impares: verde muy tenue (zebra)

        def _resolver(campo):
            if campo_mapeo and campo in campo_mapeo:
                return campo_mapeo[campo]
            return campo

        campos = list(campos_visibles) if campos_visibles else []
        n_cols = len(campos)
        n_rows_data = len(rows)

        if n_cols == 0 or n_rows_data == 0:
            return

        # Anchos proporcionales al contenido
        pesos = []
        for campo in campos:
            etiq = _etiqueta_campo(campo)
            max_len = len(etiq)
            for r in rows[:5]:
                campo_real = _resolver(campo)
                val = _fmt_valor(r.get(campo_real, None))
                if val and val != "\u2014":
                    max_len = max(max_len, len(val))
            pesos.append(max(max_len, 3))
        total_peso = sum(pesos)
        col_widths = [p / total_peso for p in pesos]

        # Acumular posiciones X
        col_x = [0.0]
        for w in col_widths:
            col_x.append(col_x[-1] + w)

        # La tabla se ancla arriba del axes (y=1.0 hacia abajo)
        total_rows = n_rows_data + 1  # +1 cabecera
        # Altura máxima por fila: limitar para evitar celdas con mucho blanco
        max_row_h = 0.06
        row_h = min(1.0 / max(total_rows, 1), max_row_h)

        lw_h = 0.8   # linewidth cabecera
        lw_d = 0.4   # linewidth datos (más fino)
        fsz_h = 2.5  # fontsize cabecera
        fsz_d = 2.0  # fontsize datos

        # ── Cabecera (fondo verde institucional, texto blanco) ──
        for ci, campo in enumerate(campos):
            x0 = col_x[ci]
            cw = col_widths[ci]
            ax.add_patch(Rectangle((x0, 1 - row_h), cw, row_h,
                                    facecolor=C_HDR_BG, edgecolor=C_BORDER,
                                    linewidth=lw_h, zorder=1))
            etiq = _etiqueta_campo(campo)
            if len(etiq) > 12:
                etiq = etiq[:11] + "."
            ax.text(x0 + cw / 2, 1 - row_h / 2, etiq.upper(),
                    ha="center", va="center", fontsize=fsz_h,
                    fontweight="bold", color=C_HDR_TXT, zorder=2)

        # ── Filas de datos (zebra: alternas blanco / verde tenue) ──
        for ri, r in enumerate(rows):
            y = 1 - (ri + 2) * row_h
            bg = C_ROW_ODD if ri % 2 == 1 else C_ROW_EVEN
            for ci, campo in enumerate(campos):
                x0 = col_x[ci]
                cw = col_widths[ci]
                ax.add_patch(Rectangle((x0, y), cw, row_h,
                                        facecolor=bg, edgecolor=C_BORDER_LIGHT,
                                        linewidth=lw_d, zorder=1))
                campo_real = _resolver(campo)
                valor = _fmt_valor(r.get(campo_real, None))
                if len(valor) > 20:
                    valor = valor[:19] + "\u2026"
                ax.text(x0 + cw / 2, y + row_h / 2, valor,
                        ha="center", va="center", fontsize=fsz_d,
                        color=C_TXT_LIGHT, zorder=2)

    # ── Mapa de localización (panel inferior derecho) ──────────────────

    def dibujar_mapa_posicion(self, cx, cy, ruta_raster_loc=""):
        ax = self.ax_mini

        # ── Escala fija 1:250.000 ──
        escala_loc = 250_000

        # Tamaño físico aproximado del panel de localización (mm)
        ancho_util = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        alto_util = (self.fmt_mm[1] - MARGENES_MM["sup"] - MARGENES_MM["inf"]
                     - _CABECERA_MM)
        if self.es_lateral:
            # Panel lateral: 20% del ancho, ~22% del alto (minimapa pequeño)
            panel_w_mm = ancho_util * 0.20 * 0.90
            panel_h_mm = alto_util * 0.22 * 0.90
        else:
            panel_w_mm = ancho_util * 0.30 * 0.95   # col 2 ratio, menos wspace
            panel_h_mm = alto_util * (1 - RATIO_MAPA_ALTO) * 0.90  # menos hspace

        # Extensión real a 1:250.000
        semi_x = (panel_w_mm / 1000.0) * escala_loc / 2
        semi_y = (panel_h_mm / 1000.0) * escala_loc / 2

        xmin_m, xmax_m = cx - semi_x, cx + semi_x
        ymin_m, ymax_m = cy - semi_y, cy + semi_y

        ax.set_xlim(xmin_m, xmax_m)
        ax.set_ylim(ymin_m, ymax_m)
        ax.set_aspect("auto")
        ax.set_facecolor("#E8E8E0")

        for sp in ax.spines.values():
            sp.set_linewidth(1.0)
            sp.set_color("#2C3E50")
        ax.tick_params(labelbottom=False, labelleft=False,
                       bottom=False, left=False)

        # Fondo: ráster local o WMS IGN
        _fondo_ok = False
        if ruta_raster_loc:
            try:
                import os
                if os.path.isfile(ruta_raster_loc):
                    from .cartografia import añadir_fondo_raster_local
                    añadir_fondo_raster_local(ax, ruta_raster_loc,
                                               xmin_m, xmax_m, ymin_m, ymax_m)
                    ax.set_xlim(xmin_m, xmax_m)
                    ax.set_ylim(ymin_m, ymax_m)
                    _fondo_ok = True
            except Exception:
                pass
        if not _fondo_ok:
            try:
                from .cartografia import _descargar_wms
                wms_url = (
                    "https://www.ign.es/wms-inspire/mapa-raster?"
                    "SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
                    "&LAYERS=mtn_rasterizado&STYLES="
                    "&CRS=EPSG:25830&FORMAT=image/png"
                )
                _descargar_wms(ax, wms_url, xmin_m, xmax_m, ymin_m, ymax_m)
                ax.set_xlim(xmin_m, xmax_m)
                ax.set_ylim(ymin_m, ymax_m)
            except Exception:
                pass

        # Punto de localización
        ax.plot(cx, cy, "o", color="white", markersize=5, zorder=5)
        ax.plot(cx, cy, "o", color="#E74C3C", markersize=3.5, zorder=6,
                markeredgecolor="white", markeredgewidth=0.3)

        # Recuadro extensión del mapa principal
        try:
            xlims = self.ax_map.get_xlim()
            ylims = self.ax_map.get_ylim()
            rw = xlims[1] - xlims[0]
            rh = ylims[1] - ylims[0]
            ax.add_patch(Rectangle(
                (xlims[0], ylims[0]), rw, rh,
                fill=False, edgecolor="#E74C3C", linewidth=0.7, zorder=7,
                linestyle="--"))
        except Exception:
            pass

        # Título dentro del panel (consistente con cajetín y datos)
        ax.text(0.5, 0.97, "LOCALIZACIÓN", ha="center", va="top",
                fontsize=5, fontweight="bold", color="white",
                transform=ax.transAxes, zorder=12,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#2C3E50",
                          edgecolor="none"))

        # ── Escala del mapa de localización ──
        extent_m = xmax_m - xmin_m
        barra_loc_m = 5000  # 5 km
        barra_frac = barra_loc_m / extent_m

        bar_x0 = 0.05
        bar_y = 0.04
        bar_h = 0.025
        n_seg = 2
        seg_frac = barra_frac / n_seg
        for i in range(n_seg):
            c = "#1A1A2E" if i % 2 == 0 else "white"
            ax.add_patch(Rectangle(
                (bar_x0 + i * seg_frac, bar_y), seg_frac, bar_h,
                facecolor=c, edgecolor="#1A1A2E", linewidth=0.3,
                transform=ax.transAxes, zorder=10))
        ax.text(bar_x0 + barra_frac + 0.02, bar_y + bar_h / 2,
                f"{barra_loc_m // 1000} km", ha="left", va="center",
                fontsize=3.5, color="#1A1A2E", fontweight="bold",
                transform=ax.transAxes, zorder=10)
        # Texto de escala
        ax.text(0.95, 0.04, f"E 1:{escala_loc:,}".replace(",", "."),
                ha="right", va="bottom", fontsize=3.5, fontweight="bold",
                color="#2C3E50", transform=ax.transAxes, zorder=10,
                bbox=dict(boxstyle="round,pad=0.1", facecolor="white",
                          edgecolor="none", alpha=0.7))

    # ── Cajetín + Escala + Norte (panel inferior izquierdo) ───────────

    def dibujar_barra_escala(self, proveedor: str, cx_utm=None, cy_utm=None,
                             cajetin=None, items_categoria=None):
        ax = self.ax_esc
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        caj = cajetin or {}
        COL_DARK = "#1C2333"
        COL_MID = "#2C3E50"
        COL_LIGHT = "#F7F8FA"
        COL_ACCENT = "#2980B9"
        COL_LINE = "#BDC3C7"
        COL_TXT = "#1A1A2E"

        # ── Fondo general ──
        ax.add_patch(Rectangle((0, 0), 1, 1,
                                facecolor="white", edgecolor=COL_DARK,
                                linewidth=1.2, zorder=0))

        # ═══════════════════════════════════════════════════════════════
        # ZONA SUPERIOR: Logo + Organización (banda oscura)
        # ═══════════════════════════════════════════════════════════════
        header_h = 0.14
        header_y = 1.0 - header_h
        ax.add_patch(Rectangle((0, header_y), 1, header_h,
                                facecolor=COL_DARK, edgecolor="none", zorder=1))
        # Línea de acento bajo la cabecera
        ax.add_patch(Rectangle((0, header_y - 0.008), 1, 0.008,
                                facecolor=COL_ACCENT, edgecolor="none", zorder=1))

        org = caj.get("organizacion", "")
        logo_path = caj.get("logo_path", "")

        x_txt = 0.06
        if logo_path:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(logo_path)
                # Calcular posición del logo dentro del axes
                logo_size = header_h * 0.75
                logo_ax = ax.inset_axes([0.02, header_y + header_h * 0.12,
                                          0.10, logo_size],
                                         transform=ax.transAxes)
                logo_ax.imshow(img, aspect="equal")
                logo_ax.axis("off")
                x_txt = 0.14
            except Exception:
                pass

        if org:
            ax.text(x_txt, header_y + header_h * 0.50, org.upper(),
                    ha="left", va="center", fontsize=5.5, fontweight="bold",
                    color="white", zorder=2)
        else:
            ax.text(0.5, header_y + header_h * 0.50, "CAJETÍN DE PROYECTO",
                    ha="center", va="center", fontsize=5.5, fontweight="bold",
                    color="white", zorder=2)

        # ═══════════════════════════════════════════════════════════════
        # MINI-LEYENDA DE CATEGORÍAS (entre cabecera y tabla de datos)
        # ═══════════════════════════════════════════════════════════════
        cat_zone_h = 0.0  # espacio reservado para categorías
        cat_top = header_y - 0.018

        if items_categoria and len(items_categoria) > 0:
            n_cat = len(items_categoria)
            import math as _math
            n_cols = 2
            n_rows = _math.ceil(n_cat / n_cols)
            cat_row_h = min(0.032, 0.20 / max(n_rows, 1))
            cat_zone_h = cat_row_h * n_rows + 0.03  # filas + título + padding

            # Título
            ax.text(0.5, cat_top - 0.005, "SIMBOLOGÍA",
                    ha="center", va="top", fontsize=4.2, fontweight="bold",
                    color=COL_DARK, zorder=3)

            margin_x = 0.05
            col_width = (1.0 - 2 * margin_x) / n_cols
            y_start = cat_top - 0.022

            for i, (label, color, geom_type, linestyle, marker,
                    facecolor) in enumerate(items_categoria):
                col_idx = i // n_rows
                row_idx = i % n_rows
                y = y_start - row_idx * cat_row_h

                if col_idx == 0:
                    # ── Columna izquierda: [línea] [texto] alineado a la izquierda
                    line_x0 = margin_x + 0.02
                    line_x1 = margin_x + 0.12
                    text_x = line_x1 + 0.03
                    text_ha = "left"
                else:
                    # ── Columna derecha: [texto] [línea] alineado a la derecha
                    line_x1 = 1.0 - margin_x - 0.02
                    line_x0 = line_x1 - 0.10
                    text_x = line_x0 - 0.03
                    text_ha = "right"

                # Dibujar muestra de trazo/símbolo
                if "point" in geom_type:
                    ax.plot((line_x0 + line_x1) / 2, y, marker=marker or "o",
                            color=color, markersize=4, markeredgecolor="white",
                            markeredgewidth=0.3, transform=ax.transAxes,
                            zorder=3)
                elif "line" in geom_type or "string" in geom_type:
                    ax.plot([line_x0, line_x1], [y, y], color=color,
                            linewidth=2.0, linestyle=linestyle or "-",
                            transform=ax.transAxes, zorder=3, solid_capstyle="round")
                else:
                    # Polígono: rectángulo relleno
                    rect_w = line_x1 - line_x0
                    rect_h = cat_row_h * 0.55
                    ax.add_patch(Rectangle(
                        (line_x0, y - rect_h / 2), rect_w, rect_h,
                        facecolor=facecolor or (color + "55"),
                        edgecolor=color, linewidth=0.6,
                        transform=ax.transAxes, zorder=3))

                # Etiqueta
                txt = str(label)[:22]
                ax.text(text_x, y, txt, ha=text_ha, va="center",
                        fontsize=3.8, color=COL_TXT,
                        transform=ax.transAxes, zorder=3)

            # Línea separadora bajo las categorías
            sep_y = y_start - n_rows * cat_row_h - 0.006
            ax.plot([margin_x, 1 - margin_x], [sep_y, sep_y],
                    color=COL_LINE, linewidth=0.5, transform=ax.transAxes,
                    zorder=2)

        # ═══════════════════════════════════════════════════════════════
        # ZONA DE DATOS: tabla de campos del proyecto
        # ═══════════════════════════════════════════════════════════════
        data_top = header_y - 0.018 - cat_zone_h  # desplazar según categorías
        margin_x = 0.05

        fecha = date.today().strftime("%d/%m/%Y")
        srs = "ETRS89 UTM H30N"

        campos_caj = [
            ("PROYECTO", caj.get("proyecto", "")),
            ("N\u00ba PROYECTO", caj.get("num_proyecto", "")),
            ("AUTOR", caj.get("autor", "")),
            ("REVISI\u00d3N", caj.get("revision", "")),
            ("FIRMA", caj.get("firma", "")),
            ("FECHA", fecha),
            ("SRC", srs),
            ("ESCALA", f"1:{self.escala:,}".replace(",", ".")),
        ]

        n_campos = len(campos_caj)
        # Espacio disponible entre data_top y la zona de la barra de escala
        barra_zone_h = 0.22  # reservar para barra + créditos
        data_h = data_top - barra_zone_h
        row_h = data_h / max(n_campos, 1)

        for i, (etiq, valor) in enumerate(campos_caj):
            y_top_row = data_top - i * row_h
            y_bot_row = y_top_row - row_h
            y_mid = (y_top_row + y_bot_row) / 2

            # Fondo alternado
            if i % 2 == 0:
                ax.add_patch(Rectangle(
                    (margin_x, y_bot_row), 1 - 2 * margin_x, row_h,
                    facecolor=COL_LIGHT, edgecolor="none", zorder=1))

            # Línea separadora fina
            ax.plot([margin_x, 1 - margin_x], [y_bot_row, y_bot_row],
                    color=COL_LINE, linewidth=0.3, zorder=2)

            # Etiqueta
            ax.text(margin_x + 0.02, y_mid, etiq,
                    ha="left", va="center", fontsize=4.2,
                    fontweight="bold", color=COL_MID, zorder=3)
            # Valor
            ax.text(1 - margin_x - 0.02, y_mid, str(valor),
                    ha="right", va="center", fontsize=4.2,
                    color=COL_TXT, zorder=3)

        # Línea superior de la tabla
        ax.plot([margin_x, 1 - margin_x], [data_top, data_top],
                color=COL_MID, linewidth=0.6, zorder=2)

        # ═══════════════════════════════════════════════════════════════
        # ZONA INFERIOR: Barra de escala gráfica profesional
        # ═══════════════════════════════════════════════════════════════
        barra_m = BARRA_ESCALA_M.get(self.escala, 1000)
        barra_frac = 0.55
        esc_y = 0.10
        bar_h = 0.022

        # Subdivisión izquierda (1 segmento extra antes del 0)
        sub_m = barra_m // 4  # subdivisión = 1/4 de la barra principal
        sub_frac = barra_frac / 4  # fracción gráfica de la subdivisión
        esc_x0 = (1 - barra_frac - sub_frac) / 2  # inicio con subdivisión

        # Formato de escala con punto (convención española)
        escala_txt = f"1:{self.escala:,}".replace(",", ".")

        # Texto de escala sobre la barra
        ax.text(0.5, esc_y + 0.058, f"Escala {escala_txt}",
                ha="center", va="bottom", fontsize=5.5, fontweight="bold",
                color=COL_DARK, zorder=3)

        # ── Subdivisión izquierda (antes del 0): 4 micro-segmentos ──
        n_micro = 4
        micro_seg = sub_frac / n_micro
        for i in range(n_micro):
            c = COL_DARK if i % 2 == 0 else "white"
            ax.add_patch(Rectangle(
                (esc_x0 + i * micro_seg, esc_y), micro_seg, bar_h,
                facecolor=c, edgecolor=COL_DARK, linewidth=0.3, zorder=2))

        # ── Barra principal: 4 segmentos ──
        n_seg = 4
        seg = barra_frac / n_seg
        main_x0 = esc_x0 + sub_frac  # el 0 está aquí
        for i in range(n_seg):
            c = COL_DARK if i % 2 == 0 else "white"
            ax.add_patch(Rectangle(
                (main_x0 + i * seg, esc_y), seg, bar_h,
                facecolor=c, edgecolor=COL_DARK, linewidth=0.3, zorder=2))

        # ── Ticks y etiquetas ──
        tick_y_top = esc_y + bar_h + 0.003
        tick_y_bot = esc_y - 0.003
        label_y = esc_y - 0.018

        # Tick y etiqueta de subdivisión (izquierda del 0)
        ax.plot([esc_x0, esc_x0], [esc_y, tick_y_top],
                color=COL_DARK, linewidth=0.4, transform=ax.transAxes, zorder=3)
        ax.text(esc_x0, label_y, f"{sub_m}", ha="center", va="top",
                fontsize=3, color=COL_TXT, zorder=3)

        # Tick y etiqueta del 0
        ax.plot([main_x0, main_x0], [esc_y, tick_y_top],
                color=COL_DARK, linewidth=0.4, transform=ax.transAxes, zorder=3)
        ax.text(main_x0, label_y, "0", ha="center", va="top",
                fontsize=3.5, fontweight="bold", color=COL_TXT, zorder=3)

        # Ticks intermedios y final
        for i in range(1, n_seg + 1):
            x_tick = main_x0 + i * seg
            ax.plot([x_tick, x_tick], [esc_y, tick_y_top],
                    color=COL_DARK, linewidth=0.4,
                    transform=ax.transAxes, zorder=3)
            dist = int(barra_m * i / n_seg)
            # Formatear distancias: usar km si >= 1000
            if dist >= 1000:
                txt = f"{dist // 1000} km" if dist % 1000 == 0 else f"{dist} m"
            else:
                txt = f"{dist} m"
            ax.text(x_tick, label_y, txt, ha="center", va="top",
                    fontsize=3, color=COL_TXT, zorder=3)

        # ── Créditos: cartografía base ──
        ax.text(0.5, 0.015, f"Base cartogr\u00e1fica: {proveedor}",
                ha="center", va="bottom", fontsize=3.0, color="#888",
                style="italic", zorder=3)

    # ── Leyenda lateral (Plantilla 2: ax_info) ──────────────────────────

    def dibujar_leyenda_lateral(self, items_leyenda_infra, items_leyenda_montes):
        """Dibuja la leyenda estilo plano de referencia.

        Formato:
        - Título LEYENDA centrado con subrayado
        - Izquierda: TIPO INFRAESTRUCTURA (2 sub-columnas de items)
        - Derecha: MONTES PÚBLICOS (1 columna de items)
        """
        ax = self.ax_info
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        C_BORDER = "#2C2C2C"
        C_TXT = "#1A1A2E"
        C_GREEN = "#007932"
        C_GREEN_DARK = "#368f3f"
        C_LABEL = "#007932"
        C_BG_LEYENDA = "#FAFCFA"     # Fondo general leyenda
        C_DIVIDER = "#CCCCCC"         # Líneas divisorias internas

        # ── Calcular altura real del contenido ──
        items_inf = items_leyenda_infra or []
        items_mon = items_leyenda_montes or []
        n_inf = min(len(items_inf), 12)
        n_mon = min(len(items_mon), 8)
        mid = (n_inf + 1) // 2  # filas en sub-columna más larga

        # Cada fila de items mide row_h; calcular cuántas filas máx
        n_rows_max = max(mid, n_mon, 1)
        row_h = min(0.07, 0.70 / max(n_rows_max, 1))

        # Usar todo el axes disponible (ya dimensionado por gs_lateral)
        y_top = 1.0
        y_bot = 0.0

        # Borde del panel
        ax.add_patch(Rectangle((0, y_bot), 1, 1.0, facecolor=C_BG_LEYENDA,
                                edgecolor=C_BORDER, linewidth=1.0, zorder=0))

        # Barra de título LEYENDA compacta
        title_h = 0.10
        ax.add_patch(Rectangle((0, y_top - title_h), 1, title_h,
                                facecolor=C_GREEN, edgecolor=C_BORDER,
                                linewidth=1.0, zorder=1))
        t_y = y_top - title_h / 2
        ax.text(0.5, t_y, "LEYENDA", ha="center", va="center",
                fontsize=5, fontweight="bold", color="white",
                transform=ax.transAxes, zorder=2)

        # Línea divisoria vertical entre infraestructura y montes
        ax.plot([0.65, 0.65], [y_top - title_h, y_bot],
                color=C_DIVIDER, linewidth=0.5,
                transform=ax.transAxes, zorder=1)

        # ── helper para dibujar un símbolo + texto ──
        def _dibujar_item(x_sym0, x_sym1, x_txt, y, item, rh):
            label, color, geom_type, linestyle, marker, facecolor = item
            if "point" in geom_type:
                ax.plot((x_sym0 + x_sym1) / 2, y, marker=marker or "o",
                        color=color, markersize=2.5, markeredgecolor="white",
                        markeredgewidth=0.2, transform=ax.transAxes, zorder=3)
            elif "line" in geom_type or "string" in geom_type:
                ax.plot([x_sym0, x_sym1], [y, y], color=color,
                        linewidth=1.3, linestyle=linestyle or "-",
                        transform=ax.transAxes, zorder=3, solid_capstyle="round")
            else:
                rect_w = x_sym1 - x_sym0
                rect_h = rh * 0.45
                ax.add_patch(Rectangle(
                    (x_sym0, y - rect_h / 2), rect_w, rect_h,
                    facecolor=facecolor or (color + "55"),
                    edgecolor=color, linewidth=0.5,
                    transform=ax.transAxes, zorder=3))
            ax.text(x_txt, y, str(label)[:16], ha="left", va="center",
                    fontsize=2.8, color="#3A3A4A", transform=ax.transAxes, zorder=3)

        # ── Posición Y del subtítulo y primer item (compacto) ──
        sub_y = y_top - title_h - 0.06
        first_y = sub_y - 0.05

        # ── Sección izquierda: TIPO INFRAESTRUCTURA (2 sub-columnas) ──
        ax.text(0.02, sub_y, "TIPO INFRAESTRUCTURA", ha="left", va="center",
                fontsize=3.5, fontweight="bold", color=C_GREEN_DARK, zorder=2)

        col_left = items_inf[:mid]
        col_right = items_inf[mid:n_inf]

        # Sub-columna izquierda (x: 0.02-0.35)
        for i, item in enumerate(col_left):
            y = first_y - i * row_h
            _dibujar_item(0.02, 0.08, 0.09, y, item, row_h)

        # Sub-columna derecha (x: 0.35-0.65)
        for i, item in enumerate(col_right):
            y = first_y - i * row_h
            _dibujar_item(0.35, 0.41, 0.42, y, item, row_h)

        # ── Sección derecha: MONTES PÚBLICOS ──
        ax.text(0.80, sub_y, "MONTES PÚBLICOS", ha="center", va="center",
                fontsize=3.5, fontweight="bold", color=C_GREEN_DARK, zorder=2)

        for i, item in enumerate(items_mon[:n_mon]):
            y = first_y - i * row_h
            _dibujar_item(0.67, 0.73, 0.74, y, item, row_h)

    # ── Cajetín lateral (Plantilla 2: ax_esc) ────────────────────────

    def dibujar_cajetin_lateral(self, row, cajetin=None, plantilla=None,
                                 num_plano=None, proveedor="",
                                 campo_mapeo=None):
        """Dibuja el cajetín completo estilo Junta de Andalucía.

        Estructura idéntica al plano de referencia (de arriba a abajo):
        1. Barra organización: fondo BLANCO, logos + texto verde
        2. Título del proyecto (recuadro centrado, bold)
        3. Monte/T.M. (izq 65%) | Nº DE PLANO (der 35%)
        4. AUTORES (izq, 2 técnicos) | Vº.Bº (centro) | ESCALA (der 50%)
           con sub-fila inferior: Firmas de los 2 autores juntas | Firma Vº.Bº | FECHA
        """
        ax = self.ax_esc
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        caj = cajetin or {}
        pl = plantilla or {}

        C_BORDER = "#2C2C2C"        # Borde gris oscuro (más suave que negro)
        C_BORDER_LIGHT = "#888888"  # Borde interno sutil
        C_TXT = "#1A1A2E"           # Texto principal oscuro
        C_TXT_LIGHT = "#4A4A5A"     # Texto secundario
        C_GREEN = "#007932"          # Verde Junta de Andalucía
        C_GREEN_DARK = "#368f3f"     # Verde oscuro para fondos
        C_BG_ORG = "#007932"         # Fondo barra organización
        C_BG_PROY = "#F0F4F0"        # Fondo proyecto (verde muy tenue)
        C_BG_MONTE = "#FAFAFA"       # Fondo monte (gris casi blanco)
        C_BG_NUM = "#F5F7F5"         # Fondo nº de plano
        C_BG_AUT = "#FFFFFF"          # Fondo autores
        C_BG_ESCALA = "#F0F4F0"       # Fondo escala/fecha
        C_LABEL = "#007932"           # Color etiquetas (verde)
        LW = 0.8  # linewidth de celdas

        # ── Alturas de cada fila (de arriba a abajo) ──
        # Compactas: ajustadas al contenido de texto
        org_h = 0.10
        proy_h = 0.12
        monte_h = 0.12
        aut_h = 0.12
        total_h = org_h + proy_h + monte_h + aut_h  # 0.46

        # Posiciones calculadas desde la parte inferior (y=0)
        aut_y = 0.0
        monte_y = aut_y + aut_h
        proy_y = monte_y + monte_h
        org_y = proy_y + proy_h

        # ═══════════════════════════════════════════════════════════════
        # 1. BARRA ORGANIZACIÓN (fondo VERDE institucional, texto BLANCO)
        # ═══════════════════════════════════════════════════════════════

        ax.add_patch(Rectangle((0, org_y), 1, org_h,
                                facecolor=C_BG_ORG, edgecolor=C_GREEN_DARK,
                                linewidth=1.2, zorder=1))

        org = caj.get("organizacion", "")
        logo_path = caj.get("logo_path", "")

        x_txt = 0.02
        if logo_path:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(logo_path)
                iw, ih = img.size
                aspect_img = iw / max(ih, 1)
                logo_h_frac = org_h * 0.90
                logo_w_frac = min(0.35, logo_h_frac * aspect_img * 0.7)
                logo_ax = ax.inset_axes(
                    [0.02, org_y + org_h * 0.05, logo_w_frac, logo_h_frac],
                    transform=ax.transAxes)
                logo_ax.imshow(img, aspect="equal")
                logo_ax.axis("off")
                x_txt = 0.02 + logo_w_frac + 0.02
            except Exception:
                pass

        if org:
            lineas = org.split("\n")
            x_centro = x_txt + (1.0 - x_txt) / 2

            if len(lineas) >= 2:
                linea1 = lineas[0].upper()
                linea2 = lineas[1]
                fsz1 = 5 if len(linea1) <= 30 else (4.5 if len(linea1) <= 45 else 3.8)
                ax.text(x_centro, org_y + org_h * 0.65,
                        linea1, ha="center", va="center",
                        fontsize=fsz1, fontweight="bold", color="white", zorder=3)
                ax.text(x_centro, org_y + org_h * 0.28,
                        linea2, ha="center", va="center",
                        fontsize=3.2, color="#E0F0E0", zorder=3)
            else:
                texto = org.upper()
                if len(texto) <= 30:
                    ax.text(x_centro, org_y + org_h * 0.50, texto,
                            ha="center", va="center",
                            fontsize=5, fontweight="bold", color="white", zorder=3)
                else:
                    mid = len(texto) // 2
                    pos = texto.rfind(" ", 0, mid + 8)
                    if pos < 5:
                        pos = texto.find(" ", mid)
                    if pos > 0:
                        linea1 = texto[:pos]
                        linea2 = texto[pos + 1:]
                    else:
                        linea1 = texto
                        linea2 = ""
                    fsz = 5 if len(linea1) <= 35 else (4.2 if len(linea1) <= 45 else 3.8)
                    ax.text(x_centro, org_y + org_h * 0.65,
                            linea1, ha="center", va="center",
                            fontsize=fsz, fontweight="bold", color="white", zorder=3)
                    if linea2:
                        ax.text(x_centro, org_y + org_h * 0.28,
                                linea2, ha="center", va="center",
                                fontsize=fsz, fontweight="bold", color="white", zorder=3)

        # ═══════════════════════════════════════════════════════════════
        # 2. TÍTULO DEL PROYECTO
        # ═══════════════════════════════════════════════════════════════

        ax.add_patch(Rectangle((0, proy_y), 1, proy_h,
                                facecolor=C_BG_PROY, edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        # Líneas decorativas superior e inferior del proyecto
        ax.plot([0.08, 0.92], [proy_y + proy_h * 0.92, proy_y + proy_h * 0.92],
                color=C_GREEN, linewidth=0.5, zorder=2)
        ax.plot([0.08, 0.92], [proy_y + proy_h * 0.08, proy_y + proy_h * 0.08],
                color=C_GREEN, linewidth=0.5, zorder=2)

        titulo_proy = caj.get("proyecto", "")
        subtitulo = caj.get("subtitulo", "")
        campo_sub = caj.get("campo_subtitulo", "")
        if campo_sub and row is not None:
            val = str(row.get(campo_sub, ""))
            if val and val != "nan":
                subtitulo = val

        texto_proy = titulo_proy or subtitulo or "PROYECTO"
        if len(texto_proy) > 50:
            mid = len(texto_proy) // 2
            space_pos = texto_proy.rfind(" ", 0, mid + 10)
            if space_pos > 10:
                texto_proy = texto_proy[:space_pos] + "\n" + texto_proy[space_pos + 1:]

        fsz_proy = 6 if len(texto_proy) <= 40 else 5
        ax.text(0.5, proy_y + proy_h * 0.50, texto_proy.upper(),
                ha="center", va="center", fontsize=fsz_proy, fontweight="bold",
                color=C_GREEN_DARK, zorder=3, linespacing=1.4)

        # ═══════════════════════════════════════════════════════════════
        # 3. MONTE / T.M. (izq 66%) + Nº DE PLANO (der 34%)
        # ═══════════════════════════════════════════════════════════════
        col_r = 0.66  # alineado con c2 de cabeceras/firmas

        # Celda izquierda: Monte + T.M.
        ax.add_patch(Rectangle((0, monte_y), col_r, monte_h,
                                facecolor=C_BG_MONTE, edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        # Celda derecha: Nº de plano
        ax.add_patch(Rectangle((col_r, monte_y), 1 - col_r, monte_h,
                                facecolor=C_BG_NUM, edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))

        monte_txt = ""
        tm_txt = ""
        if row is not None:
            # Resolver nombres de campo reales usando campo_mapeo
            _map = campo_mapeo or {}
            candidatos_monte = ["Monte", "MONTE", "Nombre_Monte", "NOMBRE_MONTE",
                                "MP", "M.P.", "monte"]
            candidatos_muni = ["Municipio", "MUNICIPIO", "TM", "T.M.",
                               "municipio", "TERMINO_MUNICIPAL"]
            # Anteponer campos mapeados (ej: "Monte" -> "NOM_MONTE")
            if "Monte" in _map:
                candidatos_monte.insert(0, _map["Monte"])
            if "Municipio" in _map:
                candidatos_muni.insert(0, _map["Municipio"])
            for candidato in candidatos_monte:
                val = str(row.get(candidato, ""))
                if val and val != "nan":
                    monte_txt = f"M.P. {val}"
                    break
            for candidato in candidatos_muni:
                val = str(row.get(candidato, ""))
                if val and val != "nan":
                    tm_txt = f"T.M. {val}"
                    break

        if monte_txt:
            ax.text(0.03, monte_y + monte_h * 0.65, monte_txt,
                    ha="left", va="center", fontsize=4.5, color=C_TXT,
                    fontweight="bold", zorder=3)
        if tm_txt:
            ax.text(0.03, monte_y + monte_h * 0.30, tm_txt,
                    ha="left", va="center", fontsize=4.5, color=C_TXT,
                    fontweight="bold", zorder=3)

        # Nº de plano
        try:
            num_inicio = int(caj.get("num_plano_inicio", 1))
        except (ValueError, TypeError):
            num_inicio = 1
        if num_plano is not None:
            n_plano = num_plano
        else:
            idx = (row.name if row is not None and hasattr(row, "name")
                   and isinstance(row.name, int) else 0)
            n_plano = idx + num_inicio

        mid_r = col_r + (1 - col_r) / 2
        # Escalar fuentes del Nº de plano según ancho real del panel
        # Panel lateral = 20% del ancho útil del papel
        _ancho_mm = self.fmt_mm[0]
        _panel_mm = _ancho_mm * 0.20  # ancho físico del panel lateral
        _factor = _panel_mm / 60.0  # base: ~60mm (A3 × 20%)
        _factor = min(_factor, 1.5)  # limitar para formatos grandes
        fsz_label_np = 3.5 * _factor
        fsz_num_np = 7 * _factor
        ax.text(mid_r, monte_y + monte_h * 0.78,
                "Nº DE PLANO:", ha="center", va="center",
                fontsize=fsz_label_np, color=C_LABEL, fontweight="bold", zorder=3)
        ax.text(mid_r, monte_y + monte_h * 0.45,
                str(n_plano), ha="center", va="center",
                fontsize=fsz_num_np, fontweight="bold", color=C_GREEN_DARK, zorder=3)
        # Mostrar solo el tamaño de papel (p.ej. "A3") sin orientación
        _formato_corto = self.formato_key.split()[0]  # "A3 Horizontal" -> "A3"
        ax.text(mid_r, monte_y + monte_h * 0.15,
                _formato_corto, ha="center", va="center",
                fontsize=fsz_label_np * 0.85, color=C_LABEL, zorder=3)

        # ═══════════════════════════════════════════════════════════════
        # 4. AUTORES (un solo recuadro) | Vº.Bº | ESCALA / FECHA
        #    "AUTORES:" título arriba-izq, 2 firmas lado a lado debajo
        # ═══════════════════════════════════════════════════════════════
        c1 = 0.33   # fin columna autores
        c2 = 0.66   # fin columna Vº.Bº

        autor = caj.get("autor", "")
        cargo_autor = caj.get("cargo_autor", "")
        firma_txt = caj.get("firma", "")
        cargo_firma = caj.get("cargo_firma", "")
        revision = caj.get("revision", "")
        cargo_revision = caj.get("cargo_revision", "")

        # ── Celda AUTORES (un solo rectángulo con título + 2 firmas) ──
        ax.add_patch(Rectangle((0, aut_y), c1, aut_h,
                                facecolor=C_BG_AUT, edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        # Título "AUTORES:" arriba-izquierda (verde institucional)
        ax.text(0.01, aut_y + aut_h * 0.92,
                "AUTORES:", ha="left", va="top",
                fontsize=3.0, fontweight="bold", color=C_LABEL, zorder=3)
        # Firma autor 1 (mitad izquierda)
        mid_a1 = c1 * 0.25  # centro de la mitad izq
        if autor:
            ax.text(mid_a1, aut_y + aut_h * 0.62,
                    f"Fdo.: {autor}", ha="center", va="center",
                    fontsize=2.8, color=C_TXT, fontweight="bold", zorder=3)
        if cargo_autor:
            ax.text(mid_a1, aut_y + aut_h * 0.38,
                    cargo_autor, ha="center", va="center",
                    fontsize=2.3, color=C_TXT_LIGHT, fontstyle="italic", zorder=3)
        # Firma autor 2 (mitad derecha)
        mid_a2 = c1 * 0.75  # centro de la mitad der
        if firma_txt:
            ax.text(mid_a2, aut_y + aut_h * 0.62,
                    f"Fdo.: {firma_txt}", ha="center", va="center",
                    fontsize=2.8, color=C_TXT, fontweight="bold", zorder=3)
        if cargo_firma:
            ax.text(mid_a2, aut_y + aut_h * 0.38,
                    cargo_firma, ha="center", va="center",
                    fontsize=2.3, color=C_TXT_LIGHT, fontstyle="italic", zorder=3)

        # ── Celda Vº.Bº ──
        ax.add_patch(Rectangle((c1, aut_y), c2 - c1, aut_h,
                                facecolor=C_BG_AUT, edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        ax.text(c1 + 0.01, aut_y + aut_h * 0.92,
                "Vº.Bº", ha="left", va="top",
                fontsize=3.0, fontweight="bold", color=C_LABEL, zorder=3)
        if revision:
            ax.text((c1 + c2) / 2, aut_y + aut_h * 0.62,
                    f"Fdo.: {revision}", ha="center", va="center",
                    fontsize=2.8, color=C_TXT, fontweight="bold", zorder=3)
        if cargo_revision:
            ax.text((c1 + c2) / 2, aut_y + aut_h * 0.38,
                    cargo_revision, ha="center", va="center",
                    fontsize=2.3, color=C_TXT_LIGHT, fontstyle="italic", zorder=3)

        # ── Celda ESCALA + FECHA + SRC (apiladas en la misma columna) ──
        ax.add_patch(Rectangle((c2, aut_y), 1 - c2, aut_h,
                                facecolor=C_BG_ESCALA, edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        mid_x = c2 + (1 - c2) * 0.50
        # Separador escala / fecha
        ax.plot([c2 + 0.01, 1 - 0.01],
                [aut_y + aut_h * 0.60, aut_y + aut_h * 0.60],
                color=C_BORDER_LIGHT, linewidth=0.3, zorder=2)
        # Separador fecha / SRC
        ax.plot([c2 + 0.01, 1 - 0.01],
                [aut_y + aut_h * 0.28, aut_y + aut_h * 0.28],
                color=C_BORDER_LIGHT, linewidth=0.3, zorder=2)
        # Escala (tercio superior)
        ax.text(mid_x, aut_y + aut_h * 0.88,
                "ESCALA:", ha="center", va="center",
                fontsize=3.0, color=C_LABEL, fontweight="bold", zorder=3)
        escala_txt = f"1:{self.escala:,}".replace(",", ".")
        ax.text(mid_x, aut_y + aut_h * 0.70,
                escala_txt, ha="center", va="center",
                fontsize=4.5, fontweight="bold", color=C_GREEN_DARK, zorder=3)
        # Fecha (tercio medio)
        ax.text(mid_x, aut_y + aut_h * 0.50,
                "FECHA:", ha="center", va="center",
                fontsize=3.0, color=C_LABEL, fontweight="bold", zorder=3)
        _MESES_ES = {1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
                     5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
                     9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE",
                     12: "DICIEMBRE"}
        hoy = date.today()
        fecha = f"{_MESES_ES[hoy.month]} {hoy.year}"
        ax.text(mid_x, aut_y + aut_h * 0.36,
                fecha, ha="center", va="center",
                fontsize=3.5, fontweight="bold", color=C_GREEN_DARK, zorder=3)
        # Sistema de coordenadas (tercio inferior)
        ax.text(mid_x, aut_y + aut_h * 0.18,
                "COORD:", ha="center", va="center",
                fontsize=2.5, color=C_LABEL, fontweight="bold", zorder=3)
        ax.text(mid_x, aut_y + aut_h * 0.06,
                "ETRS89 UTM 30N", ha="center", va="center",
                fontsize=2.8, fontweight="bold", color=C_GREEN_DARK, zorder=3)


    # ── Rosa de los vientos (dentro del mapa principal, arriba-izquierda) ──

    def dibujar_norte_en_mapa(self):
        """Dibuja un indicador de norte minimalista y moderno en el mapa."""
        ax = self.ax_map
        from matplotlib.patches import Polygon as MplPolygon, FancyBboxPatch
        from matplotlib.path import Path
        import matplotlib.patches as mpatches

        # Posición (esquina superior izquierda) y tamaño
        cx, cy = 0.045, 0.90
        h = 0.055       # altura total de la flecha
        w = 0.014        # ancho de la flecha

        # Fondo: rectángulo redondeado sutil
        bg_w, bg_h = 0.042, 0.095
        bg = FancyBboxPatch(
            (cx - bg_w / 2, cy - h * 0.45 - 0.006), bg_w, bg_h,
            boxstyle="round,pad=0.005", facecolor="white", edgecolor="#AAAAAA",
            linewidth=0.4, alpha=0.90,
            transform=ax.transAxes, zorder=14)
        ax.add_patch(bg)

        # Flecha norte: mitad izquierda oscura, mitad derecha clara
        tri_left = MplPolygon(
            [(cx, cy + h * 0.5),        # punta
             (cx - w, cy - h * 0.35),   # base izquierda
             (cx, cy - h * 0.1)],       # centro base
            facecolor="#1C2333", edgecolor="#1C2333", linewidth=0.4,
            transform=ax.transAxes, zorder=15, closed=True)

        tri_right = MplPolygon(
            [(cx, cy + h * 0.5),        # punta
             (cx + w, cy - h * 0.35),   # base derecha
             (cx, cy - h * 0.1)],       # centro base
            facecolor="#5A6377", edgecolor="#1C2333", linewidth=0.4,
            transform=ax.transAxes, zorder=15, closed=True)

        ax.add_patch(tri_left)
        ax.add_patch(tri_right)

        # Línea central fina (eje de la flecha)
        ax.plot([cx, cx], [cy - h * 0.38, cy + h * 0.5],
                color="#1C2333", linewidth=0.5,
                transform=ax.transAxes, zorder=16)

        # Letra "N" — limpia, encima de la flecha
        ax.text(cx, cy + h * 0.5 + 0.01, "N",
                ha="center", va="bottom", fontsize=5.5, fontweight="bold",
                color="#1C2333", transform=ax.transAxes, zorder=16)

    # ── Cajetín (integrado) ────────────────────────────────────────────

    def dibujar_cajetin(self, cajetin: dict):
        pass

    # ── Cabecera ───────────────────────────────────────────────────────

    def dibujar_cabecera(self, row, titulo_grupo=None, num_plano_override=None,
                          cajetin=None, plantilla=None):
        pl = plantilla or {}
        c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
        c_texto = pl.get("color_cabecera_texto", "#FFFFFF")
        c_acento = pl.get("color_cabecera_acento", "#007932")

        org = ""
        subtit = "PLANO DE INFRAESTRUCTURA FORESTAL"
        titulo_proy = ""
        titulo_mapa = ""
        logo_path = ""
        num_inicio = 1

        if cajetin:
            if cajetin.get("organizacion"):
                org = cajetin["organizacion"]
            if cajetin.get("subtitulo"):
                subtit = cajetin["subtitulo"]
            titulo_proy = cajetin.get("proyecto", "")
            titulo_mapa = cajetin.get("titulo_mapa", "")
            logo_path = cajetin.get("logo_path", "")
            try:
                num_inicio = int(cajetin.get("num_plano_inicio", 1))
            except (ValueError, TypeError):
                num_inicio = 1
            # Subtítulo dinámico desde un campo de la tabla de atributos
            campo_sub = cajetin.get("campo_subtitulo", "")
            if campo_sub and row is not None:
                val = str(row.get(campo_sub, ""))
                if val and val != "nan":
                    subtit = val

        izq_f = MARGENES_MM["izq"] / self.fmt_mm[0]
        der_f = MARGENES_MM["der"] / self.fmt_mm[0]
        sup_f = MARGENES_MM["sup"] / self.fmt_mm[1]
        h_cab = _CABECERA_MM / self.fmt_mm[1]

        ax_cab = self.fig.add_axes([
            izq_f, 1 - sup_f - h_cab,
            1 - izq_f - der_f, h_cab,
        ])
        ax_cab.set_xlim(0, 1)
        ax_cab.set_ylim(0, 1)
        ax_cab.axis("off")

        ax_cab.add_patch(Rectangle((0, 0), 1, 1, facecolor=c_fondo,
                                    edgecolor="none"))
        ax_cab.add_patch(Rectangle((0, 0), 1, 0.04, facecolor=c_acento,
                                    edgecolor="none"))

        # ── Izquierda: logo + organización ──
        x_org = 0.015
        if logo_path:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(logo_path)
                # Encajar logo en el 12% izquierdo de la cabecera
                logo_ax = self.fig.add_axes([
                    izq_f + 0.003,
                    1 - sup_f - h_cab + h_cab * 0.10,
                    0.04,
                    h_cab * 0.80,
                ], zorder=30)
                logo_ax.imshow(img, aspect="equal")
                logo_ax.axis("off")
                x_org = 0.065
            except Exception:
                pass

        ax_cab.text(x_org, 0.55, org, ha="left", va="center", fontsize=4.5,
                    fontweight="bold", color=c_acento, linespacing=1.1)

        # ── Centro: título mapa + subtítulo ──
        titulo_final = ""
        if titulo_grupo:
            titulo_final = titulo_grupo
        elif titulo_mapa:
            titulo_final = titulo_mapa
        elif titulo_proy:
            titulo_final = titulo_proy
        else:
            titulo_final = str(row.get("Nombre_Infra", "INFRAESTRUCTURA FORESTAL"))

        ax_cab.text(0.5, 0.60, titulo_final.upper(), ha="center",
                    va="center", fontsize=7, fontweight="bold",
                    color=c_texto)

        ax_cab.text(0.5, 0.20, subtit.upper(), ha="center", va="center",
                    fontsize=4.5, color="#95A5A6")

        # ── Derecha: número de plano ──
        if num_plano_override is not None:
            num = num_plano_override
        else:
            idx = (row.name if hasattr(row, "name")
                   and isinstance(row.name, int) else 0)
            num = idx + num_inicio
        ax_cab.text(0.985, 0.55, f"Plano n\u00ba {num:04d}",
                    ha="right", va="center", fontsize=5.5, fontweight="bold",
                    color=c_acento)

    # ── Marcos ─────────────────────────────────────────────────────────

    def dibujar_marcos(self, plantilla=None, cajetin=None):
        pl = plantilla or {}
        c_ext = pl.get("color_marco_exterior", "#1C2333")
        c_int = pl.get("color_marco_interior", "#007932")

        ax = self.fig.add_axes([0, 0, 1, 1], zorder=20)
        ax.set_xlim(0, self.fmt_mm[0])
        ax.set_ylim(0, self.fmt_mm[1])
        ax.axis("off")
        ax.patch.set_visible(False)
        ax.add_patch(Rectangle(
            (3, 3), self.fmt_mm[0] - 6, self.fmt_mm[1] - 6,
            fill=False, edgecolor=c_ext, linewidth=2.0))
        ax.add_patch(Rectangle(
            (5, 5), self.fmt_mm[0] - 10, self.fmt_mm[1] - 10,
            fill=False, edgecolor=c_int, linewidth=0.5))

        # Copyright lateral izquierdo (vertical)
        copyright_text = cajetin.get("copyright", "") if cajetin else ""
        if not copyright_text:
            copyright_text = (
                "APP PLANOS PDF COPYRIGHT: JOSE CABALLERO SÁNCHEZ (CAZORLA-2026)"
            )
        ax.text(
            1.8, self.fmt_mm[1] / 2, copyright_text,
            rotation=90, ha="center", va="center",
            fontsize=3.5, color="#666666", alpha=0.7,
        )

    def guardar(self, ruta_out: str, dpi_save: int = None):
        try:
            self.fig.savefig(ruta_out, format="pdf",
                              dpi=dpi_save or self.dpi,
                              facecolor="white")
        finally:
            plt.close(self.fig)


# ════════════════════════════════════════════════════════════════════════
#  Portada / Índice
# ════════════════════════════════════════════════════════════════════════

def crear_portada(formato_key: str, titulo_proyecto: str,
                   subtitulo: str = "", datos_extra: dict = None,
                   cajetin: dict = None, plantilla: dict = None) -> plt.Figure:
    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#007932")

    fmt = FORMATOS[formato_key]
    fig = plt.figure(figsize=(fmt[0] / 25.4, fmt[1] / 25.4),
                      dpi=DPI_DEFAULT, facecolor="white")
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

    org = ""
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
    c_acento = pl.get("color_cabecera_acento", "#007932")

    fmt = FORMATOS[formato_key]
    fig = plt.figure(figsize=(fmt[0] / 25.4, fmt[1] / 25.4),
                      dpi=DPI_DEFAULT, facecolor="white")
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
