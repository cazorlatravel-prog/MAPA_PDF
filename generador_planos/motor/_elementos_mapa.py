"""Mixin de elementos cartográficos del mapa (grid UTM, escala, etiquetas, leyenda, norte)."""

import math

import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D
from .escala import INTERVALOS_GRID, BARRA_ESCALA_M


class ElementosMapaMixin:
    """Métodos de dibujo de elementos cartográficos sobre el mapa."""

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
                           fontsize=4.5, color="#2C3E50", rotation=90,
                           va="center")

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
                texto, xy=(cx, cy + offset_y), fontsize=5.5, fontweight="bold",
                color="#1A1A2E", ha="center", va="bottom", zorder=8,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor="#2C3E50", linewidth=0.5, alpha=0.90),
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
        from matplotlib.patches import Patch
        handles = []
        for item in items_leyenda:
            label, color, geom_type, linestyle, marker, facecolor = item[:6]
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
            leg = self.ax_map.legend(
                handles=handles, loc="lower left", fontsize=4.5,
                bbox_to_anchor=(0.0, 0.045),
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

    # ── Norte ──────────────────────────────────────────────────────────

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
