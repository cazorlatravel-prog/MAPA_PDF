"""Mixin de elementos cartográficos del mapa (grid UTM, escala, etiquetas, leyenda, norte)."""

import math

import numpy as np
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D
from .escala import INTERVALOS_GRID


def _intervalo_grid(escala) -> int:
    """Intervalo de cuadrícula UTM (m) para cualquier escala.

    Para las escalas estándar usa INTERVALOS_GRID; para una escala manual
    cualquiera elige el intervalo del tramo correspondiente (antes todas
    recibían 1 km: saturado a 1:50.000 y vacío a 1:1.000).
    """
    try:
        if escala in INTERVALOS_GRID:
            return INTERVALOS_GRID[escala]
        e = float(escala or 10000)
    except (TypeError, ValueError):
        return 1000
    for tope, intervalo in ((1500, 100), (3500, 200), (7500, 500),
                            (15000, 1000), (25000, 2000), (60000, 5000),
                            (150000, 10000), (400000, 25000)):
        if e <= tope:
            return intervalo
    return 50000


def _adjust_text_sin_imagenes(ax, textos, **kwargs):
    """adjustText ocultando las imágenes de fondo durante el ajuste.

    adjust_text redibuja la figura entera para medir los textos; con la
    ortofoto visible eso costaba 3-4 s por plano (1 s a 120 dpi). Las
    imágenes no influyen en el solapamiento de etiquetas.
    """
    from adjustText import adjust_text
    imagenes = [im for im in ax.images if im.get_visible()]
    for im in imagenes:
        im.set_visible(False)
    try:
        adjust_text(textos, ax=ax, **kwargs)
    finally:
        for im in imagenes:
            im.set_visible(True)

# ── Escala tipográfica (puntos) ──────────────────────────────────────────
# Usar estas constantes en lugar de tamaños sueltos para que todo el plano
# mantenga una jerarquía coherente.
TIPO_TITULO = 7.0     # títulos principales (cabecera, nº de plano)
TIPO_SECCION = 5.0    # títulos de panel / sección (LEYENDA, LOCALIZACIÓN…)
TIPO_ETIQUETA = 4.2   # etiquetas y valores de tablas / cajetín
TIPO_PEQUENO = 3.2    # notas, créditos, textos secundarios

COLOR_TINTA = "#1C2333"   # tinta principal de los elementos del mapa

# Longitudes "redondas" candidatas para la barra de escala sobre el mapa (m)
_BARRA_MAPA_CANDIDATOS_M = (50, 100, 200, 250, 500, 1000, 2000, 2500,
                            5000, 10000, 20000)


def halo(linewidth=2.5, color="white"):
    """Path effect de halo para que un texto se lea sobre cualquier fondo."""
    return [pe.withStroke(linewidth=linewidth, foreground=color)]


def formato_miles(valor):
    """Entero con punto como separador de miles: 4196000 → '4.196.000'."""
    return f"{int(round(valor)):,}".replace(",", ".")


def formato_distancia(metros):
    """Distancia legible con unidad: 500 → '500 m', 1000 → '1 km',
    2500 → '2,5 km', 62.5 → '62,5 m'."""
    if metros >= 1000:
        return f"{metros / 1000:g} km".replace(".", ",")
    return f"{metros:g} m".replace(".", ",")


def recortar_texto(texto, max_chars):
    """Recorta con elipsis (…) si supera ``max_chars`` caracteres."""
    texto = str(texto)
    if max_chars > 1 and len(texto) > max_chars:
        return texto[:max_chars - 1].rstrip() + "…"
    return texto


class ElementosMapaMixin:
    """Métodos de dibujo de elementos cartográficos sobre el mapa."""

    # Posición/tamaño del indicador de norte (fracción del eje del mapa)
    _NORTE_CX, _NORTE_CY = 0.045, 0.90
    _NORTE_H, _NORTE_W = 0.055, 0.014
    _NORTE_BG_W, _NORTE_BG_H = 0.042, 0.095

    # ── Utilidades de geometría del mapa ─────────────────────────────

    def _mapa_mm(self):
        """Tamaño físico (ancho, alto) del mapa en mm según la escala."""
        xlim = self.ax_map.get_xlim()
        ylim = self.ax_map.get_ylim()
        w_mm = abs(xlim[1] - xlim[0]) * 1000.0 / self.escala
        h_mm = abs(ylim[1] - ylim[0]) * 1000.0 / self.escala
        return max(w_mm, 1e-6), max(h_mm, 1e-6)

    def _zona_norte(self):
        """Rectángulo (x0, y0, x1, y1) en fracción de ejes ocupado por el norte."""
        cx, cy = self._NORTE_CX, self._NORTE_CY
        bg_w, bg_h = self._NORTE_BG_W, self._NORTE_BG_H
        y0 = cy - self._NORTE_H * 0.45 - 0.006
        m = 0.008
        return (cx - bg_w / 2 - m, y0 - m, cx + bg_w / 2 + m, y0 + bg_h + m)

    def _longitud_barra_mapa(self):
        """Longitud redonda de la barra (≈ ≤ 22 % del ancho del mapa)."""
        xlim = self.ax_map.get_xlim()
        objetivo = abs(xlim[1] - xlim[0]) * 0.22
        barra = _BARRA_MAPA_CANDIDATOS_M[0]
        for c in _BARRA_MAPA_CANDIDATOS_M:
            if c <= objetivo:
                barra = c
        return barra

    def _geometria_escala_mapa(self):
        """Caja de la escala gráfica del mapa, en fracción de ejes."""
        w_mm, h_mm = self._mapa_mm()
        barra_m = self._longitud_barra_mapa()
        bar_mm = barra_m * 1000.0 / self.escala
        lado_mm = 4.0     # holgura lateral para las etiquetas centradas
        pad_mm = 1.2
        txt_mm = 1.4      # alto de una línea de texto pequeño
        bar_h_mm = 1.1
        caja_w_mm = bar_mm + 2 * lado_mm
        caja_h_mm = pad_mm + txt_mm + 0.8 + bar_h_mm + 0.7 + txt_mm + pad_mm
        x0_mm, y0_mm = 3.0, 3.0
        fx = 1.0 / w_mm
        fy = 1.0 / h_mm
        return {
            "barra_m": barra_m,
            "caja": (x0_mm * fx, y0_mm * fy,
                     (x0_mm + caja_w_mm) * fx, (y0_mm + caja_h_mm) * fy),
            "bar_x0": (x0_mm + lado_mm) * fx,
            "bar_w": bar_mm * fx,
            "bar_y0": (y0_mm + pad_mm + txt_mm + 0.8) * fy,
            "bar_h": bar_h_mm * fy,
            "txt_escala_y": (y0_mm + pad_mm) * fy,
            "txt_dist_y": (y0_mm + pad_mm + txt_mm + 0.8 + bar_h_mm + 0.7) * fy,
            "fy": fy, "fx": fx,
        }

    # ── Grid UTM ──────────────────────────────────────────────────────

    @staticmethod
    def _formato_coord(valor):
        """Formatea coordenada UTM con punto como separador de miles (convención española).
        Ej: 508000 → '508.000', 4217500 → '4.217.500'
        """
        return formato_miles(valor)

    def dibujar_grid_utm(self, xmin, xmax, ymin, ymax):
        intervalo = _intervalo_grid(self.escala)
        ax = self.ax_map

        for sp in ax.spines.values():
            sp.set_linewidth(1.5)
            sp.set_color(COLOR_TINTA)

        # Sin títulos de eje (geopandas/rasterio pueden poner
        # "Easting [metre]"/"Northing [metre]"): las coordenadas van rotuladas
        # dentro del marco y el SRC se indica en la nota del mapa.
        ax.set_xlabel("")
        ax.set_ylabel("")

        # Margenes para filtrar líneas/etiquetas demasiado cerca de los bordes
        margen_x = (xmax - xmin) * 0.03
        margen_y = (ymax - ymin) * 0.04

        x0 = math.ceil(xmin / intervalo) * intervalo
        xs = np.arange(x0, xmax, intervalo)
        y0 = math.ceil(ymin / intervalo) * intervalo
        ys = np.arange(y0, ymax, intervalo)

        # Filtrar ticks cercanos a los bordes
        xs_filt = [x for x in xs if xmin + margen_x < x < xmax - margen_x]
        ys_filt = [y for y in ys if ymin + margen_y < y < ymax - margen_y]

        # Marcas cortas en el marco (sin rótulos: van dentro del mapa)
        ax.set_xticks(xs_filt)
        ax.set_yticks(ys_filt)
        ax.tick_params(which="major", length=2.5, width=0.5,
                       color=COLOR_TINTA, direction="out",
                       bottom=True, top=True, left=True, right=True,
                       labelbottom=False, labeltop=False,
                       labelleft=False, labelright=False)

        # Líneas de cuadrícula finas y discontinuas (solo las filtradas,
        # para no dibujar líneas pegadas al marco)
        _estilo = dict(color=COLOR_TINTA, linewidth=0.35, alpha=0.5,
                       linestyle=(0, (6, 4)), zorder=3)
        for x in xs_filt:
            ax.axvline(x, **_estilo)
        for y in ys_filt:
            ax.axhline(y, **_estilo)

        # Indicación del sistema de referencia (esquina inferior derecha del mapa)
        txt_src = ax.text(
            0.995, 0.005, "ETRS89 / UTM zona 30N · EPSG:25830",
            ha="right", va="bottom", fontsize=TIPO_PEQUENO, color=COLOR_TINTA,
            transform=ax.transAxes, zorder=12,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="#BDC3C7", linewidth=0.3, alpha=0.85))

        self._rotular_coordenadas(xs_filt, ys_filt, extra_ocupados=[txt_src])

    def _rotular_coordenadas(self, xs, ys, extra_ocupados=()):
        """Rótulos de coordenadas dentro del marco (4 lados) con halo.

        Se descartan los rótulos que pisarían el norte, la escala gráfica,
        la leyenda u otros rótulos ya colocados.
        """
        ax = self.ax_map
        try:
            ax.apply_aspect()
        except Exception:
            pass
        try:
            renderer = self.fig.canvas.get_renderer()
        except Exception:
            renderer = None

        to_disp = ax.transAxes.transform

        def _rect_disp(r):
            (a, b), (c, d) = to_disp((r[0], r[1])), to_disp((r[2], r[3]))
            return (min(a, c), min(b, d), max(a, c), max(b, d))

        ocupados = [_rect_disp(self._zona_norte()),
                    _rect_disp(self._geometria_escala_mapa()["caja"])]
        artistas = list(extra_ocupados)
        leg = ax.get_legend()
        if leg is not None:
            artistas.append(leg)
        if renderer is not None:
            for art in artistas:
                try:
                    bb = art.get_window_extent(renderer)
                    ocupados.append((bb.x0, bb.y0, bb.x1, bb.y1))
                except Exception:
                    pass

        def _solapa(a, b, m=1.0):
            return not (a[2] + m < b[0] or b[2] + m < a[0]
                        or a[3] + m < b[1] or b[3] + m < a[1])

        estilo = dict(fontsize=TIPO_ETIQUETA, color=COLOR_TINTA, zorder=13,
                      path_effects=halo(2.2), clip_on=False)
        tx = ax.get_xaxis_transform()   # x datos, y fracción de ejes
        ty = ax.get_yaxis_transform()   # x fracción de ejes, y datos
        d = 0.006
        rotulos = []
        for x in xs:
            txt = self._formato_coord(x)
            rotulos.append(ax.text(x, d, txt, ha="center", va="bottom",
                                   transform=tx, **estilo))
            rotulos.append(ax.text(x, 1 - d, txt, ha="center", va="top",
                                   transform=tx, **estilo))
        dx = d * 0.7
        for y in ys:
            txt = self._formato_coord(y)
            rotulos.append(ax.text(dx, y, txt, ha="left", va="center",
                                   rotation=90, transform=ty, **estilo))
            rotulos.append(ax.text(1 - dx, y, txt, ha="right", va="center",
                                   rotation=90, transform=ty, **estilo))

        if renderer is None:
            return
        for t in rotulos:
            try:
                bb = t.get_window_extent(renderer)
            except Exception:
                continue
            r = (bb.x0, bb.y0, bb.x1, bb.y1)
            if any(_solapa(r, o) for o in ocupados):
                t.remove()
            else:
                ocupados.append(r)

    # ── Escala gráfica sobre el mapa ─────────────────────────────────

    def dibujar_escala_grafica_mapa(self):
        """Barra de escala en la esquina inferior izquierda del mapa, sobre
        una caja blanca semitransparente para que se lea sobre cualquier fondo.
        Rótulos con unidad: 0 | 250 m | 500 m."""
        ax = self.ax_map
        g = self._geometria_escala_mapa()
        barra_m = g["barra_m"]
        cx0, cy0, cx1, cy1 = g["caja"]

        ax.add_patch(Rectangle(
            (cx0, cy0), cx1 - cx0, cy1 - cy0, transform=ax.transAxes,
            facecolor="white", edgecolor="#9AA5B1", linewidth=0.4,
            alpha=0.88, zorder=10))

        n_seg = 4
        seg_w = g["bar_w"] / n_seg
        for i in range(n_seg):
            ax.add_patch(Rectangle(
                (g["bar_x0"] + i * seg_w, g["bar_y0"]), seg_w, g["bar_h"],
                transform=ax.transAxes,
                facecolor=COLOR_TINTA if i % 2 == 0 else "white",
                edgecolor=COLOR_TINTA, linewidth=0.4, zorder=11))

        estilo = dict(fontsize=TIPO_PEQUENO, color=COLOR_TINTA, zorder=12,
                      transform=ax.transAxes, va="bottom", ha="center")
        y_txt = g["txt_dist_y"]
        ax.text(g["bar_x0"], y_txt, "0", **estilo)
        ax.text(g["bar_x0"] + g["bar_w"] / 2, y_txt,
                formato_distancia(barra_m / 2), **estilo)
        ax.text(g["bar_x0"] + g["bar_w"], y_txt,
                formato_distancia(barra_m), **estilo)

        escala_txt = f"Escala 1:{formato_miles(self.escala)}"
        ax.text((cx0 + cx1) / 2, g["txt_escala_y"], escala_txt,
                fontweight="bold", **estilo)

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

            # Centrada horizontalmente, desplazada encima de la geometría.
            # Halo blanco en lugar de caja: se lee sobre ortofoto u otros
            # fondos oscuros sin tapar el mapa.
            txt = self.ax_map.annotate(
                texto, xy=(cx, cy + offset_y), fontsize=5.5, fontweight="bold",
                color="#1A1A2E", ha="center", va="bottom", zorder=8,
                path_effects=halo(2.5),
            )
            textos_anotados.append(txt)

        # Anti-solapamiento: mover etiquetas que se pisan
        if len(textos_anotados) > 1:
            try:
                _adjust_text_sin_imagenes(
                    self.ax_map, textos_anotados,
                    arrowprops=dict(arrowstyle="-", color="#999999", lw=0.4))
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
                path_effects=halo(2.5),
            )
            textos_anotados.append(txt)

        if len(textos_anotados) > 1:
            try:
                _adjust_text_sin_imagenes(
                    self.ax_map, textos_anotados,
                    arrowprops=dict(arrowstyle="-", color="none", lw=0))
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

    _LEYENDA_MAX_CHARS = 34

    def dibujar_leyenda(self, items_leyenda, stats_resumen=None):  # noqa: ARG002
        from matplotlib.patches import Patch
        handles = []
        for item in items_leyenda:
            label, color, geom_type, linestyle, marker, facecolor = item[:6]
            # Etiquetas largas con elipsis: la leyenda no debe crecer hasta
            # tapar medio mapa ni desbordar su marco
            label = recortar_texto(label, self._LEYENDA_MAX_CHARS)
            if "point" in geom_type:
                h = Line2D([0], [0], marker=marker or "o", color="w",
                           markerfacecolor=color, markersize=5, label=label)
            elif "line" in geom_type or "string" in geom_type:
                h = Line2D([0], [0], color=color, linewidth=1.5,
                           linestyle=linestyle or "-", label=label)
            else:
                h = Patch(facecolor=facecolor or color,
                          edgecolor=color, linewidth=0.8,
                          label=label)
            handles.append(h)

        if handles:
            # Anclada justo encima de la caja de la escala gráfica
            g = self._geometria_escala_mapa()
            x_anc = g["caja"][0]
            y_anc = g["caja"][3] + 2.0 * g["fy"]
            leg = self.ax_map.legend(
                handles=handles, loc="lower left", fontsize=TIPO_ETIQUETA,
                bbox_to_anchor=(x_anc, y_anc), borderaxespad=0.0,
                title="LEYENDA", title_fontsize=TIPO_SECCION,
                frameon=True, framealpha=0.92, facecolor="white",
                edgecolor="#2C3E50", borderpad=0.6, labelspacing=0.5,
                handlelength=1.8, handletextpad=0.6,
                shadow=False, fancybox=True,
            )
            leg.set_zorder(15)
            leg.get_title().set_fontweight("bold")
            leg.get_title().set_color("#2C3E50")
            leg.get_frame().set_linewidth(0.6)

    # ── Norte ──────────────────────────────────────────────────────────

    def dibujar_norte_en_mapa(self):
        """Dibuja un indicador de norte minimalista y moderno en el mapa."""
        ax = self.ax_map
        from matplotlib.patches import Polygon as MplPolygon, FancyBboxPatch
        from matplotlib.path import Path
        import matplotlib.patches as mpatches

        # Posición (esquina superior izquierda) y tamaño: constantes de
        # clase compartidas con _zona_norte() para que los rótulos de
        # coordenadas nunca la pisen
        cx, cy = self._NORTE_CX, self._NORTE_CY
        h = self._NORTE_H        # altura total de la flecha
        w = self._NORTE_W        # ancho de la flecha

        # Fondo: rectángulo redondeado sutil
        bg_w, bg_h = self._NORTE_BG_W, self._NORTE_BG_H
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
                ha="center", va="bottom", fontsize=TIPO_SECCION + 0.5,
                fontweight="bold", color=COLOR_TINTA,
                transform=ax.transAxes, zorder=16)
