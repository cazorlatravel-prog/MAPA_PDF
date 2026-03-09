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
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
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

# Presets de calidad: (DPI figura, DPI guardado)
CALIDADES_PDF = {
    "Alta (400 DPI)": (400, 300),
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
            width_ratios=[0.72, 0.28],
            hspace=0.02, wspace=0.008,
        )

        # Mapa principal: columna izquierda
        self.ax_map = self.fig.add_subplot(gs[0, 0])

        # Panel lateral derecho: subdividido en 4 filas
        # Minimapa (grande) | Tabla datos (compacta) | Leyenda | Cajetín
        gs_lateral = gridspec.GridSpecFromSubplotSpec(
            4, 1, subplot_spec=gs[0, 1],
            height_ratios=[0.40, 0.06, 0.16, 0.38],
            hspace=0.003,
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
            # Plantilla 2: mapa ocupa 72% del ancho y toda la altura
            ancho_mm = ancho_util * 0.72
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
                    valor = str(r.get(campo_real, "\u2014"))
                    if valor == "nan":
                        valor = "\u2014"
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

        C_BORDER = "#000000"
        C_TXT = "#1A1A2E"

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
                val = str(r.get(campo_real, ""))
                if val and val != "nan":
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
        row_h = 1.0 / max(total_rows, 1)

        lw_h = 0.5   # linewidth cabecera
        lw_d = 0.3   # linewidth datos
        fsz_h = 2.2  # fontsize cabecera
        fsz_d = 1.8  # fontsize datos

        # ── Cabecera ──
        for ci, campo in enumerate(campos):
            x0 = col_x[ci]
            cw = col_widths[ci]
            ax.add_patch(Rectangle((x0, 1 - row_h), cw, row_h,
                                    facecolor="white", edgecolor=C_BORDER,
                                    linewidth=lw_h, zorder=1))
            etiq = _etiqueta_campo(campo)
            if len(etiq) > 12:
                etiq = etiq[:11] + "."
            ax.text(x0 + cw / 2, 1 - row_h / 2, etiq.upper(),
                    ha="center", va="center", fontsize=fsz_h,
                    fontweight="bold", color=C_TXT, zorder=2)

        # ── Filas de datos ──
        for ri, r in enumerate(rows):
            y = 1 - (ri + 2) * row_h
            for ci, campo in enumerate(campos):
                x0 = col_x[ci]
                cw = col_widths[ci]
                ax.add_patch(Rectangle((x0, y), cw, row_h,
                                        facecolor="white", edgecolor=C_BORDER,
                                        linewidth=lw_d, zorder=1))
                campo_real = _resolver(campo)
                valor = str(r.get(campo_real, "\u2014"))
                if valor == "nan":
                    valor = "\u2014"
                if len(valor) > 20:
                    valor = valor[:19] + "\u2026"
                ax.text(x0 + cw / 2, y + row_h / 2, valor,
                        ha="center", va="center", fontsize=fsz_d,
                        color=C_TXT, zorder=2)

    # ── Mapa de localización (panel inferior derecho) ──────────────────

    def dibujar_mapa_posicion(self, cx, cy):
        ax = self.ax_mini

        # ── Escala fija 1:250.000 ──
        escala_loc = 250_000

        # Tamaño físico aproximado del panel de localización (mm)
        ancho_util = self.fmt_mm[0] - MARGENES_MM["izq"] - MARGENES_MM["der"]
        alto_util = (self.fmt_mm[1] - MARGENES_MM["sup"] - MARGENES_MM["inf"]
                     - _CABECERA_MM)
        if self.es_lateral:
            # Panel lateral: 28% del ancho, ~38% del alto (minimapa grande)
            panel_w_mm = ancho_util * 0.28 * 0.90
            panel_h_mm = alto_util * 0.38 * 0.90
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

        # Fondo cartográfico WMS 1:250.000 (IGN Base)
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
        ax.plot(cx, cy, "o", color="white", markersize=7, zorder=5)
        ax.plot(cx, cy, "o", color="#E74C3C", markersize=4.5, zorder=6,
                markeredgecolor="white", markeredgewidth=0.4)

        # Recuadro extensión del mapa principal
        try:
            xlims = self.ax_map.get_xlim()
            ylims = self.ax_map.get_ylim()
            rw = xlims[1] - xlims[0]
            rh = ylims[1] - ylims[0]
            ax.add_patch(Rectangle(
                (xlims[0], ylims[0]), rw, rh,
                fill=False, edgecolor="#E74C3C", linewidth=1.0, zorder=7,
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

        C_BORDER = "#000000"
        C_TXT = "#1A1A2E"

        # Borde del panel
        ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="white",
                                edgecolor=C_BORDER, linewidth=1.0, zorder=0))

        # Título LEYENDA (centrado, bold, subrayado)
        ax.text(0.5, 0.92, "LEYENDA", ha="center", va="center",
                fontsize=7, fontweight="bold", color=C_TXT,
                transform=ax.transAxes, zorder=2)
        ax.plot([0.30, 0.70], [0.87, 0.87], color=C_BORDER, linewidth=1.0,
                transform=ax.transAxes, zorder=2)

        # ── helper para dibujar un símbolo + texto ──
        def _dibujar_item(x_sym0, x_sym1, x_txt, y, item, rh):
            label, color, geom_type, linestyle, marker, facecolor = item
            if "point" in geom_type:
                ax.plot((x_sym0 + x_sym1) / 2, y, marker=marker or "o",
                        color=color, markersize=3.5, markeredgecolor="white",
                        markeredgewidth=0.2, transform=ax.transAxes, zorder=3)
            elif "line" in geom_type or "string" in geom_type:
                ax.plot([x_sym0, x_sym1], [y, y], color=color,
                        linewidth=2.0, linestyle=linestyle or "-",
                        transform=ax.transAxes, zorder=3, solid_capstyle="round")
            else:
                rect_w = x_sym1 - x_sym0
                rect_h = rh * 0.50
                ax.add_patch(Rectangle(
                    (x_sym0, y - rect_h / 2), rect_w, rect_h,
                    facecolor=facecolor or (color + "55"),
                    edgecolor=color, linewidth=0.6,
                    transform=ax.transAxes, zorder=3))
            ax.text(x_txt, y, str(label)[:22], ha="left", va="center",
                    fontsize=3.5, color=C_TXT, transform=ax.transAxes, zorder=3)

        # ── Sección izquierda: TIPO INFRAESTRUCTURA (2 sub-columnas) ──
        ax.text(0.02, 0.81, "TIPO INFRAESTRUCTURA", ha="left", va="center",
                fontsize=4, fontweight="bold", color=C_TXT, zorder=2)

        items_inf = items_leyenda_infra or []
        n_inf = min(len(items_inf), 12)
        # Dividir en 2 sub-columnas: primera mitad izq, segunda mitad der
        mid = (n_inf + 1) // 2
        col_left = items_inf[:mid]
        col_right = items_inf[mid:n_inf]

        row_h = min(0.10, 0.65 / max(mid, 1))

        # Sub-columna izquierda (x: 0.02-0.35)
        for i, item in enumerate(col_left):
            y = 0.74 - i * row_h
            _dibujar_item(0.02, 0.09, 0.10, y, item, row_h)

        # Sub-columna derecha (x: 0.35-0.65)
        for i, item in enumerate(col_right):
            y = 0.74 - i * row_h
            _dibujar_item(0.35, 0.42, 0.43, y, item, row_h)

        # ── Sección derecha: MONTES PÚBLICOS ──
        ax.text(0.80, 0.81, "MONTES PÚBLICOS", ha="center", va="center",
                fontsize=4, fontweight="bold", color=C_TXT, zorder=2)

        items_mon = items_leyenda_montes or []
        n_mon = min(len(items_mon), 8)
        row_h_m = min(0.10, 0.65 / max(n_mon, 1))

        for i, item in enumerate(items_mon[:n_mon]):
            y = 0.74 - i * row_h_m
            _dibujar_item(0.67, 0.74, 0.75, y, item, row_h_m)

    # ── Cajetín lateral (Plantilla 2: ax_esc) ────────────────────────

    def dibujar_cajetin_lateral(self, row, cajetin=None, plantilla=None,
                                 num_plano=None, proveedor=""):
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

        C_BORDER = "#000000"
        C_TXT = "#1A1A2E"
        C_GREEN = "#00953B"  # Verde Junta de Andalucía
        LW = 0.6  # linewidth de celdas

        # ═══════════════════════════════════════════════════════════════
        # 1. BARRA ORGANIZACIÓN (fondo BLANCO, texto VERDE)
        # ═══════════════════════════════════════════════════════════════
        org_h = 0.18
        org_y = 1.0 - org_h

        ax.add_patch(Rectangle((0, org_y), 1, org_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=1.0, zorder=1))

        org = caj.get("organizacion", "")
        logo_path = caj.get("logo_path", "")

        x_txt = 0.02
        if logo_path:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(logo_path)
                iw, ih = img.size
                aspect_img = iw / max(ih, 1)
                logo_h_frac = org_h * 0.80
                logo_w_frac = min(0.35, logo_h_frac * aspect_img * 0.7)
                logo_ax = ax.inset_axes(
                    [0.02, org_y + org_h * 0.10, logo_w_frac, logo_h_frac],
                    transform=ax.transAxes)
                logo_ax.imshow(img, aspect="equal")
                logo_ax.axis("off")
                x_txt = 0.02 + logo_w_frac + 0.02
            except Exception:
                pass

        if org:
            lineas = org.split("\n")
            if len(lineas) >= 2:
                ax.text(max(x_txt, 0.38), org_y + org_h * 0.62,
                        lineas[0].upper(), ha="left", va="center",
                        fontsize=8, fontweight="bold", color=C_GREEN, zorder=3)
                ax.text(max(x_txt, 0.38), org_y + org_h * 0.28,
                        lineas[1], ha="left", va="center",
                        fontsize=4.5, color=C_TXT, zorder=3)
            else:
                ax.text(0.5, org_y + org_h * 0.50, org.upper(),
                        ha="center", va="center",
                        fontsize=7, fontweight="bold", color=C_GREEN, zorder=3)

        # ═══════════════════════════════════════════════════════════════
        # 2. TÍTULO DEL PROYECTO
        # ═══════════════════════════════════════════════════════════════
        proy_h = 0.14
        proy_y = org_y - proy_h

        ax.add_patch(Rectangle((0, proy_y), 1, proy_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))

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

        ax.text(0.5, proy_y + proy_h * 0.50, texto_proy.upper(),
                ha="center", va="center", fontsize=5, fontweight="bold",
                color=C_TXT, zorder=3, linespacing=1.4)

        # ═══════════════════════════════════════════════════════════════
        # 3. MONTE / T.M. (izq 65%) + Nº DE PLANO (der 35%)
        # ═══════════════════════════════════════════════════════════════
        monte_h = 0.14
        monte_y = proy_y - monte_h
        col_r = 0.65  # divisor izquierda/derecha

        # Celda izquierda: Monte + T.M.
        ax.add_patch(Rectangle((0, monte_y), col_r, monte_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        # Celda derecha: Nº de plano
        ax.add_patch(Rectangle((col_r, monte_y), 1 - col_r, monte_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))

        monte_txt = ""
        tm_txt = ""
        if row is not None:
            for candidato in ["Monte", "MONTE", "Nombre_Monte", "NOMBRE_MONTE",
                              "MP", "M.P.", "monte"]:
                val = str(row.get(candidato, ""))
                if val and val != "nan":
                    monte_txt = f"M.P. {val}"
                    break
            for candidato in ["Municipio", "MUNICIPIO", "TM", "T.M.",
                              "municipio", "TERMINO_MUNICIPAL"]:
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
                    ha="left", va="center", fontsize=4.5, color=C_TXT, zorder=3)

        # Nº de plano
        num_inicio = caj.get("num_plano_inicio", 1)
        if num_plano is not None:
            n_plano = num_plano
        else:
            idx = (row.name if row is not None and hasattr(row, "name")
                   and isinstance(row.name, int) else 0)
            n_plano = idx + num_inicio

        mid_r = col_r + (1 - col_r) / 2
        ax.text(mid_r, monte_y + monte_h * 0.78,
                "Nº DE PLANO:", ha="center", va="center",
                fontsize=3.5, color=C_TXT, zorder=3)
        ax.text(mid_r, monte_y + monte_h * 0.35,
                str(n_plano), ha="center", va="center",
                fontsize=14, fontweight="bold", color=C_TXT, zorder=3)

        # ═══════════════════════════════════════════════════════════════
        # 4. AUTORES | Vº.Bº | ESCALA  (fila de cabeceras)
        # ═══════════════════════════════════════════════════════════════
        aut_h = 0.10
        aut_y = monte_y - aut_h
        c1 = 0.33
        c2 = 0.66

        # Celda AUTORES
        ax.add_patch(Rectangle((0, aut_y), c1, aut_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        ax.text(0.03, aut_y + aut_h * 0.50,
                "AUTORES:", ha="left", va="center",
                fontsize=3.5, fontweight="bold", color=C_TXT, zorder=3)

        # Celda Vº.Bº
        ax.add_patch(Rectangle((c1, aut_y), c2 - c1, aut_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        ax.text((c1 + c2) / 2, aut_y + aut_h * 0.50,
                "Vº.Bº", ha="center", va="center",
                fontsize=3.5, fontweight="bold", color=C_TXT, zorder=3)

        # Celda ESCALA (cabecera + valor)
        ax.add_patch(Rectangle((c2, aut_y), 1 - c2, aut_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        ax.text(c2 + (1 - c2) * 0.50, aut_y + aut_h * 0.72,
                "ESCALA:", ha="center", va="center",
                fontsize=3.5, color=C_TXT, zorder=3)
        escala_txt = f"1:{self.escala:,}".replace(",", ".")
        ax.text(c2 + (1 - c2) * 0.50, aut_y + aut_h * 0.28,
                escala_txt, ha="center", va="center",
                fontsize=9, fontweight="bold", color=C_TXT, zorder=3)

        # ═══════════════════════════════════════════════════════════════
        # 5. FIRMAS: Autor+Firma juntos | Vº.Bº firma | FECHA
        # ═══════════════════════════════════════════════════════════════
        firma_h = 0.22
        firma_y = aut_y - firma_h

        autor = caj.get("autor", "")
        cargo_autor = caj.get("cargo_autor", "")
        firma_txt = caj.get("firma", "")
        cargo_firma = caj.get("cargo_firma", "")
        revision = caj.get("revision", "")
        cargo_revision = caj.get("cargo_revision", "")

        # Celda izquierda: los 2 autores juntos
        ax.add_patch(Rectangle((0, firma_y), c1, firma_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        # Autor 1 (mitad superior)
        if autor:
            ax.text(c1 / 2, firma_y + firma_h * 0.72,
                    f"Fdo.: {autor}", ha="center", va="center",
                    fontsize=3.0, color=C_TXT, zorder=3)
        if cargo_autor:
            ax.text(c1 / 2, firma_y + firma_h * 0.58,
                    cargo_autor, ha="center", va="center",
                    fontsize=2.5, color=C_TXT, zorder=3)
        # Autor 2 / Firma (mitad inferior)
        if firma_txt:
            ax.text(c1 / 2, firma_y + firma_h * 0.38,
                    f"Fdo.: {firma_txt}", ha="center", va="center",
                    fontsize=3.0, color=C_TXT, zorder=3)
        if cargo_firma:
            ax.text(c1 / 2, firma_y + firma_h * 0.24,
                    cargo_firma, ha="center", va="center",
                    fontsize=2.5, color=C_TXT, zorder=3)

        # Celda centro: Vº.Bº (revisión/director)
        ax.add_patch(Rectangle((c1, firma_y), c2 - c1, firma_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        if revision:
            ax.text((c1 + c2) / 2, firma_y + firma_h * 0.55,
                    f"Fdo.: {revision}", ha="center", va="center",
                    fontsize=3.0, color=C_TXT, zorder=3)
        if cargo_revision:
            ax.text((c1 + c2) / 2, firma_y + firma_h * 0.35,
                    cargo_revision, ha="center", va="center",
                    fontsize=2.5, color=C_TXT, zorder=3)

        # Celda derecha: FECHA
        ax.add_patch(Rectangle((c2, firma_y), 1 - c2, firma_h,
                                facecolor="white", edgecolor=C_BORDER,
                                linewidth=LW, zorder=1))
        ax.text(c2 + (1 - c2) * 0.50, firma_y + firma_h * 0.72,
                "FECHA:", ha="center", va="center",
                fontsize=3.5, color=C_TXT, zorder=3)
        fecha = date.today().strftime("%B %Y").upper()
        ax.text(c2 + (1 - c2) * 0.50, firma_y + firma_h * 0.35,
                fecha, ha="center", va="center",
                fontsize=4.5, fontweight="bold", color=C_TXT, zorder=3)

        # Créditos cartografía (base del cajetín)
        ax.text(0.5, 0.005, f"Base cartográfica: {proveedor}",
                ha="center", va="bottom", fontsize=2.5, color="#888",
                style="italic", zorder=3)

    # ── Rosa de los vientos (dentro del mapa principal, arriba-izquierda) ──

    def dibujar_norte_en_mapa(self):
        """Dibuja una rosa de los vientos profesional dentro del mapa (esquina sup-izq)."""
        ax = self.ax_map
        from matplotlib.patches import Polygon as MplPolygon

        # Centro y tamaño en coordenadas de ejes
        cx, cy = 0.045, 0.91
        r = 0.022  # radio de la rosa

        # Fondo circular semitransparente
        circle_bg = plt.Circle((cx, cy - 0.005), r + 0.012,
                                facecolor="white", edgecolor="#2C3E50",
                                linewidth=0.5, alpha=0.90,
                                transform=ax.transAxes, zorder=14)
        ax.add_patch(circle_bg)

        # Triángulos de la rosa (N, S, E, W)
        # Norte (punta arriba) — mitad oscura y mitad clara
        tri_n_l = MplPolygon(
            [(cx, cy + r * 1.1), (cx - r * 0.3, cy), (cx, cy)],
            facecolor="#1A1A2E", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)
        tri_n_r = MplPolygon(
            [(cx, cy + r * 1.1), (cx + r * 0.3, cy), (cx, cy)],
            facecolor="#666666", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)
        # Sur
        tri_s_l = MplPolygon(
            [(cx, cy - r * 1.1), (cx - r * 0.3, cy), (cx, cy)],
            facecolor="#AAAAAA", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)
        tri_s_r = MplPolygon(
            [(cx, cy - r * 1.1), (cx + r * 0.3, cy), (cx, cy)],
            facecolor="#DDDDDD", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)
        # Este
        tri_e_l = MplPolygon(
            [(cx + r * 1.1, cy), (cx, cy + r * 0.3), (cx, cy)],
            facecolor="#888888", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)
        tri_e_r = MplPolygon(
            [(cx + r * 1.1, cy), (cx, cy - r * 0.3), (cx, cy)],
            facecolor="#CCCCCC", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)
        # Oeste
        tri_w_l = MplPolygon(
            [(cx - r * 1.1, cy), (cx, cy - r * 0.3), (cx, cy)],
            facecolor="#888888", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)
        tri_w_r = MplPolygon(
            [(cx - r * 1.1, cy), (cx, cy + r * 0.3), (cx, cy)],
            facecolor="#CCCCCC", edgecolor="#1A1A2E", linewidth=0.3,
            transform=ax.transAxes, zorder=15)

        for tri in [tri_n_l, tri_n_r, tri_s_l, tri_s_r,
                    tri_e_l, tri_e_r, tri_w_l, tri_w_r]:
            ax.add_patch(tri)

        # Punto central
        ax.plot(cx, cy, "o", color="#1A1A2E", markersize=1.5,
                transform=ax.transAxes, zorder=16)

        # Letra "N" sobre el triángulo norte
        ax.text(cx, cy + r * 1.1 + 0.008, "N",
                ha="center", va="bottom", fontsize=4.5, fontweight="bold",
                color="#1A1A2E", transform=ax.transAxes, zorder=16)

    # ── Cajetín (integrado) ────────────────────────────────────────────

    def dibujar_cajetin(self, cajetin: dict):
        pass

    # ── Cabecera ───────────────────────────────────────────────────────

    def dibujar_cabecera(self, row, titulo_grupo=None, num_plano_override=None,
                          cajetin=None, plantilla=None):
        pl = plantilla or {}
        c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
        c_texto = pl.get("color_cabecera_texto", "#FFFFFF")
        c_acento = pl.get("color_cabecera_acento", "#2ECC71")

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
            num_inicio = cajetin.get("num_plano_inicio", 1)
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
        c_int = pl.get("color_marco_interior", "#2ECC71")

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
    c_acento = pl.get("color_cabecera_acento", "#2ECC71")

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
    c_acento = pl.get("color_cabecera_acento", "#2ECC71")

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
