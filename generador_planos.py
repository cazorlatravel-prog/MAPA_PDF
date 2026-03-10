#!/usr/bin/env python3
"""
GENERADOR DE PLANOS FORESTALES - v1.0
Aplicación profesional para generación de planos cartográficos en serie
Autor: Generado con Claude AI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import threading
import os
import sys
import math
import io
import json
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# VERIFICACIÓN E IMPORTACIÓN DE DEPENDENCIAS
# ─────────────────────────────────────────────────────────────────────────────
missing = []
try:
    import geopandas as gpd
except ImportError:
    missing.append("geopandas")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec
    import matplotlib.ticker as mticker
    from matplotlib.patches import FancyBboxPatch, Rectangle
    from matplotlib.lines import Line2D
    from matplotlib.font_manager import FontProperties
    import matplotlib.patheffects as pe
except ImportError:
    missing.append("matplotlib")

try:
    import numpy as np
except ImportError:
    missing.append("numpy")

try:
    import requests
    from PIL import Image
except ImportError:
    missing.append("requests / Pillow")

try:
    import contextily as ctx
except ImportError:
    missing.append("contextily")

try:
    from pyproj import Transformer, CRS
except ImportError:
    missing.append("pyproj")

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A3, A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
except ImportError:
    missing.append("reportlab")

if missing:
    # Mostrar ventana de aviso con instrucciones de instalación
    root_warn = tk.Tk()
    root_warn.title("Dependencias faltantes")
    root_warn.geometry("600x400")
    root_warn.configure(bg="#1a1a2e")
    tk.Label(root_warn, text="⚠ Faltan librerías necesarias", font=("Consolas", 14, "bold"),
             bg="#1a1a2e", fg="#e94560").pack(pady=20)
    tk.Label(root_warn, text="Ejecuta en tu terminal:", font=("Consolas", 11),
             bg="#1a1a2e", fg="#aaaacc").pack()
    cmd = "pip install geopandas matplotlib numpy requests Pillow contextily pyproj reportlab"
    txt = tk.Text(root_warn, height=3, font=("Consolas", 10), bg="#0f3460", fg="#e2e2e2")
    txt.insert("1.0", cmd)
    txt.pack(padx=20, pady=10, fill="x")
    tk.Label(root_warn, text=f"Faltantes: {', '.join(missing)}", font=("Consolas", 10),
             bg="#1a1a2e", fg="#ff6b6b").pack(pady=5)
    tk.Button(root_warn, text="Cerrar", command=root_warn.destroy,
              bg="#e94560", fg="white", font=("Consolas", 11)).pack(pady=10)
    root_warn.mainloop()
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

ESCALAS = [5000, 7500, 10000, 15000, 20000]

CAPAS_BASE = {
    "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "PNOA Ortofoto (IGN)": "https://www.ign.es/wmts/pnoa-ma?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=OI.OrthoimageCoverage&STYLE=default&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
    "IGN Topográfico": "https://www.ign.es/wmts/mapa-raster?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=MTN&STYLE=default&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
    "Stamen Terrain": "https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png",
}

PROVIDERS_CTX = {
    "OpenStreetMap":        ctx.providers.OpenStreetMap.Mapnik,
    "PNOA Ortofoto (IGN)":  {
        "url": "https://www.ign.es/wmts/pnoa-ma?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=OI.OrthoimageCoverage&STYLE=default&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
        "max_zoom": 20, "attribution": "© IGN España"
    },
    "IGN Topográfico": {
        "url": "https://www.ign.es/wmts/mapa-raster?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=MTN&STYLE=default&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
        "max_zoom": 18, "attribution": "© IGN España"
    },
    "Stamen Terrain":       ctx.providers.Stamen.Terrain,
}

CAMPOS_ATRIBUTOS = [
    "Provincia", "Municipio", "Monte", "Cod_Monte",
    "CEDEFO", "Cod_Infoca", "Nombre_Infra", "Superficie",
    "Longitud", "Ancho", "Tipo_Trabajos"
]

# Colores paleta profesional forestal
COLOR_FONDO_APP    = "#1C2333"
COLOR_PANEL        = "#242D40"
COLOR_ACENTO       = "#2ECC71"
COLOR_ACENTO2      = "#27AE60"
COLOR_TEXTO        = "#ECF0F1"
COLOR_TEXTO_GRIS   = "#95A5A6"
COLOR_BORDE        = "#2C3E50"
COLOR_HOVER        = "#2ECC7120"
COLOR_ERROR        = "#E74C3C"
COLOR_ADVERTENCIA  = "#F39C12"
COLOR_EXITO        = "#27AE60"

FONT_TITULO  = ("Helvetica", 22, "bold")
FONT_LABEL   = ("Helvetica", 10)
FONT_SMALL   = ("Helvetica", 9)
FONT_BOLD    = ("Helvetica", 10, "bold")
FONT_MONO    = ("Courier", 9)


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DE GENERACIÓN DE PLANOS
# ─────────────────────────────────────────────────────────────────────────────

class GeneradorPlanos:
    """Motor principal de generación de planos cartográficos profesionales."""

    # Tamaños A3/A4 en mm → convertidos a pulgadas para matplotlib
    FORMATOS = {
        "A4 Vertical":   (210, 297),
        "A4 Horizontal": (297, 210),
        "A3 Vertical":   (297, 420),
        "A3 Horizontal": (420, 297),
    }

    MARGENES_MM = {"izq": 20, "der": 15, "sup": 15, "inf": 30}

    def __init__(self, config: dict):
        self.cfg = config
        self.gdf_infra  = None   # capa infraestructuras
        self.gdf_montes = None   # capa montes (opcional)

    # ── Carga de capas ─────────────────────────────────────────────────────

    def cargar_infraestructuras(self, ruta: str) -> tuple[bool, str]:
        try:
            gdf = gpd.read_file(ruta)
            # Reproyectar a ETRS89 / UTM zona 30N (EPSG:25830) si es necesario
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs("EPSG:25830")
            self.gdf_infra = gdf
            return True, f"✓ {len(gdf)} infraestructuras cargadas | CRS: {gdf.crs.name}"
        except Exception as e:
            return False, f"Error al cargar shapefile: {e}"

    def cargar_montes(self, ruta: str) -> tuple[bool, str]:
        try:
            gdf = gpd.read_file(ruta)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs("EPSG:25830")
            self.gdf_montes = gdf
            return True, f"✓ Capa montes: {len(gdf)} elementos"
        except Exception as e:
            return False, f"Error al cargar montes: {e}"

    # ── Selección automática de escala ─────────────────────────────────────

    def _escala_optima(self, geom, formato_mm: tuple) -> int:
        """Elige la escala más ajustada de la lista ESCALAS."""
        ancho_mapa_mm = (formato_mm[0]
                         - self.MARGENES_MM["izq"]
                         - self.MARGENES_MM["der"]) * 0.75  # ~75% ancho para mapa
        alto_mapa_mm  = (formato_mm[1]
                         - self.MARGENES_MM["sup"]
                         - self.MARGENES_MM["inf"]) * 0.90

        bounds = geom.bounds  # (minx, miny, maxx, maxy) en metros ETRS89
        ext_x = bounds[2] - bounds[0]
        ext_y = bounds[3] - bounds[1]

        # Añadir margen del 20% alrededor
        ext_x *= 1.20
        ext_y *= 1.20
        if ext_x == 0 and ext_y == 0:
            ext_x = ext_y = 500  # punto: usar 500 m por defecto

        for escala in ESCALAS:
            cap_x = ancho_mapa_mm / 1000 * escala  # metros que caben en el mapa
            cap_y = alto_mapa_mm  / 1000 * escala
            if cap_x >= ext_x and cap_y >= ext_y:
                return escala

        return ESCALAS[-1]

    # ── Descarga de teselas de fondo ───────────────────────────────────────

    def _fondo_cartografico(self, ax, gdf_view, proveedor_key: str):
        """Añade capa base de teselas al eje matplotlib."""
        try:
            proveedor = PROVIDERS_CTX.get(proveedor_key, ctx.providers.OpenStreetMap.Mapnik)
            ctx.add_basemap(
                ax,
                crs=gdf_view.crs.to_string(),
                source=proveedor,
                zoom="auto",
                attribution=False,
            )
        except Exception as e:
            print(f"[WARN] No se pudo cargar fondo cartográfico: {e}")
            ax.set_facecolor("#E8E8E0")

    # ── Generación de un plano individual ──────────────────────────────────

    def generar_plano(self, idx_fila: int, formato_key: str,
                      proveedor: str, transparencia_montes: float,
                      campos_visibles: list, color_infra: str,
                      salida_dir: str, callback_log=None) -> str:

        def log(msg):
            if callback_log:
                callback_log(msg)

        row = self.gdf_infra.iloc[idx_fila]
        geom = row.geometry

        fmt_mm = self.FORMATOS[formato_key]
        escala = self._escala_optima(geom, fmt_mm)

        log(f"  Escala elegida: 1:{escala:,}")

        # ── Calcular extensión del mapa ──
        cx, cy = geom.centroid.x, geom.centroid.y
        ancho_mapa_mm  = (fmt_mm[0] * 0.62)  # ~62% del ancho total
        alto_mapa_mm   = (fmt_mm[1]
                          - self.MARGENES_MM["sup"]
                          - self.MARGENES_MM["inf"]
                          - 10)  # 10 mm margen interno

        semiancho_m = (ancho_mapa_mm / 1000) * escala / 2
        semialto_m  = (alto_mapa_mm  / 1000) * escala / 2

        xmin, xmax = cx - semiancho_m, cx + semiancho_m
        ymin, ymax = cy - semialto_m,  cy + semialto_m

        # ── Crear figura ──
        dpi = 150
        fig_w_in = fmt_mm[0] / 25.4
        fig_h_in = fmt_mm[1] / 25.4
        fig = plt.figure(figsize=(fig_w_in, fig_h_in), dpi=dpi, facecolor="white")

        # Layout: mapa principal (izq) + panel info (der)
        gs = gridspec.GridSpec(
            2, 2,
            figure=fig,
            left   = self.MARGENES_MM["izq"] / fmt_mm[0],
            right  = 1 - self.MARGENES_MM["der"] / fmt_mm[0],
            top    = 1 - self.MARGENES_MM["sup"] / fmt_mm[1],
            bottom = self.MARGENES_MM["inf"] / fmt_mm[1],
            width_ratios=[0.63, 0.37],
            height_ratios=[0.82, 0.18],
            hspace=0.06,
            wspace=0.04,
        )

        ax_map   = fig.add_subplot(gs[0, 0])  # mapa principal
        ax_info  = fig.add_subplot(gs[0, 1])  # panel atributos
        ax_mini  = fig.add_subplot(gs[1, 1])  # mapa de posición
        ax_esc   = fig.add_subplot(gs[1, 0])  # barra de escala + créditos

        # ─── MAPA PRINCIPAL ────────────────────────────────────────────────
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)
        ax_map.set_aspect("equal")

        # Fondo cartográfico
        gdf_view = self.gdf_infra.iloc[[idx_fila]].copy()
        self._fondo_cartografico(ax_map, gdf_view, proveedor)

        # Capa montes
        if self.gdf_montes is not None:
            montes_clip = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
            if not montes_clip.empty:
                montes_clip.plot(
                    ax=ax_map,
                    facecolor="#229922",
                    edgecolor="#1a5c10",
                    linewidth=0.8,
                    alpha=transparencia_montes,
                )

        # Infraestructuras de fondo (todas las del mapa, gris)
        infra_fondo = self.gdf_infra.cx[xmin:xmax, ymin:ymax]
        if not infra_fondo.empty:
            infra_fondo.plot(
                ax=ax_map,
                color="#999999",
                linewidth=0.6,
                markersize=3,
                alpha=0.5,
            )

        # Infraestructura seleccionada (resaltada)
        gdf_sel = self.gdf_infra.iloc[[idx_fila]]
        geom_type = str(geom.geom_type).lower()
        if "point" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, markersize=12,
                         marker="o", zorder=5,
                         edgecolor="white", linewidth=0.8)
        elif "line" in geom_type or "string" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, linewidth=2.5, zorder=5)
        else:
            gdf_sel.plot(ax=ax_map, facecolor=color_infra + "55",
                         edgecolor=color_infra, linewidth=1.8, zorder=5)

        # ── Grid de coordenadas (ETRS89 UTM) ──
        self._dibujar_grid(ax_map, xmin, xmax, ymin, ymax, escala)

        # ── Leyenda (sólo infraestructuras visibles en el mapa) ──
        self._dibujar_leyenda(ax_map, infra_fondo, gdf_sel, color_infra)

        # ── Estilo del eje del mapa ──
        ax_map.tick_params(which="both", length=0)
        for spine in ax_map.spines.values():
            spine.set_linewidth(0.8)
            spine.set_color("#333333")

        # ─── PANEL DE ATRIBUTOS ────────────────────────────────────────────
        self._dibujar_panel_atributos(ax_info, row, campos_visibles, escala)

        # ─── MAPA DE POSICIÓN ──────────────────────────────────────────────
        self._dibujar_mapa_posicion(ax_mini, geom, cx, cy)

        # ─── BARRA DE ESCALA + PIE ─────────────────────────────────────────
        self._dibujar_pie_pagina(ax_esc, escala, proveedor, fmt_mm)

        # ─── CABECERA SUPERIOR ─────────────────────────────────────────────
        self._dibujar_cabecera(fig, row, fmt_mm)

        # ─── MARCO EXTERIOR PROFESIONAL ────────────────────────────────────
        self._dibujar_marcos(fig, fmt_mm)

        # ── Guardar ──
        nombre_infra = str(row.get("Nombre_Infra", f"infra_{idx_fila:04d}"))
        nombre_infra = "".join(c for c in nombre_infra if c.isalnum() or c in "_ -")[:40]
        nombre_arch  = f"plano_{idx_fila:04d}_{nombre_infra}.pdf"
        ruta_out     = os.path.join(salida_dir, nombre_arch)

        fig.savefig(ruta_out, format="pdf", dpi=dpi,
                    bbox_inches="tight", facecolor="white")
        plt.close(fig)

        log(f"  ✓ Guardado: {nombre_arch}")
        return ruta_out

    # ── Leyenda de infraestructuras visibles ────────────────────────────────

    def _dibujar_leyenda(self, ax, infra_visibles, gdf_seleccionada, color_infra):
        """Dibuja una leyenda elegante sólo con las infraestructuras visibles."""
        # Determinar tipos visibles
        col_tipo = None
        for col_name in ["Tipo_Trabajos", "Nombre_Infra", "TIPO", "tipo"]:
            if infra_visibles is not None and not infra_visibles.empty:
                if col_name in infra_visibles.columns:
                    col_tipo = col_name
                    break

        if col_tipo is None or infra_visibles is None or infra_visibles.empty:
            return

        tipos_visibles = infra_visibles[col_tipo].dropna().unique()
        if len(tipos_visibles) == 0:
            return

        # Limitar a máximo 8 tipos para que quepa la leyenda
        tipos_visibles = sorted(set(str(t) for t in tipos_visibles if str(t).strip()))[:8]
        if not tipos_visibles:
            return

        # Paleta de colores profesional para la leyenda
        paleta = ["#E74C3C", "#3498DB", "#2ECC71", "#F39C12",
                  "#9B59B6", "#1ABC9C", "#E67E22", "#34495E"]

        # Determinar tipo de geometría para los símbolos
        geom_type = str(infra_visibles.iloc[0].geometry.geom_type).lower()

        handles = []
        for i, tipo in enumerate(tipos_visibles):
            color = paleta[i % len(paleta)]
            label = str(tipo)[:30]  # Limitar longitud

            if "point" in geom_type:
                h = Line2D([0], [0], marker='o', color='none',
                           markerfacecolor=color, markeredgecolor='white',
                           markersize=6, label=label)
            elif "line" in geom_type or "string" in geom_type:
                h = Line2D([0], [0], color=color, linewidth=2, label=label)
            else:
                h = mpatches.Patch(facecolor=color + "88",
                                   edgecolor=color, linewidth=1,
                                   label=label)
            handles.append(h)

        # Añadir entrada para la infraestructura seleccionada
        sel_label = "Infra. seleccionada"
        if "point" in geom_type:
            h_sel = Line2D([0], [0], marker='o', color='none',
                           markerfacecolor=color_infra, markeredgecolor='white',
                           markersize=7, markeredgewidth=1.2, label=sel_label)
        elif "line" in geom_type or "string" in geom_type:
            h_sel = Line2D([0], [0], color=color_infra, linewidth=3, label=sel_label)
        else:
            h_sel = mpatches.Patch(facecolor=color_infra + "55",
                                   edgecolor=color_infra, linewidth=2,
                                   label=sel_label)
        handles.append(h_sel)

        legend = ax.legend(
            handles=handles,
            loc="lower left",
            fontsize=5,
            frameon=True,
            fancybox=True,
            shadow=True,
            framealpha=0.92,
            facecolor="white",
            edgecolor="#2C3E50",
            title="SIMBOLOGÍA",
            title_fontsize=6,
            borderpad=0.8,
            labelspacing=0.5,
            handlelength=1.5,
            handleheight=0.8,
        )
        legend.get_title().set_fontweight("bold")
        legend.get_title().set_color("#2C3E50")
        legend.set_zorder(10)

    # ── Grid de coordenadas ────────────────────────────────────────────────

    def _dibujar_grid(self, ax, xmin, xmax, ymin, ymax, escala):
        """Dibuja grid de coordenadas UTM profesional."""
        # Intervalo del grid según escala
        intervalos = {
            5000:  500,
            7500:  500,
            10000: 1000,
            15000: 1000,
            20000: 2000,
        }
        intervalo = intervalos.get(escala, 1000)

        # Margen para evitar que los números se solapen con los bordes/cajetines
        margen_x = (xmax - xmin) * 0.03
        margen_y = (ymax - ymin) * 0.06  # mayor margen inferior

        # Líneas verticales
        x0 = math.ceil(xmin / intervalo) * intervalo
        xs = np.arange(x0, xmax, intervalo)
        # Filtrar las líneas demasiado cercanas a los bordes
        xs = [x for x in xs if x > xmin + margen_x and x < xmax - margen_x]
        for x in xs:
            ax.axvline(x, color="#2255AA", linewidth=0.25, linestyle="--",
                       alpha=0.5, zorder=2)
            ax.text(x, ymax - (ymax - ymin) * 0.01, f"{int(x):,}",
                    ha="center", va="top", fontsize=5, color="#2255AA",
                    rotation=90, alpha=0.8,
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="white",
                              edgecolor="none", alpha=0.6))

        # Líneas horizontales
        y0 = math.ceil(ymin / intervalo) * intervalo
        ys = np.arange(y0, ymax, intervalo)
        # Filtrar las líneas demasiado cercanas a los bordes
        ys = [y for y in ys if y > ymin + margen_y and y < ymax - margen_y]
        for y in ys:
            ax.axhline(y, color="#2255AA", linewidth=0.25, linestyle="--",
                       alpha=0.5, zorder=2)
            ax.text(xmin + (xmax - xmin) * 0.005, y, f"{int(y):,}",
                    ha="left", va="center", fontsize=5, color="#2255AA",
                    alpha=0.8,
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="white",
                              edgecolor="none", alpha=0.6))

        # Cruces en intersecciones
        for x in xs:
            for y in ys:
                ax.plot(x, y, "+", color="#2255AA", markersize=4,
                        markeredgewidth=0.4, alpha=0.6, zorder=3)

    # ── Panel de atributos ─────────────────────────────────────────────────

    def _dibujar_panel_atributos(self, ax, row, campos_visibles, escala):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Fondo
        fondo = FancyBboxPatch((0, 0), 1, 1,
                               boxstyle="round,pad=0.01",
                               facecolor="#F8F9FA", edgecolor="#2C3E50",
                               linewidth=1.2, zorder=0)
        ax.add_patch(fondo)

        # Título del panel
        ax.text(0.5, 0.97, "DATOS DE LA INFRAESTRUCTURA",
                ha="center", va="top", fontsize=7.5, fontweight="bold",
                color="white", transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#2C3E50",
                          edgecolor="none"))

        campos_mostrar = [c for c in CAMPOS_ATRIBUTOS if c in campos_visibles]
        n = len(campos_mostrar)
        if n == 0:
            return

        # Etiquetas amigables
        etiquetas = {
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

        y_start = 0.90
        row_h   = (y_start - 0.05) / max(n, 1)

        for i, campo in enumerate(campos_mostrar):
            y = y_start - i * row_h
            valor = str(row.get(campo, "—"))
            etiq  = etiquetas.get(campo, campo)

            # Fondo alterno
            if i % 2 == 0:
                rect = Rectangle((0.01, y - row_h + 0.005), 0.98, row_h - 0.005,
                                  facecolor="#E8F4F8", edgecolor="none", zorder=1)
                ax.add_patch(rect)

            # Etiqueta (parte superior de la fila)
            ax.text(0.04, y - row_h * 0.3, etiq + ":",
                    ha="left", va="center", fontsize=6, fontweight="bold",
                    color="#2C3E50", transform=ax.transAxes, zorder=2)

            # Valor (misma línea, tras la etiqueta)
            # Ajustar tamaño de fuente para valores largos
            val_fontsize = 6
            if len(valor) > 35:
                val_fontsize = 5
            if len(valor) > 50:
                val_fontsize = 4.5

            ax.text(0.04, y - row_h * 0.7, valor,
                    ha="left", va="center", fontsize=val_fontsize,
                    color="#1A1A2E", transform=ax.transAxes, zorder=2)

        # Línea separadora bajo cada campo
        for i in range(1, n):
            y_line = y_start - i * row_h
            ax.axhline(y=y_line, xmin=0.02, xmax=0.98, color="#CCCCCC",
                       linewidth=0.4, transform=ax.transAxes, zorder=2)

        # Sistema de coordenadas
        ax.text(0.5, 0.03,
                "Sistema de Referencia: ETRS89 / UTM Huso 30N (EPSG:25830)",
                ha="center", va="bottom", fontsize=5.5, color="#555555",
                style="italic", transform=ax.transAxes)

        # Escala
        ax.text(0.5, 0.07,
                f"Escala 1:{escala:,}",
                ha="center", va="bottom", fontsize=7, fontweight="bold",
                color="#2C3E50", transform=ax.transAxes)

    # ── Mapa de posición ───────────────────────────────────────────────────

    def _dibujar_mapa_posicion(self, ax, geom, cx, cy):
        """Mapa de posición pequeño mostrando la ubicación en España."""
        ax.set_xlim(-9.5, 4.5)
        ax.set_ylim(35.5, 44.0)
        ax.set_aspect("equal")
        ax.set_facecolor("#D6EAF8")

        # Marco
        for spine in ax.spines.values():
            spine.set_linewidth(1.0)
            spine.set_color("#2C3E50")

        ax.tick_params(labelbottom=False, labelleft=False,
                       bottom=False, left=False)

        # Contorno simplificado de España (polígono aproximado)
        spain_x = [-9.2, -8.8, -8.2, -7.5, -6.8, -5.5, -4.5, -3.3,
                   -1.8, -0.5, 0.3, 1.8, 3.3, 3.3, 3.0, 2.0,
                   1.0, 0.2, -0.8, -1.7, -2.0, -1.8, -1.6, -2.5,
                   -4.5, -6.0, -7.2, -8.5, -9.2, -9.2]
        spain_y = [41.8, 43.7, 43.7, 43.7, 43.7, 43.7, 43.5, 43.4,
                   43.5, 43.4, 42.8, 42.3, 42.4, 41.0, 40.5, 40.8,
                   40.7, 40.0, 38.8, 37.5, 37.0, 36.6, 36.2, 36.0,
                   36.0, 36.2, 36.7, 37.5, 39.0, 41.8]
        ax.fill(spain_x, spain_y, color="#C8E6C9", edgecolor="#2C3E50",
                linewidth=0.6, alpha=0.9)

        # Punto de ubicación (convertir UTM a geográfico aprox.)
        try:
            transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326",
                                               always_xy=True)
            lon, lat = transformer.transform(cx, cy)
            # Círculo exterior
            ax.plot(lon, lat, "o", color="white", markersize=8, zorder=5)
            # Círculo interior rojo
            ax.plot(lon, lat, "o", color="#E74C3C", markersize=5,
                    zorder=6, markeredgecolor="white", markeredgewidth=0.5)
        except Exception:
            pass

        ax.set_title("LOCALIZACIÓN", fontsize=6, fontweight="bold",
                     color="#2C3E50", pad=2)

    # ── Barra de escala y pie ──────────────────────────────────────────────

    def _dibujar_pie_pagina(self, ax, escala, proveedor, fmt_mm):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # ── Barra de escala gráfica ──
        barra_m = 1000 if escala <= 10000 else 2000  # metros representados
        barra_mm_papel = (barra_m / escala) * 1000    # mm en papel
        fig_w_mm = fmt_mm[0] * 0.62  # ancho zona mapa en mm

        # Normalizado al eje (0-1)
        frac = min(barra_mm_papel / fig_w_mm, 0.4)
        x0, y0 = 0.02, 0.55

        # Barra bicolor
        n_seg = 4
        seg = frac / n_seg
        for i in range(n_seg):
            color = "#1A1A2E" if i % 2 == 0 else "white"
            rect  = Rectangle((x0 + i * seg, y0), seg, 0.18,
                               facecolor=color, edgecolor="#1A1A2E",
                               linewidth=0.6)
            ax.add_patch(rect)

        # Etiquetas de la barra
        ax.text(x0, y0 - 0.12, "0", ha="center", va="top", fontsize=7,
                color="#1A1A2E")
        ax.text(x0 + frac / 2, y0 - 0.12, f"{barra_m // 2} m",
                ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac, y0 - 0.12, f"{barra_m} m",
                ha="center", va="top", fontsize=7, color="#1A1A2E")
        ax.text(x0 + frac / 2, y0 + 0.28,
                f"Escala 1:{escala:,}", ha="center", va="bottom",
                fontsize=8, fontweight="bold", color="#1A1A2E")

        # Norte
        ax.annotate("", xy=(0.55, 0.95), xytext=(0.55, 0.50),
                    arrowprops=dict(arrowstyle="->", color="#1A1A2E", lw=1.5))
        ax.text(0.55, 0.98, "N", ha="center", va="top",
                fontsize=11, fontweight="bold", color="#1A1A2E")

        # Créditos
        from datetime import date
        fecha = date.today().strftime("%d/%m/%Y")
        ax.text(0.98, 0.05,
                f"Cartografía base: {proveedor} | ETRS89 UTM H30N | Fecha: {fecha}",
                ha="right", va="bottom", fontsize=5.5, color="#666666",
                style="italic")

    # ── Cabecera del plano ─────────────────────────────────────────────────

    def _dibujar_cabecera(self, fig, row, fmt_mm):
        # Banda superior
        ax_cab = fig.add_axes([
            self.MARGENES_MM["izq"] / fmt_mm[0],
            (fmt_mm[1] - self.MARGENES_MM["sup"]) / fmt_mm[1],
            (fmt_mm[0] - self.MARGENES_MM["izq"] - self.MARGENES_MM["der"]) / fmt_mm[0],
            (self.MARGENES_MM["sup"] - 2) / fmt_mm[1],
        ])
        ax_cab.set_xlim(0, 1)
        ax_cab.set_ylim(0, 1)
        ax_cab.axis("off")

        # Fondo cabecera
        ax_cab.add_patch(Rectangle((0, 0), 1, 1, facecolor="#1C2333",
                                   edgecolor="#2ECC71", linewidth=1.2))

        # Logo / Título organización (izquierda)
        ax_cab.text(0.01, 0.5,
                    "CONSEJERÍA DE SOSTENIBILIDAD\nJUNTA DE ANDALUCÍA",
                    ha="left", va="center", fontsize=6.5, fontweight="bold",
                    color="#2ECC71", linespacing=1.4)

        # Título del plano (centro)
        nombre = str(row.get("Nombre_Infra", "INFRAESTRUCTURA FORESTAL"))
        ax_cab.text(0.5, 0.65, nombre.upper(),
                    ha="center", va="center", fontsize=9, fontweight="bold",
                    color="white")
        ax_cab.text(0.5, 0.25, "PLANO DE INFRAESTRUCTURA FORESTAL",
                    ha="center", va="center", fontsize=6.5, color="#95A5A6")

        # Número de plano (derecha)
        ax_cab.text(0.99, 0.5, f"Plano nº\n{row.name + 1:04d}",
                    ha="right", va="center", fontsize=7, fontweight="bold",
                    color="#2ECC71")

    # ── Marcos profesionales ───────────────────────────────────────────────

    def _dibujar_marcos(self, fig, fmt_mm):
        """Marco exterior e interior profesional."""
        # Marco exterior
        ax_marco = fig.add_axes([0, 0, 1, 1])
        ax_marco.set_xlim(0, fmt_mm[0])
        ax_marco.set_ylim(0, fmt_mm[1])
        ax_marco.axis("off")
        ax_marco.set_zorder(-10)

        # Marco doble exterior
        ax_marco.add_patch(Rectangle((3, 3), fmt_mm[0] - 6, fmt_mm[1] - 6,
                                     fill=False, edgecolor="#1C2333", linewidth=2.0))
        ax_marco.add_patch(Rectangle((5, 5), fmt_mm[0] - 10, fmt_mm[1] - 10,
                                     fill=False, edgecolor="#2ECC71", linewidth=0.5))

    # ── Generación en serie ────────────────────────────────────────────────

    def generar_serie(self, indices: list, formato_key: str, proveedor: str,
                      transparencia: float, campos: list, color_infra: str,
                      salida_dir: str, callback_log=None,
                      callback_progreso=None) -> list:
        """Genera planos en serie para los índices indicados."""
        rutas = []
        total = len(indices)
        for i, idx in enumerate(indices):
            nombre = self.gdf_infra.iloc[idx].get("Nombre_Infra", f"#{idx}")
            if callback_log:
                callback_log(f"\n[{i+1}/{total}] Generando: {nombre}")
            try:
                ruta = self.generar_plano(
                    idx_fila      = idx,
                    formato_key   = formato_key,
                    proveedor     = proveedor,
                    transparencia_montes = transparencia,
                    campos_visibles = campos,
                    color_infra   = color_infra,
                    salida_dir    = salida_dir,
                    callback_log  = callback_log,
                )
                rutas.append(ruta)
            except Exception as e:
                if callback_log:
                    callback_log(f"  ✗ Error: {e}")
            if callback_progreso:
                callback_progreso(i + 1, total)
        return rutas


# ─────────────────────────────────────────────────────────────────────────────
# INTERFAZ GRÁFICA
# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Generador de Planos Forestales v1.0")
        self.geometry("1100x780")
        self.configure(bg=COLOR_FONDO_APP)
        self.resizable(True, True)

        self.motor = GeneradorPlanos({})
        self._color_infra = "#E74C3C"

        self._construir_ui()
        self._actualizar_titulo()

    # ── Construcción de la UI ──────────────────────────────────────────────

    def _construir_ui(self):
        # ── Barra superior ──
        self._barra_superior()

        # ── Contenedor principal ──
        main = tk.Frame(self, bg=COLOR_FONDO_APP)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Columna izquierda (controles)
        izq = tk.Frame(main, bg=COLOR_PANEL, bd=0)
        izq.pack(side="left", fill="y", padx=(0, 8), pady=4)

        # Columna derecha (log + tabla)
        der = tk.Frame(main, bg=COLOR_FONDO_APP)
        der.pack(side="right", fill="both", expand=True, pady=4)

        self._panel_capas(izq)
        self._panel_configuracion(izq)
        self._panel_campos(izq)
        self._panel_generacion(izq)

        self._panel_tabla(der)
        self._panel_log(der)

    def _barra_superior(self):
        barra = tk.Frame(self, bg="#141B2D", height=58)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        tk.Label(barra, text="🗺  GENERADOR DE PLANOS FORESTALES",
                 font=("Helvetica", 16, "bold"),
                 bg="#141B2D", fg=COLOR_ACENTO).pack(side="left", padx=16, pady=10)

        tk.Label(barra, text="ETRS89 · UTM H30N · INFOCA",
                 font=("Helvetica", 9), bg="#141B2D",
                 fg=COLOR_TEXTO_GRIS).pack(side="right", padx=16)

    # ── Panel: Carga de capas ──────────────────────────────────────────────

    def _panel_capas(self, parent):
        f = self._frame_seccion(parent, "📂  CAPAS")

        # Infraestructuras
        tk.Label(f, text="Shapefile Infraestructuras *",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=0, column=0, sticky="w", pady=(0, 2))

        self._ruta_infra = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_infra, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(
                 row=1, column=0, sticky="w")

        self._btn_infra = self._boton(f, "Cargar Shapefile",
                                      self._cargar_infra, icono="📥")
        self._btn_infra.grid(row=2, column=0, sticky="ew", pady=(4, 8))

        # Montes
        tk.Label(f, text="Capa Montes (opcional)",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=3, column=0, sticky="w", pady=(0, 2))

        self._ruta_montes = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_montes, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(
                 row=4, column=0, sticky="w")

        self._btn_montes = self._boton(f, "Cargar Montes",
                                       self._cargar_montes, icono="🌲")
        self._btn_montes.grid(row=5, column=0, sticky="ew", pady=(4, 2))

        # Transparencia montes
        tk.Label(f, text="Transparencia capa montes:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=6, column=0, sticky="w", pady=(6, 0))
        self._transp = tk.DoubleVar(value=0.5)
        sl = ttk.Scale(f, from_=0.0, to=1.0, variable=self._transp,
                       orient="horizontal")
        sl.grid(row=7, column=0, sticky="ew", pady=(2, 8))

        f.columnconfigure(0, weight=1)

    # ── Panel: Configuración ───────────────────────────────────────────────

    def _panel_configuracion(self, parent):
        f = self._frame_seccion(parent, "⚙  CONFIGURACIÓN")

        # Formato
        tk.Label(f, text="Formato de salida:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=0, column=0, sticky="w")
        self._formato = tk.StringVar(value="A3 Horizontal")
        cb_fmt = ttk.Combobox(f, textvariable=self._formato,
                              values=list(GeneradorPlanos.FORMATOS.keys()),
                              state="readonly", font=FONT_LABEL)
        cb_fmt.grid(row=1, column=0, sticky="ew", pady=(2, 8))

        # Cartografía de fondo
        tk.Label(f, text="Cartografía de fondo:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=2, column=0, sticky="w")
        self._proveedor = tk.StringVar(value="OpenStreetMap")
        cb_prov = ttk.Combobox(f, textvariable=self._proveedor,
                               values=list(PROVIDERS_CTX.keys()),
                               state="readonly", font=FONT_LABEL)
        cb_prov.grid(row=3, column=0, sticky="ew", pady=(2, 8))

        # Color infraestructura
        tk.Label(f, text="Color infraestructura:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=4, column=0, sticky="w")
        btn_color_frame = tk.Frame(f, bg=COLOR_PANEL)
        btn_color_frame.grid(row=5, column=0, sticky="ew", pady=(2, 8))
        self._lbl_color = tk.Label(btn_color_frame, bg=self._color_infra,
                                   width=4, relief="solid", bd=1)
        self._lbl_color.pack(side="left", padx=(0, 6))
        tk.Button(btn_color_frame, text="Elegir color",
                  command=self._elegir_color, font=FONT_SMALL,
                  bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2").pack(side="left")

        # Carpeta de salida
        tk.Label(f, text="Carpeta de salida:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=6, column=0, sticky="w")
        self._salida = tk.StringVar(value=str(Path.home() / "Planos_Forestales"))
        tk.Label(f, textvariable=self._salida, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=7, column=0, sticky="w")
        self._boton(f, "Seleccionar carpeta",
                    self._elegir_carpeta, icono="📁").grid(
                    row=8, column=0, sticky="ew", pady=(4, 4))

        f.columnconfigure(0, weight=1)

    # ── Panel: Campos a mostrar ────────────────────────────────────────────

    def _panel_campos(self, parent):
        f = self._frame_seccion(parent, "🏷  CAMPOS EN EL PLANO")

        self._check_campos = {}
        for i, campo in enumerate(CAMPOS_ATRIBUTOS):
            var = tk.BooleanVar(value=True)
            cb  = tk.Checkbutton(f, text=campo, variable=var,
                                 font=FONT_SMALL, bg=COLOR_PANEL,
                                 fg=COLOR_TEXTO, selectcolor=COLOR_BORDE,
                                 activebackground=COLOR_PANEL,
                                 activeforeground=COLOR_ACENTO,
                                 cursor="hand2")
            cb.grid(row=i, column=0, sticky="w", pady=1)
            self._check_campos[campo] = var

        f.columnconfigure(0, weight=1)

    # ── Panel: Generación ─────────────────────────────────────────────────

    def _panel_generacion(self, parent):
        f = self._frame_seccion(parent, "🖨  GENERACIÓN")

        # Selección de planos
        tk.Label(f, text="Planos a generar:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=0, column=0,
                 columnspan=2, sticky="w")

        self._modo_gen = tk.StringVar(value="todos")
        rb1 = tk.Radiobutton(f, text="Todos", variable=self._modo_gen,
                             value="todos", font=FONT_SMALL,
                             bg=COLOR_PANEL, fg=COLOR_TEXTO,
                             selectcolor=COLOR_BORDE,
                             activebackground=COLOR_PANEL, cursor="hand2")
        rb1.grid(row=1, column=0, sticky="w")

        rb2 = tk.Radiobutton(f, text="Seleccionados", variable=self._modo_gen,
                             value="seleccion", font=FONT_SMALL,
                             bg=COLOR_PANEL, fg=COLOR_TEXTO,
                             selectcolor=COLOR_BORDE,
                             activebackground=COLOR_PANEL, cursor="hand2")
        rb2.grid(row=2, column=0, sticky="w")

        rb3 = tk.Radiobutton(f, text="Rango:", variable=self._modo_gen,
                             value="rango", font=FONT_SMALL,
                             bg=COLOR_PANEL, fg=COLOR_TEXTO,
                             selectcolor=COLOR_BORDE,
                             activebackground=COLOR_PANEL, cursor="hand2")
        rb3.grid(row=3, column=0, sticky="w")

        rango_f = tk.Frame(f, bg=COLOR_PANEL)
        rango_f.grid(row=3, column=1, sticky="w", padx=(4, 0))
        self._rango_desde = tk.Entry(rango_f, width=5, font=FONT_SMALL,
                                     bg=COLOR_BORDE, fg=COLOR_TEXTO,
                                     insertbackground="white", relief="flat")
        self._rango_desde.insert(0, "1")
        self._rango_desde.pack(side="left")
        tk.Label(rango_f, text="–", bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=FONT_SMALL).pack(side="left", padx=2)
        self._rango_hasta = tk.Entry(rango_f, width=5, font=FONT_SMALL,
                                     bg=COLOR_BORDE, fg=COLOR_TEXTO,
                                     insertbackground="white", relief="flat")
        self._rango_hasta.insert(0, "10")
        self._rango_hasta.pack(side="left")

        # Barra de progreso
        tk.Label(f, text="Progreso:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._progreso = ttk.Progressbar(f, length=240, mode="determinate")
        self._progreso.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        self._lbl_progreso = tk.Label(f, text="—", font=FONT_SMALL,
                                      bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_progreso.grid(row=6, column=0, columnspan=2, pady=(0, 8))

        # Botón GENERAR
        self._btn_generar = self._boton(
            f, "  GENERAR PLANOS  ", self._iniciar_generacion,
            icono="🖨", ancho=30,
            color_bg=COLOR_ACENTO, color_fg="#1A1A2E"
        )
        self._btn_generar.grid(row=7, column=0, columnspan=2,
                               sticky="ew", pady=4)

        # Botón abrir carpeta
        self._boton(f, "Abrir carpeta de salida",
                    self._abrir_carpeta, icono="📂").grid(
                    row=8, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

    # ── Panel: Tabla de atributos ──────────────────────────────────────────

    def _panel_tabla(self, parent):
        lf = tk.LabelFrame(parent, text=" INFRAESTRUCTURAS CARGADAS ",
                           font=FONT_BOLD, bg=COLOR_FONDO_APP, fg=COLOR_ACENTO,
                           bd=1, relief="solid")
        lf.pack(fill="both", expand=True, padx=4, pady=(4, 4))

        cols = ["#", "Nombre_Infra", "Municipio", "Monte",
                "Tipo_Trabajos", "Longitud", "Superficie"]
        self._tabla = ttk.Treeview(lf, columns=cols, show="headings",
                                   selectmode="extended")
        for col in cols:
            ancho = 60 if col == "#" else 130
            self._tabla.heading(col, text=col)
            self._tabla.column(col, width=ancho, minwidth=40)

        sb_v = ttk.Scrollbar(lf, orient="vertical",
                             command=self._tabla.yview)
        sb_h = ttk.Scrollbar(lf, orient="horizontal",
                             command=self._tabla.xview)
        self._tabla.configure(yscrollcommand=sb_v.set,
                              xscrollcommand=sb_h.set)
        self._tabla.pack(side="left", fill="both", expand=True)
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")

    # ── Panel: Log ────────────────────────────────────────────────────────

    def _panel_log(self, parent):
        lf = tk.LabelFrame(parent, text=" LOG DE PROCESO ",
                           font=FONT_BOLD, bg=COLOR_FONDO_APP, fg=COLOR_ACENTO,
                           bd=1, relief="solid")
        lf.pack(fill="x", padx=4, pady=(0, 4))

        self._log = tk.Text(lf, height=7, font=FONT_MONO,
                            bg="#0D1117", fg="#58D68D",
                            insertbackground="white", relief="flat",
                            state="disabled")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        self._log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Tags de color
        self._log.tag_config("error",  foreground="#E74C3C")
        self._log.tag_config("ok",     foreground="#2ECC71")
        self._log.tag_config("warn",   foreground="#F39C12")
        self._log.tag_config("info",   foreground="#85C1E9")

        self._escribir_log("Sistema iniciado. Carga un shapefile para comenzar.", "info")

    # ── Helpers UI ────────────────────────────────────────────────────────

    def _frame_seccion(self, parent, titulo: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=COLOR_PANEL)
        outer.pack(fill="x", padx=6, pady=(8, 0))

        tk.Label(outer, text=titulo, font=("Helvetica", 9, "bold"),
                 bg=COLOR_PANEL, fg=COLOR_ACENTO).pack(anchor="w", pady=(0, 2))

        sep = tk.Frame(outer, bg=COLOR_ACENTO, height=1)
        sep.pack(fill="x", pady=(0, 6))

        inner = tk.Frame(outer, bg=COLOR_PANEL)
        inner.pack(fill="x", padx=4)
        return inner

    def _boton(self, parent, texto, comando, icono="", ancho=None,
               color_bg=COLOR_BORDE, color_fg=COLOR_TEXTO) -> tk.Button:
        label = f"{icono} {texto}" if icono else texto
        kwargs = dict(
            text=label, command=comando, font=FONT_LABEL,
            bg=color_bg, fg=color_fg, activebackground=COLOR_ACENTO,
            activeforeground="#1A1A2E", relief="flat", cursor="hand2",
            pady=5,
        )
        if ancho:
            kwargs["width"] = ancho
        return tk.Button(parent, **kwargs)

    def _escribir_log(self, msg: str, tipo: str = ""):
        def _do():
            self._log.configure(state="normal")
            tag = tipo if tipo else ""
            self._log.insert("end", msg + "\n", tag)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _actualizar_titulo(self):
        pass

    # ── Acciones ──────────────────────────────────────────────────────────

    def _cargar_infra(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Infraestructuras",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")]
        )
        if not ruta:
            return
        ok, msg = self.motor.cargar_infraestructuras(ruta)
        if ok:
            self._ruta_infra.set(os.path.basename(ruta))
            self._escribir_log(msg, "ok")
            self._poblar_tabla()
        else:
            self._ruta_infra.set("Error al cargar")
            self._escribir_log(msg, "error")
            messagebox.showerror("Error", msg)

    def _cargar_montes(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Montes",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")]
        )
        if not ruta:
            return
        ok, msg = self.motor.cargar_montes(ruta)
        if ok:
            self._ruta_montes.set(os.path.basename(ruta))
            self._escribir_log(msg, "ok")
        else:
            self._ruta_montes.set("Error al cargar")
            self._escribir_log(msg, "error")

    def _poblar_tabla(self):
        gdf = self.motor.gdf_infra
        if gdf is None:
            return
        for item in self._tabla.get_children():
            self._tabla.delete(item)

        cols_existentes = list(gdf.columns)

        def _val(row, campo):
            if campo in cols_existentes:
                return str(row[campo])
            return "—"

        for i, (_, row) in enumerate(gdf.iterrows()):
            vals = [
                i + 1,
                _val(row, "Nombre_Infra"),
                _val(row, "Municipio"),
                _val(row, "Monte"),
                _val(row, "Tipo_Trabajos"),
                _val(row, "Longitud"),
                _val(row, "Superficie"),
            ]
            tag = "par" if i % 2 == 0 else "impar"
            self._tabla.insert("", "end", values=vals, tags=(tag,))

        self._tabla.tag_configure("par",   background="#1E2A3A")
        self._tabla.tag_configure("impar", background="#172030")
        self._escribir_log(
            f"Tabla actualizada: {len(gdf)} infraestructuras.", "info")

    def _elegir_color(self):
        color = colorchooser.askcolor(color=self._color_infra,
                                      title="Color infraestructura")[1]
        if color:
            self._color_infra = color
            self._lbl_color.configure(bg=color)

    def _elegir_carpeta(self):
        carpeta = filedialog.askdirectory(title="Carpeta de salida")
        if carpeta:
            self._salida.set(carpeta)

    def _abrir_carpeta(self):
        carpeta = self._salida.get()
        os.makedirs(carpeta, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(carpeta)
        elif sys.platform == "darwin":
            os.system(f'open "{carpeta}"')
        else:
            os.system(f'xdg-open "{carpeta}"')

    def _iniciar_generacion(self):
        if self.motor.gdf_infra is None:
            messagebox.showwarning("Aviso", "Carga primero el shapefile de infraestructuras.")
            return

        gdf  = self.motor.gdf_infra
        modo = self._modo_gen.get()

        if modo == "todos":
            indices = list(range(len(gdf)))
        elif modo == "seleccion":
            sels = self._tabla.selection()
            if not sels:
                messagebox.showwarning("Aviso", "Selecciona filas en la tabla.")
                return
            indices = [self._tabla.index(s) for s in sels]
        else:  # rango
            try:
                desde = int(self._rango_desde.get()) - 1
                hasta = int(self._rango_hasta.get())
                indices = list(range(max(0, desde), min(hasta, len(gdf))))
            except ValueError:
                messagebox.showerror("Error", "Rango inválido.")
                return

        if not indices:
            messagebox.showwarning("Aviso", "No hay infraestructuras seleccionadas.")
            return

        campos = [c for c, v in self._check_campos.items() if v.get()]
        if not campos:
            messagebox.showwarning("Aviso", "Selecciona al menos un campo.")
            return

        carpeta = self._salida.get()
        os.makedirs(carpeta, exist_ok=True)

        self._btn_generar.configure(state="disabled", text="⏳ Generando...")
        self._progreso["value"] = 0
        self._progreso["maximum"] = len(indices)

        def _worker():
            self._escribir_log(
                f"\n{'='*50}\nIniciando generación de {len(indices)} planos...", "info")

            def _log(msg):
                self._escribir_log(msg)

            def _prog(actual, total):
                self.after(0, lambda: self._progreso.__setitem__("value", actual))
                self.after(0, lambda: self._lbl_progreso.configure(
                    text=f"{actual}/{total} planos generados"))

            self.motor.generar_serie(
                indices       = indices,
                formato_key   = self._formato.get(),
                proveedor     = self._proveedor.get(),
                transparencia = self._transp.get(),
                campos        = campos,
                color_infra   = self._color_infra,
                salida_dir    = carpeta,
                callback_log  = _log,
                callback_progreso = _prog,
            )

            self.after(0, self._fin_generacion)

        threading.Thread(target=_worker, daemon=True).start()

    def _fin_generacion(self):
        self._btn_generar.configure(state="normal", text="  GENERAR PLANOS  ")
        self._escribir_log("\n✓ Proceso finalizado. Planos guardados en:\n" +
                           self._salida.get(), "ok")
        messagebox.showinfo("Completado",
                            f"Planos generados correctamente.\n\nCarpeta: {self._salida.get()}")


# ─────────────────────────────────────────────────────────────────────────────
# ESTILOS TTK
# ─────────────────────────────────────────────────────────────────────────────

def aplicar_estilos(root: tk.Tk):
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure("TCombobox",
                    fieldbackground=COLOR_BORDE,
                    background=COLOR_BORDE,
                    foreground=COLOR_TEXTO,
                    selectbackground=COLOR_ACENTO,
                    selectforeground="#1A1A2E",
                    arrowcolor=COLOR_ACENTO)

    style.configure("Horizontal.TProgressbar",
                    troughcolor=COLOR_BORDE,
                    background=COLOR_ACENTO,
                    thickness=12)

    style.configure("Treeview",
                    background="#172030",
                    foreground=COLOR_TEXTO,
                    fieldbackground="#172030",
                    rowheight=22)
    style.configure("Treeview.Heading",
                    background="#0D1117",
                    foreground=COLOR_ACENTO,
                    font=FONT_BOLD)
    style.map("Treeview",
              background=[("selected", COLOR_ACENTO)],
              foreground=[("selected", "#1A1A2E")])


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    aplicar_estilos(app)
    app.mainloop()
